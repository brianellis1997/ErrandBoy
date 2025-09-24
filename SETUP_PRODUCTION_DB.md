# Production Database Setup Guide

## Quick Fix: Use Free Cloud Services

### Option 1: Supabase (PostgreSQL) - RECOMMENDED
1. Go to https://supabase.com
2. Sign up for free account
3. Create new project
4. Get connection string from Settings → Database
5. Your connection string will look like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
   ```

### Option 2: Neon (PostgreSQL)
1. Go to https://neon.tech
2. Sign up for free account
3. Create database
4. Get connection string

### Option 3: Aiven (PostgreSQL + Redis)
1. Go to https://aiven.io
2. Free trial with $300 credits
3. Create PostgreSQL and Redis services

## For Redis (Choose One):

### Option 1: Upstash Redis - RECOMMENDED
1. Go to https://upstash.com
2. Sign up for free account
3. Create Redis database
4. Get connection string (Redis URL)

### Option 2: Redis Cloud
1. Go to https://redis.com/try-free/
2. Create free database (30MB)
3. Get connection string

## Configure Elastic Beanstalk

Once you have your database URLs, update environment variables:

```bash
eb setenv \
  DATABASE_URL="postgresql+asyncpg://[your-supabase-url]" \
  REDIS_URL="redis://[your-upstash-url]" \
  OPENAI_API_KEY="sk-..." \
  APP_ENV="production" \
  APP_DEBUG="false"
```

## AWS Native Options (More Complex)

### RDS PostgreSQL
```bash
# Create RDS instance via AWS Console
# Cost: ~$15/month for db.t3.micro
```

### ElastiCache Redis
```bash
# Create ElastiCache cluster via AWS Console  
# Cost: ~$15/month for cache.t3.micro
```

## Quick Test

After setting environment variables, the app will restart automatically.
Test at: http://groupchat-prod.eba-ys7bggv2.us-east-1.elasticbeanstalk.com