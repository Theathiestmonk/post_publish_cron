# Analytics Scripts Documentation

This directory contains scripts for managing analytics data: fetching platform connections, decrypting tokens, collecting analytics, and storing snapshots.

## 📁 Script Overview

| Script | Purpose | Key Features |
|--------|---------|--------------|
| `fetch_store_analytics.py` | Fetch analytics and store snapshots | Single user, platform-specific, detailed logging |
| `get_platform_data.py` | Get platform connection data | View connections, decrypt tokens, connection status |
| `batch_analytics_fetch.py` | Batch process multiple users | Parallel processing, user discovery, aggregate reporting |
| `test_analytics_scripts.py` | Test all analytics functionality | Comprehensive testing, validation, diagnostics |

## 🔧 Prerequisites

### Environment Variables

Make sure these are set in your environment:

```bash
# Required
SUPABASE_URL=your_supabase_url
ENCRYPTION_KEY=your_32_char_encryption_key

# Choose one (service key preferred for scripts)
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
# OR
SUPABASE_ANON_KEY=your_anon_key
```

### Dependencies

```bash
pip install supabase requests cryptography
```

## 🚀 Usage Examples

### 1. Get Platform Data for a User

```bash
# Basic platform data (no tokens shown)
python scripts/get_platform_data.py 58d91fe2-1401-46fd-b183-a2a118997fc1

# Using service role key
python scripts/get_platform_data.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --service-key

# Show decrypted tokens (WARNING: only in secure environments)
python scripts/get_platform_data.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --service-key --decrypt-tokens
```

**Output:**
```
📊 Platform Connections (2 found)

1. INSTAGRAM Connection
   ID: 123e4567-e89b-12d3-a456-426614174000
   User ID: 58d91fe2-1401-46fd-b183-a2a118997fc1
   Platform: instagram
   Account ID: 17841471587449285
   Active: ✅
   Status: active
   Created: 2024-01-15T10:30:00Z
   Token Encrypted: ✅ (256 chars)

2. FACEBOOK Connection
   ID: 987fcdeb-51a2-43d7-8f9e-123456789abc
   User ID: 58d91fe2-1401-46fd-b183-a2a118997fc1
   Platform: facebook
   Page ID: 123456789
   Page Name: My Business Page
   Active: ✅
   Status: active
   Created: 2024-01-15T10:30:00Z
   Token Encrypted: ✅ (256 chars)

📈 Summary:
   Total connections: 2
   Active connections: 2
   Platforms: instagram, facebook
```

### 2. Fetch and Store Analytics for a User

```bash
# Fetch all platforms, last 7 days
python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1

# Fetch specific platform
python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --platform instagram

# Fetch with custom date range
python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --days 30

# Using service role key
python scripts/fetch_store_analytics.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --service-key
```

**Output:**
```
ANALYTICS FETCH & STORE OPERATION STARTED
User ID: 58d91fe2-1401-46fd-b183-a2a118997fc1
Platform filter: all
Days back: 7
Timestamp: 2024-01-15T14:30:00
================================================================================

🔄 Processing instagram...
✅ Instagram analytics fetched successfully
📊 Instagram: Stored 4 snapshots

🔄 Processing facebook...
✅ Facebook analytics fetched successfully
📊 Facebook: Stored 6 snapshots

ANALYTICS FETCH & STORE OPERATION COMPLETED
Duration: 12.34 seconds
Connections found: 2
Platforms processed: 2
Successful platforms: 2
Failed platforms: 0
Total snapshots stored: 10
================================================================================

📊 Analytics Operation Summary:
User ID: 58d91fe2-1401-46fd-b183-a2a118997fc1
Connections found: 2
Platforms processed: 2
Successful: 2
Failed: 0
Snapshots stored: 10

📈 Platform Results:
  ✅ instagram: 4 snapshots
  ✅ facebook: 6 snapshots

🎉 Operation completed successfully!
```

### 3. Batch Process Multiple Users

```bash
# Process up to 5 users
python scripts/batch_analytics_fetch.py --max-users 5

# Process users for specific platform
python scripts/batch_analytics_fetch.py --platform instagram --max-users 10

# Process with custom date range and workers
python scripts/batch_analytics_fetch.py --days 30 --workers 5 --max-users 20

# Using service role key
python scripts/batch_analytics_fetch.py --service-key --max-users 3
```

