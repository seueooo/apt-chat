from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# --- GET /api/regions ---


def test_regions_response_shape():
    resp = client.get("/api/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert "regions" in data
    assert isinstance(data["regions"], list)
    assert len(data["regions"]) > 0


def test_regions_fields():
    resp = client.get("/api/regions")
    region = resp.json()["regions"][0]
    assert "sigungu" in region
    assert "dong_count" in region
    assert "apartment_count" in region


def test_regions_has_25_districts():
    """서울 25개 구가 모두 있어야 함."""
    resp = client.get("/api/regions")
    regions = resp.json()["regions"]
    assert len(regions) == 25


# --- GET /api/stats ---


def test_stats_response_shape():
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_transactions" in data
    assert "total_apartments" in data
    assert "date_range" in data


def test_stats_date_range():
    resp = client.get("/api/stats")
    dr = resp.json()["date_range"]
    assert "from" in dr
    assert "to" in dr


def test_stats_positive_counts():
    resp = client.get("/api/stats")
    data = resp.json()
    assert data["total_transactions"] > 0
    assert data["total_apartments"] > 0
