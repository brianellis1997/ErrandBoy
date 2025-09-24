#!/bin/bash

# AWS Configuration Script
echo "Setting up AWS credentials..."

# Activate conda environment
source /Users/bdogellis/miniforge3/etc/profile.d/conda.sh
conda activate GroupChat

# Create AWS credentials directory if it doesn't exist
mkdir -p ~/.aws

# Prompt for credentials
read -p "Enter your AWS Access Key ID: " AWS_ACCESS_KEY
read -s -p "Enter your AWS Secret Access Key: " AWS_SECRET_KEY
echo ""
read -p "Enter your default region (press Enter for us-east-1): " AWS_REGION

# Set default region if empty
AWS_REGION=${AWS_REGION:-us-east-1}

# Write credentials file
cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY
aws_secret_access_key = $AWS_SECRET_KEY
EOF

# Write config file
cat > ~/.aws/config << EOF
[default]
region = $AWS_REGION
output = json
EOF

echo "AWS credentials configured!"

# Test the configuration
echo "Testing AWS configuration..."
aws sts get-caller-identity

if [ $? -eq 0 ]; then
    echo "✅ AWS configuration successful!"
    echo ""
    echo "Now you can deploy with:"
    echo "eb init -p python-3.11 groupchat-app --region $AWS_REGION"
    echo "eb create groupchat-prod --instance-type t3.small"
else
    echo "❌ AWS configuration failed. Please check your credentials."
fi