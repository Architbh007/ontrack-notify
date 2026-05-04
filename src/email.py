import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import pytz

TZ = pytz.timezone("Australia/Melbourne")

PRIORITY_ORDER = {"HD": 0, "D": 1, "C": 2, "P": 3}
PRIORITY_LABEL = {0: "🔴 HD Tasks", 1: "🔴 D Tasks", 2: "🟡 Credit Tasks", 3: "🟢 Pass Tasks"}
PRIORITY_COLOR = {0: "#c0392b", 1: "#c0392b", 2: "#e67e22", 3: "#27ae60"}

SUBMITTED_STATUSES = {"ready_for_feedback"}
FEEDBACK_STATUSES  = {"discuss", "do_not_resubmit", "redo", "fix_and_resubmit", "complete", "fail"}

STATUS_EMOJI = {
    "not_started":        "⬜ Not Started",
    "working_on_it":      "🔵 Working On It",
    "need_help":          "🆘 Need Help",
    "ready_for_feedback": "📤 Ready for Feedback",
    "discuss":            "💬 Discuss",
    "do_not_resubmit":   "🚫 Do Not Resubmit",
    "redo":               "🔁 Redo",
    "fix_and_resubmit":  "🔧 Fix & Resubmit",
    "complete":           "✅ Complete",
    "fail":               "❌ Fail",
}

BASE_STYLE = """
    font-family: Arial, sans-serif;
    max-width: 700px;
    margin: auto;
    color: #222;
"""

HEADER_STYLE = """
    background: #2c3e50;
    color: white;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 4px;
"""

TABLE_STYLE = "width:100%; cellpadding:8; cellspacing:0; border-collapse:collapse; font-size:13px;"


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _days_badge(days_left: int | None) -> str:
    if days_left is None:
        return "<span style='color:#aaa;'>No date</span>"
    elif days_left < 0:
        return f"<span style='color:#c0392b;font-weight:bold;'>OVERDUE {abs(days_left)}d</span>"
    elif days_left == 0:
        return "<span style='color:#c0392b;font-weight:bold;'>Due TODAY ⚠️</span>"
    elif days_left <= 3:
        return f"<span style='color:#c0392b;font-weight:bold;'>{days_left}d ⚠️</span>"
    elif days_left <= 7:
        return f"<span style='color:#e67e22;font-weight:bold;'>{days_left}d</span>"
    else:
        return f"<span style='color:#27ae60;'>{days_left}d</span>"


def _wrap_html(body: str) -> str:
    return f"<html><body style='{BASE_STYLE}'>{body}</body></html>"


def _table_row(cells: list[str], bg: str) -> str:
    tds = "".join(f"<td>{c}</td>" for c in cells)
    return f"<tr style='background:{bg};'>{tds}</tr>"


