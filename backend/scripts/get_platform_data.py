#!/usr/bin/env python3
"""
Get Platform Data Script

This script retrieves platform connection data for a given user from the platform_connections table.
It uses service role key or anon key and shows decrypted access tokens.

Usage:
    python scripts/get_platform_data.py <user_id> [--service-key] [--decrypt-tokens]

Arguments:
    user_id: User ID to get platform data for
    --service-key: Use service role key instead of anon key
    --decrypt-tokens: Show decrypted access tokens (WARNING: only use in secure environments)

Example:
    python scripts/get_platform_data.py 58d91fe2-1401-46fd-b183-a2a118997fc1
    python scripts/get_platform_data.py 58d91fe2-1401-46fd-b183-a2a118997fc1 --service-key --decrypt-tokens
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from supabase import create_client, Client
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PlatformConnection:
    """Platform connection data structure."""
    id: str
    user_id: str
    platform: str
    account_id: str
    page_id: Optional[str]
    page_name: Optional[str]
    account_name: Optional[str]
    access_token_encrypted: str
    access_token_decrypted: Optional[str]
    is_active: bool
    status: str
    created_at: str
    last_sync_at: Optional[str]


class PlatformDataFetcher:
    """Class for fetching platform connection data."""

    def __init__(self, use_service_key: bool = False):
        """Initialize with Supabase connection."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL environment variable not found")

        # Use service role key if requested, otherwise use anon key
        if use_service_key:
            self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not self.supabase_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable not found")
            logger.info("Using SERVICE ROLE KEY for database access")
        else:
            self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
            if not self.supabase_key:
                raise ValueError("SUPABASE_ANON_KEY environment variable not found")
            logger.info("Using ANON KEY for database access")

        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)

        # Get encryption key for token decryption
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            logger.warning("ENCRYPTION_KEY not found - token decryption disabled")
            self.cipher_suite = None
        else:
            try:
                self.cipher_suite = Fernet(self.encryption_key.encode())
                logger.info("Encryption cipher initialized for token decryption")
            except Exception as e:
                logger.warning(f"Failed to initialize encryption cipher: {e}")
                self.cipher_suite = None

        logger.info("✅ PlatformDataFetcher initialized successfully")

    def decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """Decrypt access token if possible."""
        if not self.cipher_suite or not encrypted_token:
            return None

        try:
            decrypted = self.cipher_suite.decrypt(encrypted_token.encode())
            return decrypted.decode()
        except Exception as e:
            logger.warning(f"Token decryption failed: {e}")
            return None

    def get_user_platform_data(self, user_id: str, decrypt_tokens: bool = False) -> List[PlatformConnection]:
        """Get all platform connection data for a user."""
        try:
            logger.info(f"🔍 Fetching platform data for user: {user_id}")

            # Query platform_connections table
            result = self.supabase.table("platform_connections").select("*").eq(
                "user_id", user_id
            ).execute()

            if not result.data:
                logger.info(f"No platform connections found for user {user_id}")
                return []

            connections = []
            for conn_data in result.data:
                # Decrypt token if requested
                decrypted_token = None
                if decrypt_tokens:
                    encrypted_token = conn_data.get("access_token_encrypted") or conn_data.get("access_token", "")
                    decrypted_token = self.decrypt_token(encrypted_token)

                connection = PlatformConnection(
                    id=conn_data.get("id"),
                    user_id=conn_data.get("user_id"),
                    platform=conn_data.get("platform", "").lower(),
                    account_id=conn_data.get("account_id", ""),
                    page_id=conn_data.get("page_id"),
                    page_name=conn_data.get("page_name"),
                    account_name=conn_data.get("account_name"),
                    access_token_encrypted=conn_data.get("access_token_encrypted") or conn_data.get("access_token", ""),
                    access_token_decrypted=decrypted_token,
                    is_active=conn_data.get("is_active", False),
                    status=conn_data.get("status", "unknown"),
                    created_at=conn_data.get("created_at", ""),
                    last_sync_at=conn_data.get("last_sync_at")
                )
                connections.append(connection)

            logger.info(f"✅ Found {len(connections)} platform connections")
            return connections

        except Exception as e:
            logger.error(f"Failed to fetch platform data: {e}")
            return []

    def display_platform_data(self, connections: List[PlatformConnection], show_decrypted: bool = False):
        """Display platform connection data in a formatted way."""
        if not connections:
            print("❌ No platform connections found")
            return

        print(f"\n📊 Platform Connections ({len(connections)} found)")
        print("=" * 80)

        for i, conn in enumerate(connections, 1):
            print(f"\n{i}. {conn.platform.upper()} Connection")
            print("-" * 40)
            print(f"   ID: {conn.id}")
            print(f"   User ID: {conn.user_id}")
            print(f"   Platform: {conn.platform}")
            print(f"   Account ID: {conn.account_id}")
            if conn.page_id:
                print(f"   Page ID: {conn.page_id}")
            if conn.page_name:
                print(f"   Page Name: {conn.page_name}")
            if conn.account_name:
                print(f"   Account Name: {conn.account_name}")
            print(f"   Active: {'✅' if conn.is_active else '❌'}")
            print(f"   Status: {conn.status}")
            print(f"   Created: {conn.created_at}")
            if conn.last_sync_at:
                print(f"   Last Sync: {conn.last_sync_at}")

            # Token information
            token_length = len(conn.access_token_encrypted) if conn.access_token_encrypted else 0
            print(f"   Token Encrypted: {'✅' if conn.access_token_encrypted else '❌'} ({token_length} chars)")

            if show_decrypted and conn.access_token_decrypted:
                # Only show first 20 chars for security
                token_preview = conn.access_token_decrypted[:20] + "..." if len(conn.access_token_decrypted) > 20 else conn.access_token_decrypted
                print(f"   Token Decrypted: {token_preview} ({len(conn.access_token_decrypted)} chars)")
            elif show_decrypted and conn.cipher_suite is None:
                print("   Token Decrypted: ⚠️  Encryption key not available")
            elif show_decrypted:
                print("   Token Decrypted: ⚠️  Decryption failed")

        print("\n" + "=" * 80)


def main():
    """Main function to run the platform data retrieval script."""
    parser = argparse.ArgumentParser(description="Get platform connection data for a user")
    parser.add_argument("user_id", help="User ID to get platform data for")
    parser.add_argument("--service-key", action="store_true",
                       help="Use service role key instead of anon key")
    parser.add_argument("--decrypt-tokens", action="store_true",
                       help="Decrypt and show access tokens (WARNING: only use in secure environments)")

    args = parser.parse_args()

    try:
        # Initialize platform data fetcher
        fetcher = PlatformDataFetcher(use_service_key=args.service_key)

        # Get platform data
        connections = fetcher.get_user_platform_data(
            user_id=args.user_id,
            decrypt_tokens=args.decrypt_tokens
        )

        # Display results
        fetcher.display_platform_data(connections, show_decrypted=args.decrypt_tokens)

        # Summary
        active_count = sum(1 for c in connections if c.is_active)
        print(f"\n📈 Summary:")
        print(f"   Total connections: {len(connections)}")
        print(f"   Active connections: {active_count}")
        print(f"   Platforms: {', '.join(set(c.platform for c in connections))}")

        if active_count == 0:
            print("   ⚠️  No active connections found")
            sys.exit(1)
        else:
            print("   ✅ Active connections available for analytics")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"\n❌ Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
