# Setup Guide

## Installation

### 1. Activate Virtual Environment
```bash
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -e .
```

This will install all required dependencies from `pyproject.toml`:
- `pydantic` - Data validation
- `pyyaml` - Configuration loading
- `streamlit` - Dashboard UI
- `numpy` - Numerical operations
- `pandas` - Data manipulation
- `plotly` - Interactive visualizations
- `scipy` - Scientific computing (for Weibull distribution in charger failures)

### 3. Verify Installation
```bash
python -c "from scipy.special import gamma; print('✓ All dependencies installed')"
```

## Running the Dashboard

### Start Streamlit
```bash
streamlit run src/zng_simulator/dashboard/app.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Running Tests

```bash
pytest tests/ -v
```

Or for quick summary:
```bash
pytest tests/ -q
```

## Development

### Installing Dev Dependencies
```bash
pip install -e ".[dev]"
```

This adds:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting

### Running Tests with Coverage
```bash
pytest tests/ --cov=src/zng_simulator --cov-report=html
```

Coverage report will be in `htmlcov/index.html`

## Troubleshooting

### ModuleNotFoundError
If you get `ModuleNotFoundError: No module named 'scipy'` (or any other module):

1. Make sure you're in the virtual environment:
   ```bash
   which python  # Should show path to .venv/bin/python
   ```

2. If not, activate it:
   ```bash
   source .venv/bin/activate
   ```

3. Reinstall dependencies:
   ```bash
   pip install -e .
   ```

### Streamlit Not Found
```bash
pip install streamlit
```

### Port Already in Use
If port 8501 is busy:
```bash
streamlit run src/zng_simulator/dashboard/app.py --server.port 8502
```
