"""
Tests for OnTrack Notifier
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

# ── api.py tests ──────────────────────────────

def test_days_until_future():
    from src.api import _days_until
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    assert _days_until(future) > 0

def test_days_until_past():
    from src.api import _days_until
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    assert _days_until(past) < 0

def test_days_until_none():
    from src.api import _days_until
    assert _days_until(None) is None

def test_parse_date_valid():
    from src.api import _parse_date
    result = _parse_date("2025-06-01T00:00:00Z")
    assert result is not None
    assert result.year == 2025

def test_parse_date_none():
    from src.api import _parse_date
    assert _parse_date(None) is None

def test_parse_date_invalid():
    from src.api import _parse_date
    assert _parse_date("not-a-date") is None

# ── state.py tests ────────────────────────────

def test_load_state_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src import state
    result = state.load_state()
    assert result == {"task_statuses": {}, "last_digest_date": None}

def test_save_and_load_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src import state
    data = {"task_statuses": {"SIT310::2.1P": "complete"}, "last_digest_date": "2025-01-01"}
    state.save_state(data)
    loaded = state.load_state()
    assert loaded == data

# ── main.py detect_events tests ──────────────

def test_detect_no_changes():
    from main import detect_events
    tasks = {"SIT310::2.1P": {"status": "working_on_it", "unit": "SIT310", "abbrev": "2.1P",
                               "task_name": "Test", "grade": "HD", "due_date": None, "days_left": None}}
    old   = {"SIT310::2.1P": "working_on_it"}
    assert detect_events(old, tasks) == []

def test_detect_submission_event():
    from main import detect_events
    tasks = {"SIT310::2.1P": {"status": "ready_for_feedback", "unit": "SIT310", "abbrev": "2.1P",
                               "task_name": "Test", "grade": "HD", "due_date": None, "days_left": None}}
    old   = {"SIT310::2.1P": "working_on_it"}
    events = detect_events(old, tasks)
    assert len(events) == 1
    assert events[0]["event"] == "submitted"

def test_detect_feedback_event():
    from main import detect_events
    tasks = {"SIT310::2.1P": {"status": "complete", "unit": "SIT310", "abbrev": "2.1P",
                               "task_name": "Test", "grade": "HD", "due_date": None, "days_left": None}}
    old   = {"SIT310::2.1P": "ready_for_feedback"}
    events = detect_events(old, tasks)
    assert len(events) == 1
    assert events[0]["event"] == "feedback"

def test_first_run_no_events():
    """On first run, old_statuses is empty — should not fire any events."""
    from main import detect_events
    tasks = {"SIT310::2.1P": {"status": "complete", "unit": "SIT310", "abbrev": "2.1P",
                               "task_name": "Test", "grade": "HD", "due_date": None, "days_left": None}}
    assert detect_events({}, tasks) == []