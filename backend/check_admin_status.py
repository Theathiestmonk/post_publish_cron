#!/usr/bin/env python3
"""
Check admin status and token usage data
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not supabase_url or not supabase_key:
    print('Missing Supabase credentials')
    exit(1)

supabase = create_client(supabase_url, supabase_key)

# Check user's profile
user_id = '58d91fe2-1401-46fd-b183-a2a118997fc1'
profile = supabase.table('profiles').select('subscription_plan, subscription_status').eq('id', user_id).execute()
print('User profile:', profile.data)

# Check if there's any token usage data
usage = supabase.table('token_usage').select('*', count='exact').limit(5).execute()
print(f'Token usage records: {usage.count}')
if usage.data:
    print('Sample records:')
    for record in usage.data[:2]:
        print(f"  - {record['created_at']}: {record['model_name']} - {record['feature_type']}")

# Check recent token usage (last 7 days)
from datetime import datetime, timedelta
seven_days_ago = datetime.now() - timedelta(days=7)
usage_recent = supabase.table('token_usage').select('*').gte('created_at', seven_days_ago.isoformat()).execute()
print(f'Token usage records (last 7 days): {len(usage_recent.data)}')
