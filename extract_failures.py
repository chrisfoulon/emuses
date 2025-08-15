#!/usr/bin/env python3
"""Extract and categorize all test failures from comprehensive test results."""

import json
import re
from pathlib import Path
from collections import defaultdict

def extract_failures_from_json(json_file):
    """Extract failure information from test results JSON."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    failures_by_category = {}
    
    for category_data in data['categories']:
        category = category_data['category']
        if category_data['status'] == 'failed' and category_data['tests_failed'] > 0:
            # Extract failure information from output
            output = category_data['output']
            failures = extract_failure_details(output)
            failures_by_category[category] = {
                'count': category_data['tests_failed'],
                'total': category_data['tests_run'],
                'success_rate': category_data['tests_passed'] / category_data['tests_run'],
                'failures': failures
            }
    
    return failures_by_category

def extract_failure_details(output):
    """Extract detailed failure information from pytest output."""
    failures = []
    
    # Split by failure sections
    failure_sections = re.split(r'_{20,}', output)
    
    for section in failure_sections:
        if 'FAILED' not in section:
            continue
            
        # Extract test name
        test_match = re.search(r'(test_[\w_]+)', section)
        if not test_match:
            continue
            
        test_name = test_match.group(1)
        
        # Extract file path
        file_match = re.search(r'tests/[\w/]+\.py', section)
        file_path = file_match.group(0) if file_match else 'unknown'
        
        # Extract error type and message
        error_type = 'Unknown'
        error_msg = 'No error message found'
        
        if 'AssertionError' in section:
            error_type = 'AssertionError'
            assertion_match = re.search(r'AssertionError: (.+?)(?:\n|$)', section)
            if assertion_match:
                error_msg = assertion_match.group(1).strip()
        elif 'NameError' in section:
            error_type = 'NameError'
            name_match = re.search(r'NameError: (.+?)(?:\n|$)', section)
            if name_match:
                error_msg = name_match.group(1).strip()
        elif 'FileNotFoundError' in section:
            error_type = 'FileNotFoundError'
            file_match = re.search(r'FileNotFoundError: (.+?)(?:\n|$)', section)
            if file_match:
                error_msg = file_match.group(1).strip()
        elif 'ConnectError' in section:
            error_type = 'ConnectError'
            error_msg = 'Connection failed'
        
        failures.append({
            'test_name': test_name,
            'file_path': file_path,
            'error_type': error_type,
            'error_message': error_msg
        })
    
    return failures

def categorize_failures(failures_by_category):
    """Categorize failures by type and risk level."""
    categorized = {
        'api_usage': [],
        'environment': [],
        'business_logic': [],
        'integration': [],
        'configuration': []
    }
    
    for category, data in failures_by_category.items():
        for failure in data['failures']:
            failure['category'] = category
            
            # Categorize by error type and content
            error_type = failure['error_type']
            error_msg = failure['error_message'].lower()
            
            if error_type == 'NameError':
                categorized['api_usage'].append(failure)
            elif error_type == 'FileNotFoundError' and 'no such file or directory' in error_msg:
                categorized['environment'].append(failure)
            elif error_type == 'ConnectError':
                categorized['environment'].append(failure)
            elif error_type == 'AssertionError' and ('not implemented' in error_msg or 'none is not none' in error_msg):
                categorized['api_usage'].append(failure)
            elif error_type == 'AssertionError' and ('success rate' in error_msg or 'expected call not found' in error_msg):
                categorized['business_logic'].append(failure)
            elif 'integration' in failure['file_path']:
                categorized['integration'].append(failure)
            else:
                categorized['configuration'].append(failure)
    
    return categorized

def generate_failure_report(failures_by_category, categorized_failures):
    """Generate comprehensive failure analysis report."""
    report = []
    
    report.append("# COMPREHENSIVE TEST FAILURE ANALYSIS")
    report.append("## 📊 **Failure Summary by Category**")
    report.append("")
    
    total_failures = sum(data['count'] for data in failures_by_category.values())
    total_tests = sum(data['total'] for data in failures_by_category.values())
    
    report.append(f"**Overall**: {total_failures} failures out of {total_tests} tests")
    report.append("")
    
    for category, data in failures_by_category.items():
        success_rate = data['success_rate'] * 100
        report.append(f"- **{category}**: {data['count']} failures ({success_rate:.1f}% success)")
    
    report.append("")
    report.append("## 🔍 **Failure Classification**")
    report.append("")
    
    for failure_type, failures in categorized_failures.items():
        if not failures:
            continue
            
        report.append(f"### **{failure_type.replace('_', ' ').title()}** ({len(failures)} failures)")
        report.append("")
        
        for failure in failures:
            report.append(f"- **{failure['test_name']}** ({failure['category']})")
            report.append(f"  - File: `{failure['file_path']}`")
            report.append(f"  - Error: {failure['error_type']} - {failure['error_message']}")
            report.append("")
    
    return "\n".join(report)

if __name__ == "__main__":
    json_file = "final_test_results.json"
    
    if not Path(json_file).exists():
        print(f"Error: {json_file} not found")
        exit(1)
    
    failures_by_category = extract_failures_from_json(json_file)
    categorized_failures = categorize_failures(failures_by_category)
    report = generate_failure_report(failures_by_category, categorized_failures)
    
    with open("COMPREHENSIVE_FAILURE_ANALYSIS.md", "w") as f:
        f.write(report)
    
    print("✅ Failure analysis complete - saved to COMPREHENSIVE_FAILURE_ANALYSIS.md")