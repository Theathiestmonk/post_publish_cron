# Content Publishing Cron Job Setup

## Overview
This document describes the cron job setup for automatic content publishing from both `created_content` and `content_posts` tables. This solves the issue where the Python asyncio scheduler publishes multiple times when users log in with the same account during publishing time.

## Problem Solved
- **Before**: In-memory Python scheduler could publish the same posts multiple times when multiple users logged in simultaneously
- **After**: Cron job runs independently every minute, checking and publishing due posts once from both tables

## Architecture

### Data Flow
```
Cron Job (every minute)
  ↓
Query created_content table (status='scheduled')
  ↓
Calculate scheduled_datetime from scheduled_at OR (scheduled_date + scheduled_time)
  ↓
Filter posts where scheduled_datetime <= now
  ↓
Publish due posts from created_content
  ↓
Query content_posts table (status='scheduled')
  ↓
Calculate scheduled_datetime from scheduled_date + scheduled_time
  ↓
Filter posts where scheduled_datetime <= now
  ↓
Publish due posts from content_posts
```

### Table Support
The cron job supports both table structures during migration:

**created_content table:**
- Direct `user_id` field (no campaign relationship)
- Flexible scheduling: `scheduled_at` (timestamp) OR `scheduled_date` + `scheduled_time`
- `images[]` array for media
- `content_type` field (post, reel, carousel, etc.)

**content_posts table (existing):**
- `campaign_id` → `content_campaigns` → `user_id`
- Fixed scheduling: `scheduled_date` + `scheduled_time`
- `primary_image_url` or `metadata.carousel_images`
- `post_type` field

## Files Created
- `scripts/run_content_publisher.py` - Python script that publishes scheduled posts from both tables
- `scripts/run_content_publisher.sh` - Shell script wrapper with environment setup
- `services/content_publisher.py` - Shared publishing service with platform-specific logic
- `logs/content_publisher.log` - Log file for cron job execution

## Cron Job Details
- **Schedule**: Every 5 minutes (`*/5 * * * *`) - Recommended for testing
- **Alternative**: Every minute (`* * * * *`) for production
- **Command**: `/path/to/Agent_Emily/backend/scripts/run_content_publisher.sh`
- **Log File**: `/path/to/Agent_Emily/backend/logs/content_publisher.log`
- **Tables Processed**: Both `created_content` and `content_posts`

## Setup Instructions

### 1. Make Scripts Executable
```bash
cd backend
chmod +x scripts/run_content_publisher.py
chmod +x scripts/run_content_publisher.sh
chmod +x find_test_user.py
```

### 2. Setup Test User Account

#### For Testing (IMPORTANT - Prevents Content Mixing)
```bash
# Run the test user finder script
cd backend
python find_test_user.py
```

This will output something like:
```
✅ Found services@atsnai.com user!
   User ID: 12345678-1234-1234-1234-123456789abc
   Email: services@atsnai.com

📝 Add this to your .env file:
TEST_USER_ID=12345678-1234-1234-1234-123456789abc
TEST_USER_EMAIL=services@atsnai.com
```

Add these lines to your `backend/.env` file:
```env
TEST_USER_ID=your_services_user_id_here
TEST_USER_EMAIL=services@atsnai.com
```

#### Why Test Mode is Important
- **Without TEST_USER_ID**: Cron job processes ALL users' content (production mode)
- **With TEST_USER_ID**: Cron job only processes content from the test user (safe testing)
- **Prevents**: Mixing user content and posting to wrong social media accounts

### 3. Test the Script Manually
```bash
cd backend
./scripts/run_content_publisher.sh
```

### 4. Setup Cron Job
```bash
# Edit crontab
crontab -e

# For TESTING (every 5 minutes) - Perfect for your 5-minute scheduled posts:
*/5 * * * * /path/to/Agent_Emily/backend/scripts/run_content_publisher.sh >> /path/to/Agent_Emily/backend/logs/content_publisher.log 2>&1

# For PRODUCTION (every minute) - Use when confident system works:
# * * * * * /path/to/Agent_Emily/backend/scripts/run_content_publisher.sh >> /path/to/Agent_Emily/backend/logs/content_publisher.log 2>&1
```

