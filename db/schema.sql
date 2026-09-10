-- One row per brochure that has been loaded
CREATE TABLE IF NOT EXISTS brochures (
    brochure_id  INTEGER PRIMARY KEY,
    source_file  TEXT NOT NULL UNIQUE,  
    make         TEXT NOT NULL,
    model        TEXT NOT NULL,
    model_year   INTEGER,
    market       TEXT,
    loaded_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per feature per trim (one cell of the brochure grid)
CREATE TABLE IF NOT EXISTS features (
    feature_id   INTEGER PRIMARY KEY,
    brochure_id  INTEGER NOT NULL REFERENCES brochures(brochure_id),
    source_page  INTEGER NOT NULL,
    category     TEXT,
    feature      TEXT NOT NULL,
    trim         TEXT NOT NULL,
    value        TEXT NOT NULL,          -- standard, optional, not_available, unknown, or printed text like R17
    kind         TEXT NOT NULL CHECK (kind IN ('standard', 'optional', 'not_available', 'unknown', 'spec'))
);

CREATE INDEX IF NOT EXISTS idx_features_lookup ON features (brochure_id, trim, feature);