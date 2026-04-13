-- AptChat DDL
-- Supabase best practices: BIGINT IDENTITY (not SERIAL), TEXT (not VARCHAR(N)), partial indexes

BEGIN;

-- 1. regions — 지역 마스터
CREATE TABLE IF NOT EXISTS regions (
    region_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sido         TEXT NOT NULL,
    sigungu      TEXT NOT NULL,
    dong         TEXT NOT NULL DEFAULT '',
    sigungu_code TEXT NOT NULL,
    UNIQUE (sido, sigungu, dong)
);

-- 2. apartments — 아파트 마스터
CREATE TABLE IF NOT EXISTS apartments (
    apartment_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    apartment_name TEXT NOT NULL,
    region_id      BIGINT NOT NULL REFERENCES regions (region_id),
    jibun          TEXT NOT NULL DEFAULT '',
    road_name      TEXT,
    build_year     INTEGER,
    UNIQUE (apartment_name, region_id, jibun)
);

-- 3. sales_transactions — 매매 실거래가
CREATE TABLE IF NOT EXISTS sales_transactions (
    transaction_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    apartment_id     BIGINT NOT NULL REFERENCES apartments (apartment_id),
    source_id        TEXT UNIQUE,
    deal_date        DATE NOT NULL,
    deal_year        INTEGER NOT NULL,
    deal_month       INTEGER NOT NULL,
    exclusive_area   NUMERIC(10, 2) NOT NULL,
    floor            INTEGER,
    price            INTEGER NOT NULL,
    price_per_pyeong NUMERIC(10, 0),
    is_canceled      BOOLEAN DEFAULT FALSE,
    reg_date         DATE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
-- FK indexes (Postgres does NOT auto-create indexes on FK columns)
CREATE INDEX IF NOT EXISTS idx_apartment_region ON apartments (region_id);
CREATE INDEX IF NOT EXISTS idx_sales_apartment ON sales_transactions (apartment_id);

-- 지역 필터
CREATE INDEX IF NOT EXISTS idx_region_sigungu ON regions (sigungu);

-- Partial indexes: 해제 거래(is_canceled) 제외
CREATE INDEX IF NOT EXISTS idx_sales_active_date
    ON sales_transactions (deal_date DESC)
    WHERE is_canceled = FALSE;

CREATE INDEX IF NOT EXISTS idx_sales_active_price
    ON sales_transactions (price)
    WHERE is_canceled = FALSE;

CREATE INDEX IF NOT EXISTS idx_sales_active_year_month
    ON sales_transactions (deal_year, deal_month)
    WHERE is_canceled = FALSE;

COMMIT;
