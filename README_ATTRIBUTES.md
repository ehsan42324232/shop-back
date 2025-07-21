# Product Attributes System

This document describes the advanced product attributes system that allows stores to define custom attributes for their products.

## Overview

The product attributes system enables store owners to:
- Define custom attributes for their products (color, size, material, etc.)
- Create attribute groups for better organization
- Set different pricing and inventory for attribute combinations
- Generate product variants automatically

## Models

### ProductAttribute

Defines the type of attribute (e.g., "Color", "Size").

```python
class ProductAttribute(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g., "Color", "Size"
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES)
    is_required = models.BooleanField(default=False)
    is_variation = models.BooleanField(default=True)  # Affects pricing/inventory
    display_order = models.PositiveIntegerField(default=0)
```

### ProductAttributeValue

Defines possible values for an attribute (e.g., "Red", "Blue" for Color).

```python
class ProductAttributeValue(models.Model):
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)  # e.g., "Red", "Large"
    display_name = models.CharField(max_length=100)  # For localization
    color_code = models.CharField(max_length=7, blank=True)  # For color attributes
    image = models.ImageField(upload_to='attributes/', blank=True)
    extra_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
```

### ProductVariant

Represents a specific combination of attribute values.

```python
class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    sku = models.CharField(max_length=100, unique=True)
    attribute_values = models.ManyToManyField(ProductAttributeValue)
    
    # Variant-specific pricing and inventory
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
```

## API Endpoints

### Product Attributes Management

```
GET    /api/product-attributes/           # List attributes for store
POST   /api/product-attributes/           # Create new attribute
PUT    /api/product-attributes/{id}/      # Update attribute
DELETE /api/product-attributes/{id}/      # Delete attribute
```

### Attribute Values

```
GET    /api/product-attributes/{id}/values/        # List values for attribute
POST   /api/product-attributes/{id}/values/        # Add value to attribute
PUT    /api/attribute-values/{id}/                 # Update value
DELETE /api/attribute-values/{id}/                 # Delete value
```

### Product Variants

```
GET    /api/products/{id}/variants/                # List product variants
POST   /api/products/{id}/variants/generate/       # Generate all possible variants
PUT    /api/product-variants/{id}/                 # Update specific variant
DELETE /api/product-variants/{id}/                 # Delete variant
```

## Frontend Implementation

### Attribute Management Component

```typescript
@Component({
  selector: 'app-attribute-management',
  template: `
    <div class="attribute-management">
      <!-- Attribute List -->
      <div class="attributes-list">
        <div *ngFor="let attr of attributes" class="attribute-item">
          <h3>{{ attr.name }}</h3>
          <div class="attribute-values">
            <span *ngFor="let value of attr.values" 
                  class="value-tag"
                  [style.background-color]="value.color_code">
              {{ value.display_name }}
            </span>
          </div>
        </div>
      </div>
      
      <!-- Add New Attribute -->
      <button (click)="showAddAttributeModal = true">
        افزودن ویژگی جدید
      </button>
    </div>
  `
})
export class AttributeManagementComponent {
  attributes: ProductAttribute[] = [];
  
  constructor(private attributeService: AttributeService) {}
  
  loadAttributes() {
    this.attributeService.getAttributes().subscribe(data => {
      this.attributes = data;
    });
  }
}
```

### Product Variant Selector

```typescript
@Component({
  selector: 'app-variant-selector',
  template: `
    <div class="variant-selector">
      <div *ngFor="let attribute of product.attributes" class="attribute-group">
        <label>{{ attribute.name }}</label>
        <div class="attribute-options">
          <button *ngFor="let value of attribute.values"
                  [class.selected]="isSelected(attribute.id, value.id)"
                  (click)="selectValue(attribute.id, value.id)">
            <span *ngIf="value.color_code" 
                  class="color-swatch"
                  [style.background-color]="value.color_code"></span>
            {{ value.display_name }}
          </button>
        </div>
      </div>
      
      <div class="variant-info" *ngIf="selectedVariant">
        <p>قیمت: {{ getVariantPrice() | currency:'IRR' }}</p>
        <p>موجودی: {{ selectedVariant.stock_quantity }}</p>
      </div>
    </div>
  `
})
export class VariantSelectorComponent {
  @Input() product: Product;
  selectedValues: Map<number, number> = new Map();
  selectedVariant: ProductVariant | null = null;
  
  selectValue(attributeId: number, valueId: number) {
    this.selectedValues.set(attributeId, valueId);
    this.updateSelectedVariant();
  }
  
  updateSelectedVariant() {
    // Find variant that matches selected values
    this.selectedVariant = this.product.variants.find(variant => {
      return this.variantMatchesSelection(variant);
    });
  }
}
```

