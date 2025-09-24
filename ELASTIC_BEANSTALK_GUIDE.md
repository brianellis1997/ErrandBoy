# Easy AWS Elastic Beanstalk Deployment Guide

## Why Elastic Beanstalk?
- **No server management** - AWS handles everything
- **Pay as you go** - Only pay for what you use
- **Auto-scaling** - Grows with your traffic
- **One-click deploys** - Super simple updates
- **Free tier eligible** - Free for 750 hours/month

## Step 1: Install EB CLI Tool

```bash
# On Mac
brew install awsebcli

# Or with pip
pip install awsebcli
```

## Step 2: Initialize Elastic Beanstalk

In your project directory:

```bash
cd /Users/bdogellis/ErrandBoy

# Initialize EB (it will ask for AWS credentials)
eb init -p python-3.11 groupchat-app --region us-east-1

# Choose:
# - Default region: us-east-1 (or your preferred)
# - Application name: groupchat-app
# - Python version: Python 3.11
# - SSH: Yes (create new keypair)
```

## Step 3: Create Environment & Deploy

```bash
# Create environment and deploy
eb create groupchat-env --instance-type t3.small

# This will:
# - Create the environment (takes ~5 minutes)
# - Upload your code
# - Set up load balancer
# - Give you a URL like: groupchat-env.us-east-1.elasticbeanstalk.com
```

## Step 4: Set Environment Variables

```bash
# Set your environment variables
eb setenv \
  DATABASE_URL="postgresql+asyncpg://user:pass@your-rds.amazonaws.com/db" \
  REDIS_URL="redis://your-elasticache.amazonaws.com:6379/0" \
  OPENAI_API_KEY="sk-..." \
  TWILIO_ACCOUNT_SID="AC..." \
  TWILIO_AUTH_TOKEN="..." \
  TWILIO_PHONE_NUMBER="+1..." \
  APP_ENV="production" \
  APP_DEBUG="false" \
  APP_SECRET_KEY="your-secret-key"
```

## Step 5: Open Your App

```bash
# Open in browser
eb open

# Check status
eb status

# View logs
eb logs
```

## Step 6: Custom Domain (Optional)

### In AWS Console:
1. Go to **Route 53** → **Hosted Zones**
2. Create hosted zone for your domain
3. Create A record → Alias → Point to Elastic Beanstalk environment

### Or use EB CLI:
```bash
# If you have a domain in Route53
eb swap groupchat-env --destination yourdomain.com
```

## Step 7: Database Setup

### Option A: Use AWS RDS (Recommended)
1. In EB Console → Configuration → Database
2. Add RDS database:
   - Engine: PostgreSQL
   - Instance class: db.t3.micro (free tier)
   - Storage: 20GB

### Option B: Use External Database
- Use any PostgreSQL service (Supabase, Neon, etc.)
- Just update DATABASE_URL environment variable

## Updating Your App

Super easy updates:
```bash
# Make your changes, then:
eb deploy

# That's it! Zero downtime deployment
```

## Monitoring

```bash
# Check health
eb health

# View recent logs
eb logs --tail

# SSH into instance (if needed)
eb ssh
```

## Costs (Pay As You Go)

**Free Tier (First Year):**
- t3.micro EC2: 750 hours/month FREE
- RDS db.t3.micro: 750 hours/month FREE
- Total: $0/month

**After Free Tier:**
- t3.small: ~$15/month
- RDS db.t3.micro: ~$15/month
- Load Balancer: ~$20/month
- Total: ~$50/month

**Only pay for what you use!**

## Common Commands

```bash
# Deploy updates
eb deploy

# View environment variables
eb printenv

# Scale up/down
eb scale 2  # Scale to 2 instances

# Terminate (delete everything)
eb terminate --all
```

## Troubleshooting

If deploy fails:
```bash
# Check logs
eb logs

# Common fixes:
# 1. Check requirements.txt has all packages
# 2. Verify Procfile exists
# 3. Check Python version matches
```

## Alternative: Use AWS Console (GUI)

1. Go to: https://console.aws.amazon.com/elasticbeanstalk
2. Click "Create Application"
3. Upload your code as ZIP file
4. Follow the wizard
5. Done!

---

## Quick Start Summary

```bash
# 1. Install CLI
brew install awsebcli

# 2. Initialize
eb init -p python-3.11 groupchat-app

# 3. Deploy
eb create groupchat-env

# 4. Set environment variables
eb setenv KEY=value KEY2=value2

# 5. Open app
eb open
```

That's it! Your app is live on AWS!