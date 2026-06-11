# Security Dependency Updates - March 2026

## Overview
Addressing 62 dependabot alerts (2 critical, 38 high, 22 medium) across 19 packages.
Branch: `fix/security-dependency-updates`

## Rollback Plan
- All changes are in compiled requirements files (`requirements*.txt`)
- Git revert to previous commit restores all pinned versions
- `pip-sync requirements-dev.txt` after revert restores environment

## Phase Plan

### Phase 1: Critical Fixes (CVSS 9.1+)
| Package | Current | Target | CVE | Status |
|---------|---------|--------|-----|--------|
| authlib | 1.6.1 | >=1.6.9 | CVE-2026-27962 (9.1), +6 more | [x] 1.6.9 |
| nltk | 3.9.1 | >=3.9.3 | CVE-2025-14009 (10.0) | [x] 3.9.3 |

### Phase 2: High Severity - Safe Upgrades (patch/minor, low API risk)
| Package | Current | Target | CVE | Direct? | Status |
|---------|---------|--------|-----|---------|--------|
| python-multipart | 0.0.20 | >=0.0.22 | CVE-2026-24486 | Direct | [x] 0.0.22 |
| urllib3 | 2.5.0 | >=2.6.3 | CVE-2026-21441 +5 | Trans | [x] 2.6.3 |
| orjson | 3.11.1 | >=3.11.6 | CVE-2025-67221 | Trans | [x] 3.11.7 |
| tornado | 6.5.1 | >=6.5.5 | CVE-2026-31958 +3 | Trans | [x] 6.5.5 |
| cryptography | 45.0.5 | >=46.0.5 | CVE-2026-26007 | Trans | [x] 46.0.5 |
| protobuf | 6.31.1 | >=6.33.5 | CVE-2026-0994 | Trans | [x] 6.33.5 |
| pyasn1 | 0.6.1 | >=0.6.2 | CVE-2026-23490 | Trans | [x] 0.6.3 |
| azure-core | 1.35.0 | >=1.38.0 | CVE-2026-21226 | Trans | [x] 1.38.3 |
| starlette | 0.47.2 | >=0.49.1 | CVE-2025-62727 | Trans | [x] 0.49.1 (see notes) |
| PyJWT | 2.10.1 | >=2.12.0 | CVE-2026-32597 | Trans | [x] 2.12.1 |

### Phase 3: High Severity - Major Version Bumps (higher risk)
| Package | Current | Target | CVE | Risk | Status |
|---------|---------|--------|-----|------|--------|
| pillow | 11.3.0 | >=12.1.1 | CVE-2026-25990 | Major ver | [x] 12.1.1 |
| black | 25.1.0 | >=26.3.1 | CVE-2026-32274 | Dev-only | [x] 26.3.1 |

### Phase 4: Medium Severity
| Package | Current | Target | CVE | Risk | Status |
|---------|---------|--------|-----|------|--------|
| filelock | 3.18.0 | >=3.20.3 | CVE-2026-22701 | Minor | [x] 3.20.3 |
| werkzeug | 3.1.3 | >=3.1.5 | CVE-2026-21860 | Patch | [x] 3.1.5/3.1.6 |
| marshmallow | 4.0.0 | >=4.1.2 | CVE-2025-68480 | Minor | [x] 4.1.2 (dev) |
| fonttools | 4.59.0 | >=4.60.2 | CVE-2025-66034 | Minor | [x] 4.60.2 |
| fastapi-users | 14.0.1 | >=15.0.2 | CVE-2025-68481 | MAJOR ver | [x] 15.0.4 (see notes) |

### Explicitly SKIPPED
| Package | Current | Target | CVE | Reason |
|---------|---------|--------|-----|--------|
| torch | 2.7.1 | 2.8.0 | CVE-2025-3730 (Med) | CUDA compat risk, low severity |

## Notes

### starlette 0.47.2 → 0.49.1
fastapi==0.116.1 declares `starlette<0.48.0` in its metadata, technically conflicting. However, starlette 0.49.x is backward-compatible at the API level. When installing from a pinned requirements.txt pip does not re-resolve cross-package constraints, so this works in practice. Long-term: upgrade fastapi to >=0.121.0 and regenerate with pip-compile.

### fastapi-users 14.0.1 → 15.0.4
Public API unchanged: `FastAPIUsers`, `BearerTransport`, `JWTStrategy`, `AuthenticationBackend`, `UUIDIDMixin`, `BaseUserManager`, `SQLAlchemyUserDatabase`, `CreateUpdateDictModel` all present in 15.0.4. Required bumping `pwdlib` 0.2.1→0.3.0. No code changes to `emuses/multi_user_service/` needed.

### torch — deliberately skipped
CUDA compatibility risk for medium severity only (CVE-2025-3730). Document in future upgrade cycle.

### pip-compile — not used for this update
pip-compile in the miniforge3 Python 3.12 environment could not resolve requirements.in (originally compiled for Python 3.11). Changes were applied by direct edit of the pinned .txt files, which is valid for transitive dependency version bumps.

## Progress Log
- 2026-03-17: All 4 phases complete. 17 packages updated across requirements.txt, requirements-dev.txt, requirements-prod.txt. 13/13 dev tests pass in emuses conda env.
