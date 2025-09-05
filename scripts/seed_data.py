#!/usr/bin/env python3
"""Seed data script for development database"""

import asyncio
import uuid
from datetime import datetime, timedelta
import random
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groupchat.db.database import AsyncSessionLocal, engine
from groupchat.db.models import (
    Contact, ExpertiseTag, ContactExpertise, Query, Contribution,
    CompiledAnswer, Citation, ContactStatus, QueryStatus
)

# Sample data
EXPERTISE_TAGS = [
    {"name": "Python", "category": "Programming"},
    {"name": "Machine Learning", "category": "AI/ML"},
    {"name": "AWS", "category": "Cloud"},
    {"name": "Docker", "category": "DevOps"},
    {"name": "PostgreSQL", "category": "Database"},
    {"name": "React", "category": "Frontend"},
    {"name": "FastAPI", "category": "Backend"},
    {"name": "Data Science", "category": "Analytics"},
    {"name": "Security", "category": "Infrastructure"},
    {"name": "System Design", "category": "Architecture"},
]

SAMPLE_CONTACTS = [
    {
        "name": "Alice Johnson",
        "phone_number": "+15551234567",
        "email": "alice@example.com",
        "bio": "Senior Python developer with 10 years of experience in ML and backend systems",
        "expertise_summary": "Python, Machine Learning, FastAPI, PostgreSQL",
        "trust_score": 0.95,
        "response_rate": 0.92,
        "avg_response_time_minutes": 15.5,
        "tags": ["Python", "Machine Learning", "FastAPI", "PostgreSQL"]
    },
    {
        "name": "Bob Smith",
        "phone_number": "+15551234568",
        "email": "bob@example.com",
        "bio": "Cloud architect specializing in AWS and containerization",
        "expertise_summary": "AWS, Docker, System Design, Security",
        "trust_score": 0.88,
        "response_rate": 0.85,
        "avg_response_time_minutes": 22.3,
        "tags": ["AWS", "Docker", "System Design", "Security"]
    },
    {
        "name": "Carol Davis",
        "phone_number": "+15551234569",
        "email": "carol@example.com",
        "bio": "Full-stack developer with expertise in React and Python",
        "expertise_summary": "React, Python, FastAPI, PostgreSQL",
        "trust_score": 0.91,
        "response_rate": 0.88,
        "avg_response_time_minutes": 18.7,
        "tags": ["React", "Python", "FastAPI", "PostgreSQL"]
    },
    {
        "name": "David Wilson",
        "phone_number": "+15551234570",
        "email": "david@example.com",
        "bio": "Data scientist with expertise in ML and analytics",
        "expertise_summary": "Data Science, Machine Learning, Python",
        "trust_score": 0.93,
        "response_rate": 0.90,
        "avg_response_time_minutes": 20.1,
        "tags": ["Data Science", "Machine Learning", "Python"]
    },
    {
        "name": "Eve Martinez",
        "phone_number": "+15551234571",
        "email": "eve@example.com",
        "bio": "DevOps engineer specializing in CI/CD and infrastructure",
        "expertise_summary": "Docker, AWS, Security, System Design",
        "trust_score": 0.87,
        "response_rate": 0.82,
        "avg_response_time_minutes": 25.5,
        "tags": ["Docker", "AWS", "Security", "System Design"]
    }
]

SAMPLE_QUERIES = [
    {
        "user_phone": "+15559876543",
        "question_text": "How can I optimize my PostgreSQL queries for better performance?",
        "status": QueryStatus.COMPLETED,
        "contributions": [
            {
                "contact_name": "Alice Johnson",
                "response_text": "To optimize PostgreSQL queries: 1) Use EXPLAIN ANALYZE to understand query plans, 2) Create appropriate indexes on frequently queried columns, 3) Consider partial indexes for filtered queries, 4) Use connection pooling to reduce overhead.",
                "confidence_score": 0.95,
                "was_used": True
            },
            {
                "contact_name": "Carol Davis",
                "response_text": "Additionally, make sure to: vacuum and analyze regularly, avoid SELECT *, use prepared statements when possible, and consider partitioning large tables.",
                "confidence_score": 0.88,
                "was_used": True
            }
        ],
        "compiled_answer": "To optimize PostgreSQL queries for better performance:\n\n1. **Query Analysis**: Use EXPLAIN ANALYZE to understand query execution plans\n2. **Indexing Strategy**: Create appropriate indexes on frequently queried columns and consider partial indexes for filtered queries\n3. **Connection Management**: Implement connection pooling to reduce overhead\n4. **Maintenance**: Run VACUUM and ANALYZE regularly\n5. **Query Optimization**: Avoid SELECT *, use prepared statements, and consider table partitioning for large datasets\n\nThese optimizations can significantly improve query performance and database efficiency."
    },
    {
        "user_phone": "+15559876544",
        "question_text": "What's the best way to containerize a Python FastAPI application?",
        "status": QueryStatus.COMPLETED,
        "contributions": [
            {
                "contact_name": "Bob Smith",
                "response_text": "Use a multi-stage Dockerfile: First stage for dependencies with pip-compile, second stage for the app. Use Alpine Linux for smaller images. Configure uvicorn with proper workers.",
                "confidence_score": 0.92,
                "was_used": True
            },
            {
                "contact_name": "Eve Martinez",
                "response_text": "Don't forget health checks, non-root user, and proper signal handling. Use docker-compose for local development with hot reload enabled.",
                "confidence_score": 0.85,
                "was_used": True
            }
        ],
        "compiled_answer": "Best practices for containerizing a FastAPI application:\n\n1. **Multi-stage Build**: Use multi-stage Dockerfile to optimize image size\n2. **Base Image**: Consider Alpine Linux for minimal footprint\n3. **Dependencies**: Use pip-compile for reproducible builds\n4. **Runtime**: Configure uvicorn with appropriate worker count\n5. **Security**: Run as non-root user and implement health checks\n6. **Development**: Use docker-compose with volume mounts for hot reload\n\nThis approach ensures efficient, secure, and maintainable containerization."
    }
]


