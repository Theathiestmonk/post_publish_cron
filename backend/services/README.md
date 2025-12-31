# Daily Analytics Collection System

## Overview

Production-grade daily analytics ingestion pipeline that runs independently from the main analytics query system (Emily + Orion). This service collects **account-level metrics only** from all connected social media platforms and stores them in the `analytics_snapshots` table.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ANALYTICS SYSTEM                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │    Emily     │◄────────│    Orion     │                 │
│  │  (Chatbot)   │         │  (Analytics  │                 │
│  │              │         │   Engine)    │                 │
│  └──────────────┘         └──────────────┘                 │
│         │                        │                          │
│         │                        │                          │
│         └────────READ ONLY───────┘                          │
│                     │                                        │
│                     ▼                                        │
│         ┌───────────────────────┐                          │
│         │ analytics_snapshots   │                          │
│         │       (Table)         │                          │
│         └───────────────────────┘                          │
│                     ▲                                        │
│                     │                                        │
│          ┌──────WRITE ONLY──────┐                          │
│          │                       │                          │
│  ┌──────────────┐       ┌──────────────┐                   │
│  │  Collector   │       │  Scheduler   │                   │
│  │   Service    │◄──────│  (APScheduler│                   │
│  │              │       │  or pg_cron) │                   │
│  └──────────────┘       └──────────────┘                   │
│          │                                                   │
│          ▼                                                   │
│  ┌──────────────────────────────────┐                      │
│  │  Platform APIs                   │                      │
│  │  • Instagram Graph API           │                      │
│  │  • Facebook Graph API            │                      │
│  │  • YouTube Analytics API         │                      │
│  │  • LinkedIn API (future)         │                      │
│  └──────────────────────────────────┘                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. **Separation of Concerns**
- **Collector Service**: WRITE-ONLY to `analytics_snapshots`
- **Emily & Orion**: READ-ONLY from `analytics_snapshots`
- No modification to existing analytics query flow

### 2. **Account-Level Only**
- ✅ Collects: Daily account metrics (impressions, reach, engagement)
- ❌ Never collects: Individual post data (stays live via APIs)
- `post_id` is **ALWAYS NULL** in collected snapshots

### 3. **Metadata Storage**
- **Purpose**: Store content type context when available
- **Usage**: Future analytics slicing (reels vs posts, videos vs shorts)
- **Structure**: JSONB containing `post_type`, `api`, `period`, `fetched_at`

## Files

### Core Services

| File | Purpose |
|------|---------|
| `services/analytics_collector.py` | Main collection service - fetches and stores daily metrics |
| `services/scheduler.py` | APScheduler configuration for daily 2:00 AM runs |
| `services/setup_pg_cron.sql` | Alternative pg_cron SQL setup |
| `services/README.md` | This file |

### Integration Points

| File | Changes Made |
|------|--------------|
| `main.py` | Added scheduler startup/shutdown, internal API endpoints |

## Scheduling Options

### Option 1: APScheduler (Recommended for Backend)

**Implemented in**: `services/scheduler.py`

**Advantages**:
- Python-native, integrated with FastAPI
- No DB extensions required
- Easy monitoring and debugging

**Configuration**:
```python
# In main.py - already integrated
from services.scheduler import start_analytics_scheduler

@app.on_event("startup")
async def startup_event():
    start_analytics_scheduler()  # Runs at 2:00 AM UTC daily
```

### Option 2: Supabase pg_cron

**Setup file**: `services/setup_pg_cron.sql`

**Advantages**:
- Survives application restarts
- Native PostgreSQL scheduling
- Centralized in database

**Setup**:
1. Enable pg_cron in Supabase dashboard
2. Run SQL from `setup_pg_cron.sql`
3. Configure webhook endpoint protection

## Environment Variables

Add to your `.env`:

```bash
# Required (already present)
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
ENCRYPTION_KEY=your_encryption_key

# New for analytics collection
INTERNAL_CRON_SECRET=your_secret_token_here  # Protects internal endpoints
```

