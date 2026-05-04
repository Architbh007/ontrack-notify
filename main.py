"""
OnTrack Notifier — Entry Point
-------------------------------
Runs a loop that:
  - 8am daily       → sends morning digest email
  - Hourly 8am–10pm → polls OnTrack, emails on any status change
"""

import time
import sys
from datetime import datetime
import pytz

from src.api import get_all_tasks, SUBMITTED_STATUSES, FEEDBACK_STATUSES
from src.email import send_morning_digest, send_event_email
from src.state import load_state, save_state

TZ = pytz.timezone("Australia/Melbourne")


def detect_events(old_statuses: dict, new_tasks: dict) -> list[dict]:
    """Compare old vs new statuses and return list of change events."""
    events = []

    for key, task in new_tasks.items():
        new_status = task["status"]
        old_status = old_statuses.get(key)

        # First run — just record, don't email
        if old_status is None:
            continue

        if new_status == old_status:
            continue

        if new_status in SUBMITTED_STATUSES and old_status not in SUBMITTED_STATUSES:
            events.append({
                **task,
                "event":      "submitted",
                "old_status": old_status,
                "new_status": new_status,
            })

        elif new_status in FEEDBACK_STATUSES and old_status not in FEEDBACK_STATUSES:
            events.append({
                **task,
                "event":      "feedback",
                "old_status": old_status,
                "new_status": new_status,
            })

    return events


def run():
    print("[START] OnTrack Notifier is running...")
    state = load_state()

    while True:
        now   = datetime.now(TZ)
        hour  = now.hour
        today = now.strftime("%Y-%m-%d")

        if 8 <= hour < 22:
            print(f"[POLL] {now.strftime('%H:%M')} — fetching tasks...")

            try:
                tasks = get_all_tasks()
            except Exception as e:
                print(f"[ERROR] Failed to fetch tasks: {e}")
                time.sleep(60 * 60)
                continue

            # ── Morning digest at 8am, once per day ──
            if hour == 8 and state.get("last_digest_date") != today:
                print("[DIGEST] Sending morning digest...")
                try:
                    send_morning_digest(tasks)
                    state["last_digest_date"] = today
                except Exception as e:
                    print(f"[ERROR] Failed to send digest: {e}")

            # ── Check for status changes ──
            events = detect_events(state.get("task_statuses", {}), tasks)

            if events:
                print(f"[EVENT] {len(events)} change(s) detected — sending email...")
                try:
                    send_event_email(events)
                except Exception as e:
                    print(f"[ERROR] Failed to send event email: {e}")

            # ── Persist state ──
            state["task_statuses"] = {k: v["status"] for k, v in tasks.items()}
            save_state(state)

        else:
            print(f"[SKIP] {now.strftime('%H:%M')} — outside 8am–10pm window.")

        print("[WAIT] Sleeping 60 minutes...\n")
        time.sleep(60 * 60)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down.")
        sys.exit(0)