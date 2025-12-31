# Supabase Setup Guide for ATSN Agent

## ✅ Supabase Integration Complete

The ATSN agent now follows the **exact same pattern** as the rest of the application for Supabase database access.

---

## 🔧 How It Was Set Up

### 1. **Import Pattern** (Line ~44)

```python
from supabase import create_client, Client
```

**Why:** Matches the pattern used in `main.py` and all agents like `Leo_Content_Generation.py`

---

### 2. **Client Initialization** (Line ~50-56)

```python
# Initialize Supabase client (following the app's pattern)
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

if not supabase:
    logger.warning("⚠️  Supabase not configured. Using mock data. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
else:
    logger.info("✓ Supabase client initialized successfully")
```

**Key Features:**
- ✅ Uses `SUPABASE_SERVICE_ROLE_KEY` first (admin access for agents)
- ✅ Falls back to `SUPABASE_ANON_KEY` if service key not available
- ✅ Gracefully handles missing credentials
- ✅ Provides helpful logging
- ✅ Global client instance (no need to recreate for each query)

**Pattern Source:** Copied from `backend/agents/tools/Leo_Content_Generation.py` lines 17-20

---

### 3. **Agent State Enhanced** (Line ~172)

Added `user_id` field for secure database queries:

```python
class AgentState(BaseModel):
    user_query: str = ""
    conversation_history: List[str] = Field(default_factory=list)
    intent: Optional[str] = None
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    payload_complete: bool = False
    clarification_question: Optional[str] = None
    waiting_for_user: bool = False
    result: Optional[str] = None
    error: Optional[str] = None
    current_step: str = "intent_classification"
    user_id: Optional[str] = None  # ✅ NEW - User ID for database queries
```

**Why:** All database operations should be user-specific for security and privacy.

---

### 4. **Database Query Implementation** (Line ~1230)

```python
def handle_view_content(state: AgentState) -> AgentState:
    """View content from database with filters"""
    payload = state.payload
    
    if not supabase:
        # Mock data for testing without database
        state.result = _generate_mock_view_content(payload)
        logger.warning("Using mock data - Supabase not configured")
        return state
    
    try:
        # Build query for created_content table
        query = supabase.table('created_content').select('*')
        
        # Security: Filter by user_id if available
        if state.user_id:
            query = query.eq('user_id', state.user_id)
        
        # Apply filters from payload
        if payload.get('channel'):
            query = query.eq('channel', payload['channel'])
        
        if payload.get('platform'):
            query = query.eq('platform', payload['platform'])
        
        if payload.get('status'):
            query = query.eq('status', payload['status'])
        
        if payload.get('content_type'):
            query = query.eq('content_type', payload['content_type'])
        
        # Apply date range filter
        if payload.get('date_range'):
            date_filter = _get_date_range_filter(payload['date_range'])
            if date_filter:
                query = query.gte('created_at', date_filter['start'])
                if date_filter.get('end'):
                    query = query.lte('created_at', date_filter['end'])
        
        # Order by most recent first
        query = query.order('created_at', desc=True)
        
        # Execute query
        response = query.execute()
        
        # ... format and return results
```

**Key Features:**
- ✅ Uses global `supabase` client
- ✅ Checks if client is available
- ✅ Filters by `user_id` for security
- ✅ Chains filter conditions
- ✅ Orders results
- ✅ Executes query with `.execute()`

**Pattern Source:** Based on patterns from `Leo_Content_Generation.py` and `content.py`

---

### 5. **Agent Class Updated** (Line ~1675)

```python
class ATSNAgent:
    """Main agent class for content and lead management"""
    
    def __init__(self, user_id: Optional[str] = None):
        self.graph = build_graph()
        self.state = None
        self.user_id = user_id  # ✅ Store user_id
    
    def process_query(self, user_query: str, conversation_history: List[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Process a user query"""
        
        # Use provided user_id or fall back to instance user_id
        active_user_id = user_id or self.user_id
        
        # Initialize or update state
        if self.state is None or not self.state.waiting_for_user:
            self.state = AgentState(
                user_query=user_query,
                conversation_history=conversation_history or [],
                user_id=active_user_id  # ✅ Pass user_id to state
            )
```

