# Multi-Store E-commerce Platform - Backend

A Django REST API backend for a comprehensive multi-tenant e-commerce platform that allows multiple store owners to run independent online stores on their own domains.

## 🚀 Features

### 🏪 Multi-Store Architecture
- **Domain-based store separation** - Each store operates on its own domain
- **Store-specific data isolation** - Complete separation of products, orders, and customers
- **Independent store management** - Store owners manage their own inventory and settings
- **Platform admin oversight** - Centralized management of all stores

### 👑 Admin Capabilities

#### Platform Admin
- ✅ **Store approval system** - Review and approve new store requests
- ✅ **Multi-store analytics** - Cross-store performance metrics
- ✅ **User management** - Manage store owners and platform users
- ✅ **System configuration** - Platform-wide settings and policies

#### Store Owner Admin
- ✅ **Complete product management** - CRUD operations for products
- ✅ **Multi-level categories** - Hierarchical category structure
- ✅ **Dynamic product attributes** - Custom fields per store
- ✅ **Bulk product import** - CSV/Excel upload with validation
- ✅ **Inventory management** - Stock tracking and alerts
- ✅ **Order processing** - Complete order lifecycle management
- ✅ **Store customization** - Branding, settings, and configuration

### 🛍️ Customer Experience
- ✅ **Store-specific shopping** - Each domain serves one store
- ✅ **Shopping cart system** - Add, update, remove items
- ✅ **Checkout process** - Complete order flow
- ✅ **Address management** - Save and manage delivery addresses
- ✅ **Order tracking** - Real-time order status updates
- ✅ **Wishlist functionality** - Save products for later
- ✅ **Product reviews** - Customer ratings and comments

### 📊 Advanced Features
- ✅ **CSV/Excel import/export** - Bulk product management
- ✅ **Multi-language support** - Persian (Farsi) and English
- ✅ **API documentation** - Comprehensive Swagger docs
- ✅ **Authentication system** - JWT token-based auth
- ✅ **File upload handling** - Product images and documents
- ✅ **Search and filtering** - Advanced product search
- ✅ **Delivery management** - Zones, methods, and pricing
- ✅ **Payment gateway ready** - Support for Iranian payment systems

## 🏗️ Architecture

### Backend Structure
```
shop-back/
├── shop/                          # Main application
│   ├── models.py                  # Core models (Store, Product, Category)
│   ├── storefront_models.py       # Shopping models (Cart, Order, Address)
│   ├── views.py                   # Main API views
│   ├── authentication.py          # Auth system (login, register, store request)
│   ├── storefront_views.py        # Shopping cart and checkout APIs
│   ├── import_views.py            # CSV/Excel import/export
│   ├── middleware.py              # Domain-based routing
│   ├── serializers.py             # API serializers
│   ├── urls.py                    # API routing
│   ├── utils.py                   # Utility functions
│   └── admin.py                   # Django admin configuration
├── shop_platform/                 # Django project settings
│   ├── settings.py               # Configuration
│   ├── urls.py                   # Main URL routing
│   └── wsgi.py                   # WSGI application
├── requirements.txt               # Python dependencies
├── manage.py                     # Django management
└── .env.example                  # Environment configuration template
```

### Key Models

#### Core Models
- **Store** - Multi-tenant store with domain, settings, and owner
- **Category** - Hierarchical product categories per store
- **Product** - Rich product model with SEO, inventory, pricing
- **ProductAttribute** - Dynamic attributes system per store
- **ProductImage** - Multiple images per product with ordering

#### Shopping Models
- **Basket** - Shopping cart items per user per store
- **Order** - Complete order with status tracking
- **OrderItem** - Individual items within orders
- **CustomerAddress** - Saved delivery addresses
- **DeliveryZone** - Store-specific delivery areas and pricing
- **PaymentGateway** - Payment method configuration per store

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.8+
- PostgreSQL 12+ (or SQLite for development)
- Redis (optional, for caching)

### Quick Start

1. **Clone the repository**:
```bash
git clone https://github.com/ehsan42324232/shop-back.git
cd shop-back
```

2. **Create virtual environment**:
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment**:
```bash
# Copy and edit environment file
cp .env.example .env

# Edit .env with your settings:
# - Database credentials
# - Secret key
# - Domain configuration
```

5. **Setup database**:
```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

6. **Start development server**:
```bash
python manage.py runserver 0.0.0.0:8000
```

### Windows Setup with PyCharm

1. **Open project in PyCharm**
2. **Configure Python interpreter** (File → Settings → Python Interpreter)
3. **Create virtual environment** in PyCharm
4. **Install requirements** in PyCharm terminal
5. **Configure run configuration** for Django server
6. **Setup PostgreSQL database** (or use SQLite)

## 🌐 Multi-Store Configuration

### Domain Setup
For local development, add these entries to your hosts file:

**Windows**: `C:\Windows\System32\drivers\etc\hosts`
**macOS/Linux**: `/etc/hosts`

```
127.0.0.1 localhost
127.0.0.1 shop1.localhost
127.0.0.1 shop2.localhost
127.0.0.1 admin.localhost
```

### Environment Configuration
```env
# Platform settings
PLATFORM_DOMAIN=localhost
ALLOWED_HOSTS=localhost,127.0.0.1,*.localhost,shop1.localhost,shop2.localhost

