# GroupChat (ErrandBoy)
> 🌍 If the world was a group chat — an errand boy for your questions.
> > Ask anything. The most relevant people answer. Answers are cited, cached, and reused.

## Overview

GroupChat is a network intelligence system that routes questions to the most relevant experts in your network, collects their responses, and synthesizes answers with full attribution. Every contribution is tracked and micropayments are distributed to contributors.

## Features

- 🎯 **Smart Routing**: Questions are matched to experts using semantic search and multi-factor scoring
- 💬 **Multi-Channel Communication**: Reach experts via SMS, WhatsApp, email (Twilio integration)
- 📝 **Citation by Design**: Every claim in answers traces back to who said it
- 💰 **Micropayments**: Contributors earn fractions of cents per accepted answer
- 🔍 **Expertise Tracking**: Build knowledge graphs of who knows what
- ⚡ **Fast API**: Async Python with FastAPI for high performance

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis (optional, for caching)
- Twilio account (for SMS features)
- OpenAI API key (for embeddings)

### Local Development Setup

1. **Clone the repository**
```bash
git clone https://github.com/brianellis1997/ErrandBoy.git
cd ErrandBoy
```

2. **Activate conda environment**
```bash
conda activate GroupChat
```

3. **Install dependencies**
```bash
python -m pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Start the development server**
```bash
python -m uvicorn groupchat.main:app --reload
```

6. **View API documentation**
Open http://localhost:8000/docs in your browser

## Project Structure

```
ErrandBoy/
├── groupchat/           # Main application package
│   ├── api/            # FastAPI endpoints
│   ├── agent/          # AI agent tools and workflows
│   ├── db/             # Database models and connections
│   ├── services/       # Business logic and external services
│   └── utils/          # Utility functions
├── static/             # Frontend HTML/CSS/JS
├── migrations/         # Alembic database migrations (if needed)
└── scripts/            # Development scripts
```

## Architecture

GroupChat follows a microservices-inspired architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Agent Tools    │    │   Workflow      │
│   (FastAPI)     │────│  (LangGraph)    │────│  Orchestration  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Core Services │    │  External APIs  │    │   Database      │
│                 │    │                 │    │                 │
│ • Contacts      │    │ • Twilio SMS    │    │ • PostgreSQL    │
│ • Queries       │    │ • OpenAI        │    │ • pgvector      │
│ • Synthesis     │    │ • Stripe        │    │ • Redis Cache   │
│ • Matching      │    │ • Email         │    │                 │
│ • Payments      │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## API Endpoints

### 🏥 Health & Status
- `GET /health/` - Basic health check
- `GET /health/ready` - Readiness check with database status
- `GET /health/live` - Liveness probe
- `GET /health/config` - Configuration validation

### 👥 Contact Management
- `POST /api/v1/contacts` - Create a contact
- `GET /api/v1/contacts` - List all contacts
- `GET /api/v1/contacts/search` - Search contacts by expertise
- `GET /api/v1/contacts/{id}` - Get contact details
- `PUT /api/v1/contacts/{id}` - Update contact
- `DELETE /api/v1/contacts/{id}` - Soft delete contact
- `POST /api/v1/contacts/{id}/expertise` - Update expertise tags

### ❓ Query Processing
- `POST /api/v1/queries` - Submit a query
- `GET /api/v1/queries` - List queries
- `GET /api/v1/queries/{id}` - Get query details
- `GET /api/v1/queries/{id}/status` - Get detailed query status
- `POST /api/v1/queries/{id}/route` - Route query to experts
- `GET /api/v1/queries/{id}/matches` - Get expert matches
- `GET /api/v1/queries/{id}/contributions` - Get all contributions
- `GET /api/v1/queries/{id}/answer` - Get compiled answer with citations
- `POST /api/v1/queries/{id}/synthesize` - Trigger answer synthesis
- `GET /api/v1/queries/{id}/synthesis/status` - Get synthesis status
- `POST /api/v1/queries/{id}/accept` - Accept answer and trigger payments

### 🎯 Expert Matching
- `POST /api/v1/matching/experts/{query_id}` - Find expert matches
- `GET /api/v1/matching/stats/{query_id}` - Get matching statistics
- `GET /api/v1/matching/test/similarity` - Test similarity scoring

### 💰 Payments & Ledger
- `GET /api/v1/ledger/balance/{account_type}/{account_id}` - Get account balance
- `GET /api/v1/ledger/transactions` - Get transaction history
- `GET /api/v1/ledger/transaction/{id}/validate` - Validate transaction balance
- `POST /api/v1/ledger/process-payment` - Process query payment
- `GET /api/v1/ledger/contact/{id}/earnings` - Get contact earnings
- `GET /api/v1/ledger/stats/platform` - Get platform statistics

### 🤖 Agent & Workflow
- `POST /api/v1/agent/process-query` - **Full end-to-end query processing**
- `POST /api/v1/agent/tools/save-contact` - Save contact profile
- `PUT /api/v1/agent/tools/contacts/{id}/expertise` - Update expertise
- `GET /api/v1/agent/tools/search-contacts` - Search contacts
- `POST /api/v1/agent/tools/queries` - Create query
- `GET /api/v1/agent/tools/queries/{id}/status` - Get query status
- `POST /api/v1/agent/tools/queries/{id}/synthesize` - Synthesize answer
- `POST /api/v1/agent/tools/queries/{id}/settle` - Settle query with payment

### 🔗 Webhooks & Integrations
- `POST /api/v1/webhooks/twilio` - Twilio SMS webhook
- `POST /api/v1/webhooks/stripe` - Stripe payment webhook

### 🛠️ Admin & Monitoring
- `GET /api/v1/admin/stats` - System statistics
- `GET /api/v1/admin/health` - Detailed health check

## Usage Examples

### Submit and Process a Complete Query

```bash
# 1. Submit query via agent (handles everything automatically)
curl -X POST "http://localhost:8000/api/v1/agent/process-query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_phone": "+1234567890",
    "question_text": "What are the best practices for scaling PostgreSQL?",
    "max_spend_cents": 500
  }'

