from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

BASE_BODY = {
    "salary": 5000,
    "savings": 10000,
    "loan_years": 30,
}


def test_basic_response_shape():
    """기본 요청 → 응답에 필수 필드 존재."""
    resp = client.post("/api/simulate", json=BASE_BODY)
    assert resp.status_code == 200
    data = resp.json()
    assert "max_loan" in data
    assert "monthly_payment" in data
    assert "total_budget" in data
    assert "affordable_count" in data
    assert "apartments" in data
    assert isinstance(data["apartments"], list)


def test_no_duplicate_apartments():
    """동일 아파트가 결과에 1번만 등장."""
    resp = client.post("/api/simulate", json=BASE_BODY)
    data = resp.json()
    apts = data["apartments"]
    # (apartment_name, sigungu, dong, exclusive_area) 조합으로 중복 체크
    keys = [(a["apartment_name"], a["sigungu"], a["dong"]) for a in apts]
    assert len(keys) == len(set(keys))


def test_affordable_count_matches_list():
    """affordable_count == apartments 목록 길이 (200건 미만 시)."""
    resp = client.post("/api/simulate", json={**BASE_BODY, "savings": 0, "salary": 2000})
    data = resp.json()
    if data["affordable_count"] <= 200:
        assert data["affordable_count"] == len(data["apartments"])


def test_region_filter():
    """지역 필터 → 응답 아파트의 sigungu가 모두 해당 구."""
    resp = client.post("/api/simulate", json={**BASE_BODY, "region": "강남구"})
    data = resp.json()
    for apt in data["apartments"]:
        assert apt["sigungu"] == "강남구"


def test_stricter_conditions_lower_budget():
    """높은 금리 + 낮은 DSR → 기본값보다 total_budget 낮아야 함."""
    default = client.post("/api/simulate", json=BASE_BODY).json()
    strict = client.post(
        "/api/simulate",
        json={
            **BASE_BODY,
            "interest_rate": 6.0,
            "dsr_limit": 30,
        },
    ).json()
    assert strict["total_budget"] < default["total_budget"]
