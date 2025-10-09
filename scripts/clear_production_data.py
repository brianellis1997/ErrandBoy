"""
Clear all data from production database for clean launch.

WARNING: This will delete ALL data including:
- Contacts/Profiles
- Queries
- Contributions
- Ledger entries
- Transactions

Use with caution!
"""

import asyncio
import sys
from sqlalchemy import text

sys.path.insert(0, "/Users/bdogellis/ErrandBoy")

from groupchat.db.database import AsyncSessionLocal


async def clear_all_data():
    """Clear all data from the database"""
    async with AsyncSessionLocal() as session:
        try:
            print("🗑️  Starting database cleanup...")

            # Disable foreign key checks temporarily (PostgreSQL specific)
            await session.execute(text("SET CONSTRAINTS ALL DEFERRED"))

            # Delete in order to respect foreign keys
            tables = [
                "ledger_entries",
                "contributions",
                "queries",
                "contacts"
            ]

            for table in tables:
                try:
                    result = await session.execute(text(f"DELETE FROM {table}"))
                    count = result.rowcount
                    print(f"  ✓ Deleted {count} records from {table}")
                except Exception as e:
                    print(f"  ⚠ Skipped {table} (table may not exist): {e}")
                    await session.rollback()
                    await session.begin()

            # Commit the transaction
            await session.commit()

            print("\n✅ Database cleared successfully!")
            print("\nVerifying tables are empty:")

            # Verify counts
            for table in tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    status = "✓" if count == 0 else "✗"
                    print(f"  {status} {table}: {count} records")
                except Exception:
                    print(f"  - {table}: N/A (table doesn't exist)")

            return True

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error clearing database: {e}")
            return False


async def show_current_counts():
    """Show current record counts before deletion"""
    async with AsyncSessionLocal() as session:
        print("\n📊 Current database state:")

        tables = ["contacts", "queries", "contributions", "ledger_entries"]

        for table in tables:
            try:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table}: {count} records")
            except Exception as e:
                print(f"  {table}: N/A (table doesn't exist)")
                await session.rollback()


async def main():
    import sys

    print("=" * 60)
    print("PRODUCTION DATABASE CLEANUP")
    print("=" * 60)

    # Show current state
    await show_current_counts()

    # Check for --confirm flag
    if "--confirm" not in sys.argv:
        print("\n⚠️  WARNING: This will permanently delete ALL data!")
        print("\nTo proceed, run with: python scripts/clear_production_data.py --confirm")
        return

    print("\n⚠️  Proceeding with data deletion...")

    # Clear the data
    success = await clear_all_data()

    if success:
        print("\n🎉 Production database is now clean and ready for launch!")
    else:
        print("\n❌ Failed to clear database. Please check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
