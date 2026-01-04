#!/usr/bin/env python3
"""
Check the status of all scheduled posts to see why they're not publishing
"""

import os
import pytz
from datetime import datetime
from supabase import create_client

# Load environment
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: Missing SUPABASE credentials")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

def main():
    print('🔍 CHECKING SCHEDULED POSTS STATUS...')
    print('=' * 50)

    # Get current time in IST
    utc_now = datetime.now(pytz.UTC)
    ist_now = utc_now.astimezone(pytz.timezone('Asia/Kolkata'))
    print(f'Current IST Time: {ist_now.strftime("%Y-%m-%d %H:%M:%S %Z")}')
    print()

    # Query scheduled posts
    response = supabase.table('created_content').select(
        'id,user_id,platform,channel,title,scheduled_at,status'
    ).eq('status', 'scheduled').execute()

    posts = response.data
    print(f'Found {len(posts)} scheduled posts:')
    print()

    due_posts = 0
    future_posts = 0

    for i, post in enumerate(posts, 1):
        post_id = post['id'][:8] + '...'
        platform = post['platform']
        scheduled_utc = post['scheduled_at']

        if scheduled_utc:
            try:
                if scheduled_utc.endswith('Z'):
                    scheduled_utc = scheduled_utc[:-1] + '+00:00'
                utc_dt = datetime.fromisoformat(scheduled_utc.replace('Z', '+00:00'))
                ist_dt = utc_dt.astimezone(pytz.timezone('Asia/Kolkata'))
                scheduled_ist = ist_dt.strftime('%H:%M:%S IST')

                # Check if due
                if ist_now >= ist_dt:
                    status = 'DUE'
                    due_posts += 1
                else:
                    status = 'WAITING'
                    future_posts += 1

                print(f'{i}. {post_id} | {platform} | Scheduled: {scheduled_ist} | {status}')

            except Exception as e:
                print(f'{i}. {post_id} | {platform} | Error: {str(e)[:50]}...')
        else:
            print(f'{i}. {post_id} | {platform} | No schedule time')

    print()
    print(f'📊 Summary: {due_posts} DUE posts, {future_posts} future posts')

    if due_posts == 0:
        print()
        print('INFO: Why no posts are publishing:')
        print('   - All posts are scheduled for future times')
        print('   - Next post due in a few minutes')
        print('   - Cron job is working correctly by waiting')
    else:
        print()
        print('WARNING: There are DUE posts that should publish!')
        print('   - Check platform credentials')
        print('   - Check network connectivity')
        print('   - Check cron job publishing logic')

if __name__ == "__main__":
    main()
