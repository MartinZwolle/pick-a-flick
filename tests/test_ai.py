import json
from types import SimpleNamespace as NS

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import AIConfig, Settings
from app.database import Base
from app.movie_night import ai, service
from app.movie_night.models import MovieNight, MovieNightCandidate
from app.profiles.models import Profile


@pytest.fixture
def settings(monkeypatch):
    value = Settings(ai=AIConfig(enabled=True, provider="ollama", model="local-model"))
    value.streaming.subscriptions = ["netflix"]
    monkeypatch.setattr(ai, "get_settings", lambda: value)
    return value


@pytest.mark.parametrize("kind", ["ollama", "openai", "anthropic", "openai_compatible", "deepseek"])
def test_adapters(settings, monkeypatch, kind):
    settings.ai.provider = kind
    settings.ai.base_url = "https://compatible.example/v1"
    monkeypatch.setenv("PICKAFLICK_AI_API_KEY", "secret-test-key")
    result = json.dumps({"movies": [{"title": "Jaws", "year": 1975, "reason": "Water met spanning"}]})
    seen = []
    def handler(request):
        seen.append(request)
        if kind == "ollama":
            payload = {"message": {"content": result}}
        elif kind == "anthropic":
            payload = {"content": [{"type": "text", "text": result}]}
        else:
            payload = {"choices": [{"message": {"content": result}}]}
        return httpx.Response(200, json=payload)
    real_client = httpx.Client
    monkeypatch.setattr(ai.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    assert ai.suggest(settings, "Duiken met Kermit", {})[0].title == "Jaws"
    request = seen[0]
    assert "secret-test-key" not in request.content.decode()
    if kind == "ollama":
        assert "authorization" not in request.headers and "x-api-key" not in request.headers
        assert request.url.path.endswith("/api/chat")
    elif kind == "anthropic":
        assert request.url.host == "api.anthropic.com"
        assert request.headers["x-api-key"] == "secret-test-key"
    elif kind == "openai":
        assert request.url.host == "api.openai.com"
        assert json.loads(request.content)["max_completion_tokens"] == 4096
    elif kind == "deepseek":
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret-test-key"
        body = json.loads(request.content)
        assert body["max_tokens"] == 4096
        assert "max_completion_tokens" not in body
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        assert body["stream"] is False
    else:
        assert request.url.host == "compatible.example"


@pytest.mark.parametrize("payload", ["not json", '{"movies":[{"title":"Fake"}]}', '{"movies":' + json.dumps([{"title":"x","year":2000,"reason":"x"}] * 31) + '}'])
def test_invalid_model_output_is_safe(settings, monkeypatch, payload):
    real_client = httpx.Client
    def handler(request):
        return httpx.Response(200, json={"message": {"content": payload}})
    monkeypatch.setattr(ai.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(ai.ExpertError, match="bruikbaar"):
        ai.suggest(settings, "film", {})


@pytest.mark.parametrize("kind", ["ollama", "deepseek"])
@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_provider_errors_do_not_leak(settings, monkeypatch, status, kind):
    settings.ai.provider = kind
    monkeypatch.setenv("PICKAFLICK_AI_API_KEY", "secret-key")
    real_client = httpx.Client
    monkeypatch.setattr(ai.httpx, "Client", lambda **kw: real_client(
        transport=httpx.MockTransport(lambda req: httpx.Response(status, text="secret-key", headers={"location": "https://evil.example"})), **kw))
    with pytest.raises(ai.ExpertError) as exc:
        ai.suggest(settings, "film", {})
    assert "secret-key" not in str(exc.value)


@pytest.mark.parametrize("kind", ["openai", "deepseek"])
def test_disabled_and_missing_key(settings, monkeypatch, kind):
    settings.ai.enabled = False
    with pytest.raises(ai.ExpertError, match="staat uit"):
        ai.suggest(settings, "film", {})
    settings.ai.enabled = True
    settings.ai.provider = kind
    monkeypatch.delenv("PICKAFLICK_AI_API_KEY", raising=False)
    with pytest.raises(ai.ExpertError, match="sleutel ontbreekt"):
        ai.suggest(settings, "film", {})


def setup_discovery(monkeypatch, count=15):
    suggestions = [ai.Suggestion(title=f"Film {i}", year=2000, reason="Creatieve benadering") for i in range(count)]
    monkeypatch.setattr(ai, "suggest", lambda *args: suggestions + suggestions[:1])
    monkeypatch.setattr(service, "_taste", lambda *args: ({}, {}, {}, set(range(count)), {i:{1,2} for i in range(count)}))
    movies = {i:NS(id=i, title=f"Film {i}", adult=False, runtime_minutes=90, genres=[], credits=[]) for i in range(count)}
    class Provider:
        def __init__(self, settings):
            pass
        def search_movies(self, title):
            i = int(title.split()[-1])
            return [NS(tmdb_id=i, title=title, original_title=title, release_year=2000)]
    monkeypatch.setattr(ai, "TMDbProvider", Provider)
    monkeypatch.setattr(ai.catalog, "get_or_fetch_movie", lambda db, mid: movies[mid])
    monkeypatch.setattr(ai.availability, "get_for_movie", lambda db, movie: NS(
        stale=False, error=None, subscriptions=["netflix"], rentals=[]))
    return movies


def test_verified_maximum_dedup_and_soft_taste(settings, monkeypatch):
    setup_discovery(monkeypatch)
    found = ai.discover(None, [1, 2], "onmogelijke wens", None)
    assert len(found) == 10
    assert len({movie.id for _, movie, _ in found}) == 10
    assert found[0][2][0].startswith("AI-interpretatie:")


@pytest.mark.parametrize("view", [
    NS(stale=False, error=None, subscriptions=[], rentals=[]),
    NS(stale=True, error=None, subscriptions=[1], rentals=[]),
    NS(stale=False, error="timeout", subscriptions=[1], rentals=[]),
])
def test_availability_fails_closed(settings, monkeypatch, view):
    setup_discovery(monkeypatch, 1)
    monkeypatch.setattr(ai.availability, "get_for_movie", lambda *args: view)
    assert ai.discover(None, [1], "film", None) == []


def test_no_matching_title_or_year_and_runtime(settings, monkeypatch):
    movies = setup_discovery(monkeypatch, 2)
    movies[0].runtime_minutes = 150
    movies[1].runtime_minutes = None
    assert ai.discover(None, [1], "film", 100) == []
    monkeypatch.setattr(ai, "normalized", lambda text: text)
    monkeypatch.setattr(ai, "suggest", lambda *args: [ai.Suggestion(title="Invented", year=2000, reason="x")])
    monkeypatch.setattr(ai, "TMDbProvider", lambda settings: NS(search_movies=lambda title: [NS(tmdb_id=1, title="Different", original_title="Different", release_year=2000)]))
    assert ai.discover(None, [1], "film", None) == []


@pytest.mark.parametrize("viewer_count", [1, 2])
def test_direct_existing_game_with_fewer_cards(monkeypatch, viewer_count):
    import app.catalog.models
    import app.onboarding.models  # noqa: F401
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        from app.catalog.models import Movie
        movie = Movie(tmdb_id=1, title="Existing", adult=False)
        db.add(movie)
        viewers = [Profile(name=f"Viewer {i}", birth_year=1980) for i in range(viewer_count)]
        db.add_all(viewers)
        db.commit()
        monkeypatch.setattr(ai, "discover", lambda *args: [(1, movie, ["Interpretatie"])])
        night = service.create_night(db, [v.id for v in viewers], [], None, "ai", "wens")
        assert night.mode == "ai"
        rows = list(db.scalars(select(MovieNightCandidate)))
        assert len(rows) == 1 and rows[0].movie_night_id == night.id
        state = service.round_state([NS(record=rows[0])])
        assert state["current"].record.movie_id == movie.id
        service.decide(db, night, rows[0], "choose", [v.id for v in viewers])
        assert night.selected_movie_id == movie.id


def test_zero_creates_no_empty_game(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ai, "discover", lambda *args: [])
    with Session(engine) as db:
        with pytest.raises(ai.ExpertError, match="Geen verifieerbare"):
            service.create_night(db, [1], [], None, "ai", "wens")
        assert db.scalar(select(MovieNight)) is None


@pytest.mark.parametrize('content', ['', 'not JSON', '{"movies":[{"title":"Invented"}]}'])
def test_deepseek_invalid_output(settings, monkeypatch, content):
    settings.ai.provider = 'deepseek'
    settings.ai.model = 'deepseek-flash'
    monkeypatch.setenv('PICKAFLICK_AI_API_KEY', 'secret-key')
    real_client = httpx.Client
    def handler(request):
        return httpx.Response(200, json={'choices':[{'message':{
            'reasoning_content':'must never become a film or explanation', 'content':content}}]})
    monkeypatch.setattr(ai.httpx, 'Client', lambda **kw: real_client(
        transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(ai.ExpertError, match='bruikbaar'):
        ai.suggest(settings, 'filmwens', {})


def test_deepseek_timeout_is_safe(settings, monkeypatch):
    settings.ai.provider = 'deepseek'
    monkeypatch.setenv('PICKAFLICK_AI_API_KEY', 'secret-key')
    real_client = httpx.Client
    def handler(request):
        raise httpx.ReadTimeout('secret-key', request=request)
    monkeypatch.setattr(ai.httpx, 'Client', lambda **kw: real_client(
        transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(ai.ExpertError) as exc:
        ai.suggest(settings, 'filmwens', {})
    assert 'secret-key' not in str(exc.value)
