"""Tests for the release version reporting used by the deployment pipeline."""

import socket

import aceest
from aceest import create_app, read_version


def test_version_endpoint_reports_config(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "v.db"),
                      "APP_VERSION": "9.9.9", "APP_VARIANT": "canary"})
    data = app.test_client().get("/version").get_json()
    assert data == {"version": "9.9.9", "variant": "canary",
                    "pod": socket.gethostname()}


def test_home_page_shows_version(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "v.db"),
                      "APP_VERSION": "9.9.9", "APP_VARIANT": "blue"})
    page = app.test_client().get("/").data
    assert b"9.9.9" in page and b"blue" in page


def test_variant_defaults_to_default(client):
    assert client.get("/version").get_json()["variant"] == "default"


def test_read_version_prefers_env(monkeypatch):
    monkeypatch.setenv("APP_VERSION", " 3.1.4 ")
    assert read_version() == "3.1.4"


def test_read_version_uses_version_file(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_VERSION", raising=False)
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3\n")
    monkeypatch.setattr(aceest, "VERSION_FILE", version_file)
    assert read_version() == "1.2.3"


def test_read_version_matches_repo_version_file(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    assert read_version() == aceest.VERSION_FILE.read_text().strip()


def test_read_version_without_file(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.setattr(aceest, "VERSION_FILE", tmp_path / "missing")
    assert read_version() == "unknown"


def test_read_version_empty_file(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_VERSION", raising=False)
    version_file = tmp_path / "VERSION"
    version_file.write_text("\n")
    monkeypatch.setattr(aceest, "VERSION_FILE", version_file)
    assert read_version() == "unknown"


def test_entry_point_exposes_the_flask_app():
    import ACEest_Fitness
    import app as app_module
    assert ACEest_Fitness.app is app_module.app
