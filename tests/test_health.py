from pathlib import Path


def test_project_has_health_route():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert '@app.get("/health"' in source
