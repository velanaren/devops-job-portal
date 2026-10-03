CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    company          TEXT    NOT NULL,
    location_raw     TEXT,
    location_tag     TEXT    NOT NULL,
    job_type         TEXT,
    source_name      TEXT    NOT NULL,
    source_url       TEXT    NOT NULL,
    apply_url        TEXT    NOT NULL,
    posted_date      DATE,
    fetched_date     DATE    NOT NULL,
    skills           TEXT,
    experience_level TEXT,
    role_type        TEXT,
    dedup_key        TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs_staging (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    company          TEXT    NOT NULL,
    location_raw     TEXT,
    location_tag     TEXT,
    job_type         TEXT,
    source_name      TEXT    NOT NULL,
    source_url       TEXT,
    apply_url        TEXT,
    posted_date      DATE,
    fetched_date     DATE    NOT NULL,
    skills           TEXT,
    experience_level TEXT,
    role_type        TEXT,
    dedup_key        TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scrape_logs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date         DATE    NOT NULL,
    source_name      TEXT    NOT NULL,
    status           TEXT    NOT NULL,
    jobs_fetched     INTEGER DEFAULT 0,
    error_message    TEXT,
    http_status      INTEGER,
    duration_seconds REAL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-slug ATS polling history — drives hot/cold slug pruning.
CREATE TABLE IF NOT EXISTS slug_stats (
    ats               TEXT NOT NULL,
    slug              TEXT NOT NULL,
    last_checked_date DATE,
    last_hit_date     DATE,
    PRIMARY KEY (ats, slug)
);

-- Small key/value store: last_swap_at, run_lock.
CREATE TABLE IF NOT EXISTS scrape_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
