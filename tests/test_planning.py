# ruff: noqa: F811 - imported shared pytest fixtures are injected by name
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet
from test_admin import client, configured, csrf, environment, login, migrated  # noqa: F401

from app.admin.security import AdminError
from app.admin.storage import transaction
from app.movie_night import planning

TOKEN = "123456:" + "a" * 30
NOW = datetime(2030, 3, 29, 12, tzinfo=UTC).timestamp()


@pytest.fixture
def seeded(environment, monkeypatch):
    monkeypatch.setenv("PICKAFLICK_SECRET_KEY", Fernet.generate_key().decode())
    # No real delivery; deterministic tests explicitly drive the durable worker.
    from app.movie_night import worker
    monkeypatch.setattr(worker, "deliver_one", lambda: False)
    with transaction() as db:
        db.execute("INSERT INTO movies(id,tmdb_id,title,adult,metadata_source) VALUES(1,1,'Testfilm',0,'tmdb')")
        db.execute("INSERT INTO movie_nights(id,status,mode,selected_movie_id) VALUES(1,'chosen','normal',1)")
        db.execute("INSERT INTO movie_nights(id,status,mode) VALUES(2,'choosing','normal')")
    return environment


def enable():
    with transaction() as db:
        planning.save_config(db, {
            "planning_revision": str(planning.settings(db)["revision"]),
            "timezone": "Europe/Amsterdam", "telegram_enabled": "on",
            "bot_token": TOKEN, "chat_id": "-123", "base_url": "https://films.example",
        })


def rows():
    with transaction() as db:
        return [dict(row) for row in db.execute("SELECT * FROM notifications ORDER BY id")]


@pytest.mark.parametrize("day,clock", [
    ("2030-03-31", "02:30"), ("2030-10-27", "02:30"),
    ("2030-02-30", "20:00"), ("2030-03-30", ""), ("", "20:00"),
])
def test_invalid_and_dst_wall_times(day, clock):
    with pytest.raises(AdminError):
        planning.local_instant(day, clock, "Europe/Amsterdam")


def test_dst_calendar_reminders_and_rating_deeplink(seeded):
    enable()
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    jobs = {r["kind"]: r for r in rows()}
    assert len(jobs) == 4
    assert jobs["day"]["due_at"] == datetime(2030, 3, 30, 9, tzinfo=UTC).timestamp()
    assert jobs["hour"]["due_at"] == datetime(2030, 3, 30, 18, tzinfo=UTC).timestamp()
    assert jobs["rating"]["due_at"] == datetime(2030, 3, 31, 8, tzinfo=UTC).timestamp()
    assert "https://films.example/filmavond/1/feedback" in jobs["rating"]["message"]


def test_optional_telegram_and_missing_winner(seeded):
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    assert rows() == []
    with pytest.raises(AdminError):
        planning.schedule(2, "2030-03-30", "20:00", 0, now=NOW)
    with pytest.raises(AdminError):
        planning.schedule(1, "2020-03-30", "20:00", 1, now=NOW)


def test_reschedule_cancel_and_optimistic_concurrency(seeded):
    enable()
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    planning.schedule(1, "2030-03-31", "21:00", 1, now=NOW)
    with pytest.raises(AdminError) as error:
        planning.schedule(1, "2030-04-01", "20:00", 1, now=NOW)
    assert error.value.status == 409
    assert all(r["state"] == "superseded" for r in rows()[:4])
    planning.schedule(1, "", "", 2, cancel=True, now=NOW)
    pending = [r for r in rows() if r["state"] == "pending"]
    assert len(pending) == 1 and "Geannuleerd" in pending[0]["message"]
    assert planning.snapshot(1)[1][0]["history"]


def test_skip_elapsed_moments_and_restart_persistence(seeded):
    enable()
    now = planning.local_instant("2030-03-30", "19:30", "Europe/Amsterdam")
    planning.schedule(1, "2030-03-30", "20:00", 0, now=now)
    assert {r["kind"] for r in rows()} == {"change", "rating"}
    sent = []
    sender = lambda config, message: sent.append(message) or "sent"
    # Each delivery opens fresh connections, as a restarted process would.
    assert planning.deliver_one(now=now, sender=sender)
    assert not planning.deliver_one(now=now, sender=sender)
    assert len(sent) == 1
    rating = next(r for r in rows() if r["kind"] == "rating")
    assert not planning.deliver_one(now=rating["due_at"] + 61, sender=sender)
    assert rows()[-1]["state"] == "skipped"


def test_two_workers_send_once(seeded):
    enable()
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    sent = []
    def deliver(_):
        return planning.deliver_one(now=NOW, sender=lambda c, m: sent.append(m) or "sent")
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(deliver, range(2)))
    assert len(sent) == 1


def test_crash_after_claim_does_not_repeat(seeded):
    enable()
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    def crash(config, message):
        raise RuntimeError("simulated process loss")
    with pytest.raises(RuntimeError):
        planning.deliver_one(now=NOW, sender=crash)
    assert rows()[0]["state"] == "claimed"
    assert not planning.deliver_one(now=NOW, sender=lambda c, m: pytest.fail("duplicate"))


def test_secrets_and_timezone_rebuild(seeded):
    enable()
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    before = planning.snapshot(1)[1][0]["starts_at"]
    with transaction() as db:
        config = planning.settings(db)
        assert TOKEN not in config["token"]
        assert planning.token_value(config) == TOKEN
        planning.save_config(db, {"planning_revision": str(config["revision"]),
                                 "timezone": "America/New_York"})
    config, items = planning.snapshot(1)
    assert not config["enabled"]
    assert items[0]["starts_at"] == before
    assert not [r for r in rows() if r["state"] == "pending"]


