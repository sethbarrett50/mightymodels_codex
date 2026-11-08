"""Post-edit checker is read-only, bounded, and scoped to this checkout."""

import ast
import subprocess
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = run_path(str(ROOT / 'scripts/codex_post_edit_check.py'))
python_paths = MODULE['python_paths']
feedback = MODULE['feedback']


def edit_event(cwd: Path, patch_text: str, response: object = None) -> dict[str, object]:
    return {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'apply_patch',
        'cwd': str(cwd),
        'tool_input': {'command': patch_text},
        'tool_response': response,
    }


def patch_for(filename: str) -> str:
    return f'*** Begin Patch\n*** Update File: {filename}\n@@\n+value = 1\n*** End Patch'


@pytest.mark.unit
def test_only_changed_local_python_files_are_selected(tmp_path: Path) -> None:
    (tmp_path / 'demo.py').write_text('value = 1')
    (tmp_path / 'README.md').write_text('ok')
    patch_text = (
        '*** Begin Patch\n*** Update File: README.md\n@@\n+ok\n'
        '*** Update File: demo.py\n@@\n+value = 1\n*** End Patch'
    )
    assert python_paths(edit_event(tmp_path, patch_text), tmp_path) == (tmp_path / 'demo.py',)


@pytest.mark.unit
def test_non_python_and_failed_edit_do_not_invoke_checkers(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('ok')
    (tmp_path / 'demo.py').write_text('value = 1')
    assert feedback(edit_event(tmp_path, patch_for('README.md')), tmp_path) is None
    assert feedback(edit_event(tmp_path, patch_for('demo.py'), {'isError': True}), tmp_path) is None


@pytest.mark.unit
def test_other_repositories_and_traversal_never_run(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'demo.py').write_text('value = 1')
    assert python_paths(edit_event(outside, patch_for('demo.py')), checkout) == ()
    assert python_paths(edit_event(checkout, patch_for('../outside/demo.py')), checkout) == ()


@pytest.mark.unit
def test_symlinked_python_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / 'source.py').write_text('value = 1')
    (tmp_path / 'link.py').symlink_to(tmp_path / 'source.py')
    assert python_paths(edit_event(tmp_path, patch_for('link.py')), tmp_path) == ()


@pytest.mark.unit
def test_missing_ruff_is_explicit_not_false_success(tmp_path: Path) -> None:
    (tmp_path / 'demo.py').write_text('value = 1')
    result = feedback(edit_event(tmp_path, patch_for('demo.py')), tmp_path)
    assert result is not None
    assert 'not run' in result['hookSpecificOutput']['additionalContext']
    assert 'make check' in result['hookSpecificOutput']['additionalContext']


@pytest.mark.unit
def test_successful_checks_do_not_emit_fake_diagnostics(tmp_path: Path) -> None:
    (tmp_path / 'demo.py').write_text('value = 1')
    binary = tmp_path / '.venv/bin/ruff'
    binary.parent.mkdir(parents=True)
    binary.touch()
    (binary.parent / 'ty').touch()
    outcome = subprocess.CompletedProcess(args=['ruff'], returncode=0, stdout='', stderr='')
    with patch.object(subprocess, 'run', return_value=outcome) as execute:
        assert feedback(edit_event(tmp_path, patch_for('demo.py')), tmp_path) is None
    assert execute.call_count == 3
    assert all(call.kwargs['cwd'] == tmp_path for call in execute.call_args_list)
    assert all(call.kwargs['timeout'] == 8 for call in execute.call_args_list)
    assert all(
        '--no-fix' in call.args[0]
        or '--check' in call.args[0]
        or ('ty' in call.args[0][0] and 'check' in call.args[0])
        for call in execute.call_args_list
    )


@pytest.mark.unit
def test_failed_check_hides_tool_output_and_recommends_manual_check(tmp_path: Path) -> None:
    (tmp_path / 'demo.py').write_text('value = 1')
    binary = tmp_path / '.venv/bin/ruff'
    binary.parent.mkdir(parents=True)
    binary.touch()
    outcome = subprocess.CompletedProcess(
        args=['ruff'], returncode=1, stdout='PRIVATE SOURCE', stderr='SECRET TOKEN'
    )
    with patch.object(subprocess, 'run', return_value=outcome):
        report = feedback(edit_event(tmp_path, patch_for('demo.py')), tmp_path)
    assert report is not None
    message = report['hookSpecificOutput']['additionalContext']
    assert 'format did not pass' in message
    assert 'lint did not pass' in message
    assert 'PRIVATE' not in message
    assert 'SECRET' not in message