# Response includes query_id, final_answer, experts_contacted, payment details
```

### Manual Query Processing (Step by Step)

```bash
# 1. Create query
curl -X POST "http://localhost:8000/api/v1/queries" \
  -H "Content-Type: application/json" \
  -d '{
    "user_phone": "+1234567890", 
    "question_text": "How do I optimize React performance?",
    "max_spend_cents": 300
  }'

# 2. Route to experts
curl -X POST "http://localhost:8000/api/v1/queries/{query_id}/route"

# 3. Check status
curl "http://localhost:8000/api/v1/queries/{query_id}/status"

# 4. Get final answer (after experts respond)
curl "http://localhost:8000/api/v1/queries/{query_id}/answer"
```

### Contact Management

```bash
# Create expert contact
curl -X POST "http://localhost:8000/api/v1/contacts" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dr. Jane Smith",
    "phone_number": "+1987654321",
    "email": "jane@university.edu",
    "bio": "Database systems researcher with 10 years PostgreSQL experience",
    "expertise_tags": ["postgresql", "databases", "performance"]
  }'

# Search for experts
curl "http://localhost:8000/api/v1/contacts/search?q=postgresql&limit=5"
```

## Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/groupchat

# OpenAI (for embeddings and synthesis)
OPENAI_API_KEY=sk-your-openai-api-key

# Twilio (for SMS)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Application
APP_ENV=development
APP_DEBUG=true
APP_SECRET_KEY=your-secret-key

# Features (optional)
ENABLE_SMS=false
ENABLE_PAYMENTS=false
ENABLE_REAL_EMBEDDINGS=false
```

### Payment Configuration
```bash
# Micropayment splits (must sum to 1.0)
CONTRIBUTOR_POOL_PERCENTAGE=0.7  # 70% to contributors
PLATFORM_PERCENTAGE=0.2         # 20% to platform
REFERRER_PERCENTAGE=0.1          # 10% to referrers

# Default query price
QUERY_PRICE_CENTS=0.5           # Half a cent per query
```

