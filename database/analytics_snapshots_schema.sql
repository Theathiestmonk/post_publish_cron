-- Analytics Snapshots Table Schema
-- Stores time-series analytics data for caching and historical analysis
-- Supports both social media and blog analytics
-- Automatically maintains only last 30 days of data per user per platform per metric

-- Create Analytics Snapshots Table
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Platform and source identification
    platform TEXT NOT NULL, -- instagram, facebook, youtube, linkedin, twitter, pinterest, wordpress, etc.
    source TEXT NOT NULL CHECK (source IN ('social_media', 'blog')), -- social_media | blog
    
    -- Metric identification
    metric TEXT NOT NULL, -- reach, impressions, engagement, likes, comments, views, etc.
    
    -- Value and date
    value NUMERIC NOT NULL DEFAULT 0, -- The metric value
    date DATE NOT NULL, -- The date this snapshot represents
    
    -- Optional post/article reference
    post_id TEXT, -- For post-level metrics (references content_posts.id or social_media_posts.id)
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb, -- Additional context (e.g., API response details)
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- When this record was created
    
    -- Constraints
    CONSTRAINT unique_user_platform_metric_date_post UNIQUE (user_id, platform, source, metric, date, post_id)
);

-- Create indexes for better query performance
-- Index for user queries (most common)
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_id ON analytics_snapshots(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_platform ON analytics_snapshots(user_id, platform);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_platform_source ON analytics_snapshots(user_id, platform, source);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_platform_metric ON analytics_snapshots(user_id, platform, metric);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_date ON analytics_snapshots(date DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_date ON analytics_snapshots(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_platform_date ON analytics_snapshots(user_id, platform, date DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_user_platform_metric_date ON analytics_snapshots(user_id, platform, metric, date DESC);

-- Composite index for common query pattern: user + platform + source + metric + date range
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_query_pattern ON analytics_snapshots(user_id, platform, source, metric, date DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE analytics_snapshots ENABLE ROW LEVEL SECURITY;

-- RLS Policies for analytics_snapshots
-- Users can view their own snapshots
CREATE POLICY "Users can view own analytics snapshots" ON analytics_snapshots
    FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own snapshots
CREATE POLICY "Users can insert own analytics snapshots" ON analytics_snapshots
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own snapshots
CREATE POLICY "Users can update own analytics snapshots" ON analytics_snapshots
    FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own snapshots
CREATE POLICY "Users can delete own analytics snapshots" ON analytics_snapshots
    FOR DELETE USING (auth.uid() = user_id);

-- Function to automatically clean up snapshots older than 30 days
-- This ensures we only keep last 30 days of data per user per platform per metric
CREATE OR REPLACE FUNCTION cleanup_old_analytics_snapshots()
RETURNS void AS $$
BEGIN
    DELETE FROM analytics_snapshots
    WHERE date < CURRENT_DATE - INTERVAL '30 days';
    
    -- Log cleanup (optional, can be removed if not needed)
    RAISE NOTICE 'Cleaned up analytics snapshots older than 30 days';
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to run cleanup daily (requires pg_cron extension)
-- Note: This requires pg_cron extension to be enabled in Supabase
-- If pg_cron is not available, cleanup can be triggered manually or via backend cron job
-- Uncomment if pg_cron is enabled:
-- SELECT cron.schedule('cleanup-analytics-snapshots', '0 2 * * *', 'SELECT cleanup_old_analytics_snapshots()');

-- Add comments for documentation
COMMENT ON TABLE analytics_snapshots IS 'Stores time-series analytics snapshots for caching and historical analysis. Automatically maintains only last 30 days of data.';
COMMENT ON COLUMN analytics_snapshots.platform IS 'Platform name: instagram, facebook, youtube, linkedin, twitter, pinterest, wordpress, etc.';
COMMENT ON COLUMN analytics_snapshots.source IS 'Source type: social_media or blog';
COMMENT ON COLUMN analytics_snapshots.metric IS 'Metric name: reach, impressions, engagement, likes, comments, views, etc.';
COMMENT ON COLUMN analytics_snapshots.value IS 'The metric value at this date';
COMMENT ON COLUMN analytics_snapshots.date IS 'The date this snapshot represents (not when it was recorded)';
COMMENT ON COLUMN analytics_snapshots.post_id IS 'Optional: For post-level metrics, references the post/article ID';
COMMENT ON COLUMN analytics_snapshots.metadata IS 'Additional context stored as JSONB (e.g., API response details, calculation method)';


