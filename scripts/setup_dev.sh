#!/bin/bash

# GroupChat Development Setup Script

set -e

echo "========================================="
echo "GroupChat Development Environment Setup"
echo "========================================="

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required. Found: Python $python_version"
    exit 1
fi
echo "✓ Python $python_version"

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry not found. Installing..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "✓ Poetry installed"

# Install dependencies
echo "Installing Python dependencies..."
poetry install

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration"
else
    echo "✓ .env file exists"
fi

# Check PostgreSQL
echo "Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL client found"
    echo "  Make sure PostgreSQL server is running and configured"
else
    echo "⚠️  PostgreSQL client not found"
    echo "  Install PostgreSQL or use Docker:"
    echo "  docker run -d --name groupchat-postgres -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15"
fi

# Check Redis (optional)
echo "Checking Redis..."
if command -v redis-cli &> /dev/null; then
    echo "✓ Redis client found"
else
    echo "⚠️  Redis client not found (optional for MVP)"
    echo "  Install Redis or use Docker:"
    echo "  docker run -d --name groupchat-redis -p 6379:6379 redis:7"
fi

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Update .env with your configuration"
echo "2. Ensure PostgreSQL is running"
echo "3. Run database migrations: poetry run alembic upgrade head"
echo "4. Start the development server: poetry run uvicorn groupchat.main:app --reload"
echo ""
echo "For testing:"
echo "  poetry run pytest"
echo ""
echo "API documentation will be available at:"
echo "  http://localhost:8000/docs"