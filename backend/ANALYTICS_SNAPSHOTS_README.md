# Analytics Snapshots: Fetch, Store, and Query Guide

This guide explains how to work with analytics snapshots in the Agent Emily system - fetching data from platform APIs, decrypting access tokens, storing historical analytics, and querying stored data.

## Overview

The analytics snapshots system provides:
- **Token Decryption**: Secure access token handling
- **Real-time Fetching**: Live data from Instagram, Facebook, and other platforms
- **Historical Storage**: Time-series analytics data in the `analytics_snapshots` table
- **Query Interface**: Flexible querying of stored analytics data

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Platform APIs │───▶│ Token Decryption│───▶│   Fetch & Store │
│                 │    │                 │    │                 │
│ • Instagram     │    │ • Fernet         │    │ • analytics_db.py │
│ • Facebook      │    │ • AES-256       │    │ • Orion queries   │
│ • YouTube       │    │ • Secure        │    │ • Snapshots      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  analytics_    │───▶│   Query &       │───▶│   Analytics     │
│  snapshots     │    │   Analytics     │    │   Insights      │
│  table         │    │   Summary       │    │   Router        │
│                 │    │                 │    │                 │
│ • PostgreSQL    │    │ • Time-series   │    │ • REST API      │
│ • 30-day TTL    │    │ • Aggregation   │    │ • Real-time     │
│ • User-scoped   │    │ • Filtering     │    │ • Historical    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Token Decryption

Access tokens are encrypted using Fernet (AES-256) encryption for security.

### Automatic Decryption

```python
from database.analytics_db import decrypt_token

# Decrypt a stored access token
decrypted_token = decrypt_token(encrypted_token)
```

### Manual Decryption

```python
from cryptography.fernet import Fernet
import os

# Get encryption key from environment
encryption_key = os.getenv("ENCRYPTION_KEY")
cipher_suite = Fernet(encryption_key.encode())

# Decrypt token
decrypted_token = cipher_suite.decrypt(encrypted_token.encode()).decode()
```

### Testing Token Decryption

```python
from database.analytics_db import test_token_decryption

result = test_token_decryption(user_id="58d91fe2-1401-46fd-b183-a2a118997fc1", platform="instagram")
if result["success"]:
    print(f"✅ Token decrypted successfully (length: {result['token_length']})")
else:
    print(f"❌ Token decryption failed: {result['error']}")
```

## Fetching Analytics Data

### Real-time Platform Analytics

```python
from database.analytics_db import fetch_instagram_insights, fetch_facebook_insights

# Get platform connection
connection = get_platform_connection(user_id, "instagram")

# Fetch Instagram analytics
instagram_data = fetch_instagram_insights(
    connection=connection,
    metrics=["impressions", "reach", "profile_views", "follower_count"],
    date_range="last_7_days"
)

# Fetch Facebook analytics
facebook_data = fetch_facebook_insights(
    connection=connection,
    metrics=["page_impressions", "page_engaged_users", "page_fans"],
    date_range="last_30_days"
)
```

### Post-level Metrics

```python
from database.analytics_db import fetch_instagram_post_metrics

# Fetch metrics for latest post
post_metrics = fetch_instagram_post_metrics(
    connection=connection,
    metrics=["likes", "comments", "shares"],
    date_range="last_post"
)
```

## Storing Analytics Snapshots

### Single Snapshot Storage

```python
from database.analytics_db import store_analytics_snapshot

success = store_analytics_snapshot(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    metric="impressions",
    value=15000,
    date="2024-01-15",
    source="social_media",
    post_id=None,  # None for account-level metrics
    metadata={
        "api": "instagram_graph",
        "period": "day",
        "fetched_at": "2024-01-15T10:30:00Z"
    }
)
```

### Bulk Snapshot Storage

```python
from database.analytics_db import bulk_store_analytics_snapshots

snapshots_data = [
    {
        "platform": "instagram",
        "metric": "impressions",
        "value": 15000,
        "date": "2024-01-15",
        "source": "social_media",
        "metadata": {"batch": "daily_collection"}
    },
    {
        "platform": "instagram",
        "metric": "reach",
        "value": 12000,
        "date": "2024-01-15",
        "source": "social_media",
        "metadata": {"batch": "daily_collection"}
    }
]

result = bulk_store_analytics_snapshots(user_id, snapshots_data)
print(f"Stored {result['stored_count']} of {result['total_requested']} snapshots")
```

### Fetch and Store Combined

