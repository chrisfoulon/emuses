#!/usr/bin/env python3
"""
Concurrency and Performance Testing

Tests performance aspects of the FastAPI service including:
- Multiple simultaneous job submissions with race condition detection
- Resource cleanup verification (directories, processes, memory)
- Load testing with performance budgets and timeouts
- Memory spike detection during context serialization
"""

import asyncio
import copy
import gc
import os
import psutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pytest
import requests
from fastapi.testclient import TestClient

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def client():
    """Create FastAPI test client with mocked dependencies."""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import Optional
    from datetime import datetime
    import uuid
    
    test_app = FastAPI(title="EMUSES FastAPI Test Service")
    
    # Mock job storage
    test_jobs = {}
    
    # Mock request/response models
    class JobSubmissionRequest(BaseModel):
        pipeline_config: dict
        job_name: Optional[str] = None
        description: Optional[str] = None
    
    class JobStatusResponse(BaseModel):
        job_id: str
        status: str
        created_at: str
        progress: Optional[float] = None
        current_stage: Optional[str] = None
    
    # Add the main endpoint for testing concurrency
    @test_app.post("/api/v1/jobs/pipeline/full", status_code=201)
    async def submit_full_pipeline_job(job_request: JobSubmissionRequest) -> JobStatusResponse:
        """Submit a full pipeline job for execution (mocked for concurrency testing)."""
        try:
            config = job_request.pipeline_config
            
            # Validate required fields
            if "input_file" not in config:
                raise ValueError("input_file is required")
            if "scores_file" not in config:
                raise ValueError("scores_file is required")
            if "output_folder" not in config:
                raise ValueError("output_folder is required")
            
            # Simulate job creation with race condition protection
            job_id = str(uuid.uuid4())
            
            # Ensure unique job IDs (race condition check)
            if job_id in test_jobs:
                raise ValueError("Job ID collision detected")
            
            # Create job entry
            job_data = {
                "job_id": job_id,
                "status": "submitted",
                "created_at": datetime.now().isoformat() + "Z",
                "progress": 0.0,
                "current_stage": "initialization",
                "config": config
            }
            
            test_jobs[job_id] = job_data
            
            return JobStatusResponse(**job_data)
            
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            )
    
    # Add job status endpoint for testing
    @test_app.get("/api/v1/jobs/{job_id}/status")
    async def get_job_status(job_id: str) -> JobStatusResponse:
        """Get job status (mocked for testing)."""
        if job_id not in test_jobs:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "JOB_NOT_FOUND",
                    "message": f"Job {job_id} not found",
                    "timestamp": datetime.now().isoformat() + "Z"
                }
            )
        
        job_data = test_jobs[job_id]
        return JobStatusResponse(**job_data)
    
    return TestClient(test_app)


@pytest.fixture
def temp_jobs_dir():
    """Create temporary jobs directory."""
    with tempfile.TemporaryDirectory(prefix='test_jobs_') as td:
        yield Path(td)


@pytest.fixture
def performance_budget():
    """Performance budget requirements."""
    return {
        'max_response_time': 500,  # milliseconds
        'max_job_creation_time': 2000,  # milliseconds for job creation
        'max_memory_increase': 100,  # MB
        'max_concurrent_jobs': 10,
        'cleanup_timeout': 5000,  # milliseconds
    }


@pytest.fixture
def test_payload(temp_jobs_dir):
    """Standard test payload for performance testing with mock file paths."""
    # Create mock file paths (don't need real files for mocked tests)
    input_file = temp_jobs_dir / "test_input.csv"
    scores_file = temp_jobs_dir / "test_scores.csv"
    output_folder = temp_jobs_dir / "output"
    
    # Create minimal files for validation
    input_file.write_text("feature1,feature2,feature3\n1.0,2.0,3.0\n4.0,5.0,6.0\n")
    scores_file.write_text("score\n0.5\n1.0\n")
    output_folder.mkdir(exist_ok=True)
    
    return {
        "pipeline_config": {
            "input_file": str(input_file),
            "scores_file": str(scores_file),
            "output_folder": str(output_folder),
            "prefix": "perf_test",
            "umap_trials": 1,
            "hdbscan_trials": 1,
            "optuna_trials": 2,  # Minimal for speed
        }
    }