## API Endpoints

### Internal Endpoints (Protected)

All internal endpoints require `X-Cron-Secret` header.

#### 1. Get Scheduler Status

```http
GET /api/internal/analytics/scheduler-status
X-Cron-Secret: your_secret_token
```

**Response**:
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

#### 2. Manual Trigger

```http
POST /api/internal/analytics/trigger-collection
X-Cron-Secret: your_secret_token
```

**Response**:
```json
{
  "success": true,
  "message": "Analytics collection job started in background",
  "triggered_at": "2025-12-19T12:30:00+05:30"
}
```

## Data Flow

### Collection Process

```
1. Scheduler triggers at 2:00 AM daily
   ↓
2. Get all users with active platform connections
   ↓
3. For each user:
   ├─ For each connected platform:
   │  ├─ Decrypt access token
   │  ├─ Call platform API (daily metrics)
   │  ├─ Normalize data
   │  └─ Insert into analytics_snapshots
   │
   └─ Handle errors (per-platform isolation)
   ↓
4. Log completion statistics
```

### Data Normalization

Each metric is inserted with:

```python
{
    "user_id": "user-123",
    "platform": "instagram",  # lowercase
    "source": "social_media",
    "metric": "impressions",   # API metric name
    "value": 12543.0,          # numeric value
    "date": "2025-12-18",      # YYYY-MM-DD
    "post_id": None,           # ⚠️ ALWAYS NULL (account-level)
    "metadata": {
        "api": "instagram_graph",
        "period": "day",
        "post_type": "reel",   # if available from API
        "fetched_at": "2025-12-19T02:05:23Z"
    }
}
```

### UPSERT Safety

Uses PostgreSQL UPSERT with conflict resolution:

```sql
ON CONFLICT (user_id, platform, source, metric, date, post_id) 
DO NOTHING
```

This ensures:
- No duplicate entries
- Idempotent operations
- Safe to retry

## Platform-Specific Implementation

### Instagram Business/Creator

**API**: Facebook Graph API v18.0

**Endpoint**: `GET /{ig-business-id}/insights`

**Metrics Collected**:
- `impressions`: Total views of posts
- `reach`: Unique accounts reached
- `profile_views`: Profile visits

**Post Type Detection** (from metadata):
- If `media_type` in API response → store in `metadata.post_type`
- Values: `post`, `reel`, `video`

### Facebook Page

**API**: Facebook Graph API v18.0

**Endpoint**: `GET /{page-id}/insights`

**Metrics Collected**:
- `page_impressions`: Total page content views
- `page_engaged_users`: Unique engaged users
- `page_views`: Total page views

**Content Type** (from metadata):
- `photo` → `post`
- `video` → `video` or `reel`

### YouTube (Placeholder)

**API**: YouTube Analytics API

**Endpoint**: `reports.query`

**Metrics** (to be implemented):
- `views`: Daily video views
- `estimatedMinutesWatched`: Watch time
- `subscribersGained`: New subscribers

**Duration Detection**:
- `< 60s` → `short`
- ` 60s` → `video`

## Error Handling

### Per-User Isolation

If one user's collection fails, others continue:

```python
for user in users:
    try:
        # Collect for this user
    except Exception as e:
        logger.error(f"User {user_id} failed: {e}")
        # Continue to next user
```

### Per-Platform Isolation

If one platform fails, others for the same user continue:

```python
for connection in user_connections:
    try:
        # Collect platform metrics
    except Exception as e:
        logger.error(f"{platform} failed: {e}")
        # Continue to next platform
```

### Missing Permissions

- Logged as warning
- Platform skipped gracefully
- No job crash

## Monitoring

### Logs

All collection runs are logged with:
- Start/end timestamps
- Users processed (success/fail counts)
- Platforms processed (success/fail counts)
- Total metrics inserted
- Duration

**Example log output**:

