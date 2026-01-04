#!/usr/bin/env python3
"""
Diagnostic script for Render deployment troubleshooting
Tests environment variables, database connection, and scheduling logic
"""

import os
import asyncio
import sys
sys.path.append('.')

def diagnose_environment():
    """Check environment variables"""
    print("🔧 ENVIRONMENT VARIABLE DIAGNOSIS")
    print("=" * 50)

    required_vars = {
        'SUPABASE_URL': 'Supabase project URL',
        'SUPABASE_SERVICE_ROLE_KEY': 'Supabase service role key',
        'ENCRYPTION_KEY': 'Token encryption key'
    }

    all_good = True
    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        if value:
            # Mask sensitive values
            if len(value) > 20:
                display_value = value[:10] + "..." + value[-10:]
            else:
                display_value = value[:5] + "***"
            print(f"✅ {var_name}: {display_value}")
        else:
            print(f"❌ {var_name}: NOT SET - {description}")
            all_good = False

    return all_good

async def diagnose_database():
    """Test database connection and query scheduled posts"""
    print("\n🗄️ DATABASE CONNECTION DIAGNOSIS")
    print("=" * 50)

    try:
        from supabase import create_client

        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

        if not supabase_url or not supabase_key:
            print("❌ Missing database credentials")
            return False

        supabase = create_client(supabase_url, supabase_key)
        print("✅ Supabase client initialized")

        # Test basic connection
        response = supabase.table('created_content').select('id').limit(1).execute()
        print(f"✅ Database connection successful - found {len(response.data)} records")

        # Check for scheduled posts
        scheduled_response = supabase.table('created_content').select('id,user_id,platform,scheduled_at,status').eq('status', 'scheduled').execute()
        scheduled_posts = scheduled_response.data

        print(f"📊 Scheduled posts in database: {len(scheduled_posts)}")

        if scheduled_posts:
            print("📋 Recent scheduled posts:")
            for post in scheduled_posts[:5]:  # Show first 5
                print(f"  - ID: {post['id'][:8]}... | User: {post['user_id'][:8]}... | Platform: {post['platform']} | Scheduled: {post.get('scheduled_at', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ Database diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def diagnose_scheduler():
    """Test the scheduler logic"""
    print("\n📅 SCHEDULER LOGIC DIAGNOSIS")
    print("=" * 50)

    try:
        from cron_job.timezone_scheduler import TimezoneAwareScheduler

        scheduler = TimezoneAwareScheduler()
        print("✅ TimezoneAwareScheduler initialized")

        # Test MVP configuration
        print(f"🎯 MVP Configuration:")
        print(f"  - Max Users: {scheduler.MVP_MAX_USERS}")
        print(f"  - Max Posts per User: {scheduler.MVP_MAX_POSTS_PER_USER}")
        print(f"  - Target Posts: {scheduler.MVP_TARGET_POSTS}")
        print(f"  - Platform Limits: {scheduler.PLATFORM_CONCURRENT_LIMITS}")

        # Test finding due posts (this is what the cron job does)
        published_count = await scheduler.find_scheduled_content_timezone_aware()
        print(f"🔍 Scheduler scan completed - found {published_count} posts to publish")

        if published_count == 0:
            print("ℹ️  No posts were found due for publishing")
            print("   This could be because:")
            print("   - No posts are scheduled")
            print("   - Posts are scheduled in the future")
            print("   - Posts are in different timezones")
            print("   - Posts are marked as 'expired'")

        return published_count > 0

    except Exception as e:
        print(f"❌ Scheduler diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all diagnostic tests"""
    print("🔍 RENDER DEPLOYMENT DIAGNOSTIC SUITE")
    print("=" * 60)
    print("Diagnosing why scheduled posts aren't publishing...")
    print()

    # Run diagnostics
    env_ok = diagnose_environment()
    db_ok = await diagnose_database()
    scheduler_ok = await diagnose_scheduler()

    # Summary
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 60)

    results = {
        "Environment Variables": env_ok,
        "Database Connection": db_ok,
        "Scheduler Logic": scheduler_ok
    }

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test}")

    print()

    if all(results.values()):
        print("🎉 ALL DIAGNOSTICS PASSED!")
        print("If posts still aren't publishing, the issue might be:")
        print("- Posts are scheduled in the future")
        print("- Timezone differences")
        print("- Posts already published/expired")
        print("- Check Render cron job logs for detailed execution")
    else:
        print("❌ SOME DIAGNOSTICS FAILED")
        print("Fix the failed items above before posts will publish")
        print()
        print("Most common issues:")
        print("- Environment variables not set in Render dashboard")
        print("- Database credentials incorrect")
        print("- Posts scheduled with wrong timezone")

    print("\n💡 Next steps:")
    print("1. Check Render dashboard → Environment for missing variables")
    print("2. Check Render dashboard → Cron Jobs → Logs for execution details")
    print("3. Verify posts are scheduled correctly in your database")
    print("4. Test with a post scheduled for 'now' to verify the system works")

if __name__ == "__main__":
    asyncio.run(main())
