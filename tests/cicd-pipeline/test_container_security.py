"""
Container security scanning tests.

Tests that container security scanning is properly configured in CI/CD pipeline.
"""

import yaml
from pathlib import Path
import pytest


class TestContainerSecurity:
    """Test container security scanning configuration."""
    
    def test_container_security_in_ci_workflow(self):
        """Test that container security scanning is configured in CI workflow."""
        ci_file = Path(".github/workflows/ci.yml")
        with open(ci_file) as f:
            ci_config = yaml.safe_load(f)
        
        build_job = ci_config['jobs']['build']
        steps = build_job['steps']
        
        # Find security scanning steps
        grype_step = None
        sbom_step = None
        
        for step in steps:
            if 'Grype vulnerability scanner' in step.get('name', ''):
                grype_step = step
            elif 'Generate SBOM with Syft' in step.get('name', ''):
                sbom_step = step
        
        assert grype_step is not None, "Grype vulnerability scanner step should exist"
        assert sbom_step is not None, "SBOM generation step should exist"
        
        # Check Grype configuration
        assert grype_step['uses'] == 'anchore/scan-action@v3', "Should use Anchore Grype action"
        grype_with = grype_step.get('with', {})
        assert 'image' in grype_with, "Grype should specify image to scan"
        assert grype_with.get('fail-build') == True, "Grype should fail build on vulnerabilities"
        assert grype_with.get('severity-cutoff') == 'high', "Should fail on high severity vulnerabilities"
        
        # Check SBOM configuration
        assert sbom_step['uses'] == 'anchore/sbom-action@v0', "Should use Anchore SBOM action"
        sbom_with = sbom_step.get('with', {})
        assert 'image' in sbom_with, "SBOM should specify image to scan"
        assert sbom_with.get('format') == 'spdx-json', "Should generate SPDX JSON format"
        assert sbom_with.get('output-file') == 'sbom.spdx.json', "Should output to SBOM file"
    
    def test_security_reports_upload(self):
        """Test that security reports are uploaded as artifacts."""
        ci_file = Path(".github/workflows/ci.yml")
        with open(ci_file) as f:
            ci_config = yaml.safe_load(f)
        
        build_job = ci_config['jobs']['build']
        steps = build_job['steps']
        
        # Find upload artifacts step
        upload_step = None
        for step in steps:
            if step.get('uses', '').startswith('actions/upload-artifact'):
                if 'container-security' in step.get('with', {}).get('name', ''):
                    upload_step = step
                    break
        
        assert upload_step is not None, "Should upload container security artifacts"
        
        upload_with = upload_step.get('with', {})
        assert 'name' in upload_with, "Should specify artifact name"
        assert 'path' in upload_with, "Should specify files to upload"
        
        # Check that SBOM file is included
        paths = upload_with['path']
        if isinstance(paths, str):
            paths = [paths]
        elif isinstance(paths, list):
            paths = paths
        else:
            # Multi-line string format
            paths = str(paths).split('\n')
            paths = [p.strip() for p in paths if p.strip()]
        
        sbom_included = any('sbom' in path.lower() for path in paths)
        assert sbom_included, "SBOM file should be included in artifacts"