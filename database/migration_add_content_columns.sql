-- Migration: Add script and content columns to created_content table
-- Description: Add columns for video scripts, email content, and messages

-- Add new columns to created_content table
ALTER TABLE created_content
ADD COLUMN IF NOT EXISTS short_video_script TEXT,
ADD COLUMN IF NOT EXISTS long_video_script TEXT,
ADD COLUMN IF NOT EXISTS email_subject TEXT,
ADD COLUMN IF NOT EXISTS email_body TEXT,
ADD COLUMN IF NOT EXISTS message TEXT;

-- Create indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_created_content_short_video_script ON created_content(short_video_script) WHERE short_video_script IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_created_content_long_video_script ON created_content(long_video_script) WHERE long_video_script IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_created_content_email_subject ON created_content(email_subject) WHERE email_subject IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_created_content_email_body ON created_content(email_body) WHERE email_body IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_created_content_message ON created_content(message) WHERE message IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN created_content.short_video_script IS 'Script content for short-form videos (TikTok, Instagram Reels, YouTube Shorts)';
COMMENT ON COLUMN created_content.long_video_script IS 'Script content for long-form videos (YouTube, Vimeo)';
COMMENT ON COLUMN created_content.email_subject IS 'Email subject line for email content';
COMMENT ON COLUMN created_content.email_body IS 'Full email body content';
COMMENT ON COLUMN created_content.message IS 'Message content for messaging platforms (WhatsApp, SMS, etc.)';