```python
from database.analytics_db import fetch_and_store_platform_analytics

result = fetch_and_store_platform_analytics(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    metrics=["impressions", "reach", "profile_views"],
    date_range="last_7_days"
)

if result["success"]:
    print(f"✅ Fetched and stored {result['snapshots_stored']} snapshots")
else:
    print(f"❌ Failed: {result.get('errors', [])}")
```

## Querying Analytics Snapshots

### Basic Snapshot Query

```python
from database.analytics_db import get_analytics_snapshots

# Get all snapshots for a user (last 30 days)
snapshots = get_analytics_snapshots(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    limit=1000
)

# Get platform-specific snapshots
instagram_snapshots = get_analytics_snapshots(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    days_back=30
)

# Get specific metric
impressions_data = get_analytics_snapshots(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    metric="impressions",
    date_from="2024-01-01",
    date_to="2024-01-31"
)
```

### Latest Snapshot Query

```python
from database.analytics_db import get_latest_analytics_snapshot

latest_impressions = get_latest_analytics_snapshot(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    metric="impressions"
)

if latest_impressions:
    print(f"Latest impressions: {latest_impressions['value']} on {latest_impressions['date']}")
```

### Analytics Summary

```python
from database.analytics_db import get_analytics_summary

summary = get_analytics_summary(
    user_id="58d91fe2-1401-46fd-b183-a2a118997fc1",
    platform="instagram",
    days_back=30
)

if "error" not in summary:
    print(f"Total snapshots: {summary['total_snapshots']}")
    print(f"Platforms: {summary['platforms']}")
    print(f"Metrics: {summary['metrics']}")

    # Access platform-specific data
    instagram_data = summary['platform_data'].get('instagram', {})
    if instagram_data:
        for metric, data in instagram_data['metrics'].items():
            print(f"{metric}: {data['latest_value']} (latest: {data['latest_date']})")
```

## REST API Endpoints

### Manual Analytics Fetching

```bash
# Fetch Instagram insights manually
curl -X POST "http://localhost:8000/analytics-insights/fetch-instagram-insights" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days_back": 7}'

# Fetch Facebook insights manually
curl -X POST "http://localhost:8000/analytics-insights/fetch-facebook-insights" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days_back": 7}'

# Fetch all platforms
curl -X POST "http://localhost:8000/analytics-insights/fetch-all-insights" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days_back": 7}'
```

### Query Stored Snapshots

```bash
# Query snapshots
curl "http://localhost:8000/analytics-insights/query-snapshots?platform=instagram&metric=impressions&days_back=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Query all snapshots for a platform
curl "http://localhost:8000/analytics-insights/query-snapshots?platform=instagram&days_back=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Automated Collection

### Daily Analytics Collector

The system includes an automated daily collector that runs at 2:00 AM:

```python
# Manual execution for testing
from services.analytics_collector import collect_daily_analytics

stats = collect_daily_analytics()
print(f"Collected {stats['total_metrics_inserted']} metrics from {stats['successful_users']} users")
```

### Scheduler Setup

The collector can be scheduled using:
1. **Supabase pg_cron** (recommended for production)
2. **APScheduler** (for development/testing)

## Database Schema

### Analytics Snapshots Table

```sql
CREATE TABLE analytics_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('social_media', 'blog')),
    metric TEXT NOT NULL,
    value NUMERIC NOT NULL DEFAULT 0,
    date DATE NOT NULL,
    post_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint prevents duplicates
ALTER TABLE analytics_snapshots ADD CONSTRAINT unique_user_platform_metric_date_post
    UNIQUE (user_id, platform, source, metric, date, post_id);
```

## Example Scripts

### Running the Example Script

```bash
# Test analytics snapshots functionality
python scripts/analytics_snapshots_example.py 58d91fe2-1401-46fd-b183-a2a118997fc1 instagram

# This will demonstrate:
# 1. Token decryption testing
# 2. Real-time analytics fetching
# 3. Snapshot querying
# 4. Analytics summary generation
# 5. Bulk storage operations
```

### Custom Analytics Script

```python
#!/usr/bin/env python3
import os
from database.analytics_db import (
    get_platform_connection,
    fetch_instagram_insights,
    store_analytics_snapshot
)

