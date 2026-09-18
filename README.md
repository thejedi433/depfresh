# depfresh

Check if your `pyproject.toml` dependencies are up to date with PyPI — no install required.

## What it does

`depfresh` parses your `pyproject.toml`, extracts declared dependencies, and queries PyPI for the latest versions. It reports which dependencies have newer versions available than your declared constraints allow.

Unlike `pip list --outdated`, `depfresh` checks **declared** dependencies without installing anything. Perfect for:
- CI pipelines checking if constraints are stale
- Quick health checks across multiple projects
- Finding pinned versions that haven't been updated

## Install

```bash
pip install depfresh
```

Or run without installing:

```bash
uvx depfresh
```

## Usage

```bash
# In your project directory
depfresh
```

Example output:

```
Checking 5 dependencies...

✓  httpx: up to date (>=0.27.0)
✓  packaging: up to date (>=24.0)
🔄 requests: declared >=2.28.0,<2.30.0, latest 2.31.0
✓  pytest: up to date (>=8.0.0)
✓  pytest-cov: up to date (>=5.0.0)

Found 1 outdated dependency
```

Exit codes:
- `0`: All dependencies are up to date (or no dependencies found)
- `1`: Some dependencies are outdated, or error occurred

## How it works

- Parses `pyproject.toml` to extract dependency requirements
- Queries PyPI's JSON API for each package
- Uses `packaging` to check if the latest version satisfies your declared constraint
- Reports dependencies where the latest version is **excluded** by your specifier

A dependency is "outdated" when your constraint explicitly excludes the latest version. For example:
- `requests>=2.28.0` with latest `2.31.0` → **up to date** (2.31 satisfies >=2.28)
- `requests==2.28.0` with latest `2.31.0` → **outdated** (pinned version is behind)
- `requests>=2.28.0,<2.30.0` with latest `2.31.0` → **outdated** (upper bound excludes 2.31)

## Requirements

- Python 3.11+
- No installation of your project's dependencies needed

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests with coverage
uv run pytest --cov=depfresh --cov-report=term-missing

# Run the tool
uv run depfresh
```

## License

MIT
