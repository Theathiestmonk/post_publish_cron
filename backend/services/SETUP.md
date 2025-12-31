# Analytics Collection Setup Guide

## Quick Start (5 minutes)

### Step 1: Environment Variables

Add to your `.env` file:

```bash
# Protect internal endpoints (CHANGE THIS!)
INTERNAL_CRON_SECRET=your-strong-random-secret-here
```

> **Security Note**: Generate a strong random string for production:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

### Step 2: Verify Dependencies

All required packages are already in `requirements.txt`:
- ✅ `apscheduler` (for scheduling)
- ✅ `pytz` (for timezone management)
- ✅ `supabase` (database client)
- ✅ `cryptography` (token decryption)
- ✅ `requests` (API calls)

If you need to reinstall:
```bash
pip install -r requirements.txt
```

### Step 3: Start the Application

The scheduler starts automatically when the backend runs:

```bash
python main.py
```

You should see in logs:
```
Analytics collection scheduler started successfully
  Next run: 2025-12-20T02:00:00+00:00
```

### Step 4: Test the Collection (Optional)

Manually trigger a collection run to verify everything works:

```bash
curl -X POST http://localhost:8000/api/internal/analytics/trigger-collection \
  -H "X-Cron-Secret: your-strong-random-secret-here" \
  -H "Content-Type: application/json"
```

Expected response:
```json
{
  "success": true,
  "message": "Analytics collection job started in background",
  "triggered_at": "2025-12-19T12:30:00+05:30"
}
```

### Step 5: Verify Data Collection

Check your `analytics_snapshots` table:

```sql
-- Recent collections
SELECT 
    date,
    platform,
    metric,
    COUNT(*) as records,
    SUM(value) as total_value
FROM analytics_snapshots
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
  AND post_id IS NULL  -- Account-level only
GROUP BY date, platform, metric
ORDER BY date DESC, platform;
```

## What Happens Automatically

Once running, the system:

1. **Daily at 2:00 AM UTC**: Scheduler triggers collection
2. **For every user**: Fetches daily metrics from all connected platforms
3. **Stores in database**: Inserts normalized data into `analytics_snapshots`
4. **Logs results**: Records success/failure stats in application logs
5. **Emily/Orion can use**: The stored data becomes available for analytics queries

## Monitoring

### Check Scheduler Status

```bash
curl http://localhost:8000/api/internal/analytics/scheduler-status \
  -H "X-Cron-Secret: your-strong-random-secret-here"
```

Response:
```json
{
  "success": true,
  "data": {
    "status": "running",
    "jobs": [
      {
        "id": "daily_analytics_collection",
        "name": "Daily Analytics Collection",
        "next_run": "2025-12-20T02:00:00+00:00",
        "trigger": "cron[hour='2', minute='0']"
      }
    ]
  }
}
```

### Check Application Logs

Look for daily collection summaries:

```bash
grep "DAILY ANALYTICS COLLECTION" emily.log
```

Or in console output when running with `python main.py`.

## Alternative: Supabase pg_cron

If you prefer database-level scheduling instead of APScheduler:

1. **Enable pg_cron** in Supabase Dashboard:
   - Go to Database → Extensions
   - Enable `pg_cron`

2. **Run the setup SQL**:
   ```bash
   # Copy SQL from services/setup_pg_cron.sql
   # Run it in Supabase SQL Editor
   ```

3. **Update webhook URL** in the SQL:
   ```sql
   url := 'https://your-backend-url.com/api/internal/analytics/trigger-collection'
   ```

4. **Set secret** in SQL:
   ```sql
   'X-Cron-Secret', 'your-strong-random-secret-here'
   ```

5. **Disable APScheduler** (optional):
   - Comment out scheduler startup in `main.py` if using pg_cron exclusively

## Troubleshooting

### "No users with active connections"

**Cause**: No users have connected their social media accounts yet.

**Solution**: Connect at least one platform via the app, then test again.

### "Missing credentials for platform"

**Cause**: Platform connection exists but token is missing/invalid.

**Solution**: Check `platform_connections` table for valid `access_token` values.

### "Failed to decrypt token"

**Cause**: `ENCRYPTION_KEY` environment variable mismatch.

**Solution**: Ensure the same encryption key is used for both token storage and collection.

### "Scheduler not running"

**Cause**: Import error or startup failure.

**Solution**: 
1. Check logs for scheduler startup errors
2. Verify all dependencies installed
3. Ensure `services/scheduler.py` and `services/analytics_collector.py` exist

### "API rate limits exceeded"

**Cause**: Too many users/platforms, hitting API limits.

**Solution**: 
1. Add rate limiting in collector (sleep between API calls)
2. Spread collection across multiple times (batch users)
3. Increase API quota with platform providers

## Production Deployment

### Environment Variables

Ensure these are set in production:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ENCRYPTION_KEY=your-encryption-key
OPENAI_API_KEY=your-openai-key

# Analytics Collection
INTERNAL_CRON_SECRET=strong-random-secret-from-secrets.token_urlsafe
```

### Security Checklist

- [ ] `INTERNAL_CRON_SECRET` is a strong random value (not default)
- [ ] Internal endpoints are not exposed publicly (use firewall/VPC)
- [ ] Supabase service role key is kept secret
- [ ] Encryption key is securely stored

### Monitoring Setup

Consider adding:
- **Alerts** on collection failures (integrate with your monitoring system)
- **Metrics dashboard** showing daily collection counts
- **Log aggregation** (e.g., CloudWatch, Datadog) for centralized monitoring

## Next Steps

After setup is complete:

1. ✅ Wait for first automatic run (2:00 AM UTC)
2. ✅ Check logs for completion message
3. ✅ Query `analytics_snapshots` table to verify data
4. ✅ Test Emily's analytics queries to confirm they use the new data
5. ✅ Set up monitoring/alerts for production

## Support

If you encounter issues:

1. Check `services/README.md` for detailed documentation
2. Review logs for specific error messages
3. Test manual trigger endpoint to isolate scheduling vs. collection issues
4. Verify platform API credentials and permissions

---

**That's it!** Your analytics collection pipeline is now running automatically. 🎉
