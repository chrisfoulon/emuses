# Multi-User EMUSES Service - User Decision Log

## Purpose
This file tracks important decisions made during the planning phase to guide implementation and serve as reference for future development.

## Decision Categories

### Technical Decisions
Architecture, API design, error handling approaches

### Trade-offs  
Performance vs. simplicity, security vs. usability

### Integration Choices
How to connect with existing components

### Breaking Changes
When existing interfaces might need modification

## Decisions Made

### Decision #1: Database Schema Design - User Model Extensions

**Context**: EMUSES user interactions are primarily:
- FIT a model (train brain analysis model)
- RESUME training 
- PREDICT from new data
- Basic preferences (default parameters to avoid manual entry)

**Analysis of Options**:

**Option A: Minimal (RECOMMENDED for EMUSES)**
- Implementation Risk: LOW
- Code Breaking: MINIMAL  
- Time: 2-3 days
- Perfect for EMUSES's simple parameter defaults and workspace organization

**Option B: Rich Profile**
- Implementation Risk: MEDIUM
- Code Breaking: MODERATE
- Time: 4-6 days  
- Over-engineered for EMUSES's actual needs

**Option C: Future-Proof**
- Implementation Risk: HIGH
- Code Breaking: HIGH
- Time: 8-10 days
- Massive overkill for a research analysis tool

**DECISION**: Option A - Minimal User Extensions
**RATIONALE**: EMUSES is a focused brain analysis tool, not a social platform. Users need simple defaults (n_jobs, optuna_trials) and workspace organization. Minimal approach reduces risk and matches actual use case.

### Decision #2: Authentication Scope - Which Endpoints Require Authentication

**Context**: Need to determine which API endpoints require authentication vs remain open, considering three deployment modes and research workflow needs.

**Analysis of Options**:

**Option A: Simple Binary Protection**
- Always open: health/docs
- Always protected: everything else when auth enabled
- Risk: Too restrictive for research workflows

**Option B: Progressive Protection (RECOMMENDED)**
- Level 0 (local): No auth - current behavior  
- Level 1 (multi-user): Input protected, monitoring open
- Level 2 (production): Full protection with user isolation
- Perfect for research scenarios and deployment flexibility

**Option C: Maximum Optional Auth**  
- Everything adapts based on login status
- Risk: Complex logic, potential security gaps

**DECISION**: Option B - Progressive Protection Based on Risk
**RATIONALE**: Provides perfect deployment flexibility from single-user (no auth) to production (full auth) while supporting research workflows where status monitoring from multiple locations is common. Input operations protected, monitoring operations open in multi-user mode.

### Decision #3: Admin Interface Complexity - Basic vs Advanced Features

**Context**: Need to determine complexity level for admin interface considering research server environments and typical admin user profiles.

**Analysis of Options**:

**Option A: Basic Admin Features (RECOMMENDED)**
- Simple API endpoints + CLI commands
- Time: 1-2 days, Maintenance: Low
- Perfect for research servers without GUI
- Familiar CLI pattern for research environments

**Option B: Web-Based Admin Dashboard**
- Full web interface with visual management
- Time: 4-6 days, Maintenance: Medium-High
- Problem: GUI setup complexity on remote research servers

**Option C: Advanced Management Platform**
- Enterprise-grade comprehensive system
- Time: 8-12 days, Maintenance: High
- Massive overkill for research lab scale (5-20 users)

**DECISION**: Option A - Basic Admin Features (API + CLI)
**RATIONALE**: Research servers typically lack GUI access, making CLI ideal. Admin tasks are infrequent (monthly user adds, occasional maintenance) and performed by researchers/lab managers who prefer simple, well-documented CLI tools over complex web interfaces. Focus on excellent documentation and help commands.

### Decision #4: Background Task Management - Celery vs Simple Threading

**Context**: Need to determine how to handle background processing of brain analysis jobs (2-6 hours) for multiple users while considering EMUSES usage patterns and infrastructure reality.

**Analysis of Options**:

**Option A: Simple Threading Enhancement**
- Poor performance: GIL prevents parallel CPU processing
- Research shows threading worse than sequential for CPU tasks
- Not suitable for brain analysis workloads

**Option B: Celery with Redis/RabbitMQ**
- Best performance and infinite scalability
- Complex infrastructure (Redis/RabbitMQ setup)
- Overkill for single-server research environments

**Option C: Hybrid Approach (RECOMMENDED)**
- Python ProcessPoolExecutor for true multiprocessing
- Simple infrastructure, no external dependencies
- Perfect performance for research lab scale
- Future-proof but not over-engineered

**DECISION**: Option C - Hybrid Approach (ProcessPoolExecutor)
**RATIONALE**: Research reality shows single-server deployments with multiple users. EMUSES jobs are hours-long (not days/weeks), making complex distributed infrastructure unnecessary. Hybrid approach provides excellent CPU performance for brain analysis while maintaining simplicity for research environments. Can be upgraded to Celery later if multi-server needs emerge.

## Discussion Notes

**Key Insights from Decision Process**:
- EMUSES is a focused research tool, not a social platform - simple user models sufficient
- Research workflows need flexible auth (monitoring from multiple locations) - progressive protection ideal
- Research servers lack GUI access - CLI admin tools preferred
- Single-server deployments dominant in research - hybrid background processing optimal for current needs

*Important discussion points and rationale will be captured here*