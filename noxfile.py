"""
Nox automation script for the Terminus project.

This file defines automated development sessions such as linting and testing,
using Python version requirements extracted dynamically from pyproject.toml
to ensure consistency across local and CI environments.

Tooling used:
- Nox: session orchestration
- UV: fast, lock-aware dependency resolver
- Ruff: linter and formatter
- Pytest: testing framework

Python version is parsed from [project] requires-python in pyproject.toml.
"""

import re
import sys
import nox

try:
    import tomllib  # Python 3.11+ stdlib
except ModuleNotFoundError:
    print("ERROR: Python 3.11+ required (tomllib is missing)", file=sys.stderr)
    sys.exit(1)

# === Extract Python version from pyproject.toml ===
try:
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        version_spec = pyproject["project"]["requires-python"]
except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError) as e:
    print(f"Failed to parse pyproject.toml: {e}", file=sys.stderr)
    sys.exit(1)

match = re.search(r"[>=~=]\s*(\d+\.\d+)", version_spec)
if not match:
    print(f"Could not extract Python version from: {version_spec}", file=sys.stderr)
    sys.exit(1)

PYTHON_VERSION = match.group(1)  # e.g., "3.13"
CODE_DIR = "src"
TEST_DIR = "tests"
LINT_GROUP = "lint"
DEV_GROUP = "dev"

# Use uv to manage the virtual environment for all sessions
nox.options.default_venv_backend = "uv"


@nox.session(python=PYTHON_VERSION)
def lint(session: nox.Session) -> None:
    """
    Run Ruff to lint and check formatting of source files.

    This session installs only the linting group and runs two Ruff commands:
    - ruff check: validate lint rules
    - ruff format --check: verify formatting, do not modify
    """
    session.run(
        "uv", "sync", "--group", LINT_GROUP,
        f"--python={session.python}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
        external=True
    )

    session.run("ruff", "check", CODE_DIR)
    session.run("ruff", "format", "--check", CODE_DIR)