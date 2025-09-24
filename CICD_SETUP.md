# CI/CD Setup Guide

## How It Works Now

### Manual Deployment (Current)
```bash
# After making changes
git add .
git commit -m "Your changes"
git push origin main

# Deploy manually
eb deploy  # Takes 2-3 minutes
```

### Automatic Deployment (After Setup)
1. Push to GitHub `main` branch
2. GitHub Actions automatically:
   - Runs tests
   - Deploys to AWS if tests pass
3. Live in ~5 minutes

## Setting Up Auto-Deploy

### Step 1: Add AWS Credentials to GitHub

1. Go to your GitHub repo: https://github.com/brianellis1997/ErrandBoy
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:
   - Name: `AWS_ACCESS_KEY_ID`
   - Value: (Your AWS Access Key ID from AWS Console)
5. Add another secret:
   - Name: `AWS_SECRET_ACCESS_KEY`  
   - Value: (Your AWS Secret Access Key from AWS Console)

### Step 2: Push to GitHub

```bash
git add .
git commit -m "Add CI/CD workflow"
git push origin main
```

### Step 3: Watch It Deploy

Go to **Actions** tab on GitHub to see deployment progress.

## Deployment Workflows

### Quick Deploy (2-3 minutes)
Just pushes code, no tests:
```bash
eb deploy
```

### Safe Deploy (5-7 minutes)
Runs tests first, then deploys:
- Push to `main` branch
- GitHub Actions runs tests
- If tests pass, auto-deploys

### Feature Branch Workflow
```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes
git add .
git commit -m "Add new feature"
git push origin feature/new-feature

# Create Pull Request on GitHub
# Tests run automatically
# Merge to main = auto-deploy
```

## Monitoring Deployments

### Check Status
```bash
eb status        # Current status
eb health        # Detailed health
eb logs          # View logs
```

### Rollback If Needed
```bash
eb deploy --version=previous_version
```

## Best Practices

1. **Always test locally first**:
   ```bash
   pytest tests/
   ```

2. **Use feature branches** for big changes:
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Small, frequent deploys** are safer than big ones

4. **Monitor after deploy**:
   ```bash
   eb open  # Check it works
   eb logs  # Check for errors
   ```

## Deployment Speed

- **Manual `eb deploy`**: 2-3 minutes
- **GitHub Actions**: 5-7 minutes (includes tests)
- **Zero downtime**: EB handles rolling updates

## Environment Variables

Update secrets without code changes:
```bash
eb setenv KEY=value KEY2=value2
```

This restarts the app with new config (~1 minute).

## Debugging Deployments

If deployment fails:
```bash
# Check events
eb events -f

# View logs
eb logs

# SSH to instance
eb ssh groupchat-prod
```

## Cost Optimization

- **Auto-scaling**: Set min=1, max=3 instances
- **Schedule**: Scale down at night/weekends
- **Monitoring**: CloudWatch alerts for high usage

```bash
# Scale instances
eb scale 2  # 2 instances
eb scale 1  # Back to 1
```