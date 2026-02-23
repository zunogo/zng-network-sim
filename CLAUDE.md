# Project Conventions

## Git
- Commit messages: descriptive single-line messages (e.g., `Add Claude chat tab with tool-use loop`)
- Do not auto-commit unless explicitly asked

## Python
- Follow existing patterns: Pydantic models, type hints, module-level docstrings
- Use existing color palette and Plotly layout conventions from `src/zng_simulator/dashboard/app.py`

## Testing
- Run `pytest tests/ -v` before committing
- Existing tests must continue to pass

## General
- Do not create docs/READMEs unless asked
- Do not add comments or docstrings to code you didn't change