def test_invalid_config_atomic(seeded):
    with transaction() as db:
        with pytest.raises(AdminError):
            planning.save_config(db, {"planning_revision": "0", "timezone": "Unknown/Zone"})
        assert planning.settings(db)["revision"] == 0


def test_history_changes_automatically(seeded, monkeypatch):
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    stamp = planning.snapshot(1)[1][0]["starts_at"]
    monkeypatch.setattr(planning.time, "time", lambda: stamp - 1)
    assert not planning.snapshot(1)[1][0]["history"]
    monkeypatch.setattr(planning.time, "time", lambda: stamp)
    assert planning.snapshot(1)[1][0]["history"]


def test_public_routes_and_confirm_cancel(seeded, client):
    assert client.get("/filmavonden").status_code == 200
    response = client.post("/filmavond/1/planning", data={"revision": 0, "day": "2030-03-30", "clock": "20:00"}, follow_redirects=False)
    assert response.status_code == 303
    assert "Testfilm" in client.get("/filmavonden").text
    assert "Ja, filmavond annuleren" in client.get("/filmavond/1/annuleren").text
    assert client.post("/filmavond/1/annuleren", data={"revision": 1}).status_code == 400
    assert client.post("/filmavond/1/planning", headers={"Origin": "https://evil.example"},
                       data={"revision": 1, "day": "2030-03-31", "clock": "20:00"}).status_code == 403
    assert client.post("/filmavond/1/annuleren", data={"revision": 1, "confirm": "yes"}, follow_redirects=False).status_code == 303
    assert "Geannuleerd" in client.get("/filmavonden").text


def test_admin_planning_auth_csrf_and_secret_never_rendered(seeded, configured, monkeypatch):
    form = {"planning_revision": "0", "timezone": "Europe/Amsterdam", "bot_token": TOKEN,
            "chat_id": "-123", "base_url": "https://films.example", "telegram_enabled": "on"}
    assert configured.post("/admin/planning", data=form).status_code == 401
    login(configured)
    page = configured.get("/admin/settings")
    assert configured.post("/admin/planning", data=form | {"csrf": "invalid"}).status_code == 403
    assert configured.post("/admin/planning", data=form | {"csrf": csrf(page)}, follow_redirects=False).status_code == 303
    assert TOKEN not in configured.get("/admin/settings").text
    monkeypatch.setattr(planning, "send", lambda c, m: "sent")
    assert configured.post("/admin/telegram-test", data={"csrf": csrf(page)}, follow_redirects=False).status_code == 303
    with sqlite3.connect(seeded / "pickaflick.db") as db:
        assert TOKEN not in db.execute("SELECT token FROM planning_settings").fetchone()[0]


def test_telegram_network_errors_do_not_expose_secret(seeded, monkeypatch, caplog):
    enable()
    def broken(*args, **kwargs):
        raise httpx.ConnectError("secret URL should not be logged: " + TOKEN)
    monkeypatch.setattr(httpx.Client, "post", broken)
    with transaction() as db:
        assert planning.send(planning.settings(db), "Test") == "unknown"
    assert TOKEN not in caplog.text


def test_result_form_has_no_default_time_and_displays_appointment(seeded, client, monkeypatch):
    from app.movie_night import routes
    night = SimpleNamespace(id=1, selected_movie_id=1, status="selected")
    movie = SimpleNamespace(title="Testfilm", poster_url=None)
    candidate = SimpleNamespace(record=SimpleNamespace(movie_id=1, movie=movie, decision="choose"), reasons=[])
    monkeypatch.setattr(routes.service, "get_night", lambda *args: (night, [], [candidate]))
    page = client.get("/filmavond/1")
    assert page.status_code == 200
    assert 'name="clock" type="time" required value=""' in page.text
    assert 'name="day" type="date" required value=""' in page.text
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    page = client.get("/filmavond/1")
    assert "30-03-2030 20:00 CET" in page.text
    assert "Verplaatsen" in page.text


def test_fall_dst_and_live_timezone_rebuild(seeded):
    enable()
    planning.schedule(1, "2030-10-26", "20:00", 0, now=NOW)
    rating = next(r for r in rows() if r["kind"] == "rating")
    assert rating["due_at"] == datetime(2030, 10, 27, 9, tzinfo=UTC).timestamp()
    stamp = planning.snapshot(1)[1][0]["starts_at"]
    with transaction() as db:
        planning.save_config(db, {"planning_revision": "1", "timezone": "America/New_York",
                                 "telegram_enabled": "on", "chat_id": "-123", "base_url": "https://films.example"})
    assert planning.snapshot(1)[1][0]["starts_at"] == stamp
    pending = {r["kind"]: r for r in rows() if r["state"] == "pending"}
    assert set(pending) == {"day", "hour", "rating"}
    assert pending["rating"]["due_at"] == datetime(2030, 10, 27, 14, tzinfo=UTC).timestamp()


def test_new_process_recovers_persisted_queue(seeded):
    enable()
    planning.schedule(1, "2030-03-30", "20:00", 0, now=NOW)
    script = (
        "from app.movie_night.planning import deliver_one; "
        f"assert deliver_one(now={NOW}, sender=lambda c,m: 'sent'); "
        f"assert not deliver_one(now={NOW}, sender=lambda c,m: 'sent')"
    )
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True)
    assert rows()[0]["state"] == "sent"
