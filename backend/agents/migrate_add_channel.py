"""
Migration Script: Add channel column to created_content table
Run this script to add the channel field and update existing records
"""

import os
import sys
from supabase import create_client, Client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def migrate_add_channel():
    """Add channel column to created_content table and set default values"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("✓ Connected to Supabase")
        
        # Step 1: Check if channel column already exists
        print("\n📋 Step 1: Checking if channel column exists...")
        try:
            # Try to query the channel column
            test_query = supabase.table('created_content').select('channel').limit(1).execute()
            print("✓ Channel column already exists")
            
            # Check if there are NULL values
            null_check = supabase.table('created_content').select('id').is_('channel', 'null').limit(1).execute()
            if null_check.data:
                print("⚠️  Found records with NULL channel values, updating...")
                needs_update = True
            else:
                print("✓ All records have channel values")
                needs_update = False
        except Exception as e:
            print(f"⚠️  Channel column doesn't exist or error checking: {str(e)}")
            print("   Note: Column creation requires database admin access.")
            print("   Please run the SQL migration script manually in Supabase SQL Editor:")
            print("   File: backend/agents/add_channel_to_created_content.sql")
            needs_update = True
        
        # Step 2: Update existing records with NULL channel to 'Social Media'
        if needs_update:
            print("\n📋 Step 2: Updating existing records...")
            try:
                # Update all records where channel is NULL
                update_response = supabase.table('created_content').update({
                    'channel': 'Social Media'
                }).is_('channel', 'null').execute()
                
                print(f"✓ Updated records with default channel 'Social Media'")
                print(f"   (Note: Exact count may vary if column doesn't exist yet)")
            except Exception as e:
                print(f"⚠️  Could not update records: {str(e)}")
                print("   This is expected if the column doesn't exist yet.")
                print("   Please run the SQL migration script first.")
        
        # Step 3: Verify migration
        print("\n📋 Step 3: Verifying migration...")
        try:
            # Count records by channel
            all_records = supabase.table('created_content').select('channel').execute()
            if all_records.data:
                channel_counts = {}
                for record in all_records.data:
                    channel = record.get('channel', 'NULL')
                    channel_counts[channel] = channel_counts.get(channel, 0) + 1
                
                print("✓ Channel distribution:")
                for channel, count in channel_counts.items():
                    print(f"   - {channel}: {count} records")
            else:
                print("✓ No records found (table is empty)")
        except Exception as e:
            print(f"⚠️  Could not verify: {str(e)}")
        
        print("\n✅ Migration script completed!")
        print("\n📝 Next steps:")
        print("   1. If column doesn't exist, run the SQL script in Supabase SQL Editor:")
        print("      backend/agents/add_channel_to_created_content.sql")
        print("   2. Verify the migration was successful")
        print("   3. Update content creation code to include channel field")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("Migration: Add channel column to created_content table")
    print("=" * 80)
    
    success = migrate_add_channel()
    
    if success:
        print("\n✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)







