# MVP GitHub Issues for GroupChat

## Milestone: MVP - Network Intelligence System
**Due Date**: September 14, 2025
**Description**: First working version of GroupChat with core features: contact management, query routing, answer synthesis with citations, and ledger-based micropayments

## Issues to Create

### 1. Project Setup & Infrastructure
**Title**: Set up project structure and core dependencies
**Labels**: setup, infrastructure
**Description**:
- Initialize Python project with pyproject.toml
- Set up FastAPI application structure
- Configure PostgreSQL with pgvector extension
- Set up Alembic for migrations
- Configure environment variables (.env.example)
- Set up basic logging

**Acceptance Criteria**:
- [ ] Project runs with `uvicorn groupchat.main:app --reload`
- [ ] Database connects successfully
- [ ] Basic health check endpoint works
- [ ] Development environment documented

---

### 2. Database Schema Implementation
**Title**: Create database schema with PostgreSQL + pgvector
**Labels**: database, backend
**Description**:
Implement core tables:
- contacts (with expertise_vector)
- queries
- contributions
- compiled_answers
- citations
- ledger
- payout_splits

**Acceptance Criteria**:
- [ ] All tables created via Alembic migration
- [ ] pgvector extension configured
- [ ] Indexes optimized for query performance
- [ ] Basic seed data script available

---

### 3. Contact Management System
**Title**: Implement contact profile management
**Labels**: feature, backend
**Description**:
- CRUD operations for contacts
- Expertise tagging system
- Bio and metadata storage
- Consent tracking (SMS, email, etc.)
- Availability preferences

**Acceptance Criteria**:
- [ ] POST /contacts endpoint working
- [ ] GET /contacts/{id} endpoint working
- [ ] UPDATE /contacts/{id} endpoint working
- [ ] Expertise vectors generated from bio/tags

---

### 4. Query Processing Pipeline
**Title**: Build query submission and routing system
**Labels**: feature, core
**Description**:
- Query intake endpoint
- Query embedding generation
- Expert matching algorithm
- Outreach queue management

**Acceptance Criteria**:
- [ ] POST /queries endpoint accepts questions
- [ ] Queries are embedded using chosen model
- [ ] Top-K experts identified based on relevance
- [ ] Match scores calculated correctly

---

### 5. Expert Matching Algorithm
**Title**: Implement smart expert-to-query matching
**Labels**: feature, ml
**Description**:
- Vector similarity search with pgvector
- Multi-factor scoring (expertise, location, availability, trust)
- Re-ranking logic
- Diversity considerations

**Acceptance Criteria**:
- [ ] Semantic search working with embeddings
- [ ] Geographic proximity boost for local queries
- [ ] Trust scores affect ranking
- [ ] Results are diverse and relevant

---

### 6. SMS Integration (Twilio)
**Title**: Create Twilio webhook for SMS communication
**Labels**: feature, integration
**Description**:
- Webhook endpoint for incoming SMS
- Outbound SMS for expert queries
- STOP/START/HELP compliance
- Message threading to track conversations

**Acceptance Criteria**:
- [ ] POST /webhooks/twilio endpoint working
- [ ] Incoming SMS tied to correct query
- [ ] Opt-out handling implemented
- [ ] Rate limiting in place

---

### 7. Answer Synthesis with Citations
**Title**: Build answer compilation and citation system
**Labels**: feature, core
**Description**:
- Collect contributions from experts
- LLM-based synthesis with citation tracking
- Generate structured answer with inline [@handle] citations
- Store citation mappings

**Acceptance Criteria**:
- [ ] Contributions stored with metadata
- [ ] Synthesis produces JSON with citations
- [ ] Each claim traces to contributor
- [ ] GET /queries/{id}/answer returns cited response

---

### 8. Micropayment Ledger
**Title**: Implement ledger system for micropayments
**Labels**: feature, payments
**Description**:
- Double-entry bookkeeping ledger
- Contribution weight calculation
- Payout split computation
- Balance tracking per user

**Acceptance Criteria**:
- [ ] Ledger entries created for each transaction
- [ ] Splits calculated based on contribution weights
- [ ] User balances queryable
- [ ] Audit trail maintained

---

### 9. Agent Tools & LangGraph Integration
**Title**: Create agent tools for orchestration
**Labels**: feature, ai
**Description**:
Tools to implement:
- save_contact_profile
- create_query
- outreach_expert
- record_contribution
- compile_answer
- settle_payments

**Acceptance Criteria**:
- [ ] All tools accessible to LangGraph agent
- [ ] Tools properly typed and documented
- [ ] Error handling in place
- [ ] Tools tested individually

---

### 10. API Documentation & Testing
**Title**: Complete API documentation and basic tests
**Labels**: documentation, testing
**Description**:
- OpenAPI/Swagger documentation
- Postman collection
- Basic pytest suite
- Example requests/responses

**Acceptance Criteria**:
- [ ] Swagger UI accessible at /docs
- [ ] Core endpoints have tests
- [ ] README has clear setup instructions
- [ ] Example .env file provided

---

## Priority Order for MVP
1. Project Setup (Issue #1)
2. Database Schema (Issue #2)
3. Contact Management (Issue #3)
4. Query Processing (Issue #4)
5. Expert Matching (Issue #5)
6. Answer Synthesis (Issue #7)
7. SMS Integration (Issue #6)
8. Micropayment Ledger (Issue #8)
9. Agent Tools (Issue #9)
10. Documentation (Issue #10)

## Labels to Create
- `mvp` - Part of MVP milestone
- `setup` - Project setup and configuration
- `infrastructure` - Core infrastructure
- `database` - Database related
- `backend` - Backend development
- `feature` - New feature
- `core` - Core functionality
- `ml` - Machine learning/AI
- `integration` - Third-party integration
- `payments` - Payment/ledger related
- `ai` - AI/Agent related
- `documentation` - Documentation improvements
- `testing` - Testing related