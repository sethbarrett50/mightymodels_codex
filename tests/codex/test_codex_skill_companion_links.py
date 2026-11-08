"""Codex skill generation keeps helper/reference directory links stable."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sync_companions = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))[
    'sync_open_ticket_companions'
]


def prepare_sources(root: Path) -> None:
    for name in ('assets', 'references', 'scripts'):
        (root / 'skills/open-ticket' / name).mkdir(parents=True)


@pytest.mark.unit
def test_companion_check_is_read_only_and_repair_creates_links(tmp_path: Path) -> None:
    prepare_sources(tmp_path)
    expected = {
        f'.codex/skills/open-ticket/{name}'
        for name in ('assets', 'references', 'scripts')
    }
    assert set(sync_companions(tmp_path, check=True)) == expected
    assert not (tmp_path / '.codex').exists()
    assert sync_companions(tmp_path, check=False) == []
    assert sync_companions(tmp_path, check=True) == []
    for name in ('assets', 'references', 'scripts'):
        link = tmp_path / '.codex/skills/open-ticket' / name
        assert link.is_symlink()
        assert link.resolve() == (tmp_path / 'skills/open-ticket' / name).resolve()


@pytest.mark.unit
def test_companion_check_catches_wrong_target_and_refuses_overwrite(tmp_path: Path) -> None:
    prepare_sources(tmp_path)
    sync_companions(tmp_path, check=False)
    target = tmp_path / '.codex/skills/open-ticket/references'
    target.unlink()
    target.symlink_to(tmp_path / 'unmanaged', target_is_directory=True)
    assert sync_companions(tmp_path, check=True) == ['.codex/skills/open-ticket/references']
    with pytest.raises(ValueError, match='Refusing unmanaged'):
        sync_companions(tmp_path, check=False)
    assert target.is_symlink()
    assert target.readlink() == tmp_path / 'unmanaged'


@pytest.mark.unit
def test_missing_canonical_companion_is_not_silently_accepted(tmp_path: Path) -> None:
    prepare_sources(tmp_path)
    (tmp_path / 'skills/open-ticket/scripts').rmdir()
    with pytest.raises(ValueError, match='Missing source skill companion'):
        sync_companions(tmp_path, check=True)
