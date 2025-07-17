#!/bin/bash

# Multi-Tenant Shop Platform Deployment Script
# This script helps set up the complete shop platform with multi-tenant support

set -e

echo "🚀 Multi-Tenant Shop Platform Deployment"
echo "========================================"

# Configuration
DOMAIN=${1:-"localhost"}
DB_NAME=${2:-"shop_platform"}
DB_USER=${3:-"shop_user"}
DB_PASS=${4:-"shop_password"}
ADMIN_EMAIL=${5:-"admin@${DOMAIN}"}

echo "📋 Configuration:"
echo "   Domain: $DOMAIN"
echo "   Database: $DB_NAME"
echo "   Admin Email: $ADMIN_EMAIL"
echo ""

# Check requirements
echo "🔍 Checking requirements..."
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ Node.js/npm is required"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "❌ PostgreSQL is required"; exit 1; }

echo "✅ All requirements met"

# Backend setup
echo ""
echo "🔧 Setting up backend..."

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements_with_attributes.txt

# Create .env file
cat > .env << EOF
# Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}

# Django
DEBUG=False
SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
ALLOWED_HOSTS=${DOMAIN},*.${DOMAIN},localhost,127.0.0.1

# Domain settings
MAIN_DOMAIN=${DOMAIN}

# CORS
CORS_ALLOWED_ORIGINS=https://${DOMAIN},https://*.${DOMAIN}
CORS_ALLOW_ALL_ORIGINS=False

# Email (configure SMTP settings)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@${DOMAIN}

# Media and Static files
MEDIA_URL=/media/
STATIC_URL=/static/
MEDIA_ROOT=/var/www/${DOMAIN}/media/
STATIC_ROOT=/var/www/${DOMAIN}/static/

# Security
SECURE_SSL_REDIRECT=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
EOF

# Create database
echo "🗄️  Setting up database..."
sudo -u postgres createdb $DB_NAME 2>/dev/null || echo "Database might already exist"
sudo -u postgres createuser $DB_USER 2>/dev/null || echo "User might already exist"
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
echo "👤 Creating admin user..."
python manage.py shell << EOF
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', '${ADMIN_EMAIL}', 'admin123')
    print('Admin user created: admin/admin123')
else:
    print('Admin user already exists')
EOF

# Collect static files
python manage.py collectstatic --noinput

echo "✅ Backend setup complete"

# Frontend setup
echo ""
echo "🎨 Setting up frontend..."

# Install frontend dependencies
npm install

# Update environment configuration
cat > src/environments/environment.prod.ts << EOF
export const environment = {
  production: true,
  apiUrl: 'https://${DOMAIN}/api',
  adminUrl: 'https://admin.${DOMAIN}',
  platformUrl: 'https://${DOMAIN}'
};
EOF

# Build frontend
npm run build --prod

echo "✅ Frontend setup complete"

# Create directories
echo "📁 Creating directories..."
sudo mkdir -p /var/www/${DOMAIN}/{static,media,frontend}
sudo cp -r dist/* /var/www/${DOMAIN}/frontend/
sudo chown -R www-data:www-data /var/www/${DOMAIN}

# Nginx configuration
echo ""
echo "🌐 Setting up Nginx..."

sudo tee /etc/nginx/sites-available/${DOMAIN} > /dev/null << EOF
# Main domain (platform admin)
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Static files
    location /static/ {
        alias /var/www/${DOMAIN}/static/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/${DOMAIN}/media/;
        expires 30d;
    }

    # Frontend
    location / {
        root /var/www/${DOMAIN}/frontend/;
        try_files \$uri \$uri/ /index.html;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Admin
    location /admin/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# Wildcard for store domains
server {
    listen 80;
    server_name *.${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name *.${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # Static files
    location /static/ {
        alias /var/www/${DOMAIN}/static/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/${DOMAIN}/media/;
        expires 30d;
    }

    # Store frontend
    location / {
        root /var/www/${DOMAIN}/frontend/;
        try_files \$uri \$uri/ /index.html;
    }

    # Store API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "✅ Nginx configuration complete"

# SSL Certificate (skip in development)
if [ "$DOMAIN" != "localhost" ]; then
    echo ""
    echo "🔒 Setting up SSL certificate..."

    # Install certbot if not present
    if ! command -v certbot &> /dev/null; then
        sudo apt update
        sudo apt install -y certbot python3-certbot-nginx
    fi

    # Get SSL certificate
    sudo certbot --nginx -d ${DOMAIN} -d "*.${DOMAIN}" --agree-tos --email ${ADMIN_EMAIL} --non-interactive

    echo "✅ SSL certificate installed"
fi

# Systemd service
echo ""
echo "🔄 Setting up systemd service..."

sudo tee /etc/systemd/system/shop-platform.service > /dev/null << EOF
[Unit]
Description=Shop Platform Django Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 shop_platform.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start and enable service
sudo systemctl daemon-reload
sudo systemctl enable shop-platform
sudo systemctl start shop-platform

echo "✅ Systemd service configured"

# Create sample store
echo ""
echo "🏪 Creating sample store..."

python manage.py shell << EOF
from shop.models_with_attributes import Store
from django.contrib.auth.models import User

admin_user = User.objects.get(username='admin')

# Create sample store
store, created = Store.objects.get_or_create(
    domain='demo.${DOMAIN}',
    defaults={
        'owner': admin_user,
        'name': 'Demo Electronics Store',
        'description': 'Your premier destination for electronics and gadgets',
        'currency': 'USD',
        'tax_rate': 0.08,
        'email': 'contact@demo.${DOMAIN}',
        'phone': '+1-555-0123',
        'address': '123 Demo Street, Demo City, DC 12345'
    }
)

if created:
    print(f'Sample store created: {store.name} at {store.domain}')
else:
    print(f'Sample store already exists: {store.name}')
EOF

# Test installation
echo ""
echo "🧪 Testing installation..."

# Test backend health
if curl -f -s http://localhost:8000/api/health/ > /dev/null; then
    echo "✅ Backend is running"
else
    echo "❌ Backend health check failed"
fi

# Test domain resolution
if curl -f -s -H "Host: demo.${DOMAIN}" http://localhost:8000/api/config/domain_status/ > /dev/null; then
    echo "✅ Domain resolution working"
else
    echo "❌ Domain resolution failed"
fi

# Final instructions
echo ""
echo "🎉 Deployment Complete!"
echo "======================"
echo ""
echo "📌 Access URLs:"
echo "   Platform Admin: https://${DOMAIN}/admin"
echo "   Sample Store: https://demo.${DOMAIN}"
echo "   API: https://${DOMAIN}/api"
echo ""
echo "🔑 Admin Credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo "   Email: ${ADMIN_EMAIL}"
echo ""
echo "📋 Next Steps:"
echo "   1. Change admin password"
echo "   2. Configure email settings"
echo "   3. Set up monitoring"
echo "   4. Create your first store"
echo ""
echo "📚 Documentation:"
echo "   - README_ATTRIBUTES.md - Product attributes system"
echo "   - README_DOMAINS.md - Multi-tenant domains"
echo "   - README_FRONTEND.md - Frontend implementation"
echo ""
echo "🎯 Create a new store:"
echo "   1. Login to admin: https://${DOMAIN}/admin"
echo "   2. Go to Stores section"
echo "   3. Create new store with custom domain"
echo "   4. Point DNS to this server"
echo ""
echo "Happy selling! 🛍️"
