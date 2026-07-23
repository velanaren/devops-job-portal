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