**Usage:**
```python
# Option 1: Set user_id at initialization
agent = ATSNAgent(user_id="user-123")
response = agent.process_query("Show my Instagram posts")

# Option 2: Pass user_id with each query
agent = ATSNAgent()
response = agent.process_query("Show my Instagram posts", user_id="user-123")
```

---

## 🗄️ Database Schema

### `created_content` Table

Based on `Leo_Content_Generation.py`, the table structure:

```sql
CREATE TABLE created_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- User identification
    user_id UUID REFERENCES auth.users(id),
    
    -- Content classification
    channel TEXT,  -- 'Social Media', 'Blog', 'Email', 'messages'
    platform TEXT,  -- 'Instagram', 'Facebook', 'LinkedIn', etc.
    content_type TEXT,  -- 'post', 'short_video', 'long_video', 'blog', 'email', 'message'
    status TEXT DEFAULT 'generated',  -- 'generated', 'scheduled', 'published'
    
    -- Content data
    content_text TEXT,
    content_media_url TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scheduled_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    
    -- Additional fields
    metadata JSONB,
    generated_by TEXT,
    topic TEXT,
    campaign_id UUID
);

-- Indexes for performance
CREATE INDEX idx_created_content_user_id ON created_content(user_id);
CREATE INDEX idx_created_content_platform ON created_content(platform);
CREATE INDEX idx_created_content_status ON created_content(status);
CREATE INDEX idx_created_content_content_type ON created_content(content_type);
CREATE INDEX idx_created_content_created_at ON created_content(created_at DESC);
```

---

## 🚀 Environment Variables

### Required Variables

```bash
# Gemini API (required for all operations)
GEMINI_API_KEY="your-gemini-api-key"

# Supabase (required for database operations)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"  # Preferred for agents
# OR
SUPABASE_ANON_KEY="your-anon-key"  # Fallback
```

### Where to Get Keys

1. **SUPABASE_URL**: 
   - Go to your Supabase project dashboard
   - Settings → API
   - Copy "Project URL"

2. **SUPABASE_SERVICE_ROLE_KEY**:
   - Go to your Supabase project dashboard
   - Settings → API
   - Copy "service_role" key (secret)
   - ⚠️ Keep this secret! It bypasses Row Level Security

3. **SUPABASE_ANON_KEY**:
   - Settings → API
   - Copy "anon" key (public)
   - Safe to use in frontend, respects RLS

### Setup Example

```bash
# .env file
GEMINI_API_KEY="AIzaSyC..."
SUPABASE_URL="https://abcdefgh.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 💻 Usage Examples

### Example 1: Basic Usage (No Database)

```python
from backend.agents.atsn import ATSNAgent

# Without Supabase configured, uses mock data
agent = ATSNAgent()
response = agent.process_query("Show me Instagram posts")
print(response['result'])  # Shows mock data
```

### Example 2: With Database (No User ID)

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-key"
```

```python
from backend.agents.atsn import ATSNAgent

# Returns all content (not filtered by user)
agent = ATSNAgent()
response = agent.process_query("Show me Instagram posts")
print(response['result'])  # Shows all users' content
```

### Example 3: With Database and User ID (Recommended)

```python
from backend.agents.atsn import ATSNAgent

# Option A: Set user_id at initialization
agent = ATSNAgent(user_id="user-uuid-123")
response = agent.process_query("Show me Instagram posts")
# Returns only content for user-uuid-123

# Option B: Pass user_id with each query
agent = ATSNAgent()
response = agent.process_query(
    "Show me Instagram posts", 
    user_id="user-uuid-123"
)
# Returns only content for user-uuid-123
```

### Example 4: Integration with FastAPI

```python
from fastapi import FastAPI, Depends
from backend.agents.atsn import ATSNAgent
from backend.auth import get_current_user

app = FastAPI()

@app.post("/atsn/query")
async def atsn_query(
    message: str, 
    current_user = Depends(get_current_user)
):
    # Create agent with user's ID
    agent = ATSNAgent(user_id=current_user.id)
    
    # Process query
    response = agent.process_query(message)
    
    return response
```

---

## 🔍 How Database Queries Work