def _send(subject: str, html_body: str) -> None:
    sender   = os.environ["GMAIL_SENDER"]
    password = os.environ["GMAIL_PASSWORD"]
    receiver = os.environ["GMAIL_RECEIVER"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print(f"[EMAIL SENT] {subject}")


# ─────────────────────────────────────────────
#  MORNING DIGEST
# ─────────────────────────────────────────────
def send_morning_digest(tasks: dict) -> None:
    today_str  = datetime.now(TZ).strftime("%A, %d %B %Y")
    incomplete = [t for t in tasks.values() if t["status"] != "complete"]

    incomplete.sort(key=lambda t: (
        PRIORITY_ORDER.get(t["grade"], 3),
        t["days_left"] if t["days_left"] is not None else 9999
    ))

    buckets: dict[int, list] = {}
    for t in incomplete:
        p = PRIORITY_ORDER.get(t["grade"], 3)
        buckets.setdefault(p, []).append(t)

    body = f"""
<h2 style='{HEADER_STYLE}'>☀️ Good Morning! OnTrack Daily Digest</h2>
<p style='color:#777;margin-top:4px;'>{today_str}</p>
"""

    for p in sorted(buckets.keys()):
        group = buckets[p]
        color = PRIORITY_COLOR[p]
        label = PRIORITY_LABEL[p]

        body += f"""
<h3 style='color:{color};border-bottom:2px solid {color};padding-bottom:4px;'>{label}</h3>
<table width='100%' cellpadding='8' cellspacing='0' style='border-collapse:collapse;font-size:13px;'>
<tr style='background:#f5f5f5;font-weight:bold;'>
  <td>Unit</td><td>Task</td><td>Status</td><td>Due</td><td>Days Left</td>
</tr>"""

        for i, t in enumerate(group):
            bg      = "#fafafa" if i % 2 == 0 else "#ffffff"
            due_str = datetime.fromisoformat(t["due_date"]).strftime("%d %b %Y") if t["due_date"] else "—"
            body += _table_row([
                f"<b>{t['unit']}</b>",
                f"<b>{t['abbrev']}</b><br><span style='color:#666;font-size:11px;'>{t['task_name']}</span>",
                STATUS_EMOJI.get(t["status"], t["status"]),
                due_str,
                _days_badge(t["days_left"]),
            ], bg)

        body += "</table><br>"

    body += f"""
<p style='color:#aaa;font-size:11px;border-top:1px solid #eee;padding-top:8px;'>
  {len(incomplete)} incomplete tasks · Completed tasks hidden
</p>"""

    _send(
        f"☀️ OnTrack Morning Digest — {datetime.now(TZ).strftime('%d %b %Y')}",
        _wrap_html(body)
    )


# ─────────────────────────────────────────────
#  EVENT EMAIL (submission / feedback)
# ─────────────────────────────────────────────
def send_event_email(events: list[dict]) -> None:
    now_str   = datetime.now(TZ).strftime("%d %b %Y, %I:%M %p")
    submitted = [e for e in events if e["event"] == "submitted"]
    feedback  = [e for e in events if e["event"] == "feedback"]

    parts = []
    if feedback:
        parts.append(f"💬 {len(feedback)} feedback received")
    if submitted:
        parts.append(f"📤 {len(submitted)} task(s) submitted")
    subject = " · ".join(parts) + f" — {datetime.now(TZ).strftime('%d %b')}"

    body = f"""
<h2 style='{HEADER_STYLE}'>🔔 OnTrack Update</h2>
<p style='color:#777;'>{now_str}</p>
"""

    if feedback:
        body += """
<h3 style='color:#8e44ad;border-bottom:2px solid #8e44ad;padding-bottom:4px;'>💬 Tutor Feedback Received</h3>
<table width='100%' cellpadding='8' cellspacing='0' style='border-collapse:collapse;font-size:13px;'>
<tr style='background:#f0e6ff;font-weight:bold;'>
  <td>Unit</td><td>Task</td><td>Grade</td><td>Was</td><td>Now</td>
</tr>"""
        for i, e in enumerate(feedback):
            bg = "#faf5ff" if i % 2 == 0 else "#ffffff"
            body += _table_row([
                f"<b>{e['unit']}</b>",
                f"<b>{e['abbrev']}</b><br><span style='color:#666;font-size:11px;'>{e['task_name']}</span>",
                f"<span style='font-weight:bold;color:#8e44ad;'>{e['grade']}</span>",
                STATUS_EMOJI.get(e["old_status"], e["old_status"]),
                STATUS_EMOJI.get(e["new_status"], e["new_status"]),
            ], bg)
        body += "</table><br>"

    if submitted:
        body += """
<h3 style='color:#2980b9;border-bottom:2px solid #2980b9;padding-bottom:4px;'>📤 Tasks Submitted</h3>
<table width='100%' cellpadding='8' cellspacing='0' style='border-collapse:collapse;font-size:13px;'>
<tr style='background:#e8f4fd;font-weight:bold;'>
  <td>Unit</td><td>Task</td><td>Grade</td><td>Status</td>
</tr>"""
        for i, e in enumerate(submitted):
            bg = "#f0f8ff" if i % 2 == 0 else "#ffffff"
            body += _table_row([
                f"<b>{e['unit']}</b>",
                f"<b>{e['abbrev']}</b><br><span style='color:#666;font-size:11px;'>{e['task_name']}</span>",
                f"<span style='font-weight:bold;color:#2980b9;'>{e['grade']}</span>",
                STATUS_EMOJI.get(e["new_status"], e["new_status"]),
            ], bg)
        body += "</table><br>"

    body += """
<p style='color:#aaa;font-size:11px;border-top:1px solid #eee;padding-top:8px;'>
  Detected by your OnTrack Notifier on Railway
</p>"""

    _send(subject, _wrap_html(body))