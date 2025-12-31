#!/usr/bin/env python3
"""
Analytics Snapshots Example Script

This script demonstrates how to:
1. Decrypt access tokens
2. Fetch analytics from platform APIs
3. Store analytics snapshots
4. Query stored analytics data

Usage:
    python scripts/analytics_snapshots_example.py <user_id> <platform>

Example:
    python scripts/analytics_snapshots_example.py 58d91fe2-1401-46fd-b183-a2a118997fc1 instagram
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import analytics functions
from database.analytics_db import (
    decrypt_token,
    test_token_decryption,
    get_platform_connection,
    fetch_and_store_platform_analytics,
    get_analytics_snapshots,
    get_analytics_summary,
    get_latest_analytics_snapshot,
    store_analytics_snapshot,
    bulk_store_analytics_snapshots
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demonstrate_token_decryption(user_id: str, platform: str):
    """Demonstrate token decryption functionality."""
    print(f"\n🔐 Testing Token Decryption for {platform}")
    print("=" * 50)

    result = test_token_decryption(user_id, platform)
    if result["success"]:
        print(f"✅ Token decryption successful")
        print(f"   Platform: {result['platform']}")
        print(f"   Token encrypted: {result['token_encrypted']}")
        print(f"   Token length: {result['token_length']}")
        print(f"   Token prefix: {result['token_prefix']}")
    else:
        print(f"❌ Token decryption failed: {result['error']}")


def demonstrate_analytics_fetching(user_id: str, platform: str):
    """Demonstrate fetching and storing analytics."""
    print(f"\n📊 Fetching Analytics for {platform}")
    print("=" * 50)

    # Define metrics based on platform
    if platform.lower() == "instagram":
        metrics = ["impressions", "reach", "profile_views", "follower_count"]
    elif platform.lower() == "facebook":
        metrics = ["page_impressions", "page_engaged_users", "page_fans"]
    else:
        metrics = ["impressions", "reach", "engagement"]

    result = fetch_and_store_platform_analytics(
        user_id=user_id,
        platform=platform,
        metrics=metrics,
        date_range="last_7_days"
    )

    if result["success"]:
        print("✅ Analytics fetch and storage successful")
        print(f"   Platform: {result['platform']}")
        print(f"   API fetch success: {result['api_fetch_success']}")
        print(f"   Snapshots stored: {result['snapshots_stored']}")
    else:
        print("❌ Analytics fetch and storage failed")
        if "errors" in result:
            for error in result["errors"]:
                print(f"   Error: {error}")


def demonstrate_snapshot_querying(user_id: str, platform: str):
    """Demonstrate querying stored analytics snapshots."""
    print(f"\n🔍 Querying Analytics Snapshots for {platform}")
    print("=" * 50)

    # Get recent snapshots (last 30 days)
    snapshots = get_analytics_snapshots(
        user_id=user_id,
        platform=platform,
        days_back=30,
        limit=50
    )

    print(f"Found {len(snapshots)} recent snapshots")

    if snapshots:
        # Group by metric and show latest values
        metrics_data = {}
        for snapshot in snapshots:
            metric = snapshot["metric"]
            if metric not in metrics_data:
                metrics_data[metric] = {
                    "latest_value": snapshot["value"],
                    "latest_date": snapshot["date"],
                    "count": 0
                }
            metrics_data[metric]["count"] += 1

            # Update if this is more recent
            if snapshot["date"] > metrics_data[metric]["latest_date"]:
                metrics_data[metric]["latest_value"] = snapshot["value"]
                metrics_data[metric]["latest_date"] = snapshot["date"]

        print("\nLatest metric values:")
        for metric, data in metrics_data.items():
            print(f"   {metric}: {data['latest_value']} (on {data['latest_date']}, {data['count']} records)")
    else:
        print("   No snapshots found")


def demonstrate_analytics_summary(user_id: str, platform: str):
    """Demonstrate analytics summary functionality."""
    print(f"\n📈 Analytics Summary for {platform}")
    print("=" * 50)

    summary = get_analytics_summary(
        user_id=user_id,
        platform=platform,
        days_back=30
    )

    if "error" not in summary:
        print(f"User: {summary['user_id']}")
        print(f"Platform filter: {summary['platform_filter']}")
        print(f"Date range: {summary['date_range']}")
        print(f"Total snapshots: {summary['total_snapshots']}")
        print(f"Platforms: {', '.join(summary['platforms'])}")
        print(f"Metrics: {', '.join(summary['metrics'])}")

        if summary['platform_data']:
            for platform_name, platform_info in summary['platform_data'].items():
                print(f"\n📊 {platform_name.title()} Platform:")
                print(f"   Records: {platform_info['total_records']}")
                print(f"   Date range: {platform_info['date_range']['start']} to {platform_info['date_range']['end']}")

                for metric_name, metric_info in platform_info['metrics'].items():
                    print(f"   {metric_name}: {metric_info['latest_value']} (latest on {metric_info['latest_date']})")
    else:
        print(f"❌ Summary error: {summary['error']}")


def demonstrate_bulk_storage(user_id: str, platform: str):
    """Demonstrate bulk storage of analytics snapshots."""
    print(f"\n📦 Bulk Storage Example for {platform}")
    print("=" * 50)

    # Create sample snapshot data
    from datetime import datetime, timedelta
    today = datetime.now().date()

    sample_snapshots = []
    for i in range(7):  # Last 7 days
        date = (today - timedelta(days=i)).isoformat()
        sample_snapshots.extend([
            {
                "platform": platform,
                "metric": "impressions",
                "value": 1000 + (i * 100),  # Increasing values
                "date": date,
                "source": "social_media",
                "metadata": {"sample": True, "day_offset": i}
            },
            {
                "platform": platform,
                "metric": "reach",
                "value": 800 + (i * 80),
                "date": date,
                "source": "social_media",
                "metadata": {"sample": True, "day_offset": i}
            }
        ])

    result = bulk_store_analytics_snapshots(user_id, sample_snapshots)

    if result["success"]:
        print("✅ Bulk storage successful")
        print(f"   Requested: {result['total_requested']}")
        print(f"   Stored: {result['stored_count']}")
        print(f"   Failed: {result['failed_count']}")
    else:
        print("❌ Bulk storage failed")
        print(f"   Error: {result.get('error', 'Unknown error')}")


def main():
    """Main function to run the analytics snapshots demonstration."""
    if len(sys.argv) != 3:
        print("Usage: python scripts/analytics_snapshots_example.py <user_id> <platform>")
        print("Example: python scripts/analytics_snapshots_example.py 58d91fe2-1401-46fd-b183-a2a118997fc1 instagram")
        sys.exit(1)

    user_id = sys.argv[1]
    platform = sys.argv[2].lower()

    print("🚀 Analytics Snapshots Demonstration")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print(f"Platform: {platform}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Run demonstrations
    try:
        demonstrate_token_decryption(user_id, platform)
        demonstrate_analytics_fetching(user_id, platform)
        demonstrate_snapshot_querying(user_id, platform)
        demonstrate_analytics_summary(user_id, platform)
        demonstrate_bulk_storage(user_id, platform)

        print(f"\n🎉 Demonstration completed successfully!")

    except Exception as e:
        logger.error(f"Demonstration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
