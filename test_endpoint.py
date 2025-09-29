"""Simple test endpoint for debugging"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from groupchat.db.database import get_db
# from groupchat.services.contacts import ContactService
# from groupchat.schemas.contacts import ContactCreate

router = APIRouter()

@router.post("/test-create-contact")
async def test_create_contact():
    """Ultra simple test - no database, no services"""
    return {"test": "success", "message": "Simple endpoint works"}

@router.post("/test-with-db")
async def test_with_db(db: AsyncSession = Depends(get_db)):
    """Test with database connection only"""
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        return {"database": "connected", "test_query": row[0]}
    except Exception as e:
        return {"database": "error", "message": str(e)}

@router.post("/test-contact-service")
async def test_contact_service(db: AsyncSession = Depends(get_db)):
    """Test ContactService initialization only"""
    try:
        from groupchat.services.contacts import ContactService
        service = ContactService(db)
        return {"contact_service": "initialized", "success": True}
    except Exception as e:
        return {"contact_service": "error", "message": str(e)}

@router.post("/test-direct-contact")
async def test_direct_contact():
    """Test contact creation without database dependency"""
    try:
        from groupchat.schemas.contacts import ContactCreate
        from groupchat.db.models import Contact
        import uuid
        
        # Just test object creation, no database
        contact_data = ContactCreate(
            name="Test User",
            phone_number="+1234567890",
            bio="Test bio",
            is_available=True,
            max_queries_per_day=3,
            preferred_contact_method="sms"
        )
        
        contact = Contact(
            id=uuid.uuid4(),
            phone_number=contact_data.phone_number,
            name=contact_data.name,
            bio=contact_data.bio,
            is_available=contact_data.is_available,
        )
        
        return {
            "contact_model": "created",
            "name": contact.name,
            "phone": contact.phone_number
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug-config")
async def debug_config():
    """Debug configuration - show database URL without password"""
    try:
        from groupchat.config import settings
        import os
        
        # Get DATABASE_URL and mask password
        db_url = str(settings.database_url)
        if "@" in db_url:
            parts = db_url.split("@")
            host_part = "@" + parts[1]
            user_part = parts[0]
            if ":" in user_part:
                user, password = user_part.rsplit(":", 1)
                masked_url = user + ":***@" + parts[1]
            else:
                masked_url = db_url
        else:
            masked_url = db_url
            
        return {
            "database_url": masked_url,
            "env_database_url": os.getenv("DATABASE_URL", "NOT_SET")[:50] + "..." if os.getenv("DATABASE_URL") else "NOT_SET",
            "app_env": settings.app_env,
            "is_production": settings.app_env == "production"
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/create-tables")
async def create_tables():
    """Create database tables using minimal SQL schema"""
    try:
        from groupchat.db.database import engine
        from sqlalchemy import text
        
        # Minimal schema SQL - embedded directly
        schema_sql = """
        -- Core contacts table
        CREATE TABLE IF NOT EXISTS contacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone_number VARCHAR(20) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE,
            name VARCHAR(255) NOT NULL,
            bio TEXT,
            expertise_summary TEXT,
            trust_score FLOAT DEFAULT 0.5 NOT NULL,
            response_rate FLOAT DEFAULT 0.0 NOT NULL,
            avg_response_time_minutes FLOAT,
            total_contributions INTEGER DEFAULT 0 NOT NULL,
            total_earnings_cents INTEGER DEFAULT 0 NOT NULL,
            is_available BOOLEAN DEFAULT true NOT NULL,
            max_queries_per_day INTEGER DEFAULT 3 NOT NULL,
            preferred_contact_method VARCHAR(20) DEFAULT 'sms' NOT NULL,
            status VARCHAR(20) DEFAULT 'active' NOT NULL,
            extra_metadata JSONB DEFAULT '{}' NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            deleted_at TIMESTAMP WITH TIME ZONE
        );

        -- Core queries table
        CREATE TABLE IF NOT EXISTS queries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_phone VARCHAR(20) NOT NULL,
            question_text TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending' NOT NULL,
            max_experts INTEGER DEFAULT 5 NOT NULL,
            min_experts INTEGER DEFAULT 3 NOT NULL,
            timeout_minutes INTEGER DEFAULT 30 NOT NULL,
            total_cost_cents INTEGER DEFAULT 0 NOT NULL,
            platform_fee_cents INTEGER DEFAULT 0 NOT NULL,
            context JSONB DEFAULT '{}' NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            deleted_at TIMESTAMP WITH TIME ZONE
        );

        -- Core contributions table
        CREATE TABLE IF NOT EXISTS contributions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id UUID NOT NULL REFERENCES queries(id),
            contact_id UUID REFERENCES contacts(id),
            response_text TEXT NOT NULL,
            confidence_score FLOAT DEFAULT 0.5 NOT NULL,
            responded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            was_used BOOLEAN DEFAULT false NOT NULL,
            relevance_score FLOAT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );

        -- Core compiled answers table
        CREATE TABLE IF NOT EXISTS compiled_answers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id UUID NOT NULL REFERENCES queries(id),
            final_answer TEXT NOT NULL,
            summary TEXT,
            confidence_score FLOAT DEFAULT 0.5 NOT NULL,
            compilation_method VARCHAR(50) DEFAULT 'ai' NOT NULL,
            compilation_prompt TEXT,
            compilation_tokens_used INTEGER DEFAULT 0 NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );

        -- Core citations table
        CREATE TABLE IF NOT EXISTS citations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            compiled_answer_id UUID NOT NULL REFERENCES compiled_answers(id),
            contribution_id UUID NOT NULL REFERENCES contributions(id),
            claim_text TEXT NOT NULL,
            source_excerpt TEXT,
            position_in_answer INTEGER DEFAULT 0 NOT NULL,
            confidence FLOAT DEFAULT 0.5 NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );
        """
        
        # Execute the schema creation
        async with engine.begin() as conn:
            # Split SQL into individual statements and execute them
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            for stmt in statements:
                if stmt.startswith('--') or not stmt:
                    continue
                await conn.execute(text(stmt))
        
        return {"success": True, "message": "Minimal database schema created successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/fix-queries-table")
async def fix_queries_table():
    """Fix queries table status column to use enum"""
    try:
        from groupchat.db.database import engine
        from sqlalchemy import text
        
        # Create enum type and fix status column
        fix_status_sql = """
        -- Create QueryStatus enum if it doesn't exist
        DO $$ BEGIN
            CREATE TYPE querystatus AS ENUM ('pending', 'routing', 'collecting', 'compiling', 'completed', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        
        -- Create ContactStatus enum if it doesn't exist
        DO $$ BEGIN
            CREATE TYPE contactstatus AS ENUM ('active', 'inactive', 'pending', 'suspended');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        
        -- Alter the status columns to use the enums
        ALTER TABLE queries 
        ALTER COLUMN status TYPE querystatus 
        USING status::querystatus;
        
        ALTER TABLE contacts
        ALTER COLUMN status TYPE contactstatus
        USING status::contactstatus;
        """
        
        async with engine.begin() as conn:
            await conn.execute(text(fix_status_sql))
        
        return {"success": True, "message": "Queries table status fixed to use enum"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/test-query-creation")
async def test_query_creation():
    """Test query creation with minimal data"""
    try:
        from groupchat.db.database import engine
        from sqlalchemy import text
        import uuid
        
        # Test direct SQL insertion
        query_id = str(uuid.uuid4())
        insert_sql = """
        INSERT INTO queries (
            id, user_phone, question_text, status, 
            max_experts, min_experts, timeout_minutes,
            total_cost_cents, platform_fee_cents, context
        ) VALUES (
            :id, :user_phone, :question_text, :status,
            :max_experts, :min_experts, :timeout_minutes,
            :total_cost_cents, :platform_fee_cents, :context
        )
        """
        
        async with engine.begin() as conn:
            await conn.execute(text(insert_sql), {
                "id": query_id,
                "user_phone": "+1555123456",
                "question_text": "Test question for debugging",
                "status": "pending",
                "max_experts": 5,
                "min_experts": 3,
                "timeout_minutes": 30,
                "total_cost_cents": 100,
                "platform_fee_cents": 20,
                "context": "{}"
            })
        
        return {"success": True, "query_id": query_id, "message": "Query created successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}