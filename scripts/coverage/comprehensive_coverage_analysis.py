#!/usr/bin/env python3
"""
EMUSES Comprehensive Coverage Analysis
Runs ALL test files without timeouts and measures complete coverage.
"""

import subprocess
import sys
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import tempfile
import json
import argparse
import multiprocessing

# Repo root, derived from this file's location: scripts/coverage/<this>.py
# Previously three subprocess calls hardcoded a /mnt/c Windows path this repo
# has not lived on for years, so the script could not run anywhere.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def find_test_files():
    """Find all test files in the project."""
    test_files = []
    test_dirs = [str(PROJECT_ROOT / 'tests')]
    
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            for root, dirs, files in os.walk(test_dir):
                for file in files:
                    if file.startswith('test_') and file.endswith('.py'):
                        test_files.append(os.path.join(root, file))
    
    return sorted(test_files)

def chunk_tests(test_files, chunk_size=3):
    """Split test files into small chunks to avoid timeouts."""
    chunks = []
    for i in range(0, len(test_files), chunk_size):
        chunk = test_files[i:i + chunk_size]
        chunks.append(chunk)
    return chunks

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='EMUSES Comprehensive Coverage Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python comprehensive_coverage_analysis.py                    # Use default 4 workers
  python comprehensive_coverage_analysis.py --workers 8       # Use 8 workers  
  python comprehensive_coverage_analysis.py --workers 24      # Use 24 workers (high-end machine)
  python comprehensive_coverage_analysis.py --workers 72      # Use 72 workers (beast mode!)
  python comprehensive_coverage_analysis.py --chunk-size 5    # Larger chunks (5 files each)
  python comprehensive_coverage_analysis.py --workers 16 --chunk-size 2  # High parallelism, small chunks

