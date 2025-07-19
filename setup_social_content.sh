#!/bin/bash

# Social Content Integration Setup Script
# This script helps set up the social content system for your e-commerce platform

echo "🚀 Setting up Social Content Integration System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    print_error "manage.py not found. Please run this script from your Django project root."
    exit 1
fi

print_header "Installing Python dependencies..."

# Create requirements file for social content system
cat > requirements_social_content.txt << EOF
Pillow>=9.0.0
opencv-python>=4.5.0
requests>=2.25.0
djangorestframework>=3.12.0
django-cors-headers>=3.7.0
celery>=5.2.0  # For background tasks
redis>=4.0.0   # For caching and celery broker
EOF

# Install Python dependencies
pip install -r requirements_social_content.txt

print_status "Python dependencies installed successfully"

print_header "Setting up Django configuration..."

# Add to INSTALLED_APPS
python << EOF
import re

# Read settings file
with open('shop_platform/settings.py', 'r') as f:
    content = f.read()

# Add social content apps if not already present
if 'social_content' not in content:
    # Find INSTALLED_APPS and add our app
    pattern = r'INSTALLED_APPS\s*=\s*\[(.*?)\]'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        apps_content = match.group(1)
        if "'shop'" in apps_content:
            print("✓ Shop app already in INSTALLED_APPS")
        else:
            print("Adding shop app to INSTALLED_APPS")
    else:
        print("Could not find INSTALLED_APPS in settings.py")

print("Django settings updated")
EOF

print_header "Setting up database migrations..."

# Create and run migrations
python manage.py makemigrations shop
python manage.py migrate

print_status "Database migrations completed"

print_header "Setting up media and static files..."

# Create media directories for content storage
mkdir -p media/social_content/{images,videos,thumbnails}
mkdir -p static/social_content/

print_status "Media directories created"

print_header "Setting up URL configuration..."

# Update main URLs file
python << EOF
import os

urls_file = 'shop_platform/urls.py'
if os.path.exists(urls_file):
    with open(urls_file, 'r') as f:
        content = f.read()
    
    if 'social_content_urls' not in content:
        # Add social content URLs
        new_content = content.replace(
            "urlpatterns = [",
            """from shop.social_content_urls import urlpatterns as social_urls

urlpatterns = ["""
        )
        
        new_content = new_content.replace(
            "]",
            """    path('api/', include(social_urls)),
]""", 1
        )
        
        with open(urls_file, 'w') as f:
            f.write(new_content)
        
        print("✓ Social content URLs added to main urls.py")
    else:
        print("✓ Social content URLs already configured")
else:
    print("⚠ Could not find main urls.py file")
EOF

print_header "Setting up environment variables..."

# Create or update .env file
if [ ! -f ".env" ]; then
    touch .env
fi

# Add social content environment variables
cat >> .env << EOF

# Social Content Integration Settings
SOCIAL_CONTENT_ENABLED=True
SOCIAL_CONTENT_MAX_SYNC_ITEMS=10
SOCIAL_CONTENT_CACHE_TIMEOUT=3600

# Social Media API Keys (replace with your actual keys)
INSTAGRAM_ACCESS_TOKEN=your_instagram_token_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
FACEBOOK_ACCESS_TOKEN=your_facebook_token_here
YOUTUBE_API_KEY=your_youtube_api_key_here

# Redis Configuration (for caching and background tasks)
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
EOF

print_status "Environment variables added to .env file"

print_header "Setting up Celery for background tasks..."

# Create celery configuration
cat > shop_platform/celery.py << EOF
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shop_platform.settings')

app = Celery('shop_platform')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
EOF

# Update __init__.py
cat > shop_platform/__init__.py << EOF
# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)
EOF

print_status "Celery configuration created"

print_header "Setting up scheduled tasks..."

# Create management command for content sync
mkdir -p shop/management/commands/

cat > shop/management/commands/sync_social_content.py << EOF
from django.core.management.base import BaseCommand
from shop.social_content_models import SocialPlatform
from shop.content_extractor import SocialContentSyncer


