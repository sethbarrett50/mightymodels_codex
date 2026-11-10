"""No inference: synthetic App Server spawn item observations."""

import io
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
CLASSIFIER = SimpleNamespace(
    **runpy.run_path(str(ROOT / 'scripts/codex_app_server_dispatch_summary.py'))
)


def stream(*events: dict[str, object]) -> io.StringIO:
    return io.StringIO(''.join(json.dumps(event) + '\n' for event in events))


def spawn(status: str, receivers: list[str] | None = None) -> dict[str, object]:
    return {
        'method': 'item/completed',
        'params': {
            'item': {
                'id': 'PRIVATE_ID',
                'type': 'collabAgentToolCall',
                'tool': 'spawnAgent',
                'status': status,
                'receiverThreadIds': receivers or [],
                'prompt': 'PRIVATE_PROMPT',
            }
        },
    }


def child() -> dict[str, object]:
    return {
        'method': 'thread/started',
        'params': {
            'thread': {
                'id': 'PRIVATE_CHILD',
                'parentThreadId': 'PRIVATE_PARENT',
                'agentRole': 'mm-triage-code-scout',
                'preview': 'PRIVATE_PREVIEW',
            }
        },
    }


@pytest.mark.unit
def test_no_events_does_not_claim_no_attempt() -> None:
    report = CLASSIFIER.summarize(stream())
    assert report['dispatch_classification'] == 'spawn_attempt_not_observed'
    assert report['observed_spawn_calls'] == 0


@pytest.mark.unit
def test_failed_call_not_called_security_denial() -> None:
    report = CLASSIFIER.summarize(stream(spawn('failed')))
    assert report['dispatch_classification'] == 'spawn_failed_or_denied'
    assert report['observed_spawn_statuses'] == {'failed': 1}


@pytest.mark.unit
def test_receiver_id_without_child_is_not_child_observed() -> None:
    report = CLASSIFIER.summarize(stream(spawn('completed', ['PRIVATE_CHILD'])))
    assert report['dispatch_classification'] == 'spawn_returned_child_id_but_thread_unobserved'
    assert report['observed_children'] == 0


@pytest.mark.unit
def test_completed_without_receiver_is_unknown() -> None:
    report = CLASSIFIER.summarize(stream(spawn('completed')))
    assert report['dispatch_classification'] == 'spawn_outcome_unknown'


@pytest.mark.unit
def test_child_thread_overrides_missing_item() -> None:
    report = CLASSIFIER.summarize(stream(child()))
    assert report['dispatch_classification'] == 'child_observed'
    assert report['observed_children'] == 1


@pytest.mark.unit
def test_duplicate_call_item_is_deduplicated_and_private() -> None:
    first = spawn('inProgress')
    first['method'] = 'item/started'
    report = CLASSIFIER.summarize(stream(first, spawn('completed', ['PRIVATE_CHILD'])))
    assert report['observed_spawn_calls'] == 1
    assert report['observed_spawn_statuses'] == {'completed': 1}
    assert 'PRIVATE' not in json.dumps(report)


@pytest.mark.unit
def test_non_spawn_items_are_ignored() -> None:
    event: dict[str, object] = {
        'method': 'item/completed',
        'params': {
            'item': {
                'type': 'collabAgentToolCall',
                'id': 'PRIVATE',
                'tool': 'wait',
                'status': 'failed',
            }
        },
    }
    report = CLASSIFIER.summarize(stream(event))
    assert report['dispatch_classification'] == 'spawn_attempt_not_observed'


def activity(
    kind: str = 'started',
    model: object = 'PRIVATE_RESOLVED_MODEL',
    effort: object = 'high',
) -> dict[str, object]:
    return {
        'method': 'item/completed',
        'params': {
            'item': {
                'type': 'subAgentActivity',
                'agentThreadId': 'PRIVATE_CHILD',
                'kind': kind,
                'model': model,
                'reasoningEffort': effort,
                'agentPath': 'PRIVATE_PATH',
            },
        },
    }


@pytest.mark.unit
def test_resolved_creation_metadata_counted_without_identity() -> None:
    report = CLASSIFIER.summarize(stream(activity(), activity(), activity('completed')))
    assert report['observed_subagent_creations'] == 1
    assert report['creations_with_resolved_model'] == 1
    assert report['creations_with_resolved_effort'] == 1
    assert report['resolved_creation_metadata_is_execution_proof'] is False
    assert report['effective_child_models_verified'] is False
    assert 'PRIVATE' not in json.dumps(report)


@pytest.mark.unit
def test_missing_creation_metadata_is_not_treated_as_verified() -> None:
    report = CLASSIFIER.summarize(stream(activity(model=None, effort=None)))
    assert report['observed_subagent_creations'] == 1
    assert report['creations_with_resolved_model'] == 0
    assert report['creations_with_resolved_effort'] == 0


@pytest.mark.unit
def test_noncreation_activity_does_not_invent_creation() -> None:
    report = CLASSIFIER.summarize(stream(activity('completed')))
    assert report['observed_subagent_creations'] == 0
    assert report['creations_with_resolved_model'] == 0