# Database (choose one)
USE_SQLITE=True  # For development
# OR
DB_NAME=shop_platform
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Security
SECRET_KEY=your-very-secret-key
DEBUG=True
```

## 📚 API Documentation

Once the server is running, access the API documentation at:

- **Swagger UI**: http://localhost:8000/api/docs/
- **API Schema**: http://localhost:8000/api/schema/
- **Django Admin**: http://localhost:8000/admin/

### API Endpoints Overview

#### Authentication
```
POST   /api/auth/register/           # User registration
POST   /api/auth/login/              # User login
POST   /api/auth/logout/             # User logout
GET    /api/auth/profile/            # Get user profile
PUT    /api/auth/update-profile/     # Update profile
POST   /api/auth/change-password/    # Change password
POST   /api/auth/request-store/      # Request new store
```

#### Store Management
```
GET    /api/store/profile/           # Get store profile
PUT    /api/store/update/            # Update store settings
GET    /api/store/analytics/         # Store analytics
GET    /api/store/info/              # Public store info
```

#### Products & Categories
```
GET    /api/products/               # List products
POST   /api/products/               # Create product
GET    /api/products/{id}/          # Get product details
PUT    /api/products/{id}/          # Update product
DELETE /api/products/{id}/          # Delete product

GET    /api/categories/             # List categories
POST   /api/categories/             # Create category
GET    /api/categories/{id}/        # Get category
PUT    /api/categories/{id}/        # Update category
```

#### Shopping Cart & Orders
```
GET    /api/basket/                 # Get shopping cart
POST   /api/basket/add/             # Add to cart
PUT    /api/basket/{id}/update/     # Update cart item
DELETE /api/basket/{id}/remove/     # Remove from cart

GET    /api/orders/                 # List orders
POST   /api/orders/create/          # Create order
GET    /api/orders/{id}/            # Get order details
```

#### Bulk Import/Export
```
POST   /api/import/products/        # Import products from CSV/Excel
POST   /api/import/validate/        # Validate import file
GET    /api/import/logs/            # Import history
GET    /api/import/template/        # Download sample template
POST   /api/export/products/        # Export products
```

## 🚀 Production Deployment

### Environment Setup
```env
# Production settings
DEBUG=False
SECRET_KEY=your-super-secret-production-key
ALLOWED_HOSTS=yourdomain.com,*.yourdomain.com

# Database
DB_NAME=shop_platform_prod
DB_USER=shop_user
DB_PASSWORD=secure_password
DB_HOST=your-db-host
DB_PORT=5432

# Redis Cache
REDIS_URL=redis://your-redis-host:6379/1

# Email
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password

# File Storage (AWS S3)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
```

### Deployment Checklist
- [ ] Configure production database
- [ ] Set up Redis for caching
- [ ] Configure email backend
- [ ] Set up file storage (AWS S3)
- [ ] Configure domain DNS
- [ ] Set up SSL certificates
- [ ] Configure web server (nginx)
- [ ] Set up process manager (gunicorn + supervisor)
- [ ] Configure monitoring and logging

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test shop

# Run with coverage
coverage run manage.py test
coverage report
```

### API Testing
Use the included Swagger documentation at `/api/docs/` to test API endpoints interactively.

## 🔧 Development

### Adding New Features
1. Create feature branch: `git checkout -b feature/new-feature`
2. Implement changes
3. Add tests
4. Update documentation
5. Submit pull request

### Code Style
```bash
# Format code
black .

# Check style
flake8 .

# Type checking
mypy .
```

## 📝 Configuration

### Key Settings

#### Multi-Store Settings
```python
PLATFORM_SETTINGS = {
    'STORE_APPROVAL_REQUIRED': True,
    'AUTO_APPROVE_STORES': False,  # Set to True for development
    'MAX_PRODUCTS_PER_STORE': 10000,
    'MAX_CATEGORIES_PER_STORE': 100,
    'BULK_IMPORT_MAX_ROWS': 1000,
    'DEFAULT_CURRENCY': 'IRR',
    'DEFAULT_TAX_RATE': 0.09,  # 9% VAT
}
```

#### Security Settings
```python
# Rate limiting
MAX_REQUESTS_PER_MINUTE = 100
BLOCKED_IPS = []  # List of blocked IP addresses

# File upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
ALLOWED_DOCUMENT_EXTENSIONS = ['.csv', '.xlsx', '.xls']
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support, email support@yourplatform.com or create an issue on GitHub.

## 🙏 Acknowledgments

- Django REST Framework for the excellent API framework
- PostgreSQL for robust database support
- Redis for efficient caching
- All contributors who have helped improve this platform

---

**Built with ❤️ for the Iranian e-commerce community**