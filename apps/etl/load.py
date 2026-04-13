"""정제된 CSV를 Supabase(Postgres)에 적재."""

import hashlib
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DB_URL = os.getenv("SUPABASE_DB_URL", "")
CLEAN_CSV = Path(__file__).resolve().parent / "clean" / "sales_all.csv"
BATCH_SIZE = 1000

INSERT_REGIONS_SQL = """
INSERT INTO regions (sido, sigungu, dong, sigungu_code)
VALUES (%s, %s, %s, %s)
ON CONFLICT (sido, sigungu, dong) DO NOTHING
"""

INSERT_APARTMENTS_SQL = """
INSERT INTO apartments (apartment_name, region_id, jibun, road_name, build_year)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (apartment_name, region_id, jibun) DO NOTHING
"""

INSERT_SALES_SQL = """
INSERT INTO sales_transactions
    (apartment_id, source_id, deal_date, deal_year, deal_month,
     exclusive_area, floor, price, price_per_pyeong, is_canceled, reg_date)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (source_id) DO NOTHING
"""


def make_source_id(row) -> str:
    """거래 고유 식별용 SHA-256 해시. 행 인덱스 포함 금지."""
    fields = [
        str(getattr(row, "sigungu_code", "")),
        str(getattr(row, "deal_year", "")),
        str(getattr(row, "deal_month", "")),
        str(getattr(row, "deal_day", "")),
        str(getattr(row, "apartment_name", "")),
        str(getattr(row, "floor", "")),
        str(getattr(row, "exclusive_area", "")),
        str(getattr(row, "price", "")),
        str(getattr(row, "reg_date", "")),
    ]
    return hashlib.sha256("|".join(fields).encode()).hexdigest()


def _safe_int(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return int(val)


def load():
    if not CLEAN_CSV.exists():
        print("clean/sales_all.csv가 없습니다. transform.py를 먼저 실행하세요.")
        return

    df = pd.read_csv(CLEAN_CSV, dtype={"sigungu_code": str})
    df = df.where(pd.notnull(df), None)
    print(f"적재 대상: {len(df)}건")

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # 1. regions 적재
            regions = df[["sido", "sigungu", "dong", "sigungu_code"]].drop_duplicates()
            region_values = [
                (r.sido, r.sigungu, r.dong or "", r.sigungu_code)
                for r in regions.itertuples()
            ]
            cur.executemany(INSERT_REGIONS_SQL, region_values)
            conn.commit()
            print(f"  regions: {len(region_values)}건 시도")

            # region_id 매핑 조회
            cur.execute("SELECT region_id, sido, sigungu, dong FROM regions")
            region_map = {(r[1], r[2], r[3]): r[0] for r in cur.fetchall()}

            # 2. apartments 적재
            apts = df[["apartment_name", "sido", "sigungu", "dong", "jibun", "build_year"]].drop_duplicates(
                subset=["apartment_name", "sido", "sigungu", "dong", "jibun"]
            )
            apt_values = []
            for r in apts.itertuples():
                rid = region_map.get((r.sido, r.sigungu, r.dong or ""))
                if rid is None:
                    continue
                apt_values.append((
                    r.apartment_name,
                    rid,
                    r.jibun or "",
                    None,
                    _safe_int(r.build_year),
                ))

            cur.executemany(INSERT_APARTMENTS_SQL, apt_values)
            conn.commit()
            print(f"  apartments: {len(apt_values)}건 시도")

            # apartment_id 매핑 조회
            cur.execute("SELECT apartment_id, apartment_name, region_id, jibun FROM apartments")
            apt_map = {(r[1], r[2], r[3]): r[0] for r in cur.fetchall()}

            # 3. sales_transactions 배치 적재
            inserted = 0
            batch = []
            for row in df.itertuples():
                rid = region_map.get((row.sido, row.sigungu, getattr(row, "dong", None) or ""))
                if rid is None:
                    continue
                aid = apt_map.get((row.apartment_name, rid, getattr(row, "jibun", None) or ""))
                if aid is None:
                    continue

                batch.append((
                    aid,
                    make_source_id(row),
                    row.deal_date,
                    int(row.deal_year),
                    int(row.deal_month),
                    float(row.exclusive_area),
                    _safe_int(row.floor),
                    int(row.price),
                    _safe_int(row.price_per_pyeong),
                    bool(row.is_canceled),
                    row.reg_date if row.reg_date is not None else None,
                ))

                if len(batch) >= BATCH_SIZE:
                    cur.executemany(INSERT_SALES_SQL, batch)
                    conn.commit()
                    inserted += len(batch)
                    batch = []

            if batch:
                cur.executemany(INSERT_SALES_SQL, batch)
                conn.commit()
                inserted += len(batch)

            print(f"  sales_transactions: {inserted}건 시도")

    print("적재 완료")


if __name__ == "__main__":
    load()
