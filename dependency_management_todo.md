# Dependency Management Implementation - TodoWrite Plan

## Context and Rationale

Based on 2025 industry standards research, EMUSES needs proper dependency management to ensure production reliability and security. The current setup uses unpinned dependencies in requirements.txt, which poses risks for:
- **Security vulnerabilities**: Automatic updates could introduce vulnerable versions
- **Build reproducibility**: Different environments may install different versions
- **Deployment stability**: Production deployments could fail due to incompatible updates

**Industry Standard Solution**: Use pip-tools for dependency pinning while maintaining compatibility with existing pip-based workflow (rather than migrating to Poetry which would be disruptive).

## Implementation Tasks

### Task 1: Install and Configure pip-tools
**Priority**: High  
**Estimated Time**: 1 hour  

**Actions**:
1. Add pip-tools to development dependencies
2. Create requirements.in file from current requirements.txt
3. Generate pinned requirements.txt using pip-compile
4. Test dependency resolution and installation

**Commands**:
```bash
# Install pip-tools
pip install pip-tools

# Create requirements.in (abstract dependencies)
cp requirements.txt requirements.in

# Generate pinned requirements.txt
pip-compile requirements.in

# Verify installation works
pip-sync requirements.txt
```

### Task 2: Create Environment-Specific Requirements
**Priority**: High  
**Estimated Time**: 1 hour

**Actions**:
1. Create requirements-dev.in for development dependencies
2. Create requirements-prod.in for production-only dependencies
3. Generate corresponding .txt files with pip-compile
4. Update documentation for dependency management

**Files to Create**:
```bash
# requirements-dev.in
-r requirements.in
pytest
pytest-asyncio
pytest-cov
black
isort
flake8
mypy
bandit
safety

# requirements-prod.in  
-r requirements.in
gunicorn
uvicorn[standard]
```

### Task 3: Security Vulnerability Scanning
**Priority**: High  
**Estimated Time**: 30 minutes

**Actions**:
1. Install safety for dependency vulnerability scanning
2. Create safety policy file for known false positives
3. Add vulnerability checking to development workflow
4. Document security scanning procedures

**Implementation**:
```bash
# Install safety
pip install safety

# Check for vulnerabilities
safety check --json

# Create .safety-policy.yml for exceptions if needed
```

### Task 4: Automated Dependency Updates
**Priority**: Medium  
**Estimated Time**: 45 minutes

**Actions**:
1. Create script for dependency updates
2. Configure Dependabot for automated PRs (if using GitHub)
3. Document dependency update procedures
4. Test update workflow

**Update Script**:
```bash
#!/bin/bash
# scripts/update-dependencies.sh

echo "Updating dependencies..."

# Update base requirements
pip-compile --upgrade requirements.in

# Update development requirements  
pip-compile --upgrade requirements-dev.in

# Update production requirements
pip-compile --upgrade requirements-prod.in

echo "Dependencies updated. Review changes and test before committing."
```

### Task 5: Documentation and Integration
**Priority**: Medium  
**Estimated Time**: 45 minutes

**Actions**:
1. Update README.md with new dependency management instructions
2. Update CI/CD documentation if applicable
3. Create troubleshooting guide for dependency issues
4. Document dependency update procedures

**Documentation Updates**:
```markdown
## Dependency Management

EMUSES uses pip-tools for dependency management to ensure reproducible builds.

### Installation
```bash
# Install all dependencies
pip-sync requirements.txt

# Install development dependencies
pip-sync requirements-dev.txt
```

### Adding New Dependencies
```bash
# Add to requirements.in
echo "new-package>=1.0.0" >> requirements.in

# Regenerate requirements.txt
pip-compile requirements.in

# Install new dependencies
pip-sync requirements.txt
```

### Updating Dependencies
```bash
# Update all dependencies
./scripts/update-dependencies.sh

# Update specific package
pip-compile --upgrade-package package-name requirements.in
```
```

## Success Criteria

### Must Have
- [ ] requirements.txt contains pinned versions (package==x.y.z)
- [ ] requirements-dev.txt exists with development dependencies
- [ ] requirements-prod.txt exists with production dependencies  
- [ ] All dependencies install without conflicts
- [ ] security vulnerability scanning works
- [ ] Documentation updated with new procedures

### Quality Indicators
- [ ] Build reproducibility: Same requirements.txt produces identical environments
- [ ] Security scanning: No high-severity vulnerabilities
- [ ] Update workflow: Clear procedure for dependency updates
- [ ] CI compatibility: Works with existing testing infrastructure

## Risk Mitigation

### Technical Risks
- **Dependency conflicts**: Use pip-compile to resolve conflicts automatically
- **Breaking changes**: Pin to compatible versions, test thoroughly before updates
- **Security vulnerabilities**: Regular scanning with safety tool

### Operational Risks
- **Team adoption**: Document procedures clearly, provide training
- **CI/CD integration**: Test with existing GitHub Actions workflow
- **Rollback capability**: Keep previous requirements.txt versions in git history

## Files to be Created/Modified

### New Files
1. `requirements.in` - Abstract dependency specifications
2. `requirements-dev.in` - Development dependencies
3. `requirements-prod.in` - Production dependencies  
4. `requirements-dev.txt` - Pinned development dependencies
5. `requirements-prod.txt` - Pinned production dependencies
6. `.safety-policy.yml` - Security scanning exceptions
7. `scripts/update-dependencies.sh` - Dependency update script

### Modified Files
1. `requirements.txt` - Now contains pinned versions
2. `README.md` - Updated installation and development instructions
3. `setup.py` - May need updates for install_requires vs requirements.txt
4. `.github/workflows/ci.yml` - Use pip-sync instead of pip install -r

## Implementation Notes

**Why pip-tools over Poetry**: EMUSES already uses requirements.txt and setup.py. Migrating to Poetry would require significant restructuring and potential compatibility issues with scientific computing dependencies. pip-tools provides the benefits of dependency pinning while maintaining existing workflow compatibility.

**Security Focus**: Given EMUSES' production use cases, security vulnerability scanning is essential. The safety tool provides comprehensive vulnerability detection with configurable policies for false positives common in scientific computing libraries.

**CI/CD Integration**: The implementation must work seamlessly with existing GitHub Actions workflows and Docker build processes. pip-sync provides faster, more reliable dependency installation than pip install -r.

This implementation provides production-ready dependency management following 2025 industry standards while maintaining compatibility with EMUSES' existing development and deployment workflows.