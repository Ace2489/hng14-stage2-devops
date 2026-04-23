from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import api.main as main


@pytest.fixture
def mock_redis():
    redis = MagicMock()

    pipe = MagicMock()
    redis.pipeline.return_value = pipe

    return redis


@pytest.fixture
def client(mock_redis):
    main.app.state.redis = mock_redis
    yield TestClient(main.app)
    del main.app.state.redis


def test_health(client):
    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_create_job(client, mock_redis):
    res = client.post("/jobs")

    assert res.status_code == 200
    assert "job_id" in res.json()

    pipe = mock_redis.pipeline.return_value
    pipe.hset.assert_called_once()
    pipe.expire.assert_called_once()
    pipe.lpush.assert_called_once()
    pipe.execute.assert_called_once()


def test_get_job(client, mock_redis):
    mock_redis.hget.return_value = "queued"

    res = client.get("/jobs/test-id")

    assert res.status_code == 200
    assert res.json() == {
        "job_id": "test-id",
        "status": "queued",
    }

    mock_redis.hget.assert_called_once_with("job:test-id", "status")


def test_get_job_not_found(client, mock_redis):
    mock_redis.hget.return_value = None

    res = client.get("/jobs/missing")

    assert res.status_code == 404