@pytest.mark.unit
@pytest.mark.parametrize(
    'patch_text',
    [
        '*** Begin Patch\n*** Update File: demo.py\n@@\n+new = 1',
        '*** Begin Patch\n*** Update File: /etc/demo.py\n@@\n+new = 1\n*** End Patch',
    ],
)
def test_untrusted_patch_structures_are_skipped(tmp_path: Path, patch_text: str) -> None:
    (tmp_path / 'demo.py').write_text('value = 1')
    assert python_paths(edit_event(tmp_path, patch_text), tmp_path) == ()


@pytest.mark.unit
def test_ty_failure_redacts_output_and_does_not_change_files(tmp_path: Path) -> None:
    source = tmp_path / 'demo.py'
    source.write_text('value = 1')
    original = source.read_bytes()
    binary = tmp_path / '.venv/bin/ty'
    binary.parent.mkdir(parents=True)
    binary.touch()
    outcome = subprocess.CompletedProcess(
        args=['ty'], returncode=1, stdout='PRIVATE SOURCE', stderr='SECRET TOKEN'
    )
    with patch.object(subprocess, 'run', return_value=outcome) as execute:
        report = feedback(edit_event(tmp_path, patch_for('demo.py')), tmp_path)
    assert report is not None
    message = report['hookSpecificOutput']['additionalContext']
    assert 'Ruff not run' in message
    assert 'type check did not pass' in message
    assert 'PRIVATE' not in message
    assert 'SECRET' not in message
    assert source.read_bytes() == original
    assert execute.call_count == 1
    args = execute.call_args.args[0]
    assert args == [str(binary), 'check', str(source)]
    assert execute.call_args.kwargs['cwd'] == tmp_path
    assert execute.call_args.kwargs['timeout'] == 8


@pytest.mark.unit
def test_ty_runtime_timeout_reports_unavailable(tmp_path: Path) -> None:
    (tmp_path / 'demo.py').write_text('value = 1')
    binary = tmp_path / '.venv/bin/ty'
    binary.parent.mkdir(parents=True)
    binary.touch()
    with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('ty', 8)):
        report = feedback(edit_event(tmp_path, patch_for('demo.py')), tmp_path)
    assert report is not None
    assert 'type check unavailable' in report['hookSpecificOutput']['additionalContext']


@pytest.mark.unit
def test_absolute_native_patch_file_inside_checkout_is_selected(tmp_path: Path) -> None:
    source = tmp_path / 'demo.py'
    source.write_text('value = 1')
    assert python_paths(edit_event(tmp_path, patch_for(str(source))), tmp_path) == (source,)


@pytest.mark.unit
def test_absolute_native_patch_file_outside_checkout_is_rejected(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    source = tmp_path / 'outside.py'
    source.write_text('value = 1')
    assert python_paths(edit_event(checkout, patch_for(str(source))), checkout) == ()


@pytest.mark.unit
def test_post_edit_checker_parses_with_python313_grammar() -> None:
    source = (ROOT / 'scripts/codex_post_edit_check.py').read_text()
    ast.parse(source, filename='scripts/codex_post_edit_check.py', feature_version=(3, 13))


@pytest.mark.unit
@pytest.mark.parametrize('cwd', [None, '', '   '])
def test_post_edit_missing_checkout_context_emits_sanitized_warning(
    tmp_path: Path, cwd: str | None
) -> None:
    event = edit_event(tmp_path, patch_for('demo.py'))
    event['cwd'] = cwd
    event['tool_response'] = {'status': 'completed', 'private': 'SECRET_DO_NOT_ECHO'}
    report = feedback(event, tmp_path)
    assert report is not None
    message = report['hookSpecificOutput']['additionalContext']
    assert 'not run' in message
    assert 'checkout directory' in message
    assert 'SECRET_' not in str(report)
    assert str(tmp_path) not in str(report)


@pytest.mark.unit
def test_non_patch_tool_without_checkout_does_not_report_python_checks(tmp_path: Path) -> None:
    event = {'hook_event_name': 'PostToolUse', 'tool_name': 'Read'}
    assert feedback(event, tmp_path) is None