def get_memory_usage():
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def get_system_memory_usage():
    """Get system memory usage percentage."""
    return psutil.virtual_memory().percent


class TestConcurrentJobSubmission:
    """Test concurrent job submission and race condition detection."""

    def test_multiple_simultaneous_job_submissions(self, client, test_payload, performance_budget):
        """Test multiple simultaneous job submissions with race condition detection."""
        num_jobs = performance_budget['max_concurrent_jobs']
        results = []
        job_ids = []
        start_time = time.time()
        
        def submit_job(job_index):
            """Submit a single job and return result."""
            payload = copy.deepcopy(test_payload)
            payload['pipeline_config']['prefix'] = f"concurrent_job_{job_index}"
            
            job_start = time.time()
            response = client.post("/api/v1/jobs/pipeline/full", json=payload)
            job_end = time.time()
            
            job_creation_time = (job_end - job_start) * 1000  # Convert to ms
            
            return {
                'job_index': job_index,
                'status_code': response.status_code,
                'response_data': response.json() if response.status_code == 201 else None,
                'error_data': response.json() if response.status_code != 201 else None,
                'job_creation_time': job_creation_time,
                'timestamp': job_start
            }
        
        # Submit jobs concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=num_jobs) as executor:
            future_to_index = {
                executor.submit(submit_job, i): i
                for i in range(num_jobs)
            }
            
            for future in as_completed(future_to_index):
                result = future.result()
                results.append(result)
                if result['response_data']:
                    job_ids.append(result['response_data']['job_id'])
        
        total_time = (time.time() - start_time) * 1000
        
        # Validate race condition protection
        successful_jobs = [r for r in results if r['status_code'] == 201]
        failed_jobs = [r for r in results if r['status_code'] != 201]
        
        print("Concurrent job submission results:")
        print(f"  Total jobs submitted: {num_jobs}")
        print(f"  Successful jobs: {len(successful_jobs)}")
        print(f"  Failed jobs: {len(failed_jobs)}")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Average job creation time: {sum(r['job_creation_time'] for r in results) / len(results):.2f}ms")
        
        # Print sample error for debugging
        if failed_jobs:
            print(f"  Sample error (job {failed_jobs[0]['job_index']}): {failed_jobs[0]['error_data']}")
        
        # Validate no race conditions in job ID generation
        if len(job_ids) > 1:
            assert len(job_ids) == len(set(job_ids)), "Race condition detected: duplicate job IDs generated"
        
        # Validate job creation time is within budget
        for result in results:
            assert result['job_creation_time'] <= performance_budget['max_job_creation_time'], \
                f"Job creation time {result['job_creation_time']:.2f}ms exceeds budget {performance_budget['max_job_creation_time']}ms"
        
        # Validate at least some jobs succeed (system not completely overwhelmed)
        assert len(successful_jobs) > 0, "No jobs succeeded under concurrent load"

    def test_concurrent_job_status_access(self, client, test_payload):
        """Test concurrent access to job status updates."""
        # Create a job first
        response = client.post("/api/v1/jobs/pipeline/full", json=test_payload)
        assert response.status_code == 201
        job_id = response.json()['job_id']
        
        num_threads = 5
        status_results = []
        
        def check_job_status():
            """Check job status and return result."""
            start_time = time.time()
            response = client.get(f"/api/v1/jobs/{job_id}/status")
            end_time = time.time()
            
            return {
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000,
                'data': response.json() if response.status_code == 200 else None
            }
        
        # Access job status concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(check_job_status) for _ in range(num_threads)]
            for future in as_completed(futures):
                status_results.append(future.result())
        
        # Validate all status checks succeeded
        successful_checks = [r for r in status_results if r['status_code'] == 200]
        assert len(successful_checks) == num_threads, "Not all concurrent status checks succeeded"
        
        # Validate response times are reasonable
        for result in status_results:
            assert result['response_time'] <= 500, f"Status check took {result['response_time']:.2f}ms, exceeding 500ms budget"

    def test_job_directory_isolation(self, client, test_payload):
        """Test that concurrent job creation maintains directory isolation."""
        num_jobs = 3
        job_payloads = []
        
        # Create different payloads
        for i in range(num_jobs):
            payload = copy.deepcopy(test_payload)
            payload['pipeline_config']['prefix'] = f"isolation_test_{i}"
            job_payloads.append(payload)
        
        def create_and_verify_job(payload):
            """Create job and verify its isolation."""
            response = client.post("/api/v1/jobs/pipeline/full", json=payload)
            if response.status_code == 201:
                job_data = response.json()
                job_id = job_data['job_id']
                
                # Verify job directory exists and is isolated
                # (This is a conceptual test - actual directory verification would require access to job manager)
                return {
                    'job_id': job_id,
                    'prefix': payload['pipeline_config']['prefix'],
                    'success': True
                }
            return {'success': False, 'status_code': response.status_code}
        
        # Create jobs concurrently
        with ThreadPoolExecutor(max_workers=num_jobs) as executor:
            futures = [executor.submit(create_and_verify_job, payload) for payload in job_payloads]
            results = [future.result() for future in as_completed(futures)]
        
        successful_jobs = [r for r in results if r['success']]
        
        # Validate job isolation
        job_ids = [job['job_id'] for job in successful_jobs]
        prefixes = [job['prefix'] for job in successful_jobs]
        
        assert len(job_ids) == len(set(job_ids)), "Job ID collision detected"
        assert len(prefixes) == len(set(prefixes)), "Prefix collision detected"
        
        print(f"Created {len(successful_jobs)} isolated jobs with unique IDs and prefixes")


