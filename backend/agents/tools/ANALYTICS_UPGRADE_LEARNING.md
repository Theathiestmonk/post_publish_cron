# PHASE 0 - LEARNING & ANALYSIS DOCUMENTATION

## Executive Summary
This document captures all existing patterns, architecture, and conventions before implementing the Analytics & Insights upgrade for Emily.

---

## 1. SUPABASE CLIENT INITIALIZATION PATTERN

### Pattern Found:
```python
import os
from supabase import create_client, Client

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
```

### Locations:
- `backend/agents/emily.py` (line 24-26)
- `backend/agents/tools/Orion_Analytics_query.py` (line 38-40)
- `backend/database/analytics_db.py` (line 18-20)
- `backend/main.py` (line 136-146)
- `backend/routers/connections.py` (line 29-57)

### Key Points:
- Uses `SUPABASE_SERVICE_ROLE_KEY` for backend operations
- Always checks if URL/key exist before creating client
- Returns `None` if initialization fails (defensive pattern)
- Single client instance per module (not per function)

---

## 2. DATABASE INSERT/UPDATE PATTERNS

### Pattern Found:
```python
try:
    result = supabase.table("table_name").insert({
        "field1": value1,
        "field2": value2,
        "created_at": datetime.now().isoformat()
    }).execute()
    
    if result.data:
        logger.info(f"✅ Successfully inserted: {result.data}")
        return result.data[0]
    else:
        logger.warning("⚠️ No data returned from insert")
        return None
except Exception as e:
    logger.error(f"❌ Error inserting: {e}", exc_info=True)
    return None
```

### Update Pattern:
```python
result = supabase.table("table_name").update({
    "field": new_value,
    "updated_at": datetime.now().isoformat()
}).eq("id", record_id).execute()
```

### Key Points:
- Always wrapped in try-except
- Uses `.execute()` for execution
- Checks `result.data` before returning
- Logs success (✅), warnings (⚠️), errors (❌)
- Uses `exc_info=True` for error logging

---

## 3. ANALYTICS DATA FETCHING PATTERNS

### Current Flow:
1. **Emily** (`emily.py`) → Collects fields, normalizes payload
2. **Orion** (`Orion_Analytics_query.py`) → Executes analytics logic
3. **Platform APIs** → Fetches real-time data
4. **Response** → Formatted back to Emily

### Fetch Pattern:
```python
def fetch_platform_insights(platform: str, user_id: str, date_range: Optional[str] = None):
    connection = get_platform_connection(user_id, platform)
    if not connection:
        return None
    
    return _route_to_platform_fetcher(platform, connection, metrics, date_range)
```

### Key Points:
- Always checks connection first
- Returns `None` if no connection/data
- Uses `date_range` parameter (string format)
- Platform-specific fetchers handle API calls
- Post-level metrics handled separately from account-level

---

## 4. EXISTING ANALYTICS TABLES

### Found Tables:
1. **template_analytics** (template usage tracking)
   - `id`, `template_id`, `user_id`, `action`, `metadata`, `created_at`
   
2. **blog_post_performance** (blog analytics)
   - `id`, `blog_post_id`, `wordpress_post_id`, `views`, `likes`, `comments`, `shares`, `engagement_rate`, `last_updated`, `created_at`, `metadata`

3. **website_analyses** (website analysis results)
   - Stores SEO, performance, accessibility scores
   - JSONB fields for flexible data storage

### Missing:
- **analytics_snapshots** table (needs to be created in Phase 1)
- No time-series analytics storage for social media metrics

---

## 5. ANALYTICS FIELDS & PAYLOAD STRUCTURE

### AnalyticsPayload Structure:
```python
class AnalyticsPayload(BaseModel):
    insight_type: Literal["insight", "improvement"]  # REQUIRED
    source: Literal["social_media", "blog"]  # REQUIRED
    platform: Optional[List[str]]  # instagram, facebook, youtube, etc.
    metrics: Optional[List[str]]  # reach, impressions, engagement, likes, etc.
    blog_metrics: Optional[List[str]]  # views, read_time, bounce_rate, etc.
    date_range: Optional[str]  # "last 7 days", "last month", etc.
```

### Supported Metrics:
**Social Media:**
- Account-level: `reach`, `impressions`, `engagement`, `profile_visits`, `followers`
- Post-level: `likes`, `comments`, `shares`, `saves`, `views`
- Special: `avg_view_time`, `watch_time`, `growth`, `top_posts`

**Blog:**
- `views`, `read_time`, `bounce_rate`, `engagement`, `traffic_sources`, `top_articles`

---

## 6. PAYLOAD FLOW: EMILY → ORION → RESPONSE

### Flow Diagram:
```
User Query
    ↓
Emily.handle_analytics()
    ↓
1. Extract fields from query
2. Normalize payload
3. Check missing fields
4. Ask clarifying questions if needed
    ↓
AnalyticsPayload (validated)
    ↓
Orion.execute_analytics_query()
    ↓
1. Apply defaults (if insight mode)
2. Route to handler (_handle_social_media_analytics or _handle_blog_analytics)
3. Fetch platform data
4. Generate improvements/insights
5. Format response
    ↓
Response Dict:
{
    "success": bool,
    "data": {...} | None,
    "clarifying_question": str | None,
    "options": List[str] | None,
    "error": str | None
}
```

