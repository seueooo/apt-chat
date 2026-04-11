"""정제된 CSV를 Supabase(Postgres)에 적재."""

import hashlib
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "api" / ".env")

DB_URL = os.getenv("SUPABASE_DB_URL", "")
CLEAN_CSV = Path(__file__).resolve().parent / "clean" / "sales_all.csv"
BATCH_SIZE = 1000


def make_source_id(row: pd.Series) -> str:
    """거래 고유 식별용 SHA-256 해시. 행 인덱스 포함 금지."""
    fields = [
        str(row.get("sigungu_code", "")),
        str(row.get("deal_year", "")),
        str(row.get("deal_month", "")),
        str(row.get("deal_day", "")),
        str(row.get("apartment_name", "")),
        str(row.get("floor", "")),
        str(row.get("exclusive_area", "")),
        str(row.get("price", "")),
        str(row.get("reg_date", "")),
    ]
    return hashlib.sha256("|".join(fields).encode()).hexdigest()


def load():
    if not CLEAN_CSV.exists():
        print("clean/sales_all.csv가 없습니다. transform.py를 먼저 실행하세요.")
        return

    df = pd.read_csv(CLEAN_CSV, dtype={"sigungu_code": str})
    df = df.where(pd.notnull(df), None)
    print(f"적재 대상: {len(df)}건")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 1. regions 적재
    regions = df[["sido", "sigungu", "dong", "sigungu_code"]].drop_duplicates()
    region_values = [
        (r.sido, r.sigungu, r.dong or "", r.sigungu_code)
        for r in regions.itertuples()
    ]
    execute_values(
        cur,
        """
        INSERT INTO regions (sido, sigungu, dong, sigungu_code)
        VALUES %s
        ON CONFLICT (sido, sigungu, dong) DO NOTHING
        """,
        region_values,
    )
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
            None,  # road_name
            int(r.build_year) if r.build_year and pd.notna(r.build_year) else None,
        ))

    execute_values(
        cur,
        """
        INSERT INTO apartments (apartment_name, region_id, jibun, road_name, build_year)
        VALUES %s
        ON CONFLICT (apartment_name, region_id, jibun) DO NOTHING
        """,
        apt_values,
    )
    conn.commit()
    print(f"  apartments: {len(apt_values)}건 시도")

    # apartment_id 매핑 조회
    cur.execute("SELECT apartment_id, apartment_name, region_id, jibun FROM apartments")
    apt_map = {(r[1], r[2], r[3]): r[0] for r in cur.fetchall()}

    # 3. sales_transactions 배치 적재
    inserted = 0
    batch = []
    for _, row in df.iterrows():
        rid = region_map.get((row["sido"], row["sigungu"], row.get("dong") or ""))
        if rid is None:
            continue
        aid = apt_map.get((row["apartment_name"], rid, row.get("jibun") or ""))
        if aid is None:
            continue

        source_id = make_source_id(row)
        floor_val = int(row["floor"]) if row["floor"] is not None and pd.notna(row["floor"]) else None
        price_pp = int(row["price_per_pyeong"]) if row["price_per_pyeong"] is not None and pd.notna(row["price_per_pyeong"]) else None
        reg_date = row["reg_date"] if row["reg_date"] is not None and pd.notna(row["reg_date"]) else None

        batch.append((
            aid,
            source_id,
            row["deal_date"],
            int(row["deal_year"]),
            int(row["deal_month"]),
            float(row["exclusive_area"]),
            floor_val,
            int(row["price"]),
            price_pp,
            bool(row["is_canceled"]),
            reg_date,
        ))

        if len(batch) >= BATCH_SIZE:
            execute_values(
                cur,
                """
                INSERT INTO sales_transactions
                    (apartment_id, source_id, deal_date, deal_year, deal_month,
                     exclusive_area, floor, price, price_per_pyeong, is_canceled, reg_date)
                VALUES %s
                ON CONFLICT (source_id) DO NOTHING
                """,
                batch,
            )
            conn.commit()
            inserted += len(batch)
            batch = []

    if batch:
        execute_values(
            cur,
            """
            INSERT INTO sales_transactions
                (apartment_id, source_id, deal_date, deal_year, deal_month,
                 exclusive_area, floor, price, price_per_pyeong, is_canceled, reg_date)
            VALUES %s
            ON CONFLICT (source_id) DO NOTHING
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)

    print(f"  sales_transactions: {inserted}건 시도")

    cur.close()
    conn.close()
    print("적재 완료")


if __name__ == "__main__":
    load()
