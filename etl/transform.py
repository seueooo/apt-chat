"""수집된 CSV 원본 데이터를 정제하여 DB 적재용 단일 CSV로 변환."""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent / "raw"
CLEAN_DIR = Path(__file__).resolve().parent / "clean"

# API 컬럼 → 스키마 매핑
COLUMN_MAP = {
    "sggCd": "sigungu_code",
    "umdNm": "dong",
    "aptNm": "apartment_name",
    "jibun": "jibun",
    "excluUseAr": "exclusive_area",
    "dealYear": "deal_year",
    "dealMonth": "deal_month",
    "dealDay": "deal_day",
    "dealAmount": "deal_amount_raw",
    "floor": "floor",
    "buildYear": "build_year",
    "cdealDay": "cancel_deal_day",
    "rgstDate": "reg_date_raw",
}


def transform():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        print("raw/ 디렉토리에 CSV 파일이 없습니다. collect.py를 먼저 실행하세요.")
        return

    frames = []
    for f in csv_files:
        df = pd.read_csv(f, dtype=str)
        frames.append(df)
        print(f"  읽기: {f.name} ({len(df)}건)")

    raw = pd.concat(frames, ignore_index=True)
    print(f"전체 원본: {len(raw)}건")

    # 필요한 컬럼만 추출 + 이름 변환
    df = raw.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())].copy()

    # 가격 정제: "115,000" → 115000
    df["price"] = (
        df["deal_amount_raw"]
        .str.replace(",", "", regex=False)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )
    df.drop(columns=["deal_amount_raw"], inplace=True)

    # 수치 변환
    df["exclusive_area"] = pd.to_numeric(df["exclusive_area"], errors="coerce")
    df["deal_year"] = pd.to_numeric(df["deal_year"], errors="coerce").astype("Int64")
    df["deal_month"] = pd.to_numeric(df["deal_month"], errors="coerce").astype("Int64")
    df["deal_day"] = pd.to_numeric(df["deal_day"], errors="coerce").astype("Int64")
    df["floor"] = pd.to_numeric(df["floor"], errors="coerce").astype("Int64")
    df["build_year"] = pd.to_numeric(df["build_year"], errors="coerce").astype("Int64")

    # deal_date 생성
    df["deal_date"] = pd.to_datetime(
        df["deal_year"].astype(str) + "-" + df["deal_month"].astype(str) + "-" + df["deal_day"].astype(str),
        format="%Y-%m-%d",
        errors="coerce",
    )

    # 해제거래 마킹: cancel_deal_day에 값이 있으면 해제된 거래
    df["is_canceled"] = df["cancel_deal_day"].str.strip().fillna("").ne("")
    df.drop(columns=["cancel_deal_day"], inplace=True)

    # 평당가 계산: price / (exclusive_area / 3.306)
    df["price_per_pyeong"] = (
        df["price"] / (df["exclusive_area"] / 3.306)
    ).round(0).astype("Int64")

    # reg_date 정제: "25.05.30" → "2025-05-30"
    def parse_reg_date(val):
        if pd.isna(val) or str(val).strip() == "":
            return pd.NaT
        parts = str(val).strip().split(".")
        if len(parts) == 3:
            y, m, d = parts
            year = int(y) + 2000 if int(y) < 100 else int(y)
            return pd.Timestamp(year=year, month=int(m), day=int(d))
        return pd.NaT

    df["reg_date"] = df["reg_date_raw"].apply(parse_reg_date)
    df.drop(columns=["reg_date_raw"], inplace=True)

    # 결측치 제거 (price, exclusive_area, deal_date 필수)
    before = len(df)
    df.dropna(subset=["price", "exclusive_area", "deal_date"], inplace=True)
    dropped = before - len(df)
    if dropped:
        print(f"결측치 제거: {dropped}건")

    # 시군구코드로 시도/시군구 매핑 (서울 고정)
    df["sido"] = "서울특별시"

    # 시군구 이름 매핑
    SIGUNGU_MAP = {
        "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
        "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
        "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
        "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
        "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
        "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
        "11740": "강동구",
    }
    df["sigungu"] = df["sigungu_code"].map(SIGUNGU_MAP)

    out = CLEAN_DIR / "sales_all.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"정제 완료: {len(df)}건 → {out}")


if __name__ == "__main__":
    transform()
