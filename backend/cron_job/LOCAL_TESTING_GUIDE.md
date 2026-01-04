# 🏠 Local Testing Guide for Scheduled Content Publishing

This guide shows you how to test the cron job functionality locally on your Windows machine before deploying to Render.

## 📋 Available Testing Options

### 1. **Interactive Test Menu** (Recommended for exploration)
Run an interactive menu to test different aspects of the publishing system.

### 2. **Local Cron Scheduler**
Simulate a real cron job that runs every minute.

### 3. **One-Time Publishing Check**
Run a single check for scheduled content (like the cron job does).

### 4. **Create Test Data**
Generate test scheduled content for testing.

## 🚀 How to Test Locally

### Option A: Using Batch File (Easiest)

```cmd
cd "C:\Users\Lenovo\Desktop\Emily app\Agent_Emily\backend"
run_local_tests.bat
```

### Option B: Using PowerShell Script

```powershell
cd "C:\Users\Lenovo\Desktop\Emily app\Agent_Emily\backend"
.\test_scheduled_publishing.ps1
```

Or run specific modes:
```powershell
# Interactive menu
.\test_scheduled_publishing.ps1 -Mode menu

# Local scheduler
.\test_scheduled_publishing.ps1 -Mode scheduler

# One-time check
.\test_scheduled_publishing.ps1 -Mode check

# Create test data
.\test_scheduled_publishing.ps1 -Mode create
```

### Option C: Manual Python Execution

```bash
cd "C:\Users\Lenovo\Desktop\Emily app\Agent_Emily\backend"

# Interactive test menu
python test_scheduled_publishing.py

# Local cron scheduler
python local_cron_scheduler.py

# One-time check
python -c "
import asyncio
from test_scheduled_publishing import ScheduledPublishingTester

async def run_check():
    tester = ScheduledPublishingTester()
    await tester.find_scheduled_content()

asyncio.run(run_check())
"
```

## 🔧 Setting Up Test Data

### 1. Create Test Scheduled Content

Run the test script and choose option 3, or use:

```python
# In Python console or script
import asyncio
from test_scheduled_publishing import ScheduledPublishingTester

async def create_test():
    tester = ScheduledPublishingTester()
    content_id = await tester.create_test_scheduled_content()
    print(f"Created test content: {content_id}")

asyncio.run(create_test())
```

### 2. Manually Insert Test Data

```sql
-- Insert test scheduled content
INSERT INTO created_content (
    user_id,
    title,
    content,
    platform,
    channel,
    status,
    scheduled_at
) VALUES (
    'your-user-id-here',
    'Test Post',
    'This is a test scheduled post',
    'facebook',
    'social media',
    'scheduled',
    NOW() + INTERVAL '1 minute'
);
```

## 🔍 What Gets Tested

### Database Queries
- ✅ Find scheduled content where `status = 'scheduled'` and `scheduled_at <= NOW()`
- ✅ Check for duplicate prevention flags in `god_mode_metadata`

### Platform Connections
- ✅ Validate active platform connections exist
- ✅ Test token decryption
- ✅ Check connection status

### Publishing Logic
- ✅ Route by channel (social media, blog, email, messages)
- ✅ Platform-specific publishing preparation
- ✅ Status updates after publishing

## 📊 Test Results

The test scripts will show you:

```
🔍 Found X scheduled content items
✅ Facebook connection found for user USER_ID
🚀 Publishing content CONTENT_ID to facebook (social media) for user USER_ID
✅ Successfully published content CONTENT_ID
```

## 🛠️ Troubleshooting

### Python Not Found
```cmd
# Check if Python is installed
python --version

# If not found, install Python and add to PATH
# Or use full path: C:\Python39\python.exe test_scheduled_publishing.py
```

### Import Errors
```cmd
# Install missing dependencies
pip install python-dotenv supabase cryptography pytz httpx
```

### Database Connection Issues
- ✅ Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- ✅ Ensure `ENCRYPTION_KEY` is set for token decryption

### No Test Data Found
```sql
-- Check if you have scheduled content
SELECT COUNT(*) FROM created_content WHERE status = 'scheduled';

-- View your scheduled content
SELECT id, title, platform, scheduled_at, status
FROM created_content
WHERE status = 'scheduled'
ORDER BY scheduled_at;
```

## 🎯 Next Steps

### 1. Test with Real Data
- Create actual scheduled content through your frontend
- Set `scheduled_at` to a time in the past to trigger immediate publishing
- Test with different platforms

### 2. Test Platform Publishing
- Ensure platform connections are active
- Test with Facebook first (most common)
- Verify API permissions and tokens

### 3. Deploy to Render
- Once local testing works, deploy the cron endpoint
- Set up Render cron job as described in the main plan
- Monitor the logs for successful publishing

## 📝 Test Checklist

- [ ] Python environment working
- [ ] Database connection successful
- [ ] Can find scheduled content
- [ ] Platform connections validated
- [ ] Publishing logic works
- [ ] Status updates correctly
- [ ] No duplicate publishing
- [ ] Error handling works

## 🚨 Important Notes

1. **Test Data**: The test scripts create/find real data in your database
2. **Platform Limits**: Be careful not to spam platforms during testing
3. **Tokens**: Ensure your platform tokens are valid and have necessary permissions
4. **Cleanup**: Delete test content after testing

---

**Happy Testing!** 🎉 Test locally first, then deploy with confidence!