**Why every 5 minutes for testing:**
- ✅ Allows time for your scheduled posts to become "due"
- ✅ Less server load during testing phase
- ✅ Easier to monitor and debug the process
- ✅ Perfect timing for your 5-minute scheduled posts

### 5. Verify Cron Job
```bash
# Check if cron is running
sudo systemctl status cron

# View cron logs
tail -f /path/to/Agent_Emily/backend/logs/content_publisher.log

# Test manually
cd /path/to/Agent_Emily/backend && ./scripts/run_content_publisher.sh
```

## How It Works

### Scheduling Logic

#### For created_content T7




able
1. **Query scheduled posts**: `SELECT * FROM created_content WHERE status = 'scheduled'`
2. **Parse scheduling info**:
   - If `scheduled_at` exists: Parse as ISO timestamp
   - Else: Combine `scheduled_date` + `scheduled_time` in user's timezone
3. **Convert to UTC**: Ensure all times are in UTC for comparison
4. **Filter due posts**: Where `scheduled_datetime <= now`

#### For content_posts Table
1. **Query scheduled posts**: `SELECT * FROM content_posts WHERE status = 'scheduled'`
2. **Parse scheduling info**: Combine `scheduled_date` + `scheduled_time` in user's timezone
3. **Convert to UTC**: For consistent comparison
4. **Filter due posts**: Where `scheduled_datetime <= now`

### Publishing Process

For each due post:
1. **Double-check status**: Query database to ensure post is still scheduled
2. **Check publishing flag**: Prevent concurrent publishing attempts
3. **Get platform connection**: Query `platform_connections` table
4. **Prepare post data**: Format according to platform requirements
5. **Publish to platform**: Call platform API (Facebook, Instagram, LinkedIn)
6. **Update status**: Set to 'published' or 'draft' on failure
7. **Log results**: Record success/failure with details

### Duplicate Prevention

1. **Database status checks**: Query current status before publishing
2. **Atomic publishing flag**: Set `_publishing: true` in metadata
3. **Timestamp validation**: Check `_publishing_at` to prevent stuck posts
4. **Idempotent operations**: Safe to run multiple times

### Carousel Post Handling

**For created_content:**
- Check `metadata.carousel_images` first
- Fall back to `images[]` array if `content_type == 'carousel'`

**For content_posts:**
- Check `metadata.carousel_images`
- Fall back to `primary_image_url`

### Platform Connection Lookup

- Query `platform_connections` table by `user_id` and `platform`
- Filter by `is_active = true`
- Decrypt `access_token_encrypted` using existing encryption logic
- Support all platform types: Facebook, Instagram, LinkedIn, YouTube

## Monitoring

### Check Logs
```bash
tail -f backend/logs/content_publisher.log
```

### Verify Publishing Activity
```sql
-- Check recent publishing from created_content
SELECT id, title, platform, status, scheduled_at, scheduled_date, scheduled_time,
       metadata->>'published_at' as published_at
FROM created_content
WHERE status IN ('published', 'draft')
AND (scheduled_at >= NOW() - INTERVAL '1 day'
     OR scheduled_date >= CURRENT_DATE - INTERVAL '1 day')
ORDER BY COALESCE(scheduled_at, (scheduled_date + scheduled_time)::timestamp) DESC;

-- Check recent publishing from content_posts
SELECT cp.id, cp.title, cp.platform, cp.status, cp.scheduled_date, cp.scheduled_time,
       cp.published_at, cc.campaign_name
FROM content_posts cp
LEFT JOIN content_campaigns cc ON cp.campaign_id = cc.id
WHERE cp.status IN ('published', 'draft')
AND cp.scheduled_date >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY cp.scheduled_date DESC, cp.scheduled_time DESC;
```

### Cron Job Status
```bash
# Check if cron job is active
crontab -l | grep content_publisher

# Check cron service
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog
```

## Troubleshooting

### Cron Not Running
```bash
# Check cron service
sudo systemctl status cron
sudo systemctl start cron

# Check cron logs
grep CRON /var/log/syslog
```

### Script Not Executable
```bash
chmod +x backend/scripts/run_content_publisher.sh
chmod +x backend/scripts/run_content_publisher.py
```

