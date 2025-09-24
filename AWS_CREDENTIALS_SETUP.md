# AWS Credentials Setup Guide

## Step 1: Get Your AWS Access Keys

1. **Log into AWS Console**: https://console.aws.amazon.com
2. Click your **username** (top right) → **Security credentials**
3. Scroll to **Access keys** section
4. Click **Create access key**
5. Choose **Command Line Interface (CLI)**
6. Check the confirmation box → **Next**
7. Add description (optional): "GroupChat EB deployment"
8. Click **Create access key**
9. **IMPORTANT**: Save both:
   - Access key ID (looks like: `AKIAIOSFODNN7EXAMPLE`)
   - Secret access key (looks like: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
10. Download the .csv file for backup

## Step 2: Configure AWS CLI

Run this command and paste your keys when prompted:

```bash
aws configure
```

It will ask for:
- AWS Access Key ID: [paste your key]
- AWS Secret Access Key: [paste your secret]
- Default region name: us-east-1
- Default output format: json

## Step 3: Verify Setup

```bash
aws sts get-caller-identity
```

Should show your AWS account info.

## Alternative: Manual Setup

Create file `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

Create file `~/.aws/config`:

```ini
[default]
region = us-east-1
output = json
```

## Security Notes

- **NEVER** commit these credentials to Git
- **NEVER** share your secret access key
- Consider using IAM roles for production
- Rotate keys regularly

## After Setup

Now you can run:
```bash
eb init -p python-3.11 groupchat-app --region us-east-1
```