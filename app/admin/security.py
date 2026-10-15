from __future__ import annotations

import hashlib
import secrets
import time

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.admin.storage import transaction

COOKIE = "pickaflick_admin"
IDLE_SECONDS = 30 * 60
MAX_SECONDS = 12 * 60 * 60
LOGIN_SECONDS = 10 * 60
WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 5
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)


class AdminError(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


def password_hash(password: str) -> str:
    if not 15 <= len(password) <= 128:
        raise AdminError("Gebruik een wachtwoord van 15 tot en met 128 tekens.")
    return HASHER.hash(password)


def verify(encoded: str, password: str) -> bool:
    if len(password) > 128:
        return False
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _session(db, token, now, authenticated=False, csrf=None):
    row = db.execute(
        "SELECT s.*, a.version AS current_version FROM admin_sessions s "
        "JOIN admin_state a ON a.id=1 WHERE token_hash=?", (digest(token),)
    ).fetchone()
    if row is None:
        raise AdminError("Log opnieuw in.", 401)
    lifetime = MAX_SECONDS if row["authenticated"] else LOGIN_SECONDS
    if (
        row["version"] != row["current_version"]
        or now - row["created"] >= lifetime
        or now - row["last_seen"] >= IDLE_SECONDS
        or (authenticated and not row["authenticated"])
    ):
        raise AdminError("Log opnieuw in.", 401)
    if csrf is not None and (
        len(csrf) != 43 or not secrets.compare_digest(row["csrf"].encode(), csrf.encode())
    ):
        raise AdminError("Ongeldig formulier. Laad de pagina opnieuw.", 403)
    db.execute("UPDATE admin_sessions SET last_seen=? WHERE token_hash=?",
               (now, digest(token)))
    return dict(row)


def _new_session(db, now, version, authenticated):
    db.execute(
        "DELETE FROM admin_sessions WHERE created<=? OR last_seen<=? "
        "OR (authenticated=0 AND created<=?)",
        (now - MAX_SECONDS, now - IDLE_SECONDS, now - LOGIN_SECONDS),
    )
    # Bound storage even when someone repeatedly opens the login form.
    limit = 20 if authenticated else 100
    db.execute(
        "DELETE FROM admin_sessions WHERE token_hash IN "
        "(SELECT token_hash FROM admin_sessions WHERE authenticated=? "
        "ORDER BY created DESC LIMIT -1 OFFSET ?)",
        (int(authenticated), limit - 1),
    )
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO admin_sessions VALUES (?, ?, ?, ?, ?, ?)",
        (digest(token), csrf, now, now, version, int(authenticated)),
    )
    return token, csrf


def login_form(token):
    now = time.time()
    with transaction() as db:
        state = db.execute("SELECT * FROM admin_state WHERE id=1").fetchone()
        if not state["password_hash"]:
            raise AdminError(
                "Beheer is nog niet ingericht. Voer op de server het beheercommando uit.", 503
            )
        try:
            row = _session(db, token, now)
            return token, row["csrf"], bool(row["authenticated"])
        except AdminError:
            token, csrf = _new_session(db, now, state["version"], False)
            return token, csrf, False


def _attempt(db, now):
    state = dict(db.execute("SELECT * FROM admin_state WHERE id=1").fetchone())
    if state["blocked_until"] > now:
        raise AdminError("Te veel pogingen. Probeer het over 15 minuten opnieuw.", 429)
    if now - state["window_start"] >= WINDOW_SECONDS:
        state["attempts"] = 0
        state["window_start"] = now
    attempts = state["attempts"] + 1
    blocked = now + WINDOW_SECONDS if attempts >= MAX_ATTEMPTS else 0
    db.execute(
        "UPDATE admin_state SET attempts=?, window_start=?, blocked_until=? WHERE id=1",
        (attempts, state["window_start"], blocked),
    )
    return state


def authenticate(token, csrf, password):
    now = time.time()
    error = None
    result = None
    with transaction() as db:
        _session(db, token, now, csrf=csrf)
        state = _attempt(db, now)
        # Failed attempts must commit, so raise after leaving the transaction.
        if not state["password_hash"] or not verify(state["password_hash"], password):
            error = AdminError("Onjuist wachtwoord.", 401)
        else:
            db.execute("DELETE FROM admin_sessions WHERE token_hash=?", (digest(token),))
            db.execute(
                "UPDATE admin_state SET attempts=0, blocked_until=0, window_start=0 WHERE id=1"
            )
            result = _new_session(db, now, state["version"], True)
    if error:
        raise error
    return result


def current_session(token):
    with transaction() as db:
        return _session(db, token, time.time(), authenticated=True)


def logout(token, csrf):
    with transaction() as db:
        _session(db, token, time.time(), authenticated=True, csrf=csrf)
        db.execute("DELETE FROM admin_sessions WHERE token_hash=?", (digest(token),))


def change_password(token, csrf, old_password, new_password, confirmation):
    now = time.time()
    error = None
    with transaction() as db:
        _session(db, token, now, authenticated=True, csrf=csrf)
        state = _attempt(db, now)
        if not verify(state["password_hash"], old_password):
            error = AdminError("Onjuist huidig wachtwoord.", 400)
        elif new_password != confirmation:
            error = AdminError("De nieuwe wachtwoorden verschillen.")
        else:
            encoded = password_hash(new_password)
            db.execute(
                "UPDATE admin_state SET password_hash=?, version=version+1, attempts=0, "
                "window_start=0, blocked_until=0 WHERE id=1", (encoded,)
            )
            db.execute("DELETE FROM admin_sessions")
    if error:
        raise error


def set_password(password, *, reset=False):
    encoded = password_hash(password)
    with transaction() as db:
        state = db.execute("SELECT password_hash FROM admin_state WHERE id=1").fetchone()
        if state["password_hash"] and not reset:
            raise AdminError("Beheer bestaat al. Gebruik reset-password voor herstel.")
        if not state["password_hash"] and reset:
            raise AdminError("Beheer bestaat nog niet. Gebruik set-password.")
        db.execute(
            "UPDATE admin_state SET password_hash=?, version=version+1, attempts=0, "
            "window_start=0, blocked_until=0 WHERE id=1", (encoded,)
        )
        db.execute("DELETE FROM admin_sessions")
