-- Migration: Change migration_diagrams.svg_data (bytea) to svg_base64 (text)
-- Run this script once against your PostgreSQL database.
-- Development environment — no live data assumed.

BEGIN;

-- Step 1: Add new text column
ALTER TABLE migration_diagrams
    ADD COLUMN IF NOT EXISTS svg_base64 TEXT;

-- Step 2: Populate svg_base64 from existing bytea data (base64-encode the stored bytes)
UPDATE migration_diagrams
SET svg_base64 = encode(svg_data, 'base64')
WHERE svg_data IS NOT NULL AND svg_base64 IS NULL;

-- Step 3: Make it NOT NULL (after data migration)
ALTER TABLE migration_diagrams
    ALTER COLUMN svg_base64 SET NOT NULL;

-- Step 4: Drop old bytea column
ALTER TABLE migration_diagrams
    DROP COLUMN IF EXISTS svg_data;

COMMIT;

-- ─────────────────────────────────────────────────────────────────────────────
-- Stored Procedure: set_migration_diagram_svg
-- Replaces the old version that decoded base64 → bytea for storage.
-- Now stores the base64 string directly as TEXT.
-- Adjust the body to match your exact table/column/FK structure.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_migration_diagram_svg(
    p_migration_name    TEXT,
    p_diagram_type      TEXT,
    p_svg_base64        TEXT,
    p_file_name         TEXT      DEFAULT NULL,
    p_user_id           INTEGER   DEFAULT NULL,
    p_scope             INTEGER   DEFAULT 1
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_migration_id      INTEGER;
    v_diagram_type_id   INTEGER;
    v_diagram_id        INTEGER;
    v_sha256            TEXT;
BEGIN
    -- Resolve migration record
    SELECT id INTO v_migration_id
    FROM migration_data
    WHERE migration_name = p_migration_name
      AND (p_user_id IS NULL OR user_id = p_user_id)
    LIMIT 1;

    IF v_migration_id IS NULL THEN
        RAISE EXCEPTION 'Migration not found: %', p_migration_name;
    END IF;

    -- Resolve or insert diagram type
    SELECT id INTO v_diagram_type_id
    FROM diagram_types
    WHERE type = p_diagram_type
    LIMIT 1;

    IF v_diagram_type_id IS NULL THEN
        INSERT INTO diagram_types (type) VALUES (p_diagram_type)
        RETURNING id INTO v_diagram_type_id;
    END IF;

    -- Compute SHA-256 of the raw SVG bytes (decoded from base64) for deduplication
    v_sha256 := encode(digest(decode(p_svg_base64, 'base64'), 'sha256'), 'hex');

    -- Upsert diagram record (store base64 text directly)
    INSERT INTO migration_diagrams (migration_id, diagram_type_id, scope, svg_base64, sha256, file_name, byte_size)
    VALUES (v_migration_id, v_diagram_type_id, p_scope, p_svg_base64, v_sha256, p_file_name, length(decode(p_svg_base64, 'base64')))
    ON CONFLICT (migration_id, diagram_type_id, scope)
    DO UPDATE SET
        svg_base64 = EXCLUDED.svg_base64,
        sha256     = EXCLUDED.sha256,
        file_name  = COALESCE(EXCLUDED.file_name, migration_diagrams.file_name),
        byte_size  = EXCLUDED.byte_size
    RETURNING id INTO v_diagram_id;

    RETURN v_diagram_id;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- Stored Procedure: get_migration_diagram_svg
-- Returns the base64 TEXT directly (no more encode/decode round-trip).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION get_migration_diagram_svg(
    p_migration_name    TEXT,
    p_diagram_type      TEXT,
    p_user_id           INTEGER   DEFAULT NULL,
    p_scope             INTEGER   DEFAULT 1
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_migration_id    INTEGER;
    v_diagram_type_id INTEGER;
    v_svg_base64      TEXT;
BEGIN
    SELECT id INTO v_migration_id
    FROM migration_data
    WHERE migration_name = p_migration_name
      AND (p_user_id IS NULL OR user_id = p_user_id)
    LIMIT 1;

    IF v_migration_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT id INTO v_diagram_type_id
    FROM diagram_types
    WHERE type = p_diagram_type
    LIMIT 1;

    IF v_diagram_type_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT svg_base64 INTO v_svg_base64
    FROM migration_diagrams
    WHERE migration_id = v_migration_id
      AND diagram_type_id = v_diagram_type_id
      AND scope = p_scope
    LIMIT 1;

    RETURN v_svg_base64;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- Stored Procedure: get_migration_diagrams
-- Returns JSON array: [{diagram_type, svg_base64, file_name}, ...]
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION get_migration_diagrams(
    p_migration_name    TEXT,
    p_user_id           INTEGER   DEFAULT NULL,
    p_scope             INTEGER   DEFAULT 1
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    v_migration_id INTEGER;
BEGIN
    SELECT id INTO v_migration_id
    FROM migration_data
    WHERE migration_name = p_migration_name
      AND (p_user_id IS NULL OR user_id = p_user_id)
    LIMIT 1;

    IF v_migration_id IS NULL THEN
        RETURN '[]'::json;
    END IF;

    RETURN (
        SELECT json_agg(
            json_build_object(
                'diagram_type', dt.type,
                'svg_base64',   md.svg_base64,
                'file_name',    md.file_name
            )
        )
        FROM migration_diagrams md
        JOIN diagram_types dt ON dt.id = md.diagram_type_id
        WHERE md.migration_id = v_migration_id
          AND md.scope = p_scope
    );
END;
$$;
