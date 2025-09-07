#!/usr/bin/env python3
"""Simple command-line interface for seeding demo data"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_seed_data import create_enhanced_seed_data

async def main():
    print("🚀 Starting GroupChat demo data seeding...")
    print("This will create realistic expert profiles, query scenarios, and financial records.")
    print()
    
    try:
        await create_enhanced_seed_data()
        print("\n🎉 Demo data seeding completed successfully!")
        print("\nYou can now:")
        print("  - Submit queries through the web interface")
        print("  - View expert profiles and contributions")
        print("  - See realistic answer synthesis with citations")
        print("  - Explore financial transaction tracking")
        
    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())