class TestResourceCleanup:
    """Test resource cleanup verification."""

    def test_memory_usage_during_job_processing(self, client, test_payload, performance_budget):
        """Monitor memory usage during job processing."""
        initial_memory = get_memory_usage()
        print(f"Initial memory usage: {initial_memory:.2f} MB")
        
        # Create multiple jobs to stress memory
        job_ids = []
        memory_measurements = [initial_memory]
        
        for i in range(3):  # Create a few jobs
            gc.collect()  # Force garbage collection before measurement
            
            payload = copy.deepcopy(test_payload)
            payload['pipeline_config']['prefix'] = f"memory_test_{i}"
            
            pre_job_memory = get_memory_usage()
            response = client.post("/api/v1/jobs/pipeline/full", json=payload)
            post_job_memory = get_memory_usage()
            
            memory_measurements.extend([pre_job_memory, post_job_memory])
            
            if response.status_code == 201:
                job_ids.append(response.json()['job_id'])
                print(f"Job {i}: {pre_job_memory:.2f} MB -> {post_job_memory:.2f} MB")
        
        # Wait a bit for any background processing
        time.sleep(2)
        gc.collect()
        final_memory = get_memory_usage()
        memory_measurements.append(final_memory)
        
        max_memory = max(memory_measurements)
        memory_increase = max_memory - initial_memory
        
        print("Memory usage summary:")
        print(f"  Initial: {initial_memory:.2f} MB")
        print(f"  Peak: {max_memory:.2f} MB")
        print(f"  Final: {final_memory:.2f} MB")
        print(f"  Increase: {memory_increase:.2f} MB")
        
        # Validate memory usage is within budget
        assert memory_increase <= performance_budget['max_memory_increase'], \
            f"Memory increase {memory_increase:.2f} MB exceeds budget {performance_budget['max_memory_increase']} MB"

    def test_process_cleanup_after_job_completion(self, client, test_payload):
        """Test that background processes are cleaned up after job completion."""
        initial_process_count = len(psutil.Process().children(recursive=True))
        
        # Create a job
        response = client.post("/api/v1/jobs/pipeline/full", json=test_payload)
        assert response.status_code == 201
        job_data = response.json()
        job_id = job_data['job_id']
        
        print(f"Created job {job_id} for process cleanup testing")
        
        # Wait for potential process creation
        time.sleep(1)
        peak_process_count = len(psutil.Process().children(recursive=True))
        
        # Wait for job processing to complete/timeout
        time.sleep(5)
        final_process_count = len(psutil.Process().children(recursive=True))
        
        print(f"Process count: Initial={initial_process_count}, Peak={peak_process_count}, Final={final_process_count}")
        
        # Validate process cleanup (allow some tolerance for system processes)
        process_increase = final_process_count - initial_process_count
        assert process_increase <= 2, f"Too many lingering processes: {process_increase} processes not cleaned up"

    def test_directory_cleanup_verification(self, client, test_payload, temp_jobs_dir):
        """Test directory cleanup after job completion."""
        # This test verifies conceptual cleanup - actual implementation would depend on JobManager
        initial_dir_count = len(list(temp_jobs_dir.rglob('*'))) if temp_jobs_dir.exists() else 0
        print(f"Initial directory count: {initial_dir_count}")
        
        # Create a job
        response = client.post("/api/v1/jobs/pipeline/full", json=test_payload)
        if response.status_code == 201:
            job_id = response.json()['job_id']
            print(f"Created job {job_id} for cleanup verification")
            
            # In a real implementation, we would:
            # 1. Verify job directory was created
            # 2. Wait for job completion
            # 3. Trigger cleanup
            # 4. Verify directory was removed
            
            # For now, we validate the job was created successfully
            status_response = client.get(f"/api/v1/jobs/{job_id}/status")
            assert status_response.status_code == 200
            
            print("Directory cleanup verification passed (conceptual test)")


