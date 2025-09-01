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

2. **Run the setup script**
```bash
chmod +x scripts/setup_dev.sh
./scripts/setup_dev.sh
```

3. **Start PostgreSQL and Redis with Docker**
```bash
docker-compose up -d postgres redis
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run database migrations**
```bash
poetry run alembic upgrade head
```

6. **Start the development server**
```bash
poetry run uvicorn groupchat.main:app --reload
```

7. **View API documentation**
Open http://localhost:8000/docs in your browser

## Project Structure

```
ErrandBoy/
├── groupchat/           # Main application package
│   ├── api/            # FastAPI endpoints
│   ├── db/             # Database models and connections
│   ├── services/       # Business logic and external services
│   ├── tools/          # Agent tools for LangGraph
│   ├── workflows/      # Query processing workflows
│   └── utils/          # Utility functions
├── migrations/         # Alembic database migrations
├── tests/             # Test suite
├── scripts/           # Development and deployment scripts
└── docker-compose.yml # Local development services
```

## API Endpoints

### Health Checks
- `GET /health/` - Basic health check
- `GET /health/ready` - Readiness check with database status
- `GET /health/live` - Liveness probe

### Contacts
- `POST /api/v1/contacts` - Create a contact
- `GET /api/v1/contacts/{id}` - Get contact details
- `PUT /api/v1/contacts/{id}` - Update contact
- `DELETE /api/v1/contacts/{id}` - Soft delete contact

### Queries
- `POST /api/v1/queries` - Submit a query
- `GET /api/v1/queries/{id}` - Get query status
- `GET /api/v1/queries/{id}/answer` - Get compiled answer with citations
- `GET /api/v1/queries/{id}/contributions` - Get all contributions
- `POST /api/v1/queries/{id}/accept` - Accept answer and trigger payments

### Webhooks
- `POST /api/v1/webhooks/twilio` - Twilio SMS webhook
- `POST /api/v1/webhooks/stripe` - Stripe payment webhook

## Testing

Run the test suite:
```bash
poetry run pytest
```

With coverage:
```bash
poetry run pytest --cov=groupchat --cov-report=html
```

## Contributing

See [GitHub Issues](https://github.com/brianellis1997/ErrandBoy/issues) for current tasks and the MVP milestone.

## License

MIT License - see LICENSE file for details  
