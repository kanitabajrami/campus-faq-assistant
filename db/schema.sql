-- Campus FAQ Assistant: Week 2 schema (SQLite)
-- Create the database with:  python src/build_db.py   (or: sqlite3 db/campus_faq.db < db/schema.sql)
PRAGMA foreign_keys = ON;

CREATE TABLE category (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE faq (
    faq_id        TEXT PRIMARY KEY,                       -- e.g. FAQ001
    category_id   INTEGER NOT NULL REFERENCES category(category_id),
    question      TEXT NOT NULL COLLATE NOCASE UNIQUE,    -- no duplicate questions
    answer        TEXT NOT NULL CHECK (length(trim(answer)) > 0),
    source_url    TEXT,
    last_verified TEXT                                    -- ISO date YYYY-MM-DD
);

CREATE TABLE test_query (
    query_id        TEXT PRIMARY KEY,                     -- e.g. Q01
    query_text      TEXT NOT NULL,
    expected_faq_id TEXT REFERENCES faq(faq_id),          -- NULL = out of scope
    query_type      TEXT NOT NULL CHECK (query_type IN
        ('in_scope_direct','in_scope_paraphrase','out_of_scope_unrelated','out_of_scope_near_miss')),
    source          TEXT NOT NULL DEFAULT 'synthetic_manual'
);

CREATE TABLE test_run (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    method       TEXT NOT NULL,                           -- 'keyword_baseline'
    min_overlap  INTEGER NOT NULL,                        -- accept threshold
    run_at       TEXT NOT NULL,                           -- ISO timestamp
    n_queries    INTEGER NOT NULL,
    n_correct    INTEGER NOT NULL
);

CREATE TABLE test_result (
    result_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           INTEGER NOT NULL REFERENCES test_run(run_id),
    query_id         TEXT    NOT NULL REFERENCES test_query(query_id),
    predicted_faq_id TEXT REFERENCES faq(faq_id),         -- NULL = rejected
    overlap_score    INTEGER NOT NULL CHECK (overlap_score >= 0),
    accepted         INTEGER NOT NULL CHECK (accepted IN (0,1)),
    correct          INTEGER NOT NULL CHECK (correct IN (0,1))
);

CREATE INDEX idx_faq_category ON faq(category_id);
CREATE INDEX idx_result_run   ON test_result(run_id);