**Output:**
```
================================================================================
BATCH ANALYTICS PROCESSING STARTED
================================================================================
Users to process: 3
Platform filter: all
Days back: 7
Max workers: 3
Timestamp: 2024-01-15T14:30:00
================================================================================

🔄 Processing user: user1...
✅ User user1: 8 snapshots

🔄 Processing user: user2...
✅ User user2: 6 snapshots

🔄 Processing user: user3...
❌ User user3 failed: No active connections

================================================================================
BATCH ANALYTICS PROCESSING COMPLETED
================================================================================
Duration: 18.45 seconds
Total users: 3
Processed: 3
Successful: 2
Failed: 1
Total snapshots stored: 14
Average processing time: 6.15 seconds per user
================================================================================

📈 Batch Processing Summary:
Total users: 3
Processed: 3
Successful: 2
Failed: 1
Total snapshots stored: 14
Average snapshots per user: 7.0

👥 User Results:
✅ Successful users (2):
   user1: 8 snapshots
   user2: 6 snapshots
❌ Failed users (1):
   user3: No active connections
```

### 4. Test All Analytics Functionality

```bash
# Run comprehensive tests
python scripts/test_analytics_scripts.py 58d91fe2-1401-46fd-b183-a2a118997fc1
```

**Output:**
```
🚀 Analytics Scripts Test Suite
============================================================
User ID: 58d91fe2-1401-46fd-b183-a2a118997fc1
Timestamp: 2024-01-15T14:30:00
============================================================

🔍 Testing Platform Data Retrieval
==================================================
✅ Found 2 platform connections
✅ Active connections: 2
Platforms found:
  - instagram: ✅ ACTIVE
  - facebook: ✅ ACTIVE

✅ PASSED: Platform Data Retrieval

🔐 Testing Token Decryption
==================================================
✅ Tokens decrypted: 2/2

✅ PASSED: Token Decryption

📊 Testing Analytics Fetching
==================================================
✅ Analytics fetch result: True
✅ Snapshots stored: 4
✅ Platforms processed: 1

✅ PASSED: Analytics Fetching

🔍 Testing Snapshot Querying
==================================================
✅ Found 10 recent snapshots
✅ Analytics summary generated successfully
   Platforms: 2
   Metrics: 4
   Total snapshots: 45

✅ PASSED: Snapshot Querying

============================================================
📊 TEST RESULTS SUMMARY
============================================================
✅ Platform Data Retrieval
✅ Token Decryption
✅ Analytics Fetching
✅ Snapshot Querying

📈 Overall: 4/4 tests passed
🎉 All tests passed! Analytics system is working correctly.
```

## 🔧 Advanced Usage

### Custom Analytics Fetching

```python
from scripts.fetch_store_analytics import AnalyticsFetcher

# Initialize fetcher
fetcher = AnalyticsFetcher(use_service_key=True)

# Custom analytics fetching
result = fetcher.fetch_and_store_user_analytics(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    days_back=30
)

# Check results
if result["successful_platforms"] > 0:
    print(f"Success! Stored {result['total_snapshots_stored']} snapshots")
```

### Platform Data Inspection

```python
from scripts.get_platform_data import PlatformDataFetcher

# Get platform data
fetcher = PlatformDataFetcher(use_service_key=True)
connections = fetcher.get_user_platform_data("user_id", decrypt_tokens=True)

# Inspect connections
for conn in connections:
    if conn.is_active:
        print(f"Active {conn.platform} connection: {conn.account_id}")
        if conn.access_token_decrypted:
            # WARNING: Only log in secure environments
            print(f"Token length: {len(conn.access_token_decrypted)}")
```

### Batch Processing with Custom Logic

```python
from scripts.batch_analytics_fetch import BatchAnalyticsProcessor

# Custom batch processing
processor = BatchAnalyticsProcessor(use_service_key=True, max_workers=5)

# Get users with connections
user_ids = processor.get_users_with_connections(limit=20)

# Process with custom parameters
batch_result = processor.process_batch(
    user_ids=user_ids,
    platform="instagram",
    days_back=14
)

print(f"Processed {batch_result['successful_users']} users successfully")
```

