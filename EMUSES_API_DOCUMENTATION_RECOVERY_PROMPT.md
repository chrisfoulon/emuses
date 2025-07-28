# Prompt for EMUSES API Documentation Recovery and Creation

## Task Overview
You are tasked with recovering lost strategic documentation and creating comprehensive user-facing API documentation for the EMUSES neuroimaging analysis platform. This work follows the LAD (LLM-Assisted Development) framework conventions and requires careful verification of all technical details.

## Context
EMUSES has a mature API implementation (`emuses/api/`, `emuses/foundation_fastapi_service/`) but lost its documentation during a consolidation commit (91f5ae6, July 26, 2025). The codebase follows LAD documentation conventions with 3-level progressive disclosure for different user types.

## Part 1: Document Recovery
Recover and consolidate these specific high-value documents from git history:

### Strategic Vision Recovery
```bash
# Recover EMUSES Hub strategic vision
git show 225eeff:docs/cli-testclient-integration/emuses_hub_vision.md > docs/EMUSES_HUB_VISION.md
```

### Implementation Reference Recovery
```bash
# Create archive directory for implementation references
mkdir -p docs/_archive_implementation

# Recover FastAPI service architecture plans
git show 76f7ccd:docs/foundation-fastapi-service/plan_master.md > docs/_archive_implementation/fastapi_service_implementation_plan.md
git show 76f7ccd:docs/foundation-fastapi-service/context_0a_foundation.md > docs/_archive_implementation/fastapi_service_foundation_context.md
git show 76f7ccd:docs/foundation-fastapi-service/COMPLETION_SUMMARY_0d.md > docs/_archive_implementation/fastapi_service_completion_summary.md

# Recover enhanced CLI implementation plans
git show 76f7ccd:docs/enhanced-cli-typer/plan_master.md > docs/_archive_implementation/enhanced_cli_implementation_plan.md
git show 76f7ccd:docs/enhanced-cli-typer/context_0a_foundation.md > docs/_archive_implementation/enhanced_cli_foundation_context.md

# Recover test client integration context
git show 225eeff:docs/cli-testclient-integration/context.md > docs/_archive_implementation/cli_testclient_integration_context.md
git show 225eeff:docs/cli-testclient-integration/plan.md > docs/_archive_implementation/cli_testclient_integration_plan.md
```

**Post-recovery task**: Clean and consolidate these recovered documents, removing redundancy and extracting key architectural decisions and design patterns.

## Part 2: Comprehensive API Documentation Creation

### Documentation Requirements

**Follow LAD 3-Level Progressive Disclosure:**
- **Level 1: Visible Summary** - Overview for novice users
- **Level 2: Collapsible API Details** - `<details>` sections for advanced users  
- **Level 3: Developer Implementation** - `<details>` sections with code examples for developers

**Use `docs/_scratch/` for organization:**
- Create planning and analysis files in `docs/_scratch/api_documentation_planning/`
- Document your verification process and findings
- Note any unknowns or areas requiring future investigation

### Required Documentation Files

#### 1. `docs/emuses/api_service.md`
**Content Requirements:**
- **Level 1**: Service overview, basic usage, getting started
- **Level 2**: Complete endpoint reference, request/response models, authentication
- **Level 3**: Integration patterns, error handling, advanced configuration

**Technical Verification Required:**
- Review `emuses/api/main.py` for actual endpoints
- Examine `emuses/foundation_fastapi_service/app.py` for service architecture
- Check `emuses/foundation_fastapi_service/models.py` for request/response schemas
- Verify job management in `emuses/foundation_fastapi_service/job_manager.py`
- Review pipeline integration in `emuses/foundation_fastapi_service/pipeline_runner.py`

#### 2. `docs/emuses/cli_service_integration.md`
**Content Requirements:**
- **Level 1**: How CLI integrates with service, basic usage patterns
- **Level 2**: Service client configuration, connection management, offline fallback
- **Level 3**: Implementation details, service lifecycle management, debugging

**Technical Verification Required:**
- Examine `emuses/cli/service_client.py` for client implementation
- Review `emuses/cli/service_manager.py` for service lifecycle
- Check `emuses/cli/main.py` for CLI-to-service integration points
- Verify interactive mode integration in `emuses/cli/interactive_mode.py`

#### 3. `docs/emuses/service_deployment.md`
**Content Requirements:**
- **Level 1**: Basic deployment, local development setup
- **Level 2**: Production deployment, configuration, monitoring
- **Level 3**: Advanced deployment patterns, scaling, troubleshooting

**Technical Verification Required:**
- Review service startup/shutdown mechanisms
- Check configuration management and environment variables
- Examine logging and monitoring capabilities
- Verify security considerations and best practices

#### 4. Update `docs/emuses/EMUSES_DOCUMENTATION_SUMMARY.md`
Add comprehensive section covering the new API documentation, following existing format and style.

### Verification Requirements

**Critical: No Hallucination Policy**
- Every technical detail must be verified against actual code
- Every endpoint, parameter, and configuration option must exist in the codebase
- All code examples must be tested or clearly marked as conceptual
- All integration patterns must be verified against actual implementation

**Unknown Documentation Protocol:**
- If you cannot verify a detail from the code, explicitly note: `[VERIFICATION NEEDED: Description of what needs verification]`
- Create a consolidated list of unknowns at the end of each document
- Provide clear pointers for users/maintainers to resolve verification issues

**Verification Process:**
1. Use `Read`, `Glob`, and `Grep` tools extensively to examine actual code
2. Cross-reference recovered documentation with current implementation
3. Document your verification process in `docs/_scratch/api_documentation_planning/verification_log.md`
4. Note any discrepancies between recovered plans and actual implementation

### Quality Standards

**Industry Standard Documentation:**
- Clear, concise language suitable for technical audiences
- Comprehensive but not overwhelming
- Practical examples and common use cases
- Proper error handling and troubleshooting guidance
- Consistent formatting and structure

**LAD Framework Compliance:**
- Follow NumPy-style docstring conventions where applicable
- Use consistent markdown formatting matching existing docs
- Maintain the established 3-level progressive disclosure pattern
- Include proper cross-references and integration notes

### Deliverables Checklist

- [ ] Strategic documents recovered and cleaned
- [ ] Implementation reference archive created and organized
- [ ] `docs/emuses/api_service.md` - Complete API reference
- [ ] `docs/emuses/cli_service_integration.md` - CLI integration guide  
- [ ] `docs/emuses/service_deployment.md` - Deployment guide
- [ ] `docs/emuses/EMUSES_DOCUMENTATION_SUMMARY.md` updated
- [ ] `docs/_scratch/api_documentation_planning/` directory with planning files
- [ ] Verification log with all technical details confirmed
- [ ] Unknown/unverified items clearly documented with resolution pointers

### Success Criteria

The documentation should enable:
1. **Novice users** to understand what the API provides and get started quickly
2. **Advanced users** to integrate EMUSES API into their workflows effectively  
3. **Developers** to extend, deploy, and troubleshoot the service components
4. **Maintainers** to understand architectural decisions and implementation patterns

All information must be accurate, verified, and aligned with the actual codebase state as of the current commit.