def collect_user_analytics(user_id: str):
    """Collect and store analytics for a specific user."""

    # Get Instagram connection
    connection = get_platform_connection(user_id, "instagram")
    if not connection:
        print(f"No Instagram connection for user {user_id}")
        return

    # Fetch analytics
    metrics = ["impressions", "reach", "profile_views"]
    data = fetch_instagram_insights(connection, metrics)

    if data:
        # Store each metric
        from datetime import datetime
        today = datetime.now().date().isoformat()

        for metric, value in data.items():
            store_analytics_snapshot(
                user_id=user_id,
                platform="instagram",
                metric=metric,
                value=value,
                date=today,
                metadata={"source": "manual_collection"}
            )

        print(f"Stored {len(data)} metrics for user {user_id}")

if __name__ == "__main__":
    user_id = "58d91fe2-1401-46fd-b183-a2a118997fc1"
    collect_user_analytics(user_id)
```

## Platform Support

### Currently Supported Platforms

| Platform | Account-level Metrics | Post-level Metrics | API Status |
|----------|----------------------|-------------------|------------|
| Instagram | ✅ impressions, reach, profile_views, follower_count | ✅ likes, comments, shares | ✅ Active |
| Facebook | ✅ page_impressions, page_engaged_users, page_fans | ✅ likes, comments, shares | ✅ Active |
| YouTube | ❌ Not implemented | ❌ Not implemented | 🚧 Planned |
| LinkedIn | ❌ Not implemented | ❌ Not implemented | 🚧 Planned |
| Twitter/X | ❌ Not implemented | ❌ Not implemented | 🚧 Planned |

### Adding New Platforms

To add a new platform:

1. **Create fetch function** in `analytics_db.py`:
```python
def fetch_platform_insights(connection, metrics, date_range):
    # Platform-specific API logic
    pass
```

2. **Add to platform router** in `get_platform_insights_from_db()`:
```python
elif platform_lower == "newplatform":
    return fetch_newplatform_insights(connection, metrics, date_range)
```

3. **Update collector** in `analytics_collector.py`:
```python
def collect_newplatform_daily_metrics(connection, snapshot_date):
    # Daily collection logic
    pass
```

## Security Considerations

### Token Security
- Access tokens are encrypted at rest using Fernet (AES-256)
- Decryption only happens in memory during API calls
- Never log decrypted tokens in production

### Data Privacy
- Analytics data is user-scoped (RLS policies)
- Users can only access their own analytics snapshots
- 30-day automatic cleanup prevents indefinite data retention

### API Rate Limiting
- Respect platform API rate limits
- Implement exponential backoff for retries
- Use caching to reduce API calls when possible

## Troubleshooting

### Common Issues

1. **Token Decryption Failed**
   - Check `ENCRYPTION_KEY` environment variable
   - Verify token was encrypted with the same key
   - Check token format (should be base64-encoded)

2. **Platform API Errors**
   - Verify token permissions (e.g., `instagram_manage_insights`)
   - Check token expiration
   - Review platform-specific rate limits

3. **No Analytics Data**
   - Check platform connection status
   - Verify account has analytics data available
   - Check date ranges (some metrics have delays)

4. **Database Connection Issues**
   - Verify Supabase credentials
   - Check network connectivity
   - Review RLS policies

### Debugging Commands

```bash
# Check token decryption
python -c "
from database.analytics_db import test_token_decryption
result = test_token_decryption('user_id', 'instagram')
print(result)
"

# Test analytics fetching
python -c "
from database.analytics_db import fetch_and_store_platform_analytics
result = fetch_and_store_platform_analytics('user_id', 'instagram', ['impressions'])
print(result)
"

# Query recent snapshots
python -c "
from database.analytics_db import get_analytics_snapshots
snapshots = get_analytics_snapshots('user_id', platform='instagram', days_back=7)
print(f'Found {len(snapshots)} snapshots')
"
```

## Monitoring and Maintenance

### Health Checks

- Monitor daily collection success rates
- Track API error rates by platform
- Alert on authentication failures
- Review data freshness (no data older than expected)

### Maintenance Tasks

- **Daily**: Review collection logs for failures
- **Weekly**: Clean up old snapshots (automatic)
- **Monthly**: Audit token validity and refresh as needed
- **Quarterly**: Review analytics data retention policies

### Performance Optimization

- Use database indexes for common query patterns
- Implement caching for frequently accessed data
- Batch operations to reduce API calls
- Monitor query performance and optimize slow queries

## Support

For issues or questions about analytics snapshots:

1. Check the logs in `backend/logs/` directory
2. Run the example script for testing
3. Review platform-specific API documentation
4. Check Supabase dashboard for data consistency

The analytics snapshots system is designed to be robust, secure, and scalable for handling social media analytics across multiple platforms.