## Testing

### Run All Tests
```bash
poetry run pytest
```

### Run Specific Test Types
```bash
# Unit tests only
poetry run pytest -m "unit"

# Integration tests only  
poetry run pytest -m "integration"

# With coverage report
poetry run pytest --cov=groupchat --cov-report=html

# Run tests with specific markers
poetry run pytest -m "not slow" --tb=short
```

### Test Categories
- **Unit**: Individual function testing
- **Integration**: API endpoint testing
- **E2E**: End-to-end workflow testing
- **External**: Tests requiring external services

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check PostgreSQL status
pg_isready -h localhost -p 5432

# Reset database
poetry run alembic downgrade base
poetry run alembic upgrade head

# Check connection string
echo $DATABASE_URL
```

#### Import/Module Issues
```bash
# Reinstall dependencies
poetry install --no-cache

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Verify installation
poetry run python -c "from groupchat.main import app; print('✓ App imports successfully')"
```

#### Port Already in Use
```bash
# Find process using port 8000
lsof -ti:8000

# Kill process
kill $(lsof -ti:8000)

# Use different port
poetry run uvicorn groupchat.main:app --port 8001
```

#### OpenAI API Issues
```bash
# Test API key
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models | jq '.data[0].id'

# Check rate limits in logs
grep -i "rate limit" logs/app.log
```

### Development Commands

```bash
# Start with auto-reload
poetry run uvicorn groupchat.main:app --reload

# Run with specific log level
poetry run uvicorn groupchat.main:app --log-level debug

# Check configuration
poetry run python -c "from groupchat.config import settings; print(settings.validate_configuration())"

# Database shell
poetry run python -c "
from groupchat.db.database import AsyncSessionLocal
import asyncio
async def main():
    async with AsyncSessionLocal() as session:
        print('Database connection successful')
asyncio.run(main())
"
```

### Performance Tuning

#### Database Optimization
```sql
-- Add indexes for common queries
CREATE INDEX CONCURRENTLY idx_queries_created_status ON queries(created_at, status);
CREATE INDEX CONCURRENTLY idx_contacts_expertise_gin ON contacts USING gin(expertise_embedding);

-- Update statistics
ANALYZE contacts;
ANALYZE queries;
```

#### Caching Configuration
```bash
# Enable Redis caching
REDIS_URL=redis://localhost:6379/0

# Cache embeddings
ENABLE_EMBEDDING_CACHE=true

# Set cache TTL
CACHE_TTL_SECONDS=3600
```

## Deployment

### Railway Deployment

GroupChat is deployed on [Railway](https://railway.app):

**Live URL**: https://web-production-92dde.up.railway.app

**Deployment Process**:
1. Push changes to `main` branch
2. Railway automatically builds and deploys
3. Deployment completes in 30-60 seconds

**Environment Variables** (set via Railway dashboard):
- `DATABASE_URL` - Automatically provided by Railway PostgreSQL
- `OPENAI_API_KEY` - Your OpenAI API key
- `TWILIO_ACCOUNT_SID` - Twilio SID (for SMS)
- `TWILIO_AUTH_TOKEN` - Twilio token (for SMS)
- `TWILIO_PHONE_NUMBER` - Twilio phone number (for SMS)

**Check Deployment**:
```bash
# Open live app
open https://web-production-92dde.up.railway.app

# Health check
curl https://web-production-92dde.up.railway.app/health/ready
```

## Contributing

See [GitHub Issues](https://github.com/brianellis1997/ErrandBoy/issues) for current tasks and the MVP milestone.

### Development Workflow
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes following the existing patterns
4. Add tests for new functionality
5. Run the test suite: `poetry run pytest`
6. Submit a pull request

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all functions
- Add docstrings for public APIs
- Keep functions focused and small
- Use meaningful variable names

## License

MIT License - see LICENSE file for details
