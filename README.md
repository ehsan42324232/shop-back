# Shop Platform Backend

A Django REST API backend for a multi-store e-commerce platform.

## Features

- **Multi-store Architecture**: Support for multiple stores on one platform
- **Product Management**: Categories, products with media, ratings, and comments
- **User Authentication**: Token-based authentication with registration/login
- **Shopping Cart**: Basket functionality with order creation
- **Order Management**: Complete order lifecycle with logistics tracking
- **API Documentation**: Swagger/OpenAPI documentation
- **File Upload**: Support for product images and media
- **Search & Filtering**: Advanced product search capabilities

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/ehsan42324232/shop-back.git
cd shop-back
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start with Docker Compose:
```bash
docker-compose up --build
```

4. Run migrations:
```bash
docker-compose exec backend python manage.py migrate
```

5. Create superuser:
```bash
docker-compose exec backend python manage.py createsuperuser
```

### Manual Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run migrations:
```bash
python manage.py migrate
```

3. Create superuser:
```bash
python manage.py createsuperuser
```

4. Start development server:
```bash
python manage.py runserver
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout

### Stores
- `GET /api/stores/` - List all stores
- `POST /api/stores/` - Create store (authenticated)
- `GET /api/stores/{id}/` - Get store details
- `GET /api/stores/{id}/products/` - Get store products

### Products
- `GET /api/products/` - List products (filterable)
- `GET /api/products/{id}/` - Get product details
- `POST /api/products/{id}/add_comment/` - Add product comment
- `POST /api/products/{id}/add_rating/` - Add product rating

### Categories
- `GET /api/categories/` - List categories
- `POST /api/categories/` - Create category

### Shopping Cart
- `GET /api/basket/` - Get user's basket
- `POST /api/basket/` - Add item to basket
- `DELETE /api/basket/{id}/` - Remove item from basket
- `DELETE /api/basket/clear/` - Clear entire basket

### Orders
- `GET /api/orders/` - List user's orders
- `POST /api/orders/` - Create order from basket
- `GET /api/orders/{id}/` - Get order details

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/api/docs/`
- OpenAPI Schema: `http://localhost:8000/api/schema/`

## Project Structure

```
shop-back/
├── shop/                   # Main app
│   ├── models.py          # Database models
│   ├── serializers.py     # API serializers
│   ├── views.py           # API views
│   ├── authentication.py # Auth endpoints
│   └── urls.py           # URL routing
├── shop_platform/         # Django project
│   ├── settings.py       # Django settings
│   └── urls.py          # Main URL config
├── requirements.txt       # Python dependencies
├── docker-compose.yml    # Docker configuration
└── Dockerfile           # Docker image
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Required |
| `DEBUG` | Debug mode | `True` |
| `DATABASE_URL` | Database connection string | SQLite |
| `ALLOWED_HOSTS` | Allowed hosts | `localhost,127.0.0.1` |

## Development

### Running Tests
```bash
python manage.py test
```

### Code Style
```bash
flake8 .
black .
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## Production Deployment

1. Set environment variables
2. Use PostgreSQL database
3. Configure static/media file serving
4. Set up reverse proxy (nginx)
5. Use gunicorn as WSGI server

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Run tests
5. Submit pull request

## License

MIT License
