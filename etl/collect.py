"""서울 25개 구 아파트 매매 실거래 데이터 수집."""

import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import xmltodict
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "api" / ".env")

API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
RAW_DIR = Path(__file__).resolve().parent / "raw"

# 서울 25개 구 법정동코드 (앞 5자리)
SEOUL_DISTRICTS = {
    "11110": "종로구",
    "11140": "중구",
    "11170": "용산구",
    "11200": "성동구",
    "11215": "광진구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11290": "성북구",
    "11305": "강북구",
    "11320": "도봉구",
    "11350": "노원구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11470": "양천구",
    "11500": "강서구",
    "11530": "구로구",
    "11545": "금천구",
    "11560": "영등포구",
    "11590": "동작구",
    "11620": "관악구",
    "11650": "서초구",
    "11680": "강남구",
    "11710": "송파구",
    "11740": "강동구",
}


def generate_year_months(start: str = "202301") -> list[str]:
    """start부터 오늘 기준 YYYYMM까지의 목록 생성."""
    now = datetime.today()
    end = now.strftime("%Y%m")
    months = []
    year, month = int(start[:4]), int(start[4:])
    while True:
        ym = f"{year}{month:02d}"
        if ym > end:
            break
        months.append(ym)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def fetch_page(sigungu_code: str, deal_ymd: str, page: int = 1, rows: int = 1000) -> list[dict]:
    """API 한 페이지 호출."""
    params = {
        "serviceKey": API_KEY,
        "LAWD_CD": sigungu_code,
        "DEAL_YMD": deal_ymd,
        "pageNo": str(page),
        "numOfRows": str(rows),
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()

    data = xmltodict.parse(resp.text)
    body = data["response"]["body"]
    total = int(body["totalCount"])
    items = body.get("items", {})

    if total == 0 or items is None:
        return []

    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    return item_list, total


def fetch_all(sigungu_code: str, deal_ymd: str) -> list[dict]:
    """특정 구/월의 전체 데이터를 페이지네이션으로 수집."""
    rows_per_page = 1000
    first_page, total = fetch_page(sigungu_code, deal_ymd, page=1, rows=rows_per_page)
    all_items = list(first_page)

    total_pages = (total + rows_per_page - 1) // rows_per_page
    for p in range(2, total_pages + 1):
        items, _ = fetch_page(sigungu_code, deal_ymd, page=p, rows=rows_per_page)
        all_items.extend(items)
        time.sleep(0.1)

    return all_items


def collect(mode: str = "full"):
    """mode: 'full' = 전체 기간, 'recent' = 최근 3개월만."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if mode == "recent":
        now = datetime.today()
        # 3개월 전부터
        m = now.month - 2
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        start = f"{y}{m:02d}"
        year_months = generate_year_months(start)
    else:
        year_months = generate_year_months()

    print(f"수집 모드: {mode} | 기간: {year_months[0]} ~ {year_months[-1]} ({len(year_months)}개월)")

    for code, name in SEOUL_DISTRICTS.items():
        all_items = []
        for ym in year_months:
            try:
                items = fetch_all(code, ym)
                all_items.extend(items)
                print(f"  {name}({code}) {ym}: {len(items)}건")
            except Exception as e:
                print(f"  {name}({code}) {ym}: 실패 - {e}")
            time.sleep(0.2)

        if all_items:
            df = pd.DataFrame(all_items)
            df.to_csv(RAW_DIR / f"{code}_{name}.csv", index=False, encoding="utf-8-sig")
            print(f"✓ {name}: 총 {len(all_items)}건 저장")
        else:
            print(f"✗ {name}: 데이터 없음")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "recent"], default="recent",
                        help="full: 전체 기간 수집, recent: 최근 3개월만 (기본값)")
    args = parser.parse_args()
    collect(mode=args.mode)