class Command(BaseCommand):
    help = 'Sync content from all active social media platforms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            type=str,
            help='Sync specific platform only',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Number of items to sync per platform',
        )

    def handle(self, *args, **options):
        platforms = SocialPlatform.objects.filter(is_active=True)
        
        if options['platform']:
            platforms = platforms.filter(platform_type=options['platform'])
        
        for platform in platforms:
            self.stdout.write(f'Syncing {platform.platform_type} - @{platform.username}')
            
            syncer = SocialContentSyncer(platform)
            
            # Sync stories
            story_log = syncer.sync_stories(limit=options['limit'])
            self.stdout.write(
                f'  Stories: {story_log.new_items_created} new, '
                f'{story_log.items_updated} updated, '
                f'{story_log.items_failed} failed'
            )
            
            # Sync posts
            post_log = syncer.sync_posts(limit=options['limit'])
            self.stdout.write(
                f'  Posts: {post_log.new_items_created} new, '
                f'{post_log.items_updated} updated, '
                f'{post_log.items_failed} failed'
            )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully synced content from all platforms')
        )
EOF

print_status "Management command created"

print_header "Setting up cron job for automatic sync..."

# Add cron job for automatic syncing
(crontab -l 2>/dev/null; echo "0 */6 * * * cd $(pwd) && python manage.py sync_social_content") | crontab -

print_status "Cron job added for automatic content sync every 6 hours"

print_header "Creating sample data..."

# Create sample social platform
python manage.py shell << EOF
from shop.models import Store
from shop.social_content_models import SocialPlatform
from django.contrib.auth.models import User

# Get first store (or create one)
try:
    store = Store.objects.first()
    if not store:
        # Create a sample store
        user = User.objects.first()
        if not user:
            user = User.objects.create_user('admin', 'admin@example.com', 'admin123')
        
        store = Store.objects.create(
            owner=user,
            name='Sample Store',
            name_en='Sample Store',
            domain='sample.shop',
            is_active=True,
            is_approved=True
        )
        print(f"Created sample store: {store.name}")
    
    # Create sample platform
    platform, created = SocialPlatform.objects.get_or_create(
        store=store,
        platform_type='instagram',
        defaults={
            'username': 'sample_account',
            'is_active': False  # Keep inactive until real credentials are added
        }
    )
    
    if created:
        print(f"Created sample platform: {platform.platform_type} - @{platform.username}")
    else:
        print(f"Platform already exists: {platform.platform_type} - @{platform.username}")

except Exception as e:
    print(f"Error creating sample data: {e}")
EOF

print_status "Sample data created"

print_header "Frontend setup instructions..."

echo ""
echo "📋 Next Steps:"
echo ""
echo "1. 🔑 Update API Keys:"
echo "   Edit .env file and add your real social media API credentials"
echo ""
echo "2. 🎨 Frontend Setup:"
echo "   cd to your Angular project and run:"
echo "   npm install primeng primeicons"
echo ""
echo "3. 📱 Import Component:"
echo "   Add ContentSelectorComponent to your Angular module"
echo ""
echo "4. 🚀 Start Services:"
echo "   python manage.py runserver"
echo "   celery -A shop_platform worker --loglevel=info"
echo ""
echo "5. 🔄 Test Sync:"
echo "   python manage.py sync_social_content --limit=2"
echo ""
echo "6. 🌐 Frontend Development:"
echo "   Use the content selector component in your product forms"
echo ""

print_status "Setup completed successfully! 🎉"

echo ""
echo "📖 Documentation:"
echo "   - Check README_SOCIAL_CONTENT.md for detailed usage"
echo "   - API endpoints available at /api/social/"
echo "   - Admin interface for platform management"
echo ""

print_warning "Remember to:"
print_warning "- Add real API credentials to .env"
print_warning "- Configure Redis server for caching"
print_warning "- Set up proper SSL certificates for production"
print_warning "- Review and comply with social media platform policies"

echo ""
echo "Happy coding! 🚀"