## 📊 Data Flow

```
User ID ──► Platform Connections Table ──► Decrypt Tokens ──► API Calls ──► Store Snapshots
              (service/anon key)              (Fernet)        (Instagram/Facebook)   (analytics_snapshots)
```

## 🔒 Security Considerations

### Token Handling
- Access tokens are encrypted at rest using Fernet (AES-256)
- Decryption only happens in memory during API calls
- Never log decrypted tokens in production code
- Use `--decrypt-tokens` only in secure development environments

### Database Access
- Service role key has full database access - use carefully
- Anon key has RLS restrictions - safer for read operations
- All operations are user-scoped through RLS policies

### API Rate Limits
- Respect platform API rate limits
- Batch processing includes delays between users
- Monitor API errors and implement backoff strategies

## 🐛 Troubleshooting

### Common Issues

1. **"SUPABASE_URL environment variable not found"**
   - Set the `SUPABASE_URL` environment variable
   - Check your `.env` file or environment configuration

2. **"No active platform connections found"**
   - User has no connected social media accounts
   - Connections exist but are marked as inactive
   - Check platform connection status in database

3. **"Token decryption failed"**
   - ENCRYPTION_KEY not set or incorrect
   - Tokens may not be encrypted (older format)
   - Check encryption key length (32 characters for Fernet)

4. **"Platform API error"**
   - Access token may be expired
   - Insufficient permissions (need read_insights, instagram_manage_insights)
   - API rate limits exceeded
   - Network connectivity issues

5. **"No analytics data extracted"**
   - Account may have no analytics data available
   - Date range may be too restrictive
   - Platform API may not support requested metrics

### Debug Mode

Enable debug logging:

```bash
export PYTHONPATH=/path/to/backend:$PYTHONPATH
python -c "import logging; logging.basicConfig(level=logging.DEBUG)" && python scripts/fetch_store_analytics.py user_id
```

### Manual Testing

Test individual components:

```bash
# Test database connection
python -c "from supabase import create_client; print('DB connection OK')"

# Test token decryption
python -c "
from cryptography.fernet import Fernet
import os
key = os.getenv('ENCRYPTION_KEY')
cipher = Fernet(key.encode())
print('Encryption key OK')
"

# Test platform API
python -c "
import requests
# Test with known working token
response = requests.get('https://graph.facebook.com/v18.0/me', params={'access_token': 'test_token'})
print(f'API response: {response.status_code}')
"
```

## 📈 Performance Tips

### Batch Processing
- Use multiple workers for parallel processing
- Limit batch size to avoid overwhelming APIs
- Monitor memory usage with large batches
- Consider API rate limits when setting worker counts

### Database Optimization
- Use UPSERT operations to avoid duplicates
- Batch database operations when possible
- Monitor query performance with large datasets
- Consider indexing on frequently queried columns

### Memory Management
- Process users in smaller batches for large operations
- Clean up large data structures after processing
- Monitor memory usage in long-running processes
- Use streaming for very large result sets

## 🔄 Automation

### Cron Jobs

Set up automated analytics collection:

```bash
# Daily analytics collection at 2 AM
crontab -e
# Add: 0 2 * * * cd /path/to/project && python backend/scripts/batch_analytics_fetch.py --max-users 50 --service-key

# Weekly summary reports
# Add: 0 3 * * 1 cd /path/to/project && python backend/scripts/generate_analytics_report.py
```

### Systemd Service

Create a systemd service for reliable automation:

```ini
# /etc/systemd/system/analytics-collector.service
[Unit]
Description=Analytics Data Collector
After=network.target

[Service]
Type=oneshot
User=analytics
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 backend/scripts/batch_analytics_fetch.py --max-users 100 --service-key
```

## 📞 Support

For issues with analytics scripts:

1. Run the test script to identify problems:
   ```bash
   python scripts/test_analytics_scripts.py user_id
   ```

2. Check logs for detailed error information

3. Verify environment variables and permissions

4. Test individual components in isolation

5. Check platform API status and documentation

The analytics scripts are designed to be robust, secure, and scalable for production use.
