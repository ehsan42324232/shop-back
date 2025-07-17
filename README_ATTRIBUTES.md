# Shop Platform with Attributes System

## New Features Added

### 1. Product Attributes System
- **Dynamic Attributes**: Store owners can define custom attributes for their products
- **Attribute Types**: Support for text, number, boolean, choice, color, and date attributes
- **Filtering**: Products can be filtered by attribute values
- **Validation**: Attribute values are validated based on their type

### 2. Bulk Import System
- **CSV/Excel Support**: Import products from CSV or Excel files
- **Automatic Category Creation**: Creates category hierarchy from import data
- **Attribute Mapping**: Maps CSV columns to product attributes
- **Import Logging**: Tracks import status and errors
- **Update Existing**: Option to update existing products or create new ones

### 3. Enhanced Models

#### ProductAttribute
```python
class ProductAttribute(TimestampedModel):
    store = ForeignKey(Store)
    name = CharField(max_length=100)
    attribute_type = CharField(choices=ATTRIBUTE_TYPES)
    is_required = BooleanField(default=False)
    is_filterable = BooleanField(default=True)
    is_searchable = BooleanField(default=False)
    choices = JSONField(default=list)  # For choice attributes
    unit = CharField(max_length=20, blank=True)  # For number attributes
```

#### ProductAttributeValue
```python
class ProductAttributeValue(TimestampedModel):
    product = ForeignKey(Product)
    attribute = ForeignKey(ProductAttribute)
    value = TextField()
```

#### BulkImportLog
```python
class BulkImportLog(TimestampedModel):
    store = ForeignKey(Store)
    user = ForeignKey(User)
    filename = CharField(max_length=255)
    status = CharField(choices=IMPORT_STATUS_CHOICES)
    total_rows = IntegerField(default=0)
    successful_rows = IntegerField(default=0)
    failed_rows = IntegerField(default=0)
    error_details = JSONField(default=list)
```

### 4. API Endpoints

#### Product Attributes
- `GET /api/product-attributes/` - List attributes
- `POST /api/product-attributes/` - Create attribute
- `GET /api/product-attributes/{id}/` - Get attribute details
- `PUT /api/product-attributes/{id}/` - Update attribute
- `DELETE /api/product-attributes/{id}/` - Delete attribute

#### Product with Attributes
- `POST /api/products/{id}/attributes/` - Set product attributes
- `PUT /api/products/{id}/attributes/` - Replace product attributes
- `GET /api/products/?attr_color=red&attr_size=large` - Filter by attributes

#### Bulk Import
- `POST /api/products/bulk_import/` - Import products from CSV/Excel
- `GET /api/import-logs/` - List import logs
- `GET /api/import-logs/{id}/` - Get import log details

#### Store Attributes
- `GET /api/stores/{id}/attributes/` - Get store's attributes

### 5. CSV Import Format

The CSV file should have the following structure:

```csv
title,description,price,sku,stock,category,attr_color,attr_size,attr_material,attr_brand
"iPhone 15 Pro","Latest smartphone",999.99,IP15001,50,"Electronics > Smartphones","Blue","128GB","Titanium","Apple"
```

#### Required Columns:
- `title`: Product title
- `price`: Product price
- `stock`: Stock quantity

#### Optional Columns:
- `description`: Product description
- `sku`: Stock keeping unit
- `category`: Category path (e.g., "Electronics > Smartphones")
- `attr_*`: Attribute columns (e.g., `attr_color`, `attr_size`)

### 6. Domain Resolution Middleware

Added middleware to resolve stores by domain:

```python
class DomainMiddleware(MiddlewareMixin):
    def process_request(self, request):
        host = request.get_host()
        try:
            store = Store.objects.get(domain=host, is_active=True)
            request.store = store
        except Store.DoesNotExist:
            request.store = None
```

### 7. Enhanced Search and Filtering

- **Attribute-based filtering**: Filter products by attribute values
- **Advanced search**: Search in product titles, descriptions, and attribute values
- **Price range filtering**: Filter by minimum and maximum price
- **Stock availability**: Filter by in-stock or out-of-stock products

### 8. Usage Examples

#### Creating a Store with Attributes
```python
# Create store
store = Store.objects.create(
    owner=user,
    name="My Electronics Store",
    domain="electronics.example.com"
)

# Create attributes
color_attr = ProductAttribute.objects.create(
    store=store,
    name="Color",
    attribute_type="choice",
    choices=["Red", "Blue", "Green", "Black"],
    is_filterable=True
)

size_attr = ProductAttribute.objects.create(
    store=store,
    name="Storage",
    attribute_type="choice",
    choices=["128GB", "256GB", "512GB", "1TB"],
    is_filterable=True
)
```

#### Creating a Product with Attributes
```python
# Create product
product = Product.objects.create(
    store=store,
    title="iPhone 15 Pro",
    price=999.99,
    stock=50
)

# Add attributes
ProductAttributeValue.objects.create(
    product=product,
    attribute=color_attr,
    value="Blue"
)

ProductAttributeValue.objects.create(
    product=product,
    attribute=size_attr,
    value="256GB"
)
```

#### Filtering Products by Attributes
```python
# API call: GET /api/products/?attr_color=Blue&attr_storage=256GB
# This will return products with Blue color and 256GB storage
```

#### Bulk Import via API
```python
import requests

files = {'file': open('products.csv', 'rb')}
data = {
    'store_id': 'your-store-uuid',
    'update_existing': True,
    'create_categories': True
}

response = requests.post('/api/products/bulk_import/', files=files, data=data)
```

### 9. Installation and Setup

1. **Install new dependencies**:
```bash
pip install -r requirements_with_attributes.txt
```

2. **Update your models**:
```python
# Replace your existing models with models_with_attributes.py
```

3. **Run migrations**:
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **Update URLs**:
```python
# Use urls_with_attributes.py for your URL configuration
```

5. **Add middleware to settings**:
```python
MIDDLEWARE = [
    # ... other middleware
    'shop.middleware.DomainMiddleware',
    'shop.middleware.StoreContextMiddleware',
]
```

### 10. Testing the New Features

#### Test Attribute Creation
```bash
curl -X POST http://localhost:8000/api/product-attributes/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "Color",
    "attribute_type": "choice",
    "choices": ["Red", "Blue", "Green"],
    "is_filterable": true
  }'
```

#### Test Product Attribute Assignment
```bash
curl -X POST http://localhost:8000/api/products/PRODUCT_ID/attributes/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "attributes": [
      {"attribute_id": "ATTR_ID", "value": "Red"}
    ]
  }'
```

#### Test Bulk Import
```bash
curl -X POST http://localhost:8000/api/products/bulk_import/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@sample_import_template.csv" \
  -F "store_id=YOUR_STORE_ID" \
  -F "update_existing=true" \
  -F "create_categories=true"
```

### 11. Next Steps

This implementation provides the foundation for:
- **Frontend admin panels** for managing attributes and imports
- **Advanced filtering UI** for customers
- **Domain-specific storefronts** for each store
- **Payment and delivery integration**
- **Analytics and reporting**

The system is now ready for the frontend implementation and further enhancements!