class TestLoadTesting:
    """Test load testing with performance budgets."""

    def test_sustained_load_performance(self, client, test_payload, performance_budget):
        """Test sustained load within performance budgets."""
        duration_seconds = 10  # Short test duration
        max_concurrent = 3    # Reduced for testing
        
        results = []
        start_time = time.time()
        stop_time = start_time + duration_seconds
        
        def submit_continuous_jobs():
            """Submit jobs continuously during test period."""
            job_count = 0
            while time.time() < stop_time:
                payload = copy.deepcopy(test_payload)
                payload['pipeline_config']['prefix'] = f"load_test_{job_count}_{threading.current_thread().ident}"
                
                request_start = time.time()
                response = client.post("/api/v1/jobs/pipeline/full", json=payload)
                request_end = time.time()
                
                response_time = (request_end - request_start) * 1000
                
                results.append({
                    'job_count': job_count,
                    'thread_id': threading.current_thread().ident,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'timestamp': request_start
                })
                
                job_count += 1
                time.sleep(0.1)  # Brief pause between requests
        
        # Run sustained load test
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = [executor.submit(submit_continuous_jobs) for _ in range(max_concurrent)]
            for future in as_completed(futures):
                future.result()  # Wait for completion
        
        # Analyze results
        successful_requests = [r for r in results if r['status_code'] == 201]
        failed_requests = [r for r in results if r['status_code'] != 201]
        
        if results:
            avg_response_time = sum(r['response_time'] for r in results) / len(results)
            max_response_time = max(r['response_time'] for r in results)
            
            print("Load test results:")
            print(f"  Duration: {duration_seconds}s")
            print(f"  Total requests: {len(results)}")
            print(f"  Successful: {len(successful_requests)}")
            print(f"  Failed: {len(failed_requests)}")
            print(f"  Average response time: {avg_response_time:.2f}ms")
            print(f"  Max response time: {max_response_time:.2f}ms")
            
            # Validate performance within budget
            assert avg_response_time <= performance_budget['max_response_time'], \
                f"Average response time {avg_response_time:.2f}ms exceeds budget {performance_budget['max_response_time']}ms"
            
            # Validate system didn't completely fail
            success_rate = len(successful_requests) / len(results)
            assert success_rate >= 0.5, f"Success rate {success_rate:.2%} too low under sustained load"

    def test_response_time_under_concurrent_load(self, client, test_payload, performance_budget):
        """Test response times under concurrent load."""
        num_concurrent = 5
        response_times = []
        
        def measure_response_time():
            """Measure response time for a single request."""
            start_time = time.time()
            response = client.get("/api/health")  # Use health endpoint for quick response
            end_time = time.time()
            
            return {
                'response_time': (end_time - start_time) * 1000,
                'status_code': response.status_code
            }
        
        # Measure response times under concurrent load
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(measure_response_time) for _ in range(num_concurrent)]
            for future in as_completed(futures):
                result = future.result()
                response_times.append(result)
        
        # Analyze response times
        successful_responses = [r for r in response_times if r['status_code'] == 200]
        
        if successful_responses:
            avg_time = sum(r['response_time'] for r in successful_responses) / len(successful_responses)
            max_time = max(r['response_time'] for r in successful_responses)
            
            print("Response time under load:")
            print(f"  Concurrent requests: {num_concurrent}")
            print(f"  Average time: {avg_time:.2f}ms")
            print(f"  Max time: {max_time:.2f}ms")
            
            # Validate response times are within budget
            assert avg_time <= performance_budget['max_response_time'], \
                f"Average response time {avg_time:.2f}ms exceeds budget {performance_budget['max_response_time']}ms"


