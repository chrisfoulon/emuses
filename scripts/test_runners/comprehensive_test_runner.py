#!/usr/bin/env python3
"""
EMUSES Comprehensive Test Runner

A category-based test execution utility that prevents timeout issues and zombie processes
by running tests in organized categories with proper resource management.

This replaces the anti-pattern of running pytest from within pytest tests.

Usage:
    python scripts/test_runners/comprehensive_test_runner.py --category security
    python scripts/test_runners/comprehensive_test_runner.py --all
    python scripts/test_runners/comprehensive_test_runner.py --parallel
"""

import argparse
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import concurrent.futures
import threading
from dataclasses import dataclass, asdict


@dataclass
class TestCategoryResult:
    """Results from running a test category."""
    category: str
    status: str  # 'passed', 'failed', 'timeout', 'error'
    duration: float
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    output: str
    error_output: str
    timeout_occurred: bool = False


class ComprehensiveTestRunner:
    """
    Comprehensive test runner with category-based execution and timeout management.
    
    Designed for neuroimaging research platform validation without meta-testing anti-patterns.
    """
    
    # Test categories with estimated runtimes and timeout limits
    TEST_CATEGORIES = {
        'security': {
            'paths': ['tests/security/'],
            'description': 'OWASP validation, authentication, permissions',
            'estimated_time': '5-10 minutes',
            'timeout': 900,  # 15 minutes
            'priority': 'high'
        },
        'model_registry': {
            'paths': ['tests/model_registry/', 'tests/tools/test_model_registry_health.py', 'tests/tools/test_model_registry_metrics.py'],
            'description': 'Local/database/cloud registry functionality',
            'estimated_time': '10-15 minutes', 
            'timeout': 1200,  # 20 minutes
            'priority': 'high'
        },
        'integration': {
            'paths': ['tests/integration/'],
            'description': 'Cross-mode workflows, API endpoints',
            'estimated_time': '15-20 minutes',
            'timeout': 1500,  # 25 minutes
            'priority': 'high'
        },
        'deployment': {
            'paths': ['tests/deployment/'],
            'description': 'Environment validation, configuration checks',
            'estimated_time': '5-10 minutes',
            'timeout': 900,   # 15 minutes
            'priority': 'medium'
        },
        'performance': {
            'paths': ['tests/performance/'],
            'description': 'Caching, query optimization, scalability',
            'estimated_time': '10-15 minutes',
            'timeout': 1200,  # 20 minutes
            'priority': 'medium'
        },
        'cli': {
            'paths': ['tests/enhanced-cli-typer/', 'tests/cli/'],
            'description': 'Command-line interface functionality',
            'estimated_time': '10-15 minutes',
            'timeout': 1200,  # 20 minutes
            'priority': 'high'
        },
        'foundation': {
            'paths': ['tests/foundation_fastapi_service/'],
            'description': 'FastAPI service layer',
            'estimated_time': '5-10 minutes',
            'timeout': 900,   # 15 minutes
            'priority': 'high'
        },
        'multi_user': {
            'paths': ['tests/multi-user-service/'],
            'description': 'Multi-user authentication and workspace management',
            'estimated_time': '10-15 minutes',
            'timeout': 1200,  # 20 minutes
            'priority': 'high'
        },
        'tools': {
            'paths': ['tests/tools/'],
            'description': 'Neuroimaging analysis tools and utilities',
            'estimated_time': '15-20 minutes',
            'timeout': 1500,  # 25 minutes
            'priority': 'medium'
        },
        'pipelines': {
            'paths': ['tests/pipelines/'],
            'description': 'Data processing pipelines',
            'estimated_time': '10-15 minutes', 
            'timeout': 1200,  # 20 minutes
            'priority': 'high'
        }
    }
    
    def __init__(self):
        """Initialize the comprehensive test runner."""
        self.project_root = Path(__file__).parent.parent.parent
        self.results: List[TestCategoryResult] = []
        self.start_time = None
        self.end_time = None
        
    def run_category(self, category: str, verbose: bool = False) -> TestCategoryResult:
        """
        Run tests for a specific category with timeout management.
        
        Parameters
        ----------
        category : str
            Test category name
        verbose : bool
            Enable verbose output
            
        Returns
        -------
        TestCategoryResult
            Results from test execution
        """
        if category not in self.TEST_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
            
        cat_info = self.TEST_CATEGORIES[category]
        print(f"\n🧪 Running {category} tests")
        print(f"   Description: {cat_info['description']}")
        print(f"   Estimated time: {cat_info['estimated_time']}")
        
        start_time = time.time()
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest']
        cmd.extend(cat_info['paths'])
        cmd.extend([
            '-q' if not verbose else '-v',
            '--tb=short',
            '--maxfail=10',  # Stop after 10 failures to avoid overwhelming output
            '--disable-warnings' if not verbose else '--disable-warnings'
        ])
        
        try:
            # Run with timeout
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=cat_info['timeout']
            )
            
            duration = time.time() - start_time
            
            # Parse pytest output for test counts
            tests_run, tests_passed, tests_failed, tests_skipped = self._parse_pytest_output(result.stdout)
            
            status = 'passed' if result.returncode == 0 else 'failed'
            
            return TestCategoryResult(
                category=category,
                status=status,
                duration=duration,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_skipped=tests_skipped,
                output=result.stdout,
                error_output=result.stderr,
                timeout_occurred=False
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"   ⚠️  Timeout after {duration:.1f}s (limit: {cat_info['timeout']}s)")
            
            return TestCategoryResult(
                category=category,
                status='timeout',
                duration=duration,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                output="",
                error_output=f"Test execution timed out after {cat_info['timeout']} seconds",
                timeout_occurred=True
            )
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"   ❌ Error: {e}")
            
            return TestCategoryResult(
                category=category,
                status='error',
                duration=duration,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                output="",
                error_output=str(e),
                timeout_occurred=False
            )
    
    def run_all_categories(self, verbose: bool = False, parallel: bool = False) -> List[TestCategoryResult]:
        """
        Run all test categories.
        
        Parameters
        ----------
        verbose : bool
            Enable verbose output
        parallel : bool
            Run categories in parallel (experimental)
            
        Returns
        -------
        List[TestCategoryResult]
            Results from all categories
        """
        print("🚀 EMUSES Comprehensive Test Validation")
        print("=" * 60)
        print(f"⚠️  Testing approach: Category-based to prevent timeout issues")
        print(f"🎯 Categories: {len(self.TEST_CATEGORIES)} test categories")
        print(f"📊 Parallel execution: {'Enabled' if parallel else 'Sequential'}")
        print("=" * 60)
        
        self.start_time = time.time()
        
        if parallel:
            self.results = self._run_categories_parallel(verbose)
        else:
            self.results = self._run_categories_sequential(verbose)
            
        self.end_time = time.time()
        
        return self.results
    
    def _run_categories_sequential(self, verbose: bool) -> List[TestCategoryResult]:
        """Run categories sequentially."""
        results = []
        
        for category in self.TEST_CATEGORIES.keys():
            result = self.run_category(category, verbose)
            results.append(result)
            self._print_category_result(result)
            
        return results
    
    def _run_categories_parallel(self, verbose: bool) -> List[TestCategoryResult]:
        """Run categories in parallel (experimental)."""
        print("🔄 Running categories in parallel...")
        
        results = []
        max_workers = min(4, len(self.TEST_CATEGORIES))  # Limit parallelism
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all category tests
            future_to_category = {
                executor.submit(self.run_category, category, verbose): category
                for category in self.TEST_CATEGORIES.keys()
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_category):
                category = future_to_category[future]
                try:
                    result = future.result()
                    results.append(result)
                    self._print_category_result(result)
                except Exception as e:
                    print(f"❌ Category {category} failed with exception: {e}")
                    
        # Sort results by category name for consistent reporting
        results.sort(key=lambda x: x.category)
        return results
    
    def _parse_pytest_output(self, output: str) -> Tuple[int, int, int, int]:
        """
        Parse pytest output to extract test counts.
        
        Returns
        -------
        Tuple[int, int, int, int]
            tests_run, tests_passed, tests_failed, tests_skipped
        """
        # Look for pattern like "5 passed, 2 failed, 1 skipped"
        import re
        
        # Default values
        tests_run = tests_passed = tests_failed = tests_skipped = 0
        
        # Parse final summary line
        summary_patterns = [
            r'(\d+) passed',
            r'(\d+) failed', 
            r'(\d+) skipped',
            r'(\d+) error'
        ]
        
        for line in output.split('\n'):
            if 'passed' in line or 'failed' in line or 'skipped' in line:
                for pattern in summary_patterns:
                    match = re.search(pattern, line)
                    if match:
                        count = int(match.group(1))
                        if 'passed' in pattern:
                            tests_passed = count
                        elif 'failed' in pattern or 'error' in pattern:
                            tests_failed = count
                        elif 'skipped' in pattern:
                            tests_skipped = count
        
        tests_run = tests_passed + tests_failed + tests_skipped
        return tests_run, tests_passed, tests_failed, tests_skipped
    
    def _print_category_result(self, result: TestCategoryResult):
        """Print formatted result for a category."""
        status_emoji = {
            'passed': '✅',
            'failed': '❌', 
            'timeout': '⏰',
            'error': '🚨'
        }
        
        emoji = status_emoji.get(result.status, '❓')
        print(f"{emoji} {result.category}: {result.status.upper()} "
              f"({result.duration:.1f}s, {result.tests_passed}✅ {result.tests_failed}❌ {result.tests_skipped}⏭️)")
        
        if result.status in ['failed', 'error'] and result.error_output:
            print(f"   Error: {result.error_output[:200]}...")
    
    def generate_report(self, output_file: Optional[str] = None) -> Dict:
        """
        Generate comprehensive test report.
        
        Parameters
        ----------
        output_file : str, optional
            Path to save JSON report
            
        Returns
        -------
        Dict
            Comprehensive test report
        """
        if not self.results:
            print("❌ No test results available. Run tests first.")
            return {}
            
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        # Calculate summary statistics
        total_tests = sum(r.tests_run for r in self.results)
        total_passed = sum(r.tests_passed for r in self.results)
        total_failed = sum(r.tests_failed for r in self.results)
        total_skipped = sum(r.tests_skipped for r in self.results)
        
        categories_passed = len([r for r in self.results if r.status == 'passed'])
        categories_failed = len([r for r in self.results if r.status in ['failed', 'error', 'timeout']])
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_duration': total_duration,
                'total_categories': len(self.results),
                'categories_passed': categories_passed,
                'categories_failed': categories_failed,
                'total_tests': total_tests,
                'total_passed': total_passed,
                'total_failed': total_failed,
                'total_skipped': total_skipped,
                'success_rate': total_passed / total_tests if total_tests > 0 else 0
            },
            'categories': [asdict(result) for result in self.results],
            'recommendations': self._generate_recommendations()
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST VALIDATION REPORT")
        print("=" * 60)
        print(f"⏱️  Total Duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        print(f"📁 Categories: {categories_passed}✅ passed, {categories_failed}❌ failed")
        print(f"🧪 Tests: {total_passed}✅ passed, {total_failed}❌ failed, {total_skipped}⏭️ skipped")
        print(f"📈 Success Rate: {report['summary']['success_rate']:.1%}")
        
        if categories_failed > 0:
            print(f"\n⚠️  Failed Categories:")
            for result in self.results:
                if result.status in ['failed', 'error', 'timeout']:
                    print(f"   • {result.category}: {result.status}")
        
        # Save to file if requested
        if output_file:
            output_path = Path(output_file)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Detailed report saved to: {output_path}")
            
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check for timeouts
        timeout_categories = [r for r in self.results if r.timeout_occurred]
        if timeout_categories:
            recommendations.append(
                f"Consider breaking down {len(timeout_categories)} timed-out categories into smaller chunks"
            )
        
        # Check for high failure rate
        failed_categories = [r for r in self.results if r.status in ['failed', 'error']]
        if len(failed_categories) > len(self.results) // 2:
            recommendations.append(
                "High failure rate detected. Consider running individual categories for detailed debugging"
            )
        
        # Check for specific category issues
        high_priority_failures = [
            r for r in failed_categories 
            if self.TEST_CATEGORIES.get(r.category, {}).get('priority') == 'high'
        ]
        if high_priority_failures:
            recommendations.append(
                f"High-priority categories failed: {', '.join(r.category for r in high_priority_failures)}"
            )
        
        return recommendations


def main():
    """Main entry point for comprehensive test runner."""
    parser = argparse.ArgumentParser(
        description="EMUSES Comprehensive Test Runner - Category-based validation without meta-testing"
    )
    parser.add_argument(
        '--category', 
        choices=list(ComprehensiveTestRunner.TEST_CATEGORIES.keys()),
        help='Run tests for a specific category'
    )
    parser.add_argument(
        '--all', 
        action='store_true',
        help='Run all test categories'
    )
    parser.add_argument(
        '--parallel',
        action='store_true', 
        help='Run categories in parallel (experimental)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--report',
        help='Save detailed JSON report to file'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available test categories'
    )
    
    args = parser.parse_args()
    
    runner = ComprehensiveTestRunner()
    
    if args.list:
        print("📋 Available Test Categories:")
        print("=" * 50)
        for category, info in runner.TEST_CATEGORIES.items():
            priority_emoji = "🔥" if info['priority'] == 'high' else "📋"
            print(f"{priority_emoji} {category:15} | {info['description']}")
            print(f"   {'':15} | Time: {info['estimated_time']}")
        return
    
    if args.category:
        # Run single category
        result = runner.run_category(args.category, args.verbose)
        runner.results = [result]
        runner._print_category_result(result)
        
    elif args.all:
        # Run all categories
        runner.run_all_categories(args.verbose, args.parallel)
        
    else:
        print("❌ Please specify --category, --all, or --list")
        parser.print_help()
        return
    
    # Generate report
    if runner.results:
        report = runner.generate_report(args.report)
        
        # Exit with error code if any tests failed
        if any(r.status in ['failed', 'error', 'timeout'] for r in runner.results):
            sys.exit(1)


if __name__ == '__main__':
    main()