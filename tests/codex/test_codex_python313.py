"""Standalone Codex utilities support the system Python 3.13 interpreter.

The package and its development checks may use Python 3.14+, but these
user-facing scripts are invoked explicitly with python3 on older systems.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.parametrize(
    'script',
    [
        'scripts/codex_doctor.py',
        'hooks/codex_bridge.py',
        'scripts/codex_hygiene_check.py',
        'scripts/install_codex_user.py',
        'scripts/codex_edit_guard.py',
    ],
)
def test_standalone_codex_scripts_parse_as_python_313(script: str) -> None:
    source = (ROOT / script).read_text(encoding='utf-8')
    ast.parse(source, filename=script, feature_version=(3, 13))
