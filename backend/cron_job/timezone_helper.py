#!/usr/bin/env python3
"""
Timezone helper functions for converting between user timezones and UTC
Use this when scheduling content to ensure proper UTC storage
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import pytz

load_dotenv()

class TimezoneHelper:
    """Helper class for timezone conversions"""

    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        )

    def get_user_timezone(self, user_id: str) -> str:
        """Get user's timezone, default to UTC"""
        try:
            response = self.supabase.table("profiles").select("timezone").eq("id", user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0].get("timezone", "UTC") or "UTC"
            return "UTC"
        except:
            return "UTC"

    def convert_local_to_utc(self, local_datetime: datetime, user_timezone: str) -> datetime:
        """
        Convert user's local datetime to UTC for database storage

        Args:
            local_datetime: User's local time (naive or aware)
            user_timezone: User's timezone (e.g., 'America/New_York')

        Returns:
            UTC datetime for database storage
        """
        try:
            # Get timezone object
            user_tz = pytz.timezone(user_timezone)

            # If datetime is naive, assume it's in user's timezone
            if local_datetime.tzinfo is None:
                local_datetime = user_tz.localize(local_datetime)
            elif local_datetime.tzinfo != user_tz:
                # Convert to user's timezone first
                local_datetime = local_datetime.astimezone(user_tz)

            # Convert to UTC
            utc_datetime = local_datetime.astimezone(pytz.UTC)

            return utc_datetime

        except Exception as e:
            print(f"Error converting time: {e}")
            # Fallback: assume input is already UTC
            if local_datetime.tzinfo is None:
                return pytz.UTC.localize(local_datetime)
            return local_datetime

    def convert_utc_to_local(self, utc_datetime: datetime, user_timezone: str) -> datetime:
        """
        Convert UTC datetime to user's local time for display

        Args:
            utc_datetime: UTC time from database
            user_timezone: User's timezone

        Returns:
            User's local time
        """
        try:
            user_tz = pytz.timezone(user_timezone)

            # Ensure input is UTC
            if utc_datetime.tzinfo is None:
                utc_datetime = pytz.UTC.localize(utc_datetime)
            elif utc_datetime.tzinfo != pytz.UTC:
                utc_datetime = utc_datetime.astimezone(pytz.UTC)

            # Convert to user's timezone
            local_datetime = utc_datetime.astimezone(user_tz)

            return local_datetime

        except Exception as e:
            print(f"Error converting time: {e}")
            return utc_datetime

# Example usage functions
def schedule_content_for_user(user_id: str, local_datetime: datetime, content_data: dict):
    """
    Example: How to schedule content in user's local time

    This converts local time to UTC before storing in database
    """
    helper = TimezoneHelper()

    # Get user's timezone
    user_timezone = helper.get_user_timezone(user_id)
    print(f"User {user_id} timezone: {user_timezone}")

    # Convert local time to UTC for database
    utc_datetime = helper.convert_local_to_utc(local_datetime, user_timezone)
    print(f"Local time: {local_datetime}")
    print(f"UTC time for DB: {utc_datetime}")

    # Store in database with UTC timestamp
    content_data['scheduled_at'] = utc_datetime.isoformat()
    content_data['user_timezone'] = user_timezone  # Optional: store for reference

    # Save to database
    # supabase.table("created_content").insert(content_data).execute()

    return utc_datetime

def display_scheduled_time(user_id: str, utc_timestamp: str):
    """
    Example: How to display scheduled time in user's local timezone
    """
    helper = TimezoneHelper()

    # Parse UTC timestamp
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))

    # Get user's timezone
    user_timezone = helper.get_user_timezone(user_id)

    # Convert to local time
    local_dt = helper.convert_utc_to_local(utc_dt, user_timezone)

    return local_dt

# Common timezone examples
COMMON_TIMEZONES = [
    'UTC',
    'America/New_York',      # EST/EDT
    'America/Chicago',       # CST/CDT
    'America/Denver',        # MST/MDT
    'America/Los_Angeles',   # PST/PDT
    'Europe/London',         # GMT/BST
    'Europe/Paris',          # CET/CEST
    'Asia/Kolkata',          # IST
    'Asia/Tokyo',            # JST
    'Australia/Sydney',      # AEST/AEDT
    'Pacific/Auckland',      # NZST/NZDT
]

if __name__ == "__main__":
    # Test the helper
    helper = TimezoneHelper()

    # Test conversion
    user_time = datetime(2024, 1, 15, 14, 30, 0)  # 2:30 PM local time
    utc_time = helper.convert_local_to_utc(user_time, 'America/New_York')
    print(f"New York 2:30 PM = UTC {utc_time}")

    # Test reverse conversion
    local_time = helper.convert_utc_to_local(utc_time, 'America/New_York')
    print(f"UTC {utc_time} = New York {local_time}")

