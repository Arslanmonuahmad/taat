# 🚀 Deployment Guide

This guide covers deploying the Telegram Face Swap Bot to various platforms.

## 🌐 Vercel Deployment (Recommended)

Vercel is the recommended platform for this bot due to its serverless nature and easy deployment.

### Prerequisites
- Vercel account
- GitHub repository
- PostgreSQL database (recommended: Supabase, PlanetScale, or Neon)

### Step 1: Prepare Database

**Option A: Supabase (Free PostgreSQL)**
1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Go to Settings > Database
4. Copy connection string

**Option B: PlanetScale (Free MySQL)**
1. Go to [planetscale.com](https://planetscale.com)
2. Create new database
3. Create branch and get connection string

### Step 2: Deploy to Vercel

**Method 1: GitHub Integration (Recommended)**
1. Push code to GitHub repository
2. Go to [vercel.com](https://vercel.com)
3. Import GitHub repository
4. Configure environment variables (see below)
5. Deploy

**Method 2: Vercel CLI**
```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

### Step 3: Environment Variables

In Vercel dashboard, add these environment variables:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
DATABASE_URL=your_postgresql_connection_string
SECRET_KEY=your_random_secret_key_here
ADMIN_API_KEY=your_admin_password_here

# Webhook Configuration
TELEGRAM_WEBHOOK_URL=https://your-app.vercel.app/webhook/telegram
WEBHOOK_SECRET_TOKEN=your_webhook_secret

# Optional
MAX_FILE_SIZE_MB=50
DEBUG=False
LOG_LEVEL=INFO
```

### Step 4: Set Telegram Webhook

After deployment, set the webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://your-app.vercel.app/webhook/telegram",
       "secret_token": "your_webhook_secret"
     }'
```

### Step 5: Initialize Database

Visit your deployed app and the database tables will be created automatically.

## 🐳 Docker Deployment

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads outputs temp database

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "src/main.py"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  bot:
    build: .
    ports:
      - "5000:5000"
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DATABASE_URL=postgresql://postgres:password@db:5432/faceswap
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_API_KEY=${ADMIN_API_KEY}
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads
      - ./outputs:/app/outputs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=faceswap
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### Deploy with Docker
```bash
# Build and run
docker-compose up -d

# Set webhook
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/webhook/telegram"
```

## ☁️ Cloud Platform Deployments

### Heroku

1. **Create Heroku app**
```bash
heroku create your-app-name
```

2. **Add PostgreSQL addon**
```bash
heroku addons:create heroku-postgresql:mini
```

3. **Set environment variables**
```bash
heroku config:set TELEGRAM_BOT_TOKEN=your_token
heroku config:set SECRET_KEY=your_secret
heroku config:set ADMIN_API_KEY=your_admin_key
```

4. **Create Procfile**
```
web: python src/main.py
```

5. **Deploy**
```bash
git push heroku main
```

### Railway

1. **Connect GitHub repository**
2. **Add PostgreSQL service**
3. **Set environment variables**
4. **Deploy automatically**

### DigitalOcean App Platform

1. **Create new app from GitHub**
2. **Add managed PostgreSQL database**
3. **Configure environment variables**
4. **Deploy**

## 🔧 Production Optimizations

### Database Optimizations

**PostgreSQL Configuration**
```sql
-- Add indexes for better performance
CREATE INDEX idx_users_telegram_id ON users(telegram_user_id);
CREATE INDEX idx_credits_user_id ON credits(user_id);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_face_swap_jobs_user_id ON face_swap_jobs(user_id);
CREATE INDEX idx_invites_code ON invites(invite_code);
```

### Environment-Specific Settings

**Production (.env)**
```bash
DEBUG=False
LOG_LEVEL=WARNING
MAX_FILE_SIZE_MB=50
```

**Development (.env)**
```bash
DEBUG=True
LOG_LEVEL=DEBUG
MAX_FILE_SIZE_MB=100
```

### Monitoring Setup

**Health Check Endpoint**
```bash
# Monitor your deployment
curl https://your-app.vercel.app/health
```

**Admin Dashboard**
```bash
# Monitor via admin panel
https://your-app.vercel.app/admin/
```

## 🔒 Security Considerations

### Production Security Checklist

- [ ] Use strong `SECRET_KEY` (32+ random characters)
- [ ] Use strong `ADMIN_API_KEY`
- [ ] Set `WEBHOOK_SECRET_TOKEN` for webhook verification
- [ ] Use HTTPS for all webhook URLs
- [ ] Enable database SSL in production
- [ ] Set proper CORS headers
- [ ] Monitor logs for suspicious activity
- [ ] Regular security updates

### Webhook Security

```python
# Verify webhook signature (implemented in webhook.py)
def verify_webhook_signature(data, signature, secret):
    expected = hmac.new(
        secret.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

## 📊 Monitoring & Logging

### Application Monitoring

**Vercel Analytics**
- Enable in Vercel dashboard
- Monitor function execution times
- Track error rates

**Custom Logging**
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Database Monitoring

**Query Performance**
```sql
-- Monitor slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

## 🚨 Troubleshooting

### Common Issues

**1. Webhook Not Working**
```bash
# Check webhook status
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Reset webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-app.vercel.app/webhook/telegram"
```

**2. Database Connection Issues**
- Check `DATABASE_URL` format
- Verify database credentials
- Ensure database server is accessible

**3. File Upload Issues**
- Check `MAX_FILE_SIZE_MB` setting
- Verify upload directory permissions
- Monitor disk space

**4. FaceFusion Processing Issues**
- Check FaceFusion installation
- Verify Python dependencies
- Monitor processing timeouts

### Debug Mode

Enable debug mode for development:
```bash
DEBUG=True
LOG_LEVEL=DEBUG
```

### Log Analysis

**View Vercel Logs**
```bash
vercel logs your-app-name
```

**Monitor Admin Panel**
- Visit `/admin/` for system statistics
- Check user activity and errors
- Monitor credit usage patterns

## 📈 Scaling Considerations

### Horizontal Scaling

**Separate Services**
- Bot service (Vercel)
- Face processing service (GPU server)
- Database (managed service)
- File storage (S3/Cloudinary)

**Load Balancing**
- Multiple bot instances
- Queue system for face processing
- CDN for file delivery

### Performance Optimization

**Caching**
- Redis for session storage
- CDN for static assets
- Database query caching

**Async Processing**
- Celery for background tasks
- Queue system for face swaps
- Webhook processing optimization

## 🔄 Backup & Recovery

### Database Backup

**Automated Backups**
```bash
# PostgreSQL backup
pg_dump $DATABASE_URL > backup.sql

# Restore
psql $DATABASE_URL < backup.sql
```

**Backup Strategy**
- Daily automated backups
- Weekly full backups
- Monthly archive backups

### File Backup

**User Uploads**
- Regular backup to cloud storage
- Cleanup old files automatically
- Monitor storage usage

## 📞 Support & Maintenance

### Regular Maintenance Tasks

- [ ] Monitor system health
- [ ] Update dependencies
- [ ] Clean up old files
- [ ] Review user activity
- [ ] Check payment processing
- [ ] Update documentation

### Support Channels

- **GitHub Issues**: Technical problems
- **Admin Panel**: System monitoring
- **Logs**: Error tracking
- **Health Endpoint**: Service status

---

**Need help?** Check the main README.md or create a GitHub issue.