### Environment Issues
```bash
# Test environment loading
cd backend
./scripts/run_content_publisher.sh

# Check environment variables
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY
```

### Permission Issues
```bash
# Ensure user running cron can access files
ls -la backend/scripts/run_content_publisher.sh

# Check log file permissions
touch backend/logs/content_publisher.log
chmod 644 backend/logs/content_publisher.log
```

### Database Connection Issues
```bash
# Test Supabase connection
cd backend
python -c "
import os
from supabase import create_client
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
print('Connection successful:', client is not None)
"
```

### Publishing Failures

#### Check Platform Connections
```sql
-- Verify active connections
SELECT user_id, platform, page_name, is_active, last_sync
FROM platform_connections
WHERE is_active = true
ORDER BY user_id, platform;
```

#### Check Post Status Issues
```sql
-- Find posts stuck in publishing state
SELECT id, status, metadata->>'_publishing' as is_publishing,
       metadata->>'_publishing_at' as publishing_at
FROM created_content
WHERE metadata->>'_publishing' = 'true'
   OR status = 'scheduled';

SELECT cp.id, cp.status, cp.metadata->>'_publishing' as is_publishing,
       cc.campaign_name
FROM content_posts cp
LEFT JOIN content_campaigns cc ON cp.campaign_id = cc.id
WHERE cp.metadata->>'_publishing' = 'true'
   OR cp.status = 'scheduled';
```

#### Manual Post Publishing
```bash
# Test specific post publishing
cd backend
python -c "
import asyncio
from scheduler.post_publisher import PostPublisher
import os

publisher = PostPublisher(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
asyncio.run(publisher.check_and_publish_created_content())
asyncio.run(publisher.check_and_publish_scheduled_posts())
"
```

## Performance Considerations

### Query Optimization
- Indexes on `status`, `scheduled_date`, `scheduled_time`, `scheduled_at`
- Efficient filtering of future posts
- Batched processing of due posts

### Rate Limiting
- Platform API rate limits respected
- Concurrent publishing limited by database locks
- Publishing flag prevents duplicate attempts

### Error Handling
- Individual post failures don't stop batch processing
- Comprehensive logging for debugging
- Automatic retry for transient failures

## Migration Strategy

### During Transition
1. **Both systems active**: Cron job + existing web scheduler
2. **Monitor logs**: Ensure no duplicate publishing
3. **Gradual migration**: Move content from `content_posts` to `created_content`
4. **Test thoroughly**: Verify publishing works for both tables

### Post-Migration
1. **Disable old scheduler**: Comment out web scheduler calls
2. **Remove old code**: Clean up unused methods
3. **Update documentation**: Reflect single-table operation

## Security Considerations

### Token Handling
- Encrypted tokens stored in database
- Decryption happens in-memory only
- No token logging in plain text

### Database Access
- Service role key used for cron job
- Row-level security policies enforced
- Audit logging for all changes

### Error Information
- Sensitive data not logged
- Platform tokens masked in logs
- Error messages sanitized

## Benefits Over In-Memory Scheduler

### ✅ Reliability
- **Independent of user logins**: Runs regardless of user activity
- **Server restart safe**: Doesn't lose scheduled tasks
- **Consistent timing**: Runs exactly every minute

### ✅ Scalability
- **No memory usage**: No in-memory task queues
- **Database-driven**: Scales with database performance
- **Multi-server safe**: Works with load balancers

### ✅ Monitoring
- **Centralized logging**: All activity in one log file
- **Easy debugging**: Manual execution for testing
- **Standard tools**: Cron monitoring works

### ✅ Maintenance
- **Simple deployment**: Just cron job configuration
- **No cleanup needed**: No in-memory state management
- **Cross-platform**: Works on any server environment

## Expected Behavior

### Normal Operation
- **Every minute**: Cron job executes
- **Log entries**: Processing summary for both tables
- **Status updates**: Posts move from 'scheduled' to 'published'
- **Error handling**: Failed posts marked as 'draft' with error details

### Error Scenarios
- **Network issues**: Posts retried on next run
- **Platform errors**: Posts marked as draft with error message
- **Database issues**: Logged with full error details
- **Token issues**: Connection marked inactive

This cron job system ensures reliable, duplicate-free content publishing across your entire platform.
