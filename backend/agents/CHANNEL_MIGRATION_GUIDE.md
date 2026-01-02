# Channel Column Migration Guide

## Overview
This migration adds a `channel` field to the `created_content` table to categorize content by channel type (Social Media, Blog, Email, Messages).

## Schema Change

### New Column
- **Column Name:** `channel`
- **Type:** `VARCHAR(50)`
- **Constraints:** 
  - NOT NULL
  - DEFAULT: 'Social Media'
  - CHECK constraint: Values must be one of: 'Social Media', 'Blog', 'Email', 'Messages'

### Updated Schema
```sql
created_content (
    uuid PRIMARY KEY,
    user_id UUID NOT NULL,
    channel VARCHAR(50) NOT NULL DEFAULT 'Social Media',
    platform VARCHAR(50),  -- lowercase: instagram, facebook, etc.
    content_type VARCHAR(50),
    title TEXT,
    content TEXT,
    hashtags JSONB,
    images JSONB,
    status VARCHAR(50),  -- lowercase: generated, scheduled, published
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
```

## Migration Steps

### Option 1: SQL Migration (Recommended)

1. **Open Supabase Dashboard**
   - Go to your Supabase project
   - Navigate to SQL Editor

2. **Run the SQL Script**
   - Open file: `backend/agents/add_channel_to_created_content.sql`
   - Copy and paste the SQL into the SQL Editor
   - Execute the script

3. **Verify Migration**
   ```sql
   -- Check column exists
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_name = 'created_content' AND column_name = 'channel';
   
   -- Check existing records
   SELECT channel, COUNT(*) as count
   FROM created_content
   GROUP BY channel;
   ```

### Option 2: Python Migration Script

1. **Run the Python script:**
   ```bash
   cd backend/agents
   python migrate_add_channel.py
   ```

2. **Note:** The Python script can update existing records but cannot create the column itself. You must run the SQL script first if the column doesn't exist.

## What the Migration Does

1. **Adds the column** (if it doesn't exist)
2. **Updates all existing records** to have `channel = 'Social Media'`
3. **Sets NOT NULL constraint** after updating records
4. **Sets default value** for future inserts
5. **Adds check constraint** to ensure valid values

## Code Updates

### ✅ Already Updated
- `handle_view_content()` - Now filters by channel field
- Query includes channel filter when provided in payload

### ⚠️ Needs Update
When creating new content, ensure the `channel` field is included:

```python
content_record = {
    "user_id": user_id,
    "channel": "Social Media",  # Add this field
    "platform": platform.lower(),
    "content_type": content_type,
    "title": title,
    "content": content,
    "hashtags": hashtags or [],
    "images": images or [],
    "status": "generated",
    "metadata": {...}
}
```

## Valid Channel Values

- `"Social Media"` - For social media posts (Instagram, Facebook, LinkedIn, etc.)
- `"Blog"` - For blog posts
- `"Email"` - For email content
- `"Messages"` - For messaging content (WhatsApp, etc.)

## Rollback (If Needed)

If you need to rollback this migration:

```sql
-- Remove check constraint
ALTER TABLE created_content DROP CONSTRAINT IF EXISTS check_channel_values;

-- Remove default
ALTER TABLE created_content ALTER COLUMN channel DROP DEFAULT;

-- Remove NOT NULL constraint
ALTER TABLE created_content ALTER COLUMN channel DROP NOT NULL;

-- Drop column (WARNING: This will delete data!)
ALTER TABLE created_content DROP COLUMN IF EXISTS channel;
```

## Testing

After migration, test the view_content functionality:

```python
# Test query with channel filter
payload = {
    'channel': 'Social Media',
    'platform': 'Instagram',
    'status': 'generated',
    'content_type': 'post',
    'date_range': 'yesterday'
}
```

## Support

If you encounter issues:
1. Check Supabase logs for SQL errors
2. Verify the column was created: `SELECT * FROM created_content LIMIT 1;`
3. Check that existing records have channel values
4. Ensure user_id filtering is working correctly








