# py-accountant

Development environment setup with Poetry, Ruff, Pytest, and pre-commit.

## Quick start

1. Install Poetry (if not installed):
   - macOS:
     - `curl -sSL https://install.python-poetry.org | python3 -`
     - Ensure `~/.local/bin` is on your PATH.

2. Install dependencies and create the virtual environment:

```bash
poetry install --with dev
```

3. Activate the environment (optional):

```bash
poetry shell
```

4. Run tests:

```bash
poetry run pytest
```

5. Lint and format with Ruff:

```bash
poetry run ruff check .
poetry run ruff format .
```

6. Install pre-commit hooks:

```bash
poetry run pre-commit install
```

### Using as a package
With the src/ layout, the package is published as `py-accountant` but imported as `py_accountant`:

```python
import py_accountant
print(py_accountant.get_version())
print(py_accountant.add(2, 3))  # 5
```

After installation (e.g. `poetry install`) you can verify:

```bash
poetry run python -c "import py_accountant,sys; print(py_accountant.get_version())"
```

## Notes
- SQLAlchemy is pinned to the latest 2.x series (`^2.0.0`).
- Python 3.13+ is expected (pyproject declares ">=3.13,<4.0").
