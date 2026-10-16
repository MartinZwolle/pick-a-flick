"""UTC appointments, local calendar reminders and transactional outbox.

SQLite BEGIN IMMEDIATE serializes web changes and delivery across processes.
Telegram has no idempotency key: ambiguous network failures are terminal (unknown),
never retried automatically. A crash after claiming is also deliberately at-most-once.
"""
import logging
import os
import re
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.admin.security import AdminError
from app.admin.storage import transaction


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise AdminError("Gebruik een geldige IANA-tijdzone, bijvoorbeeld Europe/Amsterdam.") from None


def local_instant(day, clock, name):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not re.fullmatch(r"\d{2}:\d{2}", clock):
            raise ValueError
        wall = datetime.fromisoformat(f"{day}T{clock}")
    except ValueError:
        raise AdminError("Vul een datum en een handmatig gekozen begintijd in.") from None
    tz = zone(name)
    candidates = set()
    for fold in (0, 1):
        aware = wall.replace(tzinfo=tz, fold=fold)
        utc = aware.astimezone(UTC)
        if utc.astimezone(tz).replace(tzinfo=None) == wall:
            candidates.add(utc.timestamp())
    if len(candidates) != 1:
        raise AdminError("Deze tijd bestaat niet of komt tweemaal voor door de klokwisseling. Kies een andere tijd.")
    return candidates.pop()


def cipher():
    try:
        return Fernet(os.environ["PICKAFLICK_SECRET_KEY"].encode())
    except (KeyError, ValueError):
        raise AdminError("Stel eerst een geldige PICKAFLICK_SECRET_KEY in op de server.") from None


def settings(db):
    return dict(db.execute("SELECT * FROM planning_settings WHERE id=1").fetchone())


def token_value(config):
    try:
        return cipher().decrypt(config["token"].encode()).decode()
    except (InvalidToken, UnicodeError):
        raise AdminError("Telegram-geheim kan niet worden ontsleuteld. Controleer de serversleutel.") from None


def readable(stamp, name):
    return datetime.fromtimestamp(stamp, zone(name)).strftime("%d-%m-%Y %H:%M %Z")


def enqueue(db, appointment, config, kind, due, message, now, immediate=False):
    if not config["enabled"] or due < now:
        return
    # Reminders tolerate a polling delay, but are never replayed hours after downtime.
    expires = due + (86400 if immediate else 60)
    db.execute(
        "INSERT OR IGNORE INTO notifications "
        "(night_id,revision,kind,due_at,expires_at,message) VALUES(?,?,?,?,?,?)",
        (appointment["night_id"], appointment["revision"], kind, due, expires, message),
    )


def reminders(db, appointment, config, title, now):
    stamp = appointment["starts_at"]
    local = datetime.fromtimestamp(stamp, zone(config["timezone"]))
    day = local.date()
    moments = [
        ("day", local_instant(day.isoformat(), "10:00", config["timezone"]), "Vandaag filmavond"),
        ("hour", stamp - 3600, "Over één uur filmavond"),
        ("rating", local_instant((day + timedelta(days=1)).isoformat(), "10:00", config["timezone"]),
         "Hoe was de film? Geef je beoordeling"),
    ]
    for kind, due, label in moments:
        link = f"{config['base_url']}/filmavond/{appointment['night_id']}"
        if kind == "rating":
            link += "/feedback"
        enqueue(db, appointment, config, kind, due, f"{label}: {title}\n{link}", now)


def schedule(night_id, day, clock, revision, cancel=False, now=None):
    now = time.time() if now is None else now
    with transaction() as db:
        config = settings(db)
        night = db.execute(
            "SELECT n.*, m.title FROM movie_nights n LEFT JOIN movies m "
            "ON m.id=n.selected_movie_id WHERE n.id=?", (night_id,),
        ).fetchone()
        if not night or not night["selected_movie_id"]:
            raise AdminError("Plan eerst een spel met een gekozen winnaar.", 404)
        old = db.execute("SELECT * FROM appointments WHERE night_id=?", (night_id,)).fetchone()
        if int(revision) != (old["revision"] if old else 0):
            raise AdminError("De afspraak is intussen gewijzigd. Laad de pagina opnieuw.", 409)
        if cancel and (not old or old["cancelled"]):
            raise AdminError("Er is geen actieve afspraak om te annuleren.")
        stamp = old["starts_at"] if cancel else local_instant(day, clock, config["timezone"])
        if stamp <= now:
            raise AdminError("Kies een tijdstip in de toekomst. Afgelopen afspraken blijven in de historie.")
        new = {"night_id": night_id, "starts_at": stamp, "revision": int(revision) + 1}
        db.execute(
            "INSERT INTO appointments(night_id,starts_at,cancelled,revision) VALUES(?,?,?,?) "
            "ON CONFLICT(night_id) DO UPDATE SET starts_at=excluded.starts_at, "
            "cancelled=excluded.cancelled, revision=excluded.revision",
            (night_id, stamp, int(cancel), new["revision"]),
        )
        db.execute("UPDATE notifications SET state='superseded' WHERE night_id=? AND state='pending'", (night_id,))
        verb = "Geannuleerd" if cancel else ("Verplaatst" if old else "Gepland")
        message = f"{verb}: {night['title']} — {readable(stamp, config['timezone'])}"
        if old and not cancel:
            message += f" (was {readable(old['starts_at'], config['timezone'])})"
        message += f"\n{config['base_url']}/filmavond/{night_id}"
        enqueue(db, new, config, "change", now, message, now, immediate=True)
        if not cancel:
            reminders(db, new, config, night["title"], now)


