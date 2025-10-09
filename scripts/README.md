# Scripts Directory

Utility scripts for GroupChat development and administration.

## Production Scripts

### `clear_production_data.py`
Clear all data from the database (local use only - requires direct DB access).

**Usage:**
```bash
conda activate GroupChat
python scripts/clear_production_data.py --confirm
```

**Warning:** This script connects to your local database. For production, use the API endpoint instead.

### `clear_remaining_contacts.sh`
Check production database status after cleanup.

**Usage:**
```bash
./scripts/clear_remaining_contacts.sh
```

**Production API Alternative:**
```bash
# Clear all production data via API
curl -X POST "https://web-production-92dde.up.railway.app/api/v1/admin/clear-all-data?confirm=DELETE_EVERYTHING"

# Clear only fake/seed data (keep Ellis family contacts)
curl -X POST "https://web-production-92dde.up.railway.app/api/v1/admin/clear-fake-data"
```

## Development Scripts

### `setup_dev.sh`
Set up local development environment.

**Usage:**
```bash
./scripts/setup_dev.sh
```

**What it does:**
- Checks Python version (3.11+)
- Installs Poetry if needed
- Installs dependencies
- Creates `.env` from template
- Checks for PostgreSQL and Redis

### `init_db.sql`
SQL initialization script for local PostgreSQL setup.

**Usage:**
```bash
psql -U postgres -f scripts/init_db.sql
```

## Database Management

### Via API (Recommended for Production)

**Check Stats:**
```bash
curl https://web-production-92dde.up.railway.app/api/v1/admin/stats
```

**Clear All Data:**
```bash
curl -X POST "https://web-production-92dde.up.railway.app/api/v1/admin/clear-all-data?confirm=DELETE_EVERYTHING"
```

**Seed Demo Data:**
```bash
curl -X POST "https://web-production-92dde.up.railway.app/api/v1/admin/seed-demo-data"
```

### Via Direct Database Access (Local Only)

**Connect to local database:**
```bash
conda activate GroupChat
python -c "
from groupchat.db.database import AsyncSessionLocal
import asyncio

async def main():
    async with AsyncSessionLocal() as session:
        print('Connected to database!')

asyncio.run(main())
"
```

## Notes

- **Local vs Production**: Scripts in this directory connect to your local database by default
- **Production Access**: Use the admin API endpoints for production database operations
- **Safety**: All data deletion operations require explicit confirmation
- **Conda Environment**: Always activate the GroupChat conda environment before running scripts

## Environment Setup

```bash
# Activate environment
source /Users/bdogellis/miniforge3/etc/profile.d/conda.sh
conda activate GroupChat

# Install package dependencies
python -m pip install -r requirements.txt

# Run development server
python -m uvicorn groupchat.main:app --reload
```
