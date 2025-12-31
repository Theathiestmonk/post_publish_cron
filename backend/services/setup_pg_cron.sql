-- ============================================================================
-- SUPABASE PG_CRON SETUP FOR DAILY ANALYTICS COLLECTION
-- ============================================================================
-- 
-- Purpose:
-- --------
-- Alternative to APScheduler - uses PostgreSQL's pg_cron extension to
-- schedule the analytics collection job directly in the database.
--
-- Advantages:
-- -----------
-- - No backend process required
-- - Survives application restarts
-- - Native PostgreSQL scheduling
-- - Centralized job management
--
-- Prerequisites:
-- --------------
-- 1. pg_cron extension must be enabled in your Supabase project
-- 2. You need a webhook/API endpoint that triggers the collection
--
-- Setup Instructions:
-- -------------------
-- 1. Enable pg_cron extension (if not already enabled):
--    Supabase Dashboard > Database > Extensions > Enable pg_cron
--
-- 2. Create the cron job (run this SQL):
--    See commands below
--
-- 3. Create an API endpoint in your backend:
--    POST /api/internal/trigger-analytics-collection
--    (Protected by secret token)
--
-- ============================================================================

-- Step 1: Enable pg_cron extension (if needed)
-- Note: This requires superuser privileges, usually done via Supabase dashboard
-- CREATE EXTENSION IF NOT EXISTS pg_cron;


-- Step 2: Schedule the daily job
-- Runs every day at 2:00 AM UTC
SELECT cron.schedule(
    'daily-analytics-collection',           -- Job name
    '0 2 * * *',                            -- Cron expression (2:00 AM daily)
    $$
    -- This SQL block will be executed daily
    -- Option A: Call a PostgreSQL function that triggers collection
    -- Option B: Use pg_net to call an HTTP endpoint (preferred for complex logic)
    
    SELECT
        net.http_post(
            url := 'https://your-backend-url.com/api/internal/trigger-analytics-collection',
            headers := jsonb_build_object(
                'Content-Type', 'application/json',
                'X-Cron-Secret', 'YOUR_SECRET_TOKEN_HERE'  -- Replace with actual secret
            ),
            body := jsonb_build_object(
                'job', 'analytics_collection',
                'triggered_by', 'pg_cron',
                'timestamp', now()
            )
        ) AS request_id;
    $$
);


-- Step 3: Verify the job was created
SELECT * FROM cron.job WHERE jobname = 'daily-analytics-collection';


-- Step 4: View job run history
SELECT * FROM cron.job_run_details 
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'daily-analytics-collection')
ORDER BY start_time DESC
LIMIT 10;


-- ============================================================================
-- MANAGEMENT COMMANDS
-- ============================================================================

-- Unschedule the job (if needed)
-- SELECT cron.unschedule('daily-analytics-collection');

-- Re-schedule with different time (example: 3:00 AM)
-- SELECT cron.unschedule('daily-analytics-collection');
-- SELECT cron.schedule('daily-analytics-collection', '0 3 * * *', $$ ... $$);

-- Check all scheduled jobs
-- SELECT * FROM cron.job;

-- Check recent job runs
-- SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;


-- ============================================================================
-- ALTERNATIVE: PostgreSQL Function Approach (if you prefer)
-- ============================================================================
-- 
-- If you want to implement collection logic in PostgreSQL instead of Python:
--
-- CREATE OR REPLACE FUNCTION collect_daily_analytics()
-- RETURNS void AS $$
-- BEGIN
--     -- Your collection logic here
--     -- This would be complex and not recommended for API calls
--     -- Better to use the HTTP endpoint approach above
--     RAISE NOTICE 'Analytics collection triggered at %', now();
-- END;
-- $$ LANGUAGE plpgsql;
--
-- Then schedule it:
-- SELECT cron.schedule(
--     'daily-analytics-collection',
--     '0 2 * * *',
--     $$ SELECT collect_daily_analytics(); $$
-- );


-- ============================================================================
-- NOTES
-- ============================================================================
--
-- 1. SECURITY: Ensure the webhook endpoint is protected with authentication
--    - Use a secret token in headers
--    - Validate the token in your backend
--    - Rate limit the endpoint
--
-- 2. MONITORING: Check cron.job_run_details regularly for failures
--
-- 3. TIMEZONE: pg_cron uses UTC by default (same as APScheduler in our setup)
--
-- 4. ERROR HANDLING: If the HTTP call fails, pg_cron will log it but won't retry
--    - Implement retry logic in your endpoint if needed
--    - Monitor job_run_details for failure status
--
-- 5. TESTING: You can manually trigger by calling your endpoint:
--    curl -X POST https://your-backend/api/internal/trigger-analytics-collection \
--         -H "X-Cron-Secret: YOUR_SECRET" \
--         -H "Content-Type: application/json"
--
-- ============================================================================
