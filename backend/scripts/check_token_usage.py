"""
Script to check total token usage and costs for OpenAI and Gemini
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from collections import defaultdict

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

def get_provider_from_model(model_name: str) -> str:
    """Determine provider from model name"""
    model_lower = model_name.lower()
    if "gemini" in model_lower:
        return "Gemini"
    elif "gpt" in model_lower or "openai" in model_lower or "dall-e" in model_lower:
        return "OpenAI"
    else:
        return "Unknown"

def format_number(num: float) -> str:
    """Format number with commas"""
    return f"{num:,.0f}"

def format_currency(amount: float) -> str:
    """Format currency amount"""
    return f"${amount:,.6f}"

def main():
    """Main function to query and display token usage"""
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set")
        return
    
    print("🔍 Connecting to Supabase...")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Query all token usage records
    print("📊 Fetching token usage data...")
    try:
        response = supabase.table("token_usage").select("*").execute()
        data = response.data
        
        if not data:
            print("ℹ️  No token usage data found in database.")
            return
        
        print(f"✅ Found {len(data)} token usage records\n")
        
        # Aggregate by provider
        provider_stats = defaultdict(lambda: {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "request_count": 0,
            "models": defaultdict(lambda: {
                "total_tokens": 0,
                "total_cost": 0.0,
                "request_count": 0
            })
        })
        
        # Process each record
        for item in data:
            model_name = item.get("model_name", "unknown")
            provider = get_provider_from_model(model_name)
            
            # Aggregate totals
            provider_stats[provider]["total_tokens"] += int(item.get("total_tokens", 0))
            provider_stats[provider]["input_tokens"] += int(item.get("input_tokens", 0))
            provider_stats[provider]["output_tokens"] += int(item.get("output_tokens", 0))
            provider_stats[provider]["total_cost"] += float(item.get("total_cost", 0))
            provider_stats[provider]["input_cost"] += float(item.get("input_cost", 0))
            provider_stats[provider]["output_cost"] += float(item.get("output_cost", 0))
            provider_stats[provider]["request_count"] += 1
            
            # Track by model
            provider_stats[provider]["models"][model_name]["total_tokens"] += int(item.get("total_tokens", 0))
            provider_stats[provider]["models"][model_name]["total_cost"] += float(item.get("total_cost", 0))
            provider_stats[provider]["models"][model_name]["request_count"] += 1
        
        # Display results
        print("=" * 80)
        print("TOKEN USAGE SUMMARY BY PROVIDER")
        print("=" * 80)
        print()
        
        total_all_tokens = 0
        total_all_cost = 0.0
        
        for provider in sorted(provider_stats.keys()):
            stats = provider_stats[provider]
            total_all_tokens += stats["total_tokens"]
            total_all_cost += stats["total_cost"]
            
            print(f"📦 {provider}")
            print("-" * 80)
            print(f"  Total Tokens:        {format_number(stats['total_tokens'])}")
            print(f"    ├─ Input Tokens:    {format_number(stats['input_tokens'])}")
            print(f"    └─ Output Tokens:   {format_number(stats['output_tokens'])}")
            print(f"  Total Cost:          {format_currency(stats['total_cost'])}")
            print(f"    ├─ Input Cost:      {format_currency(stats['input_cost'])}")
            print(f"    └─ Output Cost:     {format_currency(stats['output_cost'])}")
            print(f"  Total Requests:      {format_number(stats['request_count'])}")
            print()
            
            # Show breakdown by model
            if stats["models"]:
                print(f"  Model Breakdown:")
                for model_name in sorted(stats["models"].keys()):
                    model_stats = stats["models"][model_name]
                    print(f"    • {model_name}:")
                    print(f"      - Tokens: {format_number(model_stats['total_tokens'])}")
                    print(f"      - Cost:   {format_currency(model_stats['total_cost'])}")
                    print(f"      - Requests: {format_number(model_stats['request_count'])}")
                print()
        
        # Overall summary
        print("=" * 80)
        print("OVERALL SUMMARY")
        print("=" * 80)
        print(f"Total Tokens Used:  {format_number(total_all_tokens)}")
        print(f"Total Cost:         {format_currency(total_all_cost)}")
        print(f"Total Requests:     {format_number(sum(s['request_count'] for s in provider_stats.values()))}")
        print()
        
        # Cost breakdown
        print("=" * 80)
        print("COST BREAKDOWN")
        print("=" * 80)
        for provider in sorted(provider_stats.keys()):
            stats = provider_stats[provider]
            percentage = (stats["total_cost"] / total_all_cost * 100) if total_all_cost > 0 else 0
            print(f"{provider:15} {format_currency(stats['total_cost']):>20} ({percentage:5.2f}%)")
        print()
        
    except Exception as e:
        print(f"❌ Error querying database: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()



