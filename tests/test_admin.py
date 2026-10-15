import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PASSWORD = "A long test passphrase 2026!"
NEW_PASSWORD = "Another long passphrase 2026!"


def migrate(directory, target):
    env = os.environ | {"PICKAFLICK_DATA_DIR": str(directory)}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", target],
        env=env, check=True, capture_output=True, text=True,
    )


@pytest.fixture(scope="session")
def migrated(tmp_path_factory):
    directory = tmp_path_factory.mktemp("baseline")
    migrate(directory, "head")
    return directory / "pickaflick.db"


@pytest.fixture
def environment(tmp_path, migrated, monkeypatch):
    shutil.copyfile(migrated, tmp_path / "pickaflick.db")
    config = tmp_path / "config.yaml"
    config.write_text(Path("config.example.yaml").read_text(), encoding="utf-8")
    monkeypatch.setenv("PICKAFLICK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PICKAFLICK_CONFIG", str(config))
    monkeypatch.delenv("PICKAFLICK_ADMIN_ALLOW_HTTP", raising=False)
    from app.config import get_base_settings
    get_base_settings.cache_clear()
    yield tmp_path
    get_base_settings.cache_clear()


@pytest.fixture
def client(environment):
    from app.main import app
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def configured(client):
    from app.admin.security import set_password
    set_password(PASSWORD)
    return client


def csrf(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)


def login(client):
    form = client.get("/admin/login")
    return client.post("/admin/login", data={"csrf": csrf(form), "password": PASSWORD},
                       follow_redirects=False)


def session_token(client):
    from app.admin.security import COOKIE
    return client.cookies.get(COOKIE)


def test_unconfigured_admin_and_public_home(client):
    assert client.get("/").status_code == 200
    assert client.get("/admin/login").status_code == 503
    assert client.get("/admin/settings").status_code == 401


def test_setup_hash_and_session_rotation(configured, environment):
    form = configured.get("/admin/login")
    before = session_token(configured)
    cookie = form.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
    response = configured.post("/admin/login",
                               data={"csrf": csrf(form), "password": PASSWORD},
                               follow_redirects=False)
    assert response.status_code == 303
    after = session_token(configured)
    assert after != before
    with sqlite3.connect(environment / "pickaflick.db") as db:
        encoded = db.execute("SELECT password_hash FROM admin_state").fetchone()[0]
        tokens = [row[0] for row in db.execute("SELECT token_hash FROM admin_sessions")]
    assert encoded.startswith("$argon2id$")
    assert PASSWORD not in encoded
    assert after not in tokens
    assert hashlib.sha256(after.encode()).hexdigest() in tokens
    assert hashlib.sha256(before.encode()).hexdigest() not in tokens


def test_csrf_and_cross_origin_rejected(configured):
    form = configured.get("/admin/login")
    assert configured.post("/admin/login",
                           data={"csrf": "wrong", "password": PASSWORD}).status_code == 403
    assert configured.post("/admin/login", headers={"Origin": "https://evil.example"},
                           data={"csrf": csrf(form), "password": PASSWORD}).status_code == 403
    assert login(configured).status_code == 303
    page = configured.get("/admin/settings")
    assert configured.post("/admin/logout", data={"csrf": "wrong"}).status_code == 403
    assert configured.post("/admin/settings",
                           data={"csrf": "wrong", "revision": "0"}).status_code == 403
    assert configured.post("/admin/password", data={
        "csrf": "wrong", "old_password": PASSWORD, "new_password": NEW_PASSWORD,
        "confirmation": NEW_PASSWORD,
    }).status_code == 403
    assert configured.get("/admin/settings").status_code == 200
    assert page.headers["cache-control"] == "no-store"


def test_logout_revokes_server_session(configured):
    login(configured)
    saved = session_token(configured)
    form = configured.get("/admin/settings")
    assert configured.post("/admin/logout", data={"csrf": csrf(form)},
                           follow_redirects=False).status_code == 303
    from app.admin.security import AdminError, current_session
    with pytest.raises(AdminError):
        current_session(saved)


@pytest.mark.parametrize("column,age", [("last_seen", 1801), ("created", 43201)])
def test_session_expiry(configured, environment, column, age):
    import time
    login(configured)
    with sqlite3.connect(environment / "pickaflick.db") as db:
        db.execute(f"UPDATE admin_sessions SET {column}=?", (time.time() - age,))
    assert configured.get("/admin/settings").status_code == 401


