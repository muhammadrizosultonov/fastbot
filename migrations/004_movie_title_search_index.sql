-- Supports the indexed, case-insensitive title prefix search used by ordinary users.
CREATE INDEX IF NOT EXISTS movies_title_prefix_idx
    ON movies (lower(title) text_pattern_ops) WHERE is_active AND title IS NOT NULL;