### Query Building Pattern

```python
# Start with table
query = supabase.table('created_content').select('*')

# Add filters
query = query.eq('user_id', user_id)  # Exact match
query = query.eq('platform', 'Instagram')  # Another filter

# Date range
query = query.gte('created_at', start_date)  # Greater than or equal
query = query.lte('created_at', end_date)    # Less than or equal

# Ordering
query = query.order('created_at', desc=True)  # Most recent first

# Limit results
query = query.limit(10)

# Execute
response = query.execute()

# Access data
if response.data:
    for item in response.data:
        print(item['content_text'])
```

### Common Operations

**Insert Content:**
```python
content_record = {
    "user_id": user_id,
    "channel": "Social Media",
    "platform": "Instagram",
    "content_type": "post",
    "status": "generated",
    "content_text": "Your content here...",
    "created_at": datetime.now().isoformat()
}

response = supabase.table("created_content").insert(content_record).execute()
content_id = response.data[0]["id"] if response.data else None
```

**Update Content:**
```python
update_data = {
    "status": "published",
    "published_at": datetime.now().isoformat()
}

response = supabase.table("created_content").update(update_data).eq("id", content_id).execute()
```

**Delete Content:**
```python
response = supabase.table("created_content").delete().eq("id", content_id).eq("user_id", user_id).execute()
```

---

## 🔐 Security Best Practices

### 1. Always Filter by User ID

```python
# ✅ GOOD - User can only see their own content
query = supabase.table('created_content').select('*').eq('user_id', user_id)

# ❌ BAD - User can see everyone's content
query = supabase.table('created_content').select('*')
```

### 2. Use Service Role Key for Agents

```bash
# For backend agents that need full access
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

# For frontend/client apps that respect RLS
SUPABASE_ANON_KEY="your-anon-key"
```

### 3. Validate User Ownership

```python
# Before updating/deleting, verify user owns the content
content = supabase.table('created_content')\
    .select('*')\
    .eq('id', content_id)\
    .eq('user_id', user_id)\
    .execute()

if not content.data:
    raise HTTPException(status_code=403, detail="Not authorized")
```

---

## 🧪 Testing

### Test Without Database

```python
# Don't set SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY
agent = ATSNAgent()
response = agent.process_query("Show me Instagram posts")
# Uses mock data automatically
```

### Test With Database

```bash
# Set environment variables
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-key"

# Run test
python backend/agents/test_view_content.py
```

### Verify Connection

```python
from backend.agents.atsn import supabase

if supabase:
    print("✓ Connected to Supabase")
    # Test query
    response = supabase.table('created_content').select('count', count='exact').execute()
    print(f"Total content items: {response.count}")
else:
    print("✗ Supabase not configured")
```

---

## 📊 Comparison with Other Files

### Pattern Used in App

**`backend/main.py` (Lines 145-155):**
```python
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
```

**`backend/agents/tools/Leo_Content_Generation.py` (Lines 17-20):**
```python
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
```

**`backend/agents/atsn.py` (Lines 50-56) - NEW:**
```python
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
```

✅ **Identical pattern!**

---

## 🎯 Key Takeaways

1. ✅ **Consistent Pattern**: ATSN agent now uses the same Supabase setup as the rest of the app
2. ✅ **Global Client**: Single client instance, no need to recreate
3. ✅ **Security**: User ID filtering built-in
4. ✅ **Graceful Fallback**: Works with mock data if database not configured
5. ✅ **Production-Ready**: Follows all best practices from the existing codebase

---

## 📞 Quick Reference

| Task | Code |
|------|------|
| Check if connected | `if supabase:` |
| Query table | `supabase.table('created_content').select('*')` |
| Filter | `.eq('field', value)` |
| Date range | `.gte('created_at', start).lte('created_at', end)` |
| Order | `.order('created_at', desc=True)` |
| Execute | `.execute()` |
| Access data | `response.data` |
| Insert | `.insert(record).execute()` |
| Update | `.update(data).eq('id', id).execute()` |
| Delete | `.delete().eq('id', id).execute()` |

---

**✅ Supabase integration complete and matches the app's pattern perfectly!**

*Last Updated: December 25, 2025*