def test_persistent_global_login_throttle(configured, monkeypatch):
    from app.admin import security
    clock = [2000000000.0]
    monkeypatch.setattr(security.time, "time", lambda: clock[0])
    form = configured.get("/admin/login")
    for _ in range(5):
        assert configured.post("/admin/login", data={
            "csrf": csrf(form), "password": "incorrect",
        }).status_code == 401
    # A different browser does not bypass the single-admin throttle.
    from app.main import app
    with TestClient(app, base_url="https://testserver") as other:
        assert login(other).status_code == 429
    clock[0] += 901
    assert login(configured).status_code == 303


def test_password_change_revokes_all_sessions(configured):
    from app.main import app
    login(configured)
    with TestClient(app, base_url="https://testserver") as other:
        login(other)
        form = configured.get("/admin/password")
        response = configured.post("/admin/password", data={
            "csrf": csrf(form), "old_password": PASSWORD,
            "new_password": NEW_PASSWORD, "confirmation": NEW_PASSWORD,
        }, follow_redirects=False)
        assert response.status_code == 303
        assert other.get("/admin/settings").status_code == 401
    form = configured.get("/admin/login")
    assert configured.post("/admin/login", data={
        "csrf": csrf(form), "password": NEW_PASSWORD,
    }, follow_redirects=False).status_code == 303


def test_local_reset_and_no_accidental_overwrite(configured):
    from app.admin.security import AdminError, set_password
    login(configured)
    with pytest.raises(AdminError):
        set_password(NEW_PASSWORD)
    set_password(NEW_PASSWORD, reset=True)
    assert configured.get("/admin/settings").status_code == 401


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_policy(environment, password):
    from app.admin.security import AdminError, set_password
    with pytest.raises(AdminError):
        set_password(password)


def test_http_requires_explicit_opt_in(configured, monkeypatch):
    from app.main import app
    with TestClient(app, base_url="http://testserver") as http:
        assert http.get("/").status_code == 200
        assert http.get("/admin/login").status_code == 403
        monkeypatch.setenv("PICKAFLICK_ADMIN_ALLOW_HTTP", "true")
        form = http.get("/admin/login")
        assert form.status_code == 200
        assert "secure" not in form.headers["set-cookie"].lower()
        assert login(http).status_code == 303
    # HTTPS cookies stay Secure even when HTTP opt-in is enabled.
    assert "secure" in configured.get("/admin/login").headers["set-cookie"].lower()


def settings_data(client, **changes):
    page = client.get("/admin/settings")
    revision = re.search(r'name="revision" value="([^"]+)"', page.text).group(1)
    return {"csrf": csrf(page), "revision": revision, **changes}


def test_settings_live_merge_reset_and_conflict(configured, environment):
    from app.config import get_settings
    login(configured)
    config = environment / "config.yaml"
    original = config.read_bytes()
    assert get_settings().household.country == "NL"
    data = settings_data(configured, override=["country"], country="DE")
    assert configured.post("/admin/settings", data=data,
                           follow_redirects=False).status_code == 303
    assert get_settings().household.country == "DE"
    assert get_settings().streaming.subscriptions == ["netflix", "disney_plus", "prime_video"]
    assert configured.post("/admin/settings", data=data).status_code == 409
    with sqlite3.connect(environment / "pickaflick.db") as db:
        assert json.loads(db.execute("SELECT payload FROM settings_overrides").fetchone()[0]) == {
            "country": "DE"
        }
    # A fresh interpreter sees the committed value too (no process-local cache).
    output = subprocess.check_output(
        [sys.executable, "-c",
         "from app.config import get_settings; print(get_settings().household.country)"],
        text=True,
    )
    assert output.strip() == "DE"
    data = settings_data(configured)
    assert configured.post("/admin/settings", data=data,
                           follow_redirects=False).status_code == 303
    assert get_settings().household.country == "NL"
    assert config.read_bytes() == original


@pytest.mark.parametrize("changes", [
    {"override": ["country"], "country": "XX"},
    {"override": ["preferred"], "preferred": "zz"},
    {"override": ["preferred"], "preferred": "ja"},
    {"override": ["earliest_movie_year"], "earliest_movie_year": "9999"},
    {"override": ["adult_content"], "adult_content": "maybe"},
    {"override": ["subscriptions"], "subscriptions": "<script>"},
    {"override": ["ai"], "ai": "true"},
])
def test_invalid_settings_are_atomic(configured, changes):
    from app.admin.settings import read_overrides
    login(configured)
    response = configured.post("/admin/settings", data=settings_data(configured, **changes))
    assert response.status_code == 400
    assert read_overrides() == ({}, 0)