## Bulk Import with Attributes

### CSV Format

```csv
name,description,price,color,size,stock_color_size
تی‌شرت ساده,تی‌شرت پنبه‌ای,50000,قرمز,Large,10
تی‌شرت ساده,تی‌شرت پنبه‌ای,50000,قرمز,Medium,15
تی‌شرت ساده,تی‌شرت پنبه‌ای,50000,آبی,Large,8
```

### Import Processing

```python
def process_variant_import(file_data, store):
    """Process CSV import with variant support"""
    
    for row in file_data:
        # Get or create base product
        product, created = Product.objects.get_or_create(
            name=row['name'],
            store=store,
            defaults={
                'description': row['description'],
                'price': row['price']
            }
        )
        
        # Process attributes
        variant_values = []
        for attr_name in ['color', 'size']:  # Dynamic based on CSV columns
            if attr_name in row and row[attr_name]:
                attribute = get_or_create_attribute(store, attr_name)
                value = get_or_create_attribute_value(
                    attribute, 
                    row[attr_name]
                )
                variant_values.append(value)
        
        # Create or update variant
        if variant_values:
            variant = create_or_update_variant(
                product, 
                variant_values, 
                row
            )
```

## Advanced Features

### Dynamic Pricing Rules

```python
class AttributePricingRule(models.Model):
    """Rules for automatic pricing based on attribute combinations"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    # Conditions
    attribute_conditions = models.JSONField()  # {"color": ["red"], "size": ["large"]}
    
    # Pricing adjustments
    price_adjustment_type = models.CharField(
        max_length=20, 
        choices=[('fixed', 'Fixed'), ('percentage', 'Percentage')]
    )
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2)
    
    is_active = models.BooleanField(default=True)
```

### Inventory Alerts

```python
def check_variant_stock_alerts(store):
    """Check for low stock variants and send alerts"""
    
    low_stock_variants = ProductVariant.objects.filter(
        product__store=store,
        stock_quantity__lte=F('product__low_stock_threshold'),
        is_active=True
    )
    
    if low_stock_variants.exists():
        send_low_stock_alert(store, low_stock_variants)
```

### SEO for Variants

```python
class VariantSEO(models.Model):
    """SEO optimization for product variants"""
    variant = models.OneToOneField(ProductVariant, on_delete=models.CASCADE)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    url_slug = models.SlugField(max_length=200, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.url_slug:
            # Generate SEO-friendly slug
            variant_description = self.get_variant_description()
            self.url_slug = slugify(f"{self.variant.product.name}-{variant_description}")
        super().save(*args, **kwargs)
```

## Best Practices

### 1. Attribute Organization

- Group related attributes together
- Use consistent naming conventions
- Define attributes at store level for reusability

### 2. Performance Optimization

- Index frequently queried attribute combinations
- Use select_related/prefetch_related for variant queries
- Cache popular attribute combinations

### 3. User Experience

- Show variant availability in real-time
- Provide visual indicators for attributes (colors, images)
- Implement smart filtering based on available combinations

### 4. Inventory Management

- Track stock at variant level
- Implement automatic stock updates
- Set up low stock alerts per variant

## Migration Strategy

### From Simple Products to Variants

```python
def migrate_simple_to_variants():
    """Migrate existing simple products to variant system"""
    
    for product in Product.objects.filter(has_variants=False):
        # Create default variant
        default_variant = ProductVariant.objects.create(
            product=product,
            sku=f"{product.sku}-default",
            stock_quantity=product.stock_quantity,
            price_adjustment=0
        )
        
        # Update product to use variants
        product.has_variants = True
        product.save()
```

## Testing

### Unit Tests

```python
class ProductAttributeTestCase(TestCase):
    def test_variant_price_calculation(self):
        """Test variant price calculation with adjustments"""
        # Create product with base price
        product = Product.objects.create(
            name="Test Product",
            price=100000,
            store=self.store
        )
        
        # Create variant with price adjustment
        variant = ProductVariant.objects.create(
            product=product,
            price_adjustment=10000
        )
        
        self.assertEqual(variant.final_price, 110000)
    
    def test_variant_stock_tracking(self):
        """Test variant-level stock tracking"""
        # Test stock updates and availability
        pass
```

## Future Enhancements

1. **AI-Powered Attribute Suggestions**
   - Suggest attributes based on product category
   - Auto-complete attribute values

2. **Advanced Variant Rules**
   - Conditional attribute display
   - Complex pricing formulas

3. **Multi-Store Attribute Sharing**
   - Share common attributes across stores
   - Standardized attribute definitions

4. **Enhanced Analytics**
   - Variant performance tracking
   - Attribute popularity analysis
