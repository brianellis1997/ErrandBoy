# AWS EC2 Deployment Guide for GroupChat

## Overview
This guide walks you through deploying your GroupChat FastAPI application on AWS EC2 with a custom domain using Route53.

## Prerequisites
- AWS Account
- Domain name (can be purchased through Route53 or external registrar)
- Basic knowledge of terminal/SSH
- GitHub repository with your code

## Step 1: Set Up AWS Account and EC2 Instance

### 1.1 Create EC2 Instance
1. Log into AWS Console
2. Navigate to EC2 Dashboard
3. Click "Launch Instance"
4. Configure:
   - **Name**: GroupChat-Production
   - **AMI**: Ubuntu Server 22.04 LTS (HVM)
   - **Instance Type**: t3.medium (minimum for production)
   - **Key Pair**: Create new or use existing (.pem file for SSH)
   - **Network Settings**:
     - Allow SSH (port 22)
     - Allow HTTP (port 80)
     - Allow HTTPS (port 443)
   - **Storage**: 30 GB gp3 (adjust based on needs)

### 1.2 Elastic IP (Optional but Recommended)
1. Go to EC2 → Elastic IPs
2. Allocate new Elastic IP
3. Associate with your EC2 instance
4. Note this IP for domain configuration

## Step 2: Connect to Your EC2 Instance

```bash
# Set permissions for your key file
chmod 400 your-key.pem

# Connect via SSH
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

## Step 3: Deploy Application

### 3.1 Quick Deploy (Automated)
```bash
# Download and run deployment script
wget https://raw.githubusercontent.com/brianellis1997/ErrandBoy/main/scripts/deploy_aws.sh
chmod +x deploy_aws.sh
./deploy_aws.sh
```

### 3.2 Manual Deploy (Step by Step)

#### Install Dependencies
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python 3.11
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# Install nginx
sudo apt-get install -y nginx

# Install PostgreSQL (or skip if using RDS)
sudo apt-get install -y postgresql postgresql-contrib

# Install Redis
sudo apt-get install -y redis-server
```

#### Clone and Setup Application
```bash
# Clone repository
git clone https://github.com/brianellis1997/ErrandBoy.git ~/groupchat
cd ~/groupchat

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Copy and edit environment file
cp .env.example .env
nano .env  # Edit with your actual values
```

#### Configure Database
```bash
# If using local PostgreSQL
sudo -u postgres createdb groupchat
sudo -u postgres createuser groupchat_user

# Run migrations
alembic upgrade head
```

#### Setup Nginx
```bash
# Copy nginx config
sudo cp nginx.conf /etc/nginx/sites-available/groupchat
sudo ln -s /etc/nginx/sites-available/groupchat /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test and restart nginx
sudo nginx -t
sudo systemctl restart nginx
```

#### Run Application
```bash
# Using systemd (recommended)
sudo nano /etc/systemd/system/groupchat.service
# Copy the service configuration from deploy_aws.sh

sudo systemctl enable groupchat
sudo systemctl start groupchat

# Check status
sudo systemctl status groupchat
```

## Step 4: Configure Domain with Route53

### 4.1 Register Domain (if needed)
1. Go to Route53 → Registered domains
2. Register new domain or transfer existing

### 4.2 Create Hosted Zone
1. Route53 → Hosted zones
2. Create hosted zone for your domain
3. Note the NS records

### 4.3 Create A Records
1. In your hosted zone, create:
   - **A Record**: 
     - Name: (leave blank for root)
     - Type: A
     - Value: Your EC2 Elastic IP
   - **A Record**:
     - Name: www
     - Type: A
     - Value: Your EC2 Elastic IP

### 4.4 Update Domain Nameservers
If domain registered outside AWS:
1. Go to your registrar
2. Update nameservers to Route53 NS records

## Step 5: SSL Certificate Setup

### 5.1 Install Certbot
```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### 5.2 Obtain Certificate
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 5.3 Auto-renewal
```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot automatically sets up cron job for renewal
```

## Step 6: Environment Configuration

Edit `/home/ubuntu/groupchat/.env`:

```bash
# Database (use RDS endpoint if using RDS)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/groupchat

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...

# Twilio (if using SMS)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Application
APP_ENV=production
APP_DEBUG=false
APP_BASE_URL=https://yourdomain.com

# Update CORS for your domain
CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
```

## Step 7: Optional - Use AWS RDS for Database

### 7.1 Create RDS Instance
1. Navigate to RDS → Create database
2. Choose PostgreSQL
3. Configure:
   - DB instance identifier: groupchat-db
   - Master username: groupchat_user
   - Choose password
   - DB instance class: db.t3.micro (for testing)
   - Storage: 20 GB
   - VPC: Same as EC2
   - Security group: Allow PostgreSQL from EC2

### 7.2 Update Configuration
```bash
# Update .env with RDS endpoint
DATABASE_URL=postgresql+asyncpg://groupchat_user:password@your-rds-endpoint:5432/groupchat
```

## Step 8: Monitoring and Maintenance

### Check Application Status
```bash
# View logs
sudo journalctl -u groupchat -f

# Check nginx logs
sudo tail -f /var/log/nginx/error.log

# Application logs
tail -f /var/log/groupchat.log
```

### Update Application
```bash
cd ~/groupchat
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart groupchat
```

### Backup Database
```bash
# Create backup
pg_dump groupchat > backup_$(date +%Y%m%d).sql

# Restore backup
psql groupchat < backup_20240101.sql
```

## Step 9: Security Best Practices

1. **Security Groups**: 
   - Only allow necessary ports
   - Restrict SSH to your IP

2. **Updates**:
   ```bash
   # Regular system updates
   sudo apt-get update && sudo apt-get upgrade
   ```

3. **Firewall**:
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   ```

4. **Environment Variables**:
   - Never commit .env to git
   - Use AWS Secrets Manager for sensitive data

## Troubleshooting

### Application won't start
```bash
# Check service status
sudo systemctl status groupchat

# Check logs
sudo journalctl -u groupchat -n 100

# Test manually
cd ~/groupchat
source venv/bin/activate
uvicorn groupchat.main:app --host 127.0.0.1 --port 8000
```

### Nginx errors
```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log
```

### Database connection issues
```bash
# Test PostgreSQL connection
psql -U groupchat_user -d groupchat -h localhost

# Check PostgreSQL status
sudo systemctl status postgresql
```

## Estimated Costs

- **EC2 t3.medium**: ~$30/month
- **Elastic IP**: Free when attached to running instance
- **Route53**: $0.50/month per hosted zone + $0.40 per million queries
- **Domain**: $12-40/year (if purchased through Route53)
- **RDS db.t3.micro**: ~$15/month (optional)
- **Data transfer**: First 100GB/month free, then $0.09/GB

**Total**: ~$45-60/month for basic setup

## Support Resources

- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Route53 Documentation](https://docs.aws.amazon.com/route53/)
- [Nginx Documentation](https://nginx.org/en/docs/)

## Next Steps

1. Set up CloudWatch monitoring
2. Configure auto-scaling (if needed)
3. Set up CI/CD with GitHub Actions
4. Implement backup strategy
5. Configure CloudFront CDN for static files