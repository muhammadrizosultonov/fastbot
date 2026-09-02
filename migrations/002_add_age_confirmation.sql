-- Existing installations must apply this after 001_initial.sql.
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_confirmed BOOLEAN NOT NULL DEFAULT false;