def test_unauthenticated_settings_write(client):
    response = client.post("/admin/settings",
                           data={"csrf": "fake", "revision": "0"})
    assert response.status_code == 401


def test_upgrade_preserves_profiles_and_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("PICKAFLICK_DATA_DIR", str(tmp_path))
    migrate(tmp_path, "0007")
    with sqlite3.connect(tmp_path / "pickaflick.db") as db:
        db.execute("INSERT INTO profiles (name, birth_year) VALUES ('Existing viewer', 1980)")
    migrate(tmp_path, "head")
    with sqlite3.connect(tmp_path / "pickaflick.db") as db:
        assert db.execute("SELECT name, birth_year FROM profiles").fetchall() == [
            ("Existing viewer", 1980)
        ]
        assert db.execute("SELECT password_hash FROM admin_state").fetchone() == (None,)
        assert db.execute("SELECT payload FROM settings_overrides").fetchone() == ("{}",)
    # Rollback only removes the added administration tables.
    subprocess.run([sys.executable, "-m", "alembic", "downgrade", "0007"],
                   check=True, capture_output=True)
    with sqlite3.connect(tmp_path / "pickaflick.db") as db:
        assert db.execute("SELECT name FROM profiles").fetchone()[0] == "Existing viewer"


def test_non_ascii_csrf_fails_closed(configured):
    configured.get("/admin/login")
    assert configured.post("/admin/login",
                           data={"csrf": "é" * 43, "password": PASSWORD}).status_code == 403


def test_login_form_expires(configured, environment):
    import time
    form = configured.get("/admin/login")
    with sqlite3.connect(environment / "pickaflick.db") as db:
        db.execute("UPDATE admin_sessions SET created=?", (time.time() - 601,))
    assert configured.post("/admin/login", data={
        "csrf": csrf(form), "password": PASSWORD,
    }).status_code == 401