### Key Responsibilities:
- **Emily**: Intent detection, clarification, payload building, routing
- **Orion**: Analytics fetch, aggregation, formatting, business logic

---

## 7. INSIGHT_TYPE USAGE

### Current Implementation:
- **"insight"**: Shows current analytics data (metrics optional, defaults applied)
- **"improvement"**: Generates improvement suggestions (metrics REQUIRED)

### Logic:
```python
if payload.insight_type == "insight":
    # Metrics optional, apply defaults if missing
    if not payload.metrics:
        payload.metrics = ["comments", "likes"]  # Defaults
    
elif payload.insight_type == "improvement":
    # Metrics REQUIRED
    if not payload.metrics:
        return {"clarifying_question": "What would you like to improve?"}
```

### Improvement Generation:
- Calls `generate_improvements(platform_data, metrics)`
- Uses `services/improvement_service.py`
- Rule-based suggestions with thresholds
- Returns dict with `current`, `suggestion`, `target` for each metric

---

## 8. DATE RANGE HANDLING

### Current Implementation:
- Stored as string: `"last 7 days"`, `"last month"`, etc.
- Converted to API period: `"day"`, `"week"`, `"days_28"`
- Function: `_calculate_period(date_range: Optional[str]) -> str`

### Pattern:
```python
def _calculate_period(date_range: Optional[str]) -> str:
    if not date_range:
        return "day"
    
    date_lower = date_range.lower()
    if "month" in date_lower or "30" in date_range:
        return "days_28"
    elif "week" in date_lower or "7" in date_range:
        return "week"
    else:
        return "day"
```

### Missing:
- No natural language parsing (Hindi/English)
- No date range normalization to start_date/end_date
- No date range validation
- No aggregation logic for date ranges

---

## 9. PLATFORM RESOLUTION LOGIC

### Fallback Chain:
1. Use `payload.platform` if provided
2. Else `fetch_connected_platforms(user_id)` 
3. Else `fetch_last_post_platform(user_id)`
4. Else ask user for clarification

### Function:
```python
def _get_platforms_with_fallback(payload, user_id, allow_empty=False):
    platforms = payload.platform or fetch_connected_platforms(user_id)
    
    if not platforms:
        last_platform = fetch_last_post_platform(user_id)
        if last_platform:
            platforms = [last_platform]
        elif not allow_empty:
            return None, {"clarifying_question": "Which platform?"}
    
    return platforms or [], None
```

### Tables Used:
- `platform_connections` (OAuth connections)
- `social_media_connections` (token connections)
- `content_posts` (for last post platform)

---

## 10. ERROR HANDLING PATTERNS

### Pattern:
```python
try:
    # Operation
    result = some_operation()
    if result:
        logger.info("✅ Success")
        return result
    else:
        logger.warning("⚠️ No data")
        return None
except Exception as e:
    logger.error(f"❌ Error: {e}", exc_info=True)
    return None
```

### Response Structure:
```python
{
    "success": False,
    "error": "Error message",
    # OR
    "clarifying_question": "Question text",
    "options": ["option1", "option2"]
}
```

### Key Points:
- Always returns dict (never raises exceptions)
- Uses emoji prefixes in logs (✅⚠️❌)
- `exc_info=True` for error logging
- Graceful degradation (returns None, not crashes)

---

## 11. LOGGING PATTERNS

### Pattern:
```python
logger.info("✅ Success message")
logger.warning("⚠️ Warning message")
logger.error("❌ Error message", exc_info=True)
logger.debug("Debug details")
```

### Key Points:
- Uses emoji prefixes for visual scanning
- Info for success, warning for recoverable issues, error for failures
- `exc_info=True` includes stack trace
- Structured logging with context (user_id, platform, etc.)

---

## 12. RESPONSE FORMATTING PATTERNS

### Success Response:
```python
{
    "success": True,
    "data": {
        "type": "insight" | "improvement",
        "insights" | "improvements": {...},
        "metrics": [...],
        "platforms": [...],
        "message": "Formatted user-friendly message",
        "date_range": "last 7 days" (optional)
    }
}
```

### Clarification Response:
```python
{
    "success": False,
    "clarifying_question": "Question text",
    "options": ["option1", "option2"]  # Optional
}
```

### Error Response:
```python
{
    "success": False,
    "error": "Error message"
}
```

---

## 13. CONNECTION FETCHING PATTERNS