```
================================================================================
DAILY ANALYTICS COLLECTION STARTED
================================================================================
Found 150 users with active connections
────────────────────────────────────────────────────────────────────────────────
Processing user: user-123
────────────────────────────────────────────────────────────────────────────────
  Collecting instagram metrics...
    ✅ instagram: Inserted 3 metrics
  Collecting facebook metrics...
    ✅ facebook: Inserted 3 metrics
...
================================================================================
DAILY ANALYTICS COLLECTION COMPLETED
================================================================================
Date: 2025-12-18
Duration: 45.23s
Users: 145/150 successful
Platforms: 285/300 successful
Total Metrics Inserted: 850
================================================================================
```

### Database Queries

Check recent collections:

```sql
-- Metrics collected today
SELECT 
    platform,
    metric,
    COUNT(*) as user_count,
    SUM(value) as total_value
FROM analytics_snapshots
WHERE date = CURRENT_DATE
GROUP BY platform, metric;

-- Collection coverage by platform
SELECT 
    platform,
    COUNT(DISTINCT user_id) as users_with_data,
    MAX(date) as last_collection_date
FROM analytics_snapshots
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY platform;
```

## Testing

### Manual Trigger (CLI)

```bash
cd backend
python services/analytics_collector.py
```

### Manual Trigger (API)

```bash
curl -X POST http://localhost:8000/api/internal/analytics/trigger-collection \
  -H "X-Cron-Secret: your_secret_token" \
  -H "Content-Type: application/json"
```

### Check Scheduler Status

```bash
curl http://localhost:8000/api/internal/analytics/scheduler-status \
  -H "X-Cron-Secret: your_secret_token"
```

## Deployment Checklist

- [ ] Set `INTERNAL_CRON_SECRET` in production environment
- [ ] Verify Supabase credentials are configured
- [ ] Encryption key is set for token decryption
- [ ] Choose scheduling method (APScheduler vs pg_cron)
- [ ] If using pg_cron: Run setup SQL and configure webhook
- [ ] Monitor first collection run in logs
- [ ] Verify data appears in `analytics_snapshots` table
- [ ] Set up alerts for collection failures

## Maintenance

### Adding New Platforms

1. Create new collector function in `services/analytics_collector.py`:
   ```python
   def collect_platform_daily_metrics(connection, snapshot_date):
       # Implementation
   ```

2. Add platform routing in `collect_platform_metrics()`:
   ```python
   elif platform_lower == "new_platform":
       return collect_new_platform_daily_metrics(connection, snapshot_date)
   ```

3. Follow the same data normalization structure

### Adjusting Schedule

**APScheduler**:
```python
# In services/scheduler.py
scheduler.add_job(
    func=run_analytics_collection_job,
    trigger=CronTrigger(hour=3, minute=30),  # Change time here
    ...
)
```

**pg_cron**:
```sql
SELECT cron.unschedule('daily-analytics-collection');
SELECT cron.schedule('daily-analytics-collection', '30 3 * * *', $$...$$);
```

## FAQ

**Q: Why is `post_id` always NULL?**  
A: This service collects ACCOUNT-LEVEL metrics only. Individual post analytics remain LIVE via API calls for real-time accuracy.

**Q: What if the scheduler misses a run?**  
A: APScheduler handles misfires with 1-hour grace period. pg_cron logs the miss but doesn't retry automatically.

**Q: Can I backfill historical data?**  
A: Not recommended. Most platform APIs only provide recent daily insights. Focus on going-forward collection.

**Q: How is this different from Emily/Orion?**  
A: This service WRITES data daily. Emily/Orion READ and analyze that data on-demand.

**Q: What about post-level analytics?**  
A: Post-level data is fetched LIVE when users ask (via Orion). Not stored historically.

## Support

For issues or questions:
1. Check logs: `emily.log` or console output
2. Verify Supabase connection
3. Test manual trigger endpoint
4. Check platform API credentials
5. Review `analytics_snapshots` table for recent data