def snapshot(night_id=None):
    with transaction() as db:
        config = settings(db)
        rows = db.execute(
            "SELECT a.*, m.title FROM appointments a JOIN movie_nights n ON n.id=a.night_id "
            "JOIN movies m ON m.id=n.selected_movie_id "
            + ("WHERE a.night_id=? " if night_id is not None else "")
            + "ORDER BY a.starts_at", (() if night_id is None else (night_id,)),
        ).fetchall()
    result = []
    now = time.time()
    for row in rows:
        item = dict(row)
        local = datetime.fromtimestamp(item["starts_at"], zone(config["timezone"]))
        item.update(label=readable(item["starts_at"], config["timezone"]),
                    day=local.strftime("%Y-%m-%d"), clock=local.strftime("%H:%M"),
                    history=bool(item["cancelled"] or item["starts_at"] <= now))
        result.append(item)
    return config, result


def save_config(db, form):
    old = settings(db)
    if str(old["revision"]) != form.get("planning_revision"):
        raise AdminError("Instellingen zijn intussen gewijzigd. Laad de pagina opnieuw.", 409)
    name = form.get("timezone", "")
    zone(name)
    enabled = form.get("telegram_enabled") == "on"
    chat = form.get("chat_id", "").strip()
    base = form.get("base_url", "").strip().rstrip("/")
    if len(name) > 100 or len(chat) > 21 or len(base) > 500:
        raise AdminError("Een instelling is te lang.")
    try:
        parts = urlsplit(base)
        _ = parts.port  # Validate malformed ports before persisting a public URL.
    except ValueError:
        raise AdminError("Gebruik een geldig publiek websiteadres.") from None
    if base and (parts.scheme not in {"http", "https"} or not parts.hostname
                 or parts.username or parts.password or parts.query or parts.fragment or parts.path):
        raise AdminError("Gebruik het publieke HTTP(S)-adres zonder pad of toegangsgegevens.")
    encrypted = old["token"]
    raw = form.get("bot_token", "").strip()
    if raw:
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,100}", raw):
            raise AdminError("Ongeldig Telegram-bot-token.")
        encrypted = cipher().encrypt(raw.encode()).decode()
    if form.get("clear_token") == "on":
        encrypted = ""
    if enabled:
        if not encrypted or not re.fullmatch(r"-?\d{1,20}", chat) or not base:
            raise AdminError("Voor Telegram zijn een bot-token, numeriek chat-ID en publiek adres nodig.")
        token_value({"token": encrypted})
    db.execute(
        "UPDATE planning_settings SET timezone=?,enabled=?,token=?,chat_id=?,base_url=?,revision=revision+1 WHERE id=1",
        (name, int(enabled), encrypted, chat, base),
    )
    config = settings(db)
    # Settings changes never replay prior notifications; keep appointment instants.
    db.execute("UPDATE notifications SET state='superseded' WHERE state='pending'")
    rows = db.execute(
        "SELECT a.*,m.title FROM appointments a JOIN movie_nights n ON n.id=a.night_id "
        "JOIN movies m ON m.id=n.selected_movie_id WHERE a.cancelled=0",
    ).fetchall()
    now = time.time()
    for row in rows:
        # A new revision allows rebuilt reminders without reusing sent idempotency keys.
        db.execute("UPDATE appointments SET revision=revision+1 WHERE night_id=?", (row["night_id"],))
        item = dict(row)
        item["revision"] += 1
        reminders(db, item, config, row["title"], now)


def send(config, message):
    # Never propagate HTTP exceptions/responses containing the token-bearing URL.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                f"https://api.telegram.org/bot{token_value(config)}/sendMessage",
                json={"chat_id": config["chat_id"], "text": message[:4000],
                      "link_preview_options": {"is_disabled": True}},
            )
        payload = response.json() if response.status_code == 200 else {}
        return "sent" if isinstance(payload, dict) and payload.get("ok") else "failed"
    except (httpx.HTTPError, ValueError, AdminError):
        return "unknown"


def deliver_one(now=None, sender=send):
    now = time.time() if now is None else now
    # Keep lock during bounded network request: cancellation cannot race a stale send.
    with transaction() as db:
        db.execute("UPDATE notifications SET state='skipped' WHERE state='pending' AND expires_at<?", (now,))
        row = db.execute(
            "SELECT * FROM notifications WHERE state='pending' AND due_at<=? ORDER BY due_at,id LIMIT 1", (now,),
        ).fetchone()
        if not row:
            return False
        db.execute("UPDATE notifications SET state='claimed' WHERE id=?", (row["id"],))
    # Persist claim before external side effect, then recheck under serialization lock.
    with transaction() as db:
        current = db.execute("SELECT * FROM appointments WHERE night_id=?", (row["night_id"],)).fetchone()
        config = settings(db)
        if not config["enabled"] or not current or current["revision"] != row["revision"]:
            state = "superseded"
        else:
            state = sender(config, row["message"])
        db.execute("UPDATE notifications SET state=? WHERE id=?", (state, row["id"]))
    return True