Machine Recommendations:
  Standard laptop (4-8 cores, 8-16GB RAM):     --workers 4-8
  Workstation (16-32 cores, 32-64GB RAM):      --workers 12-24  
  Server (48+ cores, 64+ GB RAM):              --workers 24-48
  Beast machine (72 cores, 128GB RAM):         --workers 48-72
        """)
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=min(4, multiprocessing.cpu_count()),
        help=f'Number of parallel workers (default: {min(4, multiprocessing.cpu_count())}, max detected: {multiprocessing.cpu_count()})'
    )
    
    parser.add_argument(
        '--chunk-size', '-c',
        type=int, 
        default=3,
        help='Number of test files per chunk (default: 3, smaller = more parallelism but more overhead)'
    )
    
    parser.add_argument(
        '--aggressive',
        action='store_true',
        help='Aggressive mode: Use ALL CPU cores with smallest chunks (equivalent to --workers ALL --chunk-size 1)'
    )
    
    return parser.parse_args()

def run_coverage_chunk(chunk_info):
    """Run coverage for a single chunk of test files with no timeout."""
    chunk_id, chunk_tests = chunk_info
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.coverage', delete=False) as f:
            coverage_file = f.name
        
        # Run coverage on the test files with NO timeout
        cmd = [
            sys.executable, '-m', 'coverage', 'run',
            '--data-file=' + coverage_file,
            '--append',
            '-m', 'pytest',
            '--tb=no',
            '-q',
            '--maxfail=50'  # Continue even if many tests fail
        ] + chunk_tests
        
        print(f"🔄 Chunk {chunk_id:2d}: Starting {len(chunk_tests)} test files...")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            # NO TIMEOUT - let it run as long as needed
            cwd=PROJECT_ROOT
        )
        
        success = os.path.exists(coverage_file) and os.path.getsize(coverage_file) > 0
        
        if success:
            print(f"✅ Chunk {chunk_id:2d}: Completed successfully")
        else:
            print(f"❌ Chunk {chunk_id:2d}: Failed (return code: {result.returncode})")
            if result.stderr:
                print(f"   Error preview: {result.stderr[:200]}")
        
        return {
            'chunk_id': chunk_id,
            'success': success,
            'coverage_file': coverage_file if success else None,
            'return_code': result.returncode,
            'tests_run': len(chunk_tests),
            'stdout_lines': len(result.stdout.split('\n')) if result.stdout else 0,
            'stderr_preview': result.stderr[:300] if result.stderr else '',
            'test_files': chunk_tests
        }
        
    except Exception as e:
        print(f"❌ Chunk {chunk_id:2d}: Exception - {str(e)}")
        return {
            'chunk_id': chunk_id,
            'success': False,
            'coverage_file': None,
            'error': str(e),
            'tests_run': len(chunk_tests),
            'test_files': chunk_tests
        }

def cleanup_test_artifacts():
    """Clean up test artifacts (attacks, temp files, etc.)"""
    print("🧹 Cleaning up test artifacts...")
    
    cleanup_patterns = [
        "attacks/",
        "test_attacks/", 
        "temp_*",
        "*.tmp",
        ".coverage*",
        "htmlcov/",
        ".pytest_cache/",
        "__pycache__/",
        "*.pyc",
        ".tox/",
        "simulation_*",
        "test_simulation_*",
        "benchmark_*",
        "test_benchmark_*"
    ]
    
    # Use git to identify untracked files that match our patterns
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, check=True)
        untracked_files = []
        for line in result.stdout.split('\n'):
            if line.startswith('??'):
                file_path = line[3:].strip()
                # Check if it matches any cleanup pattern
                for pattern in cleanup_patterns:
                    if pattern.rstrip('/') in file_path or file_path.endswith(pattern.rstrip('*')):
                        untracked_files.append(file_path)
        
        if untracked_files:
            print(f"Found {len(untracked_files)} test artifacts to clean:")
            for file_path in untracked_files[:10]:  # Show first 10
                print(f"  - {file_path}")
            if len(untracked_files) > 10:
                print(f"  ... and {len(untracked_files) - 10} more")
            
            # Remove the artifacts
            for file_path in untracked_files:
                try:
                    if os.path.isdir(file_path):
                        subprocess.run(['rm', '-rf', file_path], check=True)
                    else:
                        subprocess.run(['rm', '-f', file_path], check=True)
                except Exception as e:
                    print(f"Warning: Could not remove {file_path}: {e}")
            
            print(f"✅ Cleaned up {len(untracked_files)} test artifacts")
        else:
            print("✅ No test artifacts found to clean")
            
    except Exception as e:
        print(f"Warning: Could not clean artifacts: {e}")

def main():
    """Run comprehensive coverage analysis without timeouts."""
    args = parse_args()
    
    # Handle aggressive mode
    if args.aggressive:
        args.workers = multiprocessing.cpu_count()
        args.chunk_size = 1
        print("🚀 AGGRESSIVE MODE ACTIVATED!")
        print(f"   Using ALL {args.workers} CPU cores with 1 file per chunk")
    
    print("🧪 EMUSES Comprehensive Coverage Analysis")
    print("=" * 60)
    print("⚠️  NO TIMEOUTS - This will run until completion")
    print(f"🔧 Configuration:")
    print(f"   Workers: {args.workers} (detected {multiprocessing.cpu_count()} CPU cores)")
    print(f"   Chunk size: {args.chunk_size} test files per chunk")
    if args.workers >= 24:
        print("🏆 BEAST MODE: High-performance parallel processing!")
    elif args.workers >= 12:
        print("💪 HIGH-PERFORMANCE: Multi-core workstation detected")
    print("=" * 60)
    
    # Cleanup test artifacts first
    cleanup_test_artifacts()
    
    # Find test files
    print("\n📂 Discovering test files...")
    test_files = find_test_files()
    print(f"Found {len(test_files)} test files")
    
    if not test_files:
        print("❌ No test files found!")
        return
    
    # Create chunks based on user configuration
    chunks = chunk_tests(test_files, chunk_size=args.chunk_size)
    print(f"Created {len(chunks)} chunks of {args.chunk_size} test files each")
    
    # Calculate expected speedup
    effective_workers = min(args.workers, len(chunks))
    expected_speedup = min(effective_workers, len(chunks) / 4)  # Baseline 4 workers
    print(f"📈 Expected speedup: {expected_speedup:.1f}x faster than baseline")
    
    # Process chunks with user-specified parallelism
    print(f"\n🚀 Running coverage analysis with {effective_workers} workers...")
    print("📊 Progress will be shown in real-time...")
    start_time = time.time()
    
    successful_chunks = []
    failed_chunks = []
    coverage_files = []
    
    with ProcessPoolExecutor(max_workers=effective_workers) as executor:
        # Submit all chunks
        future_to_chunk = {
            executor.submit(run_coverage_chunk, (i, chunk)): i 
            for i, chunk in enumerate(chunks)
        }
        
        # Process results as they complete
        for future in as_completed(future_to_chunk):
            chunk_id = future_to_chunk[future]
            try:
                result = future.result()
                
                if result['success']:
                    successful_chunks.append(result)
                    coverage_files.append(result['coverage_file'])
                else:
                    failed_chunks.append(result)
                    
            except Exception as e:
                failed_chunks.append({'chunk_id': chunk_id, 'error': str(e)})
                print(f"❌ Chunk {chunk_id:2d}: Exception - {str(e)}")
    
    duration = time.time() - start_time
    
    # Results summary
    print(f"\n📊 Chunk Processing Results ({duration/60:.1f} minutes)")
    print(f"✅ Successful: {len(successful_chunks)}/{len(chunks)}")
    print(f"❌ Failed: {len(failed_chunks)}/{len(chunks)}")
    
    if not coverage_files:
        print("\n❌ No coverage data generated - all chunks failed")
        print("\nFirst few failed chunks for debugging:")
        for chunk in failed_chunks[:5]:
            print(f"Chunk {chunk['chunk_id']}: {chunk.get('error', 'Unknown error')}")
        return
    
    # Combine coverage data
    print(f"\n🔄 Combining {len(coverage_files)} coverage files...")
    
    try:
        # Create final coverage file
        final_coverage = '.coverage_final'
        
        # Combine all coverage files
        combine_cmd = [sys.executable, '-m', 'coverage', 'combine'] + coverage_files
        combine_result = subprocess.run(
            combine_cmd, 
            capture_output=True, 
            text=True,
            cwd=PROJECT_ROOT
        )
        
        if combine_result.returncode == 0:
            print("✅ Coverage data combined successfully")
            
            # Generate comprehensive report
            print("\n📋 Generating comprehensive coverage report...")
            report_cmd = [sys.executable, '-m', 'coverage', 'report', '--show-missing']
            report_result = subprocess.run(
                report_cmd,
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            
            if report_result.returncode == 0:
                print("\n🎯 FINAL COMPREHENSIVE COVERAGE REPORT")
                print("=" * 70)
                print(report_result.stdout)
                
                # Generate JSON report for parsing
                json_cmd = [sys.executable, '-m', 'coverage', 'json']
                json_result = subprocess.run(json_cmd, capture_output=True, text=True)
                if json_result.returncode == 0:
                    with open('coverage.json', 'r') as f:
                        coverage_data = json.load(f)
                    
                    print(f"\n📈 COMPREHENSIVE COVERAGE SUMMARY")
                    print("=" * 50)
                    print(f"Total Coverage: {coverage_data['totals']['percent_covered']:.1f}%")
                    print(f"Lines Covered: {coverage_data['totals']['covered_lines']}/{coverage_data['totals']['num_statements']}")
                    print(f"Missing Lines: {coverage_data['totals']['missing_lines']}")
                    print(f"Branch Coverage: {coverage_data['totals']['percent_covered_display']}%")
                    print(f"Test Files Processed: {len(successful_chunks)} of {len(chunks)}")
                    
                    if failed_chunks:
                        print(f"\n⚠️  Note: {len(failed_chunks)} chunks failed - coverage may be incomplete")
                
            else:
                print("❌ Failed to generate coverage report")
                print(f"Error: {report_result.stderr}")
        else:
            print("❌ Failed to combine coverage data")
            print(f"Error: {combine_result.stderr}")
            
    except Exception as e:
        print(f"❌ Error during coverage combination: {e}")
    
    finally:
        # Cleanup temporary coverage files
        print(f"\n🧹 Cleaning up {len(coverage_files)} temporary coverage files...")
        for coverage_file in coverage_files:
            try:
                if os.path.exists(coverage_file):
                    os.unlink(coverage_file)
            except Exception as e:
                print(f"Warning: Could not delete {coverage_file}: {e}")
        
        # Final cleanup
        cleanup_test_artifacts()
        
    print(f"\n✅ Comprehensive coverage analysis complete!")
    print(f"📊 Total runtime: {duration/60:.1f} minutes")

if __name__ == "__main__":
    main()