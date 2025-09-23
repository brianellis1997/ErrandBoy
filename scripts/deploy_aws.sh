#!/bin/bash

# AWS EC2 Deployment Script for GroupChat FastAPI Application
# This script sets up and deploys the application on an AWS EC2 instance

set -e  # Exit on error

echo "🚀 Starting AWS EC2 Deployment for GroupChat..."

# Configuration
APP_DIR="/home/ubuntu/groupchat"
REPO_URL="https://github.com/brianellis1997/ErrandBoy.git"
BRANCH="main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running on EC2 instance
if [ ! -f /sys/hypervisor/uuid ] || [ $(head -c 3 /sys/hypervisor/uuid) != "ec2" ]; then
    print_warning "This script is intended to run on an AWS EC2 instance"
fi

# Update system packages
print_status "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
print_status "Installing system dependencies..."
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql-client \
    nginx \
    git \
    supervisor \
    certbot \
    python3-certbot-nginx \
    redis-server

# Install Docker (optional, for containerized deployment)
print_status "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
rm get-docker.sh

# Clone or update repository
if [ -d "$APP_DIR" ]; then
    print_status "Updating existing repository..."
    cd $APP_DIR
    git pull origin $BRANCH
else
    print_status "Cloning repository..."
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
    git checkout $BRANCH
fi

# Create Python virtual environment
print_status "Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file (you'll need to fill this with actual values)
if [ ! -f .env ]; then
    print_status "Creating .env file..."
    cp .env.example .env
    print_warning "Please edit /home/ubuntu/groupchat/.env with your actual configuration values"
fi

# Set up PostgreSQL database (if using RDS, skip this)
print_status "Setting up PostgreSQL..."
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user (adjust as needed)
sudo -u postgres psql <<EOF
CREATE DATABASE groupchat;
CREATE USER groupchat_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE groupchat TO groupchat_user;
EOF

# Run database migrations
print_status "Running database migrations..."
source venv/bin/activate
alembic upgrade head

# Configure Nginx
print_status "Configuring Nginx..."
sudo cp nginx.conf /etc/nginx/sites-available/groupchat
sudo ln -sf /etc/nginx/sites-available/groupchat /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# Create Supervisor configuration
print_status "Setting up Supervisor for process management..."
sudo tee /etc/supervisor/conf.d/groupchat.conf > /dev/null <<EOF
[program:groupchat]
command=/home/ubuntu/groupchat/venv/bin/uvicorn groupchat.main:app --host 127.0.0.1 --port 8000 --workers 4
directory=/home/ubuntu/groupchat
user=ubuntu
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/groupchat.log
environment=PATH="/home/ubuntu/groupchat/venv/bin",HOME="/home/ubuntu"
EOF

# Start application with Supervisor
print_status "Starting application..."
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart groupchat

# Configure Redis
print_status "Configuring Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Set up firewall rules
print_status "Configuring firewall..."
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw --force enable

# Create systemd service (alternative to Supervisor)
sudo tee /etc/systemd/system/groupchat.service > /dev/null <<EOF
[Unit]
Description=GroupChat FastAPI Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/groupchat
Environment="PATH=/home/ubuntu/groupchat/venv/bin"
ExecStart=/home/ubuntu/groupchat/venv/bin/uvicorn groupchat.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable groupchat
sudo systemctl start groupchat

# Health check
print_status "Performing health check..."
sleep 5
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_status "✅ Application is running successfully!"
else
    print_error "Application health check failed"
    sudo journalctl -u groupchat -n 50
fi

# Print status and next steps
echo ""
print_status "==================================="
print_status "Deployment completed successfully!"
print_status "==================================="
echo ""
print_status "Next steps:"
echo "1. Edit /home/ubuntu/groupchat/.env with your configuration"
echo "2. Set up your domain in Route53 and point it to this instance's IP"
echo "3. Run: sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com"
echo "4. Update nginx.conf with your domain and restart nginx"
echo ""
print_status "Useful commands:"
echo "- Check app status: sudo supervisorctl status groupchat"
echo "- View logs: sudo tail -f /var/log/groupchat.log"
echo "- Restart app: sudo supervisorctl restart groupchat"
echo "- Check nginx: sudo nginx -t && sudo systemctl restart nginx"