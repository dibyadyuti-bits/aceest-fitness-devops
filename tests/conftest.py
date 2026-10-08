import pytest

from aceest import create_app


@pytest.fixture
def app(tmp_path):
    """A fresh app backed by a throwaway SQLite file for every test."""
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def ravi(client):
    """A saved Muscle Gain client used by several API tests."""
    response = client.post("/api/clients", json={
        "name": "Ravi", "age": 28, "height": 175, "weight": 70, "program": "MG",
    })
    assert response.status_code == 201
    return response.get_json()