### Pattern:
```python
def get_platform_connection(user_id: str, platform: str):
    # Try OAuth connections first
    oauth_result = supabase.table("platform_connections").select("*").eq(
        "user_id", user_id
    ).eq("platform", platform.lower()).eq("is_active", True).execute()
    
    if oauth_result.data:
        return normalize_connection(oauth_result.data[0])
    
    # Try token connections
    token_result = supabase.table("social_media_connections").select("*").eq(
        "user_id", user_id
    ).eq("platform", platform.lower()).eq("is_active", True).execute()
    
    if token_result.data:
        return normalize_connection(token_result.data[0])
    
    return None
```

### Key Points:
- Checks both `platform_connections` and `social_media_connections`
- Always filters by `is_active=True`
- Normalizes connection data (handles `page_id` vs `account_id`)
- Returns `None` if no connection found

---

## 14. METRIC AGGREGATION (CURRENT STATE)

### Current Implementation:
- **Post-level metrics**: Aggregated from multiple posts if date range provided
- **Account-level metrics**: Single value from API (no aggregation)

### Pattern Found:
```python
# In analytics_db.py
if limit == 1:
    # Single post
    return latest_post_metrics
else:
    # Aggregate from multiple posts
    result = {"likes": 0, "comments": 0}
    for post in posts:
        result["likes"] += post.get('like_count', 0)
        result["comments"] += post.get('comments_count', 0)
    return result
```

### Missing:
- No time-series aggregation
- No day-wise breakdown
- No comparison with previous periods
- No growth calculations

---

## 15. IMPROVEMENT GENERATION PATTERNS

### Current Implementation:
- Uses `services/improvement_service.py`
- Rule-based thresholds
- Returns dict per metric with `current`, `suggestion`, `target`

### Pattern:
```python
def generate_improvements_from_data(data: Dict, metrics: List[str]):
    suggestions = {}
    for metric in metrics:
        value = data.get(metric, 0)
        
        if metric == "reach":
            if value < 1000:
                suggestions[metric] = {
                    "current": value,
                    "suggestion": "Post at peak times...",
                    "target": 1000
                }
        # ... more rules
    
    return suggestions
```

### Key Points:
- Rule-based (not AI-driven yet)
- Threshold-based suggestions
- Includes current value, suggestion text, target value
- Returns `None` if no data

---

## 16. EXISTING UTILITIES & HELPERS

### Found Utilities:
- `decrypt_token()` - Token decryption (Fernet)
- `fetch_latest_post_metrics()` - Post-level metrics
- `fetch_platform_follower_count()` - Follower counts
- `_calculate_period()` - Date range to API period conversion
- `_is_post_level_metrics()` - Metric type detection
- `_transform_post_metrics()` - API format to user format

### Missing Utilities:
- Date parsing (natural language)
- Date range normalization (start_date/end_date)
- Metric aggregation by date range
- Cache management functions
- Time-series data storage

---

## 17. ARCHITECTURE DECISIONS TO PRESERVE

1. **Separation of Concerns**:
   - Emily = Intent/Clarification
   - Orion = Analytics Execution
   - NO mixing of responsibilities

2. **Defensive Programming**:
   - Always check for None
   - Always return dict (never raise)
   - Graceful degradation

3. **Consistent Response Format**:
   - Always `{"success": bool, ...}`
   - Consistent error/clarification structure

4. **Logging Standards**:
   - Emoji prefixes
   - Structured context
   - Error stack traces

5. **Supabase Patterns**:
   - Single client per module
   - Try-except wrappers
   - Check result.data

---

## 18. GAPS IDENTIFIED FOR UPGRADE

1. **No Analytics Caching**:
   - Every request hits platform APIs
   - No historical data storage
   - No time-series analysis

2. **Limited Date Range Support**:
   - Only basic string matching
   - No natural language parsing
   - No date range validation

3. **No Aggregation Logic**:
   - Can't answer "last 7 days total"
   - No day-wise breakdowns
   - No period comparisons

4. **Basic Insight Generation**:
   - Rule-based only
   - No AI-driven insights
   - No data-driven comparisons

5. **No Multi-Language Support**:
   - English only
   - No Hindi parsing ("pichle 7 din")

---

## 19. FILES TO MODIFY (PRIORITY ORDER)

1. **Phase 1**: Create `database/analytics_snapshots_schema.sql`
2. **Phase 2**: Extend `backend/agents/tools/Orion_Analytics_query.py`
3. **Phase 3**: Add date parsing to `backend/agents/emily.py` or new utils
4. **Phase 4**: Enhance intent detection in `backend/agents/emily.py`
5. **Phase 5**: Add aggregation functions to `backend/agents/tools/Orion_Analytics_query.py`
6. **Phase 6**: Enhance `backend/services/improvement_service.py`

---

## 20. TESTING CONSIDERATIONS

### Current Test Coverage:
- No test files found for analytics
- Manual testing only

### Test Cases Needed:
1. Cache hit/miss scenarios
2. Date range parsing (English + Hindi)
3. Metric aggregation accuracy
4. Multi-platform handling
5. Error scenarios
6. Edge cases (no data, expired tokens, etc.)

---

## END OF PHASE 0 DOCUMENTATION

**Status**: ✅ Complete
**Next Step**: Proceed to Phase 1 - Create Analytics Memory Layer


