"""Sanitized token comparison never turns a usage ratio into a quota claim."""

import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = run_path(str(ROOT / 'scripts/codex_usage_comparison.py'))
load = MODULE['_load_summary']
compare = MODULE['compare']


def report(
    path: Path,
    *,
    turns: int = 2,
    input_tokens: int = 100,
    output_tokens: int = 20,
    errors: int = 0,
) -> Path:
    path.write_text(
        json.dumps({
            'source': 'codex-exec-jsonl',
            'usage': {
                'input_tokens': input_tokens,
                'cached_input_tokens': 0,
                'output_tokens': output_tokens,
                'reasoning_output_tokens': 0,
            },
            'events': {'turn_completed': turns, 'errors': errors},
            'private_prompt': 'DO_NOT_PRINT_THIS',
        })
    )
    return path


@pytest.mark.unit
def test_compare_is_numeric_and_never_claims_quota_savings(tmp_path: Path) -> None:
    before = load(report(tmp_path / 'before.json'))
    after = load(report(tmp_path / 'after.json', input_tokens=70, output_tokens=10))
    assert before is not None
    assert after is not None
    output = compare(before, after)
    assert output['relative_change_percent'] == -33.33
    assert output['quota_savings_verified'] is False
    assert output['effective_child_models_verified'] is False
    assert output['matched_workload_verified'] is False
    assert 'DO_NOT_PRINT_THIS' not in str(output)
    assert str(tmp_path) not in str(output)


@pytest.mark.unit
def test_zero_baseline_cannot_report_percentage(tmp_path: Path) -> None:
    before = load(report(tmp_path / 'before.json', input_tokens=0, output_tokens=0))
    after = load(report(tmp_path / 'after.json'))
    assert before is not None
    assert after is not None
    assert compare(before, after)['relative_change_percent'] is None


@pytest.mark.unit
@pytest.mark.parametrize(('turns', 'errors'), [(0, 0), (1, 1)])
def test_failed_or_unfinished_stream_is_rejected(tmp_path: Path, turns: int, errors: int) -> None:
    assert load(report(tmp_path / 'bad.json', turns=turns, errors=errors)) is None


@pytest.mark.unit
def test_invalid_source_and_usage_are_rejected(tmp_path: Path) -> None:
    target = report(tmp_path / 'bad.json')
    data = json.loads(target.read_text())
    data['source'] = 'untrusted-export'
    target.write_text(json.dumps(data))
    assert load(target) is None

    data['source'] = 'codex-exec-jsonl'
    data['usage']['input_tokens'] = True
    target.write_text(json.dumps(data))
    assert load(target) is None

    data['usage']['input_tokens'] = 10
    data['usage']['cached_input_tokens'] = 50
    target.write_text(json.dumps(data))
    assert load(target) is None


@pytest.mark.unit
def test_oversized_and_secret_non_numeric_data_are_rejected(tmp_path: Path) -> None:
    target = report(tmp_path / 'bad.json')
    target.write_text('X' * 65537)
    assert load(target) is None
