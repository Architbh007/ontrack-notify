import os
import requests
from datetime import datetime, timezone

BASE_URL = "https://ontrack.deakin.edu.au/api"

GRADE_MAP = {0: "P", 1: "C", 2: "D", 3: "HD"}

UNITS = [
    {"name": "SIT199", "project_id": 160857},
    {"name": "SIT310", "project_id": 157493},
    {"name": "SIT333", "project_id": 153185},
    {"name": "SIT374", "project_id": 158423},
]


def _headers() -> dict:
    return {
        "Auth-Token": os.environ["ONTRACK_AUTH_TOKEN"],
        "Username":   os.environ["ONTRACK_USERNAME"],
        "Accept":     "application/json",
    }


def _fetch_project(project_id: int) -> dict:
    url = f"{BASE_URL}/projects/{project_id}"
    r = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _days_until(dt: datetime | None) -> int | None:
    if not dt:
        return None
    return (dt - datetime.now(timezone.utc)).days


def get_all_tasks() -> dict:
    """
    Fetch all tasks across all units.

    Returns a dict keyed by 'UNIT::abbrev':
    {
        "SIT310::2.1P": {
            "unit":      "SIT310",
            "abbrev":    "2.1P",
            "task_name": "Open Loop Square",
            "grade":     "HD",
            "status":    "complete",
            "due_date":  "2025-04-01T00:00:00+00:00",
            "days_left": 12,
        },
        ...
    }
    """
    result = {}

    for unit in UNITS:
        try:
            project = _fetch_project(unit["project_id"])
        except Exception as e:
            print(f"[ERROR] Failed to fetch {unit['name']}: {e}")
            continue

        task_defs     = {td["id"]: td for td in project.get("task_definitions", [])}
        task_statuses = {t["task_definition_id"]: t for t in project.get("tasks", [])}

        for td_id, td in task_defs.items():
            status_info  = task_statuses.get(td_id, {})
            status       = status_info.get("status", "not_started")
            abbrev       = td.get("abbreviation", str(td_id))
            target_grade = td.get("target_grade", 0)

            if isinstance(target_grade, int):
                target_grade = GRADE_MAP.get(target_grade, "P")

            due_date  = _parse_date(td.get("due_date") or td.get("target_date"))
            days_left = _days_until(due_date)

            key = f"{unit['name']}::{abbrev}"
            result[key] = {
                "unit":      unit["name"],
                "abbrev":    abbrev,
                "task_name": td.get("name", abbrev),
                "grade":     target_grade,
                "status":    status,
                "due_date":  due_date.isoformat() if due_date else None,
                "days_left": days_left,
            }

    return result