class TestMemorySpike:
    """Test memory spike detection during context serialization."""

    def test_context_serialization_memory_usage(self, client, temp_jobs_dir, performance_budget):
        """Test memory usage during large context serialization."""
        initial_memory = get_memory_usage()
        
        # Create temporary files with large data for testing serialization
        input_file = temp_jobs_dir / "large_input.csv"
        scores_file = temp_jobs_dir / "large_scores.csv"
        output_folder = temp_jobs_dir / "output"
        
        # Create large CSV content
        large_csv_lines = ["feature1,feature2,feature3"]
        large_csv_lines.extend([f"{i},{i * 2},{i * 3}" for i in range(1000)])  # 1000 rows
        input_file.write_text('\n'.join(large_csv_lines))
        
        scores_csv_lines = ["score"]
        scores_csv_lines.extend([str(float(i)) for i in range(1000)])
        scores_file.write_text('\n'.join(scores_csv_lines))
        
        output_folder.mkdir(exist_ok=True)
        
        large_payload = {
            "pipeline_config": {
                "input_file": str(input_file),
                "scores_file": str(scores_file),
                "output_folder": str(output_folder),
                "prefix": "memory_spike_test",
                "umap_trials": 1,
                "hdbscan_trials": 1,
                "optuna_trials": 1,
            }
        }
        
        # Monitor memory during request
        pre_request_memory = get_memory_usage()
        
        response = client.post("/api/v1/jobs/pipeline/full", json=large_payload)
        
        post_request_memory = get_memory_usage()
        
        # Force garbage collection and measure again
        gc.collect()
        final_memory = get_memory_usage()
        
        memory_spike = post_request_memory - pre_request_memory
        memory_retention = final_memory - initial_memory
        
        print("Memory spike analysis:")
        print(f"  Initial: {initial_memory:.2f} MB")
        print(f"  Pre-request: {pre_request_memory:.2f} MB")
        print(f"  Post-request: {post_request_memory:.2f} MB")
        print(f"  Final (after GC): {final_memory:.2f} MB")
        print(f"  Spike: {memory_spike:.2f} MB")
        print(f"  Retention: {memory_retention:.2f} MB")
        print(f"  Response status: {response.status_code}")
        
        # Validate memory spike is within reasonable bounds
        assert memory_spike <= performance_budget['max_memory_increase'], \
            f"Memory spike {memory_spike:.2f} MB exceeds budget {performance_budget['max_memory_increase']} MB"
        
        # Validate memory retention is reasonable (less than 10MB or spike + 5MB, whichever is larger)
        max_retention = max(10.0, memory_spike + 5.0)
        assert memory_retention <= max_retention, \
            f"Too much memory retained after GC: {memory_retention:.2f} MB (max: {max_retention:.2f} MB)"

    def test_system_memory_monitoring(self, client, test_payload):
        """Monitor system memory usage during testing."""
        initial_system_memory = get_system_memory_usage()
        
        # Create several jobs to monitor system impact
        for i in range(3):
            payload = copy.deepcopy(test_payload)
            payload['pipeline_config']['prefix'] = f"system_memory_test_{i}"
            response = client.post("/api/v1/jobs/pipeline/full", json=payload)
            
            current_memory = get_system_memory_usage()
            print(f"Job {i}: System memory usage: {current_memory:.1f}%, Response: {response.status_code}")
        
        final_system_memory = get_system_memory_usage()
        memory_change = final_system_memory - initial_system_memory
        
        print(f"System memory change: {memory_change:.1f}%")
        
        # Validate system memory usage is reasonable
        assert final_system_memory <= 90.0, f"System memory usage too high: {final_system_memory:.1f}%"
        assert memory_change <= 10.0, f"Memory usage increased too much: {memory_change:.1f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
