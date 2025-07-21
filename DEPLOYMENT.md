# Complete Production Deployment Guide

This guide covers everything needed to deploy the multi-store e-commerce platform to production.

## 🚀 Production Environment Setup

### 1. Server Requirements

#### Minimum Hardware:
- **CPU**: 4 cores (8 recommended)
- **RAM**: 8GB (16GB recommended) 
- **Storage**: 100GB SSD (500GB recommended)
- **Network**: 1Gbps connection

#### Recommended Stack:
- **OS**: Ubuntu 22.04 LTS
- **Web Server**: Nginx
- **App Server**: Gunicorn
- **Database**: PostgreSQL 14+
- **Cache**: Redis 6+
- **Search**: Elasticsearch 7.x (optional)

### 2. Environment Configuration

#### Create Production Environment File:
```bash
# .env.production
DEBUG=False
SECRET_KEY=your-super-secret-production-key-here
ALLOWED_HOSTS=yourdomain.com,*.yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/shop_platform_prod

# Cache
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=your-email-password

# AWS S3 (for file storage)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1

# Security
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Monitoring
SENTRY_DSN=your-sentry-dsn-here
```

### 3. Database Setup

#### PostgreSQL Installation:
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres createdb shop_platform_prod
sudo -u postgres createuser shop_user
sudo -u postgres psql -c "ALTER USER shop_user WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE shop_platform_prod TO shop_user;"

# Enable required extensions
sudo -u postgres psql shop_platform_prod -c "CREATE EXTENSION IF NOT EXISTS postgis;"
sudo -u postgres psql shop_platform_prod -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

#### Redis Installation:
```bash
# Install Redis
sudo apt install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: maxmemory 2gb
# Set: maxmemory-policy allkeys-lru

sudo systemctl restart redis
sudo systemctl enable redis
```

### 4. Application Deployment

#### Clone and Setup:
```bash
# Clone repository
git clone https://github.com/yourusername/shop-back.git
cd shop-back

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install additional production packages
pip install gunicorn supervisor psycopg2-binary

# Copy environment file
cp .env.example .env
# Edit .env with production values

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser
```

#### Frontend Build:
```bash
# Navigate to frontend directory
cd ../shop-front

# Install dependencies
npm install

# Build for production
npm run build:prod

# Copy dist files to web server
sudo cp -r dist/* /var/www/html/
```

### 5. Web Server Configuration

#### Nginx Configuration:
```nginx
# /etc/nginx/sites-available/shop-platform
upstream django {
    server 127.0.0.1:8000;
}

# Platform domain
server {
    listen 80;
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/ssl/certificate.pem;
    ssl_certificate_key /path/to/ssl/private-key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Static files
    location /static/ {
        alias /path/to/shop-back/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /path/to/shop-back/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
    
    # API requests
    location /api/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Admin panel
    location /admin/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Frontend application
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}

# Wildcard for store subdomains
server {
    listen 80;
    listen 443 ssl http2;
    server_name ~^(?<subdomain>.+)\.yourdomain\.com$;
    
    # SSL Configuration
    ssl_certificate /path/to/wildcard-cert.pem;
    ssl_certificate_key /path/to/wildcard-key.pem;
    
    # Same configuration as above but for subdomains
    location /api/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }
}

# Custom domains (add as needed)
server {
    listen 80;
    listen 443 ssl http2;
    server_name store1.com www.store1.com;
    
    # SSL for custom domain
    ssl_certificate /path/to/store1-cert.pem;
    ssl_certificate_key /path/to/store1-key.pem;
    
    # Same proxy configuration
    location /api/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }
}
```

#### Enable Nginx Site:
```bash
sudo ln -s /etc/nginx/sites-available/shop-platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. Process Management

#### Gunicorn Configuration:
```python
# gunicorn.conf.py
bind = "127.0.0.1:8000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5
preload_app = True
```

#### Supervisor Configuration:
```ini
# /etc/supervisor/conf.d/shop-platform.conf
[program:shop-platform]
command=/path/to/shop-back/venv/bin/gunicorn shop_platform.wsgi:application -c gunicorn.conf.py
directory=/path/to/shop-back
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/shop-platform/gunicorn.log
stderr_logfile=/var/log/shop-platform/gunicorn-error.log

[program:celery-worker]
command=/path/to/shop-back/venv/bin/celery -A shop_platform worker -l info
directory=/path/to/shop-back
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/shop-platform/celery.log

[program:celery-beat]
command=/path/to/shop-back/venv/bin/celery -A shop_platform beat -l info
directory=/path/to/shop-back
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/shop-platform/celery-beat.log
```

#### Start Services:
```bash
# Create log directories
sudo mkdir -p /var/log/shop-platform
sudo chown www-data:www-data /var/log/shop-platform

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

### 7. SSL Certificate Setup

#### Using Let's Encrypt:
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificates
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo certbot --nginx -d *.yourdomain.com  # Wildcard certificate

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 8. Monitoring and Logging

#### Log Rotation:
```bash
# /etc/logrotate.d/shop-platform
/var/log/shop-platform/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    postrotate
        supervisorctl restart shop-platform
    endscript
}
```