def test_all_web_fields_and_environment_secrets(configured, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TMDB_API_KEY", "environment-only-test-key")
    login(configured)
    changes = {
        "country": "BE", "preferred": "nl", "allowed": "nl, en",
        "subscriptions": "", "rental": "pathe_thuis",
        "earliest_movie_year": "1990", "adult_content": "true",
    }
    data = settings_data(configured, override=list(changes), **changes)
    assert configured.post("/admin/settings", data=data,
                           follow_redirects=False).status_code == 303
    settings = get_settings()
    assert settings.household.country == "BE"
    assert settings.household.earliest_movie_year == 1990
    assert settings.household.adult_content is True
    assert settings.languages.preferred == ["nl"]
    assert settings.languages.allowed == ["nl", "en"]
    assert settings.streaming.subscriptions == []
    assert settings.streaming.rental == ["pathe_thuis"]
    assert settings.tmdb_api_key == "environment-only-test-key"
    assert "environment-only-test-key" not in configured.get("/admin/settings").text


def test_wrong_current_password_preserves_sessions(configured):
    login(configured)
    page = configured.get("/admin/password")
    response = configured.post("/admin/password", data={
        "csrf": csrf(page), "old_password": "wrong",
        "new_password": NEW_PASSWORD, "confirmation": NEW_PASSWORD,
    })
    assert response.status_code == 400
    assert configured.get("/admin/settings").status_code == 200


def test_cli_requires_interactive_terminal(environment):
    result = subprocess.run(
        [sys.executable, "-m", "app.admin.cli", "set-password"],
        check=False, input=PASSWORD, text=True, capture_output=True,
    )
    assert result.returncode == 1
    assert "interactieve terminal" in result.stderr
    assert PASSWORD not in result.stderr + result.stdout


@pytest.mark.parametrize("base_url,http", [
    ("http://homelab:8089", True),
    ("https://homelab:8443", False),
])
def test_browser_origin_login_and_settings(configured, monkeypatch, base_url, http):
    from app.main import app
    if http:
        monkeypatch.setenv("PICKAFLICK_ADMIN_ALLOW_HTTP", "true")
    with TestClient(app, base_url=base_url) as browser:
        form = browser.get("/admin/login")
        assert form.headers["referrer-policy"] == "same-origin"
        response = browser.post(
            "/admin/login", headers={"Origin": base_url},
            data={"csrf": csrf(form), "password": PASSWORD}, follow_redirects=False,
        )
        assert response.status_code == 303
        page = browser.get("/admin/settings")
        assert page.status_code == 200
        assert browser.post(
            "/admin/settings", headers={"Origin": base_url},
            data=settings_data(browser), follow_redirects=False,
        ).status_code == 303


@pytest.mark.parametrize("origin", ["null", "http://evil.example", "http://homelab:8090"])
def test_http_foreign_or_null_origin_still_rejected(configured, monkeypatch, origin):
    from app.main import app
    monkeypatch.setenv("PICKAFLICK_ADMIN_ALLOW_HTTP", "true")
    with TestClient(app, base_url="http://homelab:8089") as browser:
        page = browser.get("/admin/login")
        response = browser.post(
            "/admin/login", headers={"Origin": origin},
            data={"csrf": csrf(page), "password": PASSWORD}, follow_redirects=False,
        )
        assert response.status_code == 403


def test_ai_web_settings_secrets_and_reset(configured, monkeypatch):
    from app.config import get_settings
    from app.movie_night import routes
    monkeypatch.setattr(routes.profiles_service, 'list_profiles', lambda db: [])
    monkeypatch.setenv('PICKAFLICK_AI_API_KEY', 'never-render-this-key')
    login(configured)
    changes = {'ai_enabled':'true', 'ai_provider':'ollama', 'ai_model':'qwen3:8b',
               'ai_base_url':'http://ollama:11434'}
    response = configured.post('/admin/settings', data=settings_data(
        configured, override=list(changes), **changes), follow_redirects=False)
    assert response.status_code == 303
    assert get_settings().ai.enabled is True
    assert get_settings().ai.model == 'qwen3:8b'
    page = configured.get('/admin/settings')
    assert 'never-render-this-key' not in page.text
    assert 'AI-filmkenner' in configured.get('/filmavond').text
    assert configured.post('/admin/settings', data=settings_data(configured),
                           follow_redirects=False).status_code == 303
    assert get_settings().ai.enabled is False
    assert 'value="ai"' not in configured.get('/filmavond').text


@pytest.mark.parametrize('changes', [
    {'ai_provider':'invalid'}, {'ai_model':''},
    {'ai_base_url':'https://user:secret@example.com'},
    {'ai_base_url':'https://example.com?key=secret'},
    {'ai_base_url':'file:///etc/passwd'},
])
def test_invalid_ai_config_atomic(configured, changes):
    from app.admin.settings import read_overrides
    login(configured)
    response = configured.post('/admin/settings', data=settings_data(
        configured, override=list(changes), **changes))
    assert response.status_code == 400
    assert read_overrides() == ({}, 0)


def test_ai_route_zero_retains_wish_and_viewers(configured, monkeypatch):
    from types import SimpleNamespace

    from app.movie_night import routes
    from app.movie_night.ai import ExpertError
    monkeypatch.setattr(routes.profiles_service, 'list_profiles', lambda db: [SimpleNamespace(id=1,name='Viewer')])
    def no_results(*args):
        raise ExpertError('Geen films op je diensten gevonden.')
    monkeypatch.setattr(routes.service, 'create_night', no_results)
    response = configured.post('/filmavond', data={
        'viewers':'1', 'mode':'ai', 'prompt':'Muppets in Zweden'})
    assert response.status_code == 400
    assert 'Geen films op je diensten gevonden.' in response.text
    assert 'value="1" checked' in response.text


def test_deepseek_admin_configuration(configured, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv('PICKAFLICK_AI_API_KEY', 'deepseek-private-test-key')
    login(configured)
    changes = {'ai_enabled':'true', 'ai_provider':'deepseek', 'ai_model':'deepseek-flash'}
    response = configured.post('/admin/settings', data=settings_data(
        configured, override=list(changes), **changes), follow_redirects=False)
    assert response.status_code == 303
    assert get_settings().ai.provider == 'deepseek'
    assert get_settings().ai.model == 'deepseek-flash'
    assert get_settings().ai_api_key == 'deepseek-private-test-key'
    page = configured.get('/admin/settings')
    assert '<option selected>deepseek</option>' in page.text
    assert 'deepseek-private-test-key' not in page.text
