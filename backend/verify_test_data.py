"""
Quick verification - Check if test user has data
"""
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

test_user_id = "22ecf157-2eef-4aea-b1a7-67e7c09127d0"

print("=" * 80)
print("🔍 VERIFYING TEST USER DATA")
print("=" * 80)
print(f"\nTest User ID: {test_user_id}")

# Check if data exists
result = supabase.table("analytics_snapshots").select("*").eq(
    "user_id", test_user_id
).limit(10).execute()

if result.data:
    print(f"✅ Found {len(result.data)} records for test user")
    
    # Test exact query that Orion uses
    today = date.today()
    start_date = (today - timedelta(days=6)).isoformat()
    end_date = today.isoformat()
    
    query_result = supabase.table("analytics_snapshots").select("*").eq(
        "user_id", test_user_id
    ).eq("platform", "instagram").eq("source", "social_media").in_(
        "metric", ["likes", "comments"]
    ).gte("date", start_date).lte("date", end_date).execute()
    
    if query_result.data:
        total_likes = sum(r['value'] for r in query_result.data if r['metric'] == 'likes')
        print(f"\n📊 Instagram Analytics (Last 7 Days):")
        print(f"   Total Likes: {total_likes}")
        print(f"   Date Range: {start_date} to {end_date}")
        print(f"\n✅ DATA EXISTS! Analytics will work! 🎉")
    else:
        print("\n❌ Query returned 0 results!")
        print("Data exists but query is failing.")
else:
    print("\n❌ NO DATA for test user!")
    print("\nRun this to insert data:")
    print("   python quick_insert_analytics.py")

print("=" * 80)