async def seed_database():
    """Seed the database with sample data"""
    async with AsyncSessionLocal() as session:
        try:
            print("🌱 Starting database seeding...")
            
            # Create expertise tags
            print("Creating expertise tags...")
            tags_map = {}
            for tag_data in EXPERTISE_TAGS:
                tag = ExpertiseTag(
                    id=uuid.uuid4(),
                    name=tag_data["name"],
                    category=tag_data["category"]
                )
                session.add(tag)
                tags_map[tag.name] = tag
            
            await session.flush()
            
            # Create contacts
            print("Creating contacts...")
            contacts_map = {}
            for contact_data in SAMPLE_CONTACTS:
                contact = Contact(
                    id=uuid.uuid4(),
                    name=contact_data["name"],
                    phone_number=contact_data["phone_number"],
                    email=contact_data["email"],
                    bio=contact_data["bio"],
                    expertise_summary=contact_data["expertise_summary"],
                    trust_score=contact_data["trust_score"],
                    response_rate=contact_data["response_rate"],
                    avg_response_time_minutes=contact_data["avg_response_time_minutes"],
                    status=ContactStatus.ACTIVE,
                    is_available=True,
                    total_contributions=random.randint(10, 100),
                    total_earnings_cents=random.randint(1000, 10000)
                )
                session.add(contact)
                contacts_map[contact.name] = contact
                
                # Add expertise tags
                for tag_name in contact_data["tags"]:
                    if tag_name in tags_map:
                        contact_expertise = ContactExpertise(
                            contact_id=contact.id,
                            tag_id=tags_map[tag_name].id,
                            confidence_score=random.uniform(0.7, 1.0)
                        )
                        session.add(contact_expertise)
            
            await session.flush()
            
            # Create queries with contributions and compiled answers
            print("Creating queries with contributions...")
            for query_data in SAMPLE_QUERIES:
                query = Query(
                    id=uuid.uuid4(),
                    user_phone=query_data["user_phone"],
                    question_text=query_data["question_text"],
                    status=query_data["status"],
                    max_experts=5,
                    min_experts=2,
                    timeout_minutes=30,
                    total_cost_cents=50,
                    platform_fee_cents=10
                )
                session.add(query)
                await session.flush()
                
                # Create contributions
                contribution_ids = []
                for contrib_data in query_data["contributions"]:
                    if contrib_data["contact_name"] in contacts_map:
                        contribution = Contribution(
                            id=uuid.uuid4(),
                            query_id=query.id,
                            contact_id=contacts_map[contrib_data["contact_name"]].id,
                            response_text=contrib_data["response_text"],
                            confidence_score=contrib_data["confidence_score"],
                            was_used=contrib_data["was_used"],
                            requested_at=datetime.utcnow() - timedelta(minutes=30),
                            responded_at=datetime.utcnow() - timedelta(minutes=20),
                            response_time_minutes=10,
                            payout_amount_cents=25
                        )
                        session.add(contribution)
                        contribution_ids.append(contribution.id)
                
                await session.flush()
                
                # Create compiled answer
                if query_data.get("compiled_answer"):
                    compiled_answer = CompiledAnswer(
                        id=uuid.uuid4(),
                        query_id=query.id,
                        final_answer=query_data["compiled_answer"],
                        summary="AI-synthesized answer from multiple expert contributions",
                        confidence_score=0.9,
                        compilation_method="gpt-4",
                        compilation_tokens_used=random.randint(100, 500)
                    )
                    session.add(compiled_answer)
                    await session.flush()
                    
                    # Create sample citations
                    for i, contrib_id in enumerate(contribution_ids):
                        citation = Citation(
                            id=uuid.uuid4(),
                            compiled_answer_id=compiled_answer.id,
                            contribution_id=contrib_id,
                            claim_text=f"Claim {i+1} from the answer",
                            source_excerpt=f"Excerpt from contribution {i+1}",
                            position_in_answer=i,
                            confidence=random.uniform(0.8, 1.0)
                        )
                        session.add(citation)
            
            await session.commit()
            print("✅ Database seeded successfully!")
            
            # Print summary
            print("\n📊 Seed data summary:")
            print(f"  - {len(EXPERTISE_TAGS)} expertise tags")
            print(f"  - {len(SAMPLE_CONTACTS)} contacts")
            print(f"  - {len(SAMPLE_QUERIES)} queries with contributions")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error seeding database: {e}")
            raise


async def main():
    """Main entry point"""
    await seed_database()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())