#### System Monitoring:
```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# Setup basic monitoring script
cat > /home/admin/monitor.sh << EOF
#!/bin/bash
echo "=== System Resources ==="
free -h
df -h
echo "=== Top Processes ==="
ps aux --sort=-%cpu | head -10
echo "=== Nginx Status ==="
systemctl status nginx --no-pager
echo "=== Database Connections ==="
sudo -u postgres psql -c "SELECT count(*) as connections FROM pg_stat_activity;"
EOF

chmod +x /home/admin/monitor.sh
```

### 9. Backup Strategy

#### Database Backup:
```bash
# Create backup script
cat > /home/admin/backup.sh << EOF
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="shop_platform_prod"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
sudo -u postgres pg_dump $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Media files backup
tar -czf $BACKUP_DIR/media_backup_$DATE.tar.gz /path/to/shop-back/media/

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /home/admin/backup.sh

# Schedule daily backups
sudo crontab -e
# Add: 0 2 * * * /home/admin/backup.sh
```

#### AWS S3 Backup (Optional):
```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure

# Enhanced backup script with S3
cat > /home/admin/backup-s3.sh << EOF
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
S3_BUCKET="your-backup-bucket"

# Local backup
sudo -u postgres pg_dump shop_platform_prod | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/db_backup_$DATE.sql.gz s3://$S3_BUCKET/database/
aws s3 sync /path/to/shop-back/media/ s3://$S3_BUCKET/media/ --delete

echo "Backup uploaded to S3: $DATE"
EOF
```

### 10. Performance Optimization

#### Database Optimization:
```sql
-- PostgreSQL performance tuning
-- /etc/postgresql/14/main/postgresql.conf

# Memory settings
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 256MB
maintenance_work_mem = 1GB

# Connection settings
max_connections = 200

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 64MB

# Query planner
random_page_cost = 1.1
effective_io_concurrency = 200
```

#### Redis Optimization:
```bash
# /etc/redis/redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

#### Application Caching:
```python
# Add to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        }
    }
}

# Session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 hours
```

### 11. Security Hardening

#### Firewall Configuration:
```bash
# Configure UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

#### Fail2Ban Setup:
```bash
# Install Fail2Ban
sudo apt install fail2ban

# Configure for Nginx
sudo cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
action = iptables-multiport[name=ReqLimit, port="http,https", protocol=tcp]
logpath = /var/log/nginx/error.log
findtime = 600
bantime = 7200
maxretry = 10
EOF

sudo systemctl restart fail2ban
```

#### File Permissions:
```bash
# Set proper permissions
sudo chown -R www-data:www-data /path/to/shop-back/
sudo chmod -R 755 /path/to/shop-back/
sudo chmod -R 644 /path/to/shop-back/static/
sudo chmod -R 644 /path/to/shop-back/media/
sudo chmod 600 /path/to/shop-back/.env
```

### 12. Health Checks

#### Create Health Check Endpoint:
```python
# Add to urls.py
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis

def health_check(request):
    checks = {}
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'
    
    # Redis check
    try:
        cache.set('health_check', 'ok', 10)
        checks['redis'] = 'ok'
    except Exception as e:
        checks['redis'] = f'error: {str(e)}'
    
    # Overall status
    status = 'ok' if all(v == 'ok' for v in checks.values()) else 'error'
    
    return JsonResponse({
        'status': status,
        'checks': checks
    })

# Add URL pattern
urlpatterns += [
    path('health/', health_check, name='health_check'),
]
```

### 13. Monitoring with Uptime Checks

#### External Monitoring Script:
```bash
# /home/admin/uptime-check.sh
#!/bin/bash
HEALTH_URL="https://yourdomain.com/health/"
EMAIL="admin@yourdomain.com"

# Check health endpoint
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -ne 200 ]; then
    echo "Health check failed with status: $RESPONSE" | mail -s "Platform Down" $EMAIL
    echo "$(date): Health check failed - $RESPONSE" >> /var/log/uptime-check.log
fi
```

### 14. Deployment Automation

#### Deployment Script:
```bash
# /home/admin/deploy.sh
#!/bin/bash
set -e

APP_DIR="/path/to/shop-back"
FRONTEND_DIR="/path/to/shop-front"

echo "Starting deployment..."

# Backend deployment
cd $APP_DIR
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# Frontend deployment
cd $FRONTEND_DIR
git pull origin main
npm install
npm run build:prod
sudo cp -r dist/* /var/www/html/

# Restart services
sudo supervisorctl restart shop-platform
sudo systemctl reload nginx

echo "Deployment completed successfully!"
```

### 15. Final Checklist

- [ ] **SSL certificates** installed and working
- [ ] **Database** configured and optimized
- [ ] **Redis** caching working
- [ ] **Static files** serving correctly
- [ ] **Media uploads** working
- [ ] **Email** sending functional
- [ ] **Backups** automated
- [ ] **Monitoring** active
- [ ] **Security** hardened
- [ ] **Performance** optimized
- [ ] **Health checks** responding
- [ ] **Domain routing** working for multiple stores
- [ ] **Search functionality** operational
- [ ] **Order processing** tested
- [ ] **Payment integration** configured

## 🎉 Congratulations!

Your multi-store e-commerce platform is now deployed and ready for production use. The platform can handle:

- **Multiple stores** with custom domains
- **High traffic** with caching and optimization
- **Secure operations** with SSL and hardening
- **Reliable service** with monitoring and backups
- **Scalable growth** with proper architecture

For ongoing maintenance, monitor logs regularly, keep dependencies updated, and scale resources as needed.
