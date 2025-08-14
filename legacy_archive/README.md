# Legacy Archive

This directory contains legacy code that has been archived to prevent confusion with production interfaces.

## Scripts Archive (2025-08-14)

**Archived from**: `emuses/scripts/`
**Reason**: Legacy scripts that should not influence production implementation
**Proper Production Interfaces**: 
- CLI: `python -m emuses.cli`
- API: `python -m emuses.api.main` 
- Import: `from emuses import ...`

### Archived Files:
- `__init__.py` - Legacy module init
- `run_optim_experiments.py` - Legacy experiment runner
- `streamlit_main.py` - Legacy Streamlit interface
- `viz_streamlit.py` - Legacy visualization interface

### Migration Notes:
- Tests previously referencing `emuses/scripts/main.py` updated to use `python -m emuses.cli`
- Integration tests updated to use proper production CLI interface
- Any functionality needed from these scripts should be re-implemented through proper CLI/API interfaces