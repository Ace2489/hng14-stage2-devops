from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_redis():
    mock = MagicMock()

    # pipeline mock
    pipe = MagicMock()
    pipe.hset.return_value = pipe
    pipe.expire.return_value = pipe
    pipe.lpush.return_value = pipe
    pipe.execute.return_value = True

    mock.pipeline.return_value = pipe
    mock.hget.return_value = "queued"

    return mock


@pytest.fixture
def client(mock_redis):
    with patch("api.main.redis.Redis", return_value=mock_redis):
        from api.main import app

        return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_create_job(client):
    res = client.post("/jobs")
    assert res.status_code == 200
    assert "job_id" in res.json()


def test_get_job(client):
    res = client.get("/jobs/some-id")
    assert res.status_code == 200
    assert res.json()["status"] == "queued"
