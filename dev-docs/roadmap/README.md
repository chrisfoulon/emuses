# EMUSES Roadmap Documentation

## Overview

This directory contains roadmap planning documents, including current priorities and deferred features tracking.

## Document Structure

### Active Planning
- **Current plans**: See `docs/model-registry/plan_4_integration.md` for active implementation tasks
- **Current context**: See `docs/model-registry/context_4_4_2_academic_compliance.md` for next implementation

### Deferred Features Management

#### Purpose
Track analyzed and designed features that are deferred to future development cycles. Prevents analysis loss and provides activation pathway when conditions are met.

#### Process
1. **Analysis Phase**: Complete technical and business analysis of potential features
2. **Decision Phase**: Decide on implementation vs. deferral based on user value, complexity, and strategic fit
3. **Documentation Phase**: Archive complete implementation design in DEFERRED_FEATURES.md
4. **Tracking Phase**: Monitor activation triggers and market conditions
5. **Activation Phase**: Implement when business conditions justify the effort

#### Current Deferred Features
- **HIPAA Compliance Implementation**: Complete technical design archived, waiting for clinical user adoption

#### Documentation Standards
Each deferred feature includes:
- **Complete technical design**: Architecture, database schemas, implementation phases
- **Business justification**: Why deferred and activation triggers  
- **Resource requirements**: Effort estimates and team needs
- **Risk assessment**: Technical and business risks for future implementation
- **Integration points**: How it fits with current architecture

## Navigation

- `DEFERRED_FEATURES.md` - Complete catalog of deferred features with implementation designs
- Main project plans in `docs/model-registry/` directory
- Implementation context documents linked from main plans

## Maintenance

This roadmap documentation is updated during:
- Feature analysis and prioritization decisions
- Major architecture changes that affect deferred features
- Market condition changes that might trigger feature activation
- Quarterly roadmap reviews

---

*Last updated: 2025-08-12 - HIPAA compliance deferred, academic compliance prioritized*