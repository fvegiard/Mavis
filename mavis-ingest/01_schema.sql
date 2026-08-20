-- ============================================================
-- Mavis folder structure — created 2026-08-20
-- Project: francis-production-core (ref: tuwshovazpqzsvwnicgj)
-- Pattern: recursive folder/file model
-- ============================================================

-- Enable extensions needed for semantic search later
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram for fuzzy text search

-- Create the Mavis "folder" (schema) — keeps it separate from auth/storage
CREATE SCHEMA IF NOT EXISTS mavis;
COMMENT ON SCHEMA mavis IS 'Mavis self-knowledge base — inventory of tools, skills, agents, env, capabilities. Created 2026-08-20.';

-- Set search path so we don't have to qualify
SET search_path TO mavis, public;

-- ============================================================
-- Main table: mavis.items
-- Recursive folder/file model. Any "thing" Mavis knows about
-- is a row, with parent_id pointing to its folder.
-- ============================================================
CREATE TABLE IF NOT EXISTS mavis.items (
  id            BIGSERIAL PRIMARY KEY,
  parent_id     BIGINT REFERENCES mavis.items(id) ON DELETE CASCADE,
  -- kind: 'folder' (a container, has children) or 'file' (a leaf item)
  kind          TEXT NOT NULL CHECK (kind IN ('folder', 'file')),
  -- category: what kind of "thing" this is. NULL for folders, set for files.
  category      TEXT CHECK (category IN ('tool', 'skill', 'agent', 'env', 'structure', 'capability', 'memory', 'cron', 'drive', 'config')),
  -- name: short identifier (e.g. 'python3', 'web_search', 'claude')
  name          TEXT NOT NULL,
  -- title: human-readable name (e.g. 'Python 3.11', 'Web Search', 'Claude API')
  title         TEXT,
  -- description: 1-3 line summary
  description   TEXT,
  -- triggers: for skills, the keywords that trigger them (array of strings)
  triggers      TEXT[] DEFAULT '{}',
  -- payload: structured details (JSONB, free-form per category)
  payload       JSONB DEFAULT '{}'::jsonb,
  -- source: where this item came from (system prompt, env, mavis tool, etc.)
  source        TEXT,
  -- status: 'active' | 'inactive' | 'missing' | 'planned'
  status        TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'missing', 'planned', 'error')),
  -- embedding: for semantic search (text-embedding-3-small = 1536 dims)
  embedding     VECTOR(1536),
  -- timestamps
  created_at    TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at    TIMESTAMPTZ DEFAULT now() NOT NULL,
  -- unique name within a parent folder
  UNIQUE (parent_id, name)
);

-- Indexes for fast query
CREATE INDEX IF NOT EXISTS idx_items_parent      ON mavis.items (parent_id);
CREATE INDEX IF NOT EXISTS idx_items_category    ON mavis.items (category) WHERE category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_items_kind        ON mavis.items (kind);
CREATE INDEX IF NOT EXISTS idx_items_status      ON mavis.items (status);
CREATE INDEX IF NOT EXISTS idx_items_name        ON mavis.items (name);
CREATE INDEX IF NOT EXISTS idx_items_payload_gin ON mavis.items USING GIN (payload);
CREATE INDEX IF NOT EXISTS idx_items_name_trgm   ON mavis.items USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_items_desc_trgm   ON mavis.items USING GIN (description gin_trgm_ops);
-- IVFFlat index for vector similarity (cosine)
CREATE INDEX IF NOT EXISTS idx_items_embedding   ON mavis.items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION mavis.set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_items_updated_at ON mavis.items;
CREATE TRIGGER trg_items_updated_at
  BEFORE UPDATE ON mavis.items
  FOR EACH ROW EXECUTE FUNCTION mavis.set_updated_at();

-- ============================================================
-- RLS: public read, service_role write
-- ============================================================
ALTER TABLE mavis.items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS items_read_all ON mavis.items;
CREATE POLICY items_read_all ON mavis.items
  FOR SELECT TO anon, authenticated, service_role
  USING (true);

DROP POLICY IF EXISTS items_write_service ON mavis.items;
CREATE POLICY items_write_service ON mavis.items
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- ============================================================
-- Helper view: get the full tree starting from a folder
-- ============================================================
CREATE OR REPLACE VIEW mavis.tree AS
WITH RECURSIVE t AS (
  SELECT id, parent_id, kind, category, name, title, description, 0 AS depth,
         ARRAY[name]::text[] AS path, name AS path_string
  FROM mavis.items
  WHERE parent_id IS NULL
  UNION ALL
  SELECT i.id, i.parent_id, i.kind, i.category, i.name, i.title, i.description, t.depth + 1,
         t.path || i.name, t.path_string || '/' || i.name
  FROM mavis.items i
  JOIN t ON i.parent_id = t.id
)
SELECT * FROM t;

-- ============================================================
-- Helper view: count by category
-- ============================================================
CREATE OR REPLACE VIEW mavis.summary AS
SELECT
  kind,
  category,
  status,
  count(*) AS n
FROM mavis.items
GROUP BY kind, category, status
ORDER BY kind, category, status;

COMMENT ON TABLE  mavis.items IS 'Mavis self-knowledge — every tool/skill/agent/env/capability as a row in a recursive folder tree.';
COMMENT ON VIEW   mavis.tree  IS 'Recursive view of the Mavis folder tree, with full path and depth.';
COMMENT ON VIEW   mavis.summary IS 'Count of items by kind/category/status — quick health check.';
