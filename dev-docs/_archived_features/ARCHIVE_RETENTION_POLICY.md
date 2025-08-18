# Archive Retention Policy

## Overview

This document establishes the retention policy for completed features and development phases in the EMUSES project.

## Retention Schedule

### **2-Year Retention Period**
- All archived features are retained for **2 years** from the archive date
- After 2 years, archives should be reviewed for potential deletion
- Critical architectural decisions may be retained longer at maintainer discretion

### **Review Schedule**
- **Annual Review**: Every January, review archives from 2+ years ago
- **Deletion Candidates**: Archives older than 2 years with no ongoing relevance
- **Permanent Retention**: Core architectural decisions, migration guides, security fixes

## Archive Naming Convention

### **Format**: `YYYY-MM-DD_feature-name`
- **Date**: When the feature was completed and archived
- **Name**: Descriptive feature name using kebab-case
- **Examples**: 
  - `2025-08-03_deployment-mode-fix`
  - `2025-07-27_graceful-shutdown-fixes`
  - `2025-12-15_inference-pipeline-implementation`

## Deletion Review Checklist

When reviewing 2+ year old archives, consider:

- [ ] **Historical Value**: Does this document architectural decisions still relevant?
- [ ] **Reference Usage**: Has this been referenced in the last year?
- [ ] **Dependency Documentation**: Do current systems depend on understanding this implementation?
- [ ] **Security/Compliance**: Are there regulatory requirements to retain this?
- [ ] **Educational Value**: Would this help future developers understand the system?

## Archive Categories

### **Completed Features** (`_archived_features/`)
- Fully implemented LAD plans with completion documentation
- **Retention**: Standard 2-year policy
- **Examples**: UI improvements, performance optimizations, bug fixes

### **Development Phases** (`_archive/`)
- Major architectural transitions and development milestones  
- **Retention**: 3+ years (longer for major architectural changes)
- **Examples**: Service architecture refactoring, deployment strategy changes

### **Implementation Archives** (`_archive_implementation/`)
- Implementation-specific documentation and technical details
- **Retention**: 1-2 years (shorter for purely technical details)
- **Examples**: CLI integration patterns, API endpoint documentation

## Scheduled Review Dates

### **Next Review Dates**:
- **January 2027**: Review 2025-dated archives
- **January 2028**: Review 2026-dated archives

### **Current Archives**:
| Archive | Completion Date | Review Date | Status |
|---------|----------------|-------------|---------|
| `2025-07-27_graceful-shutdown-fixes` | 2025-07-27 | 2027-07-27 | ✅ Active |
| `2025-07-27_parallelism-optimization` | 2025-07-27 | 2027-07-27 | ✅ Active |
| `2025-07-27_multi-user-architecture` | 2025-07-27 | 2027-07-27 | ✅ Active |
| `2025-08-03_deployment-mode-fix` | 2025-08-03 | 2027-08-03 | ✅ Active |

## Maintenance Instructions

### **When Archiving New Features**:
1. Use the naming convention: `YYYY-MM-DD_feature-name`
2. Add entry to the "Current Archives" table above
3. Include completion summary in the archived folder's README
4. Calculate review date (2 years from completion)

### **During Annual Reviews**:
1. Check archives that have reached their review date
2. Use the deletion review checklist
3. Move "permanently retained" items to a separate folder if needed
4. Update this document with deletion decisions
5. Document retention reasoning for kept archives

## Contact

For questions about retention policy or archive decisions, contact the project maintainers.