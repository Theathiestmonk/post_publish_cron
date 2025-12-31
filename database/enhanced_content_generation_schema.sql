-- Enhanced Content Generation Schema
-- Adds God-Mode content generation fields to created_content table
-- Run this after the main schema.sql and content_creation_schema.sql

-- Add God-Mode content generation columns to created_content table
ALTER TABLE created_content
ADD COLUMN IF NOT EXISTS archetype VARCHAR(50),
ADD COLUMN IF NOT EXISTS visual_metaphor TEXT,
ADD COLUMN IF NOT EXISTS hook_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS call_to_action TEXT,
ADD COLUMN IF NOT EXISTS engagement_question TEXT,
ADD COLUMN IF NOT EXISTS god_mode_metadata JSONB DEFAULT '{}'::jsonb;

-- Add comments for documentation
COMMENT ON COLUMN created_content.archetype IS 'Content archetype used for generation (provocative, bold_visionary, quirky_relatable, topical_punny)';
COMMENT ON COLUMN created_content.visual_metaphor IS 'Visual metaphor used for content and image generation';
COMMENT ON COLUMN created_content.hook_type IS 'Psychological hook type (Authority, Social Proof, FOMO, etc.)';
COMMENT ON COLUMN created_content.call_to_action IS 'Platform-specific call to action text';
COMMENT ON COLUMN created_content.engagement_question IS 'Question to drive user engagement/comments';
COMMENT ON COLUMN created_content.god_mode_metadata IS 'Complete God-Mode generation metadata (version, specs, etc.)';

-- Create index for archetype queries (useful for analytics)
CREATE INDEX IF NOT EXISTS idx_created_content_archetype ON created_content(archetype) WHERE archetype IS NOT NULL;

-- Create index for visual_metaphor searches
CREATE INDEX IF NOT EXISTS idx_created_content_visual_metaphor ON created_content USING gin (to_tsvector('english', visual_metaphor)) WHERE visual_metaphor IS NOT NULL;

-- Create index for god_mode_metadata JSON queries
CREATE INDEX IF NOT EXISTS idx_created_content_god_mode_metadata ON created_content USING gin (god_mode_metadata) WHERE god_mode_metadata IS NOT NULL;

-- Update existing records to have default archetype if missing
UPDATE created_content
SET archetype = 'provocative'
WHERE archetype IS NULL AND status = 'generated';

-- Optional: Add constraints for data integrity
-- ALTER TABLE created_content
-- ADD CONSTRAINT chk_archetype_valid CHECK (archetype IN ('provocative', 'bold_visionary', 'quirky_relatable', 'topical_punny'));

-- Optional: Add default values for new content
-- ALTER TABLE created_content
-- ALTER COLUMN god_mode_metadata SET DEFAULT '{"version": "1.0", "legacy": true}'::jsonb;

-- Grant permissions if needed (adjust based on your RLS policies)
-- GRANT SELECT, INSERT, UPDATE ON created_content TO authenticated;
