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
                  [style.backgroundColor]="value.color_code">
              {{ value.display_name }}
            </span>
          </div>
        </div>
      </div>
      
      <!-- Add New Attribute -->
      <button (click)="showAddAttributeDialog()" class="btn-primary">
        افزودن ویژگی جدید
      </button>
    </div>
  `
})
export class AttributeManagementComponent {
  attributes: ProductAttribute[] = [];
  
  constructor(private attributeService: AttributeService) {}
  
  ngOnInit() {
    this.loadAttributes();
  }
  
  loadAttributes() {
    this.attributeService.getAttributes().subscribe(
      attributes => this.attributes = attributes
    );
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
        <label>{{ attribute.name }}:</label>
        <div class="attribute-options">
          <button *ngFor="let value of attribute.values"
                  class="option-button"
                  [class.selected]="isSelected(attribute.id, value.id)"
                  (click)="selectValue(attribute.id, value.id)">
            <span *ngIf="value.color_code" 
                  class="color-swatch"
                  [style.backgroundColor]="value.color_code"></span>
            <img *ngIf="value.image" [src]="value.image" class="value-image">
            {{ value.display_name }}
            <span *ngIf="value.extra_cost > 0" class="extra-cost">
              +{{ value.extra_cost | currency:'IRR' }}
            </span>
          </button>
        </div>
      </div>
      
      <div class="selected-variant" *ngIf="selectedVariant">
        <h4>محصول انتخاب شده:</h4>
        <p>SKU: {{ selectedVariant.sku }}</p>
        <p>قیمت: {{ getVariantPrice() | currency:'IRR' }}</p>
        <p>موجودی: {{ selectedVariant.stock_quantity }}</p>
      </div>
    </div>
  `
})
export class VariantSelectorComponent {
  @Input() product: Product;
  @Output() variantSelected = new EventEmitter<ProductVariant>();
  
  selectedValues: Map<number, number> = new Map();
  selectedVariant: ProductVariant | null = null;
  
  selectValue(attributeId: number, valueId: number) {
    this.selectedValues.set(attributeId, valueId);
    this.findMatchingVariant();
  }
  
  findMatchingVariant() {
    // Find variant that matches selected attribute values
    this.selectedVariant = this.product.variants.find(variant => {
      return this.variantMatchesSelection(variant);
    });
    
    if (this.selectedVariant) {
      this.variantSelected.emit(this.selectedVariant);
    }
  }
}
```

## Usage Examples

### Creating Attributes

```python
# Create a Color attribute
color_attr = ProductAttribute.objects.create(
    store=store,
    name="رنگ",
    attribute_type="color",
    is_required=True,
    is_variation=True
)

# Add color values
red = ProductAttributeValue.objects.create(
    attribute=color_attr,
    value="red",
    display_name="قرمز",
    color_code="#FF0000"
)

blue = ProductAttributeValue.objects.create(
    attribute=color_attr,
    value="blue",
    display_name="آبی",
    color_code="#0000FF"
)
```

### Generating Variants

```python
def generate_product_variants(product):
    """Generate all possible variants for a product"""
    attributes = product.attributes.all()
    
    if not attributes:
        return
    
    # Get all attribute value combinations
    value_combinations = itertools.product(
        *[attr.values.all() for attr in attributes]
    )
    
    for combination in value_combinations:
        # Create variant
        variant = ProductVariant.objects.create(
            product=product,
            sku=f"{product.sku}-{'-'.join([v.value for v in combination])}"
        )
        
        # Add attribute values
        variant.attribute_values.set(combination)
        
        # Calculate price adjustment
        extra_cost = sum(v.extra_cost for v in combination)
        variant.price_adjustment = extra_cost
        variant.save()
```

### Filtering Products by Attributes

```python
def filter_products_by_attributes(queryset, filters):
    """Filter products by attribute values"""
    for attr_name, values in filters.items():
        queryset = queryset.filter(
            variants__attribute_values__attribute__name=attr_name,
            variants__attribute_values__value__in=values
        ).distinct()
    
    return queryset

# Usage
products = Product.objects.filter(store=store)
filtered = filter_products_by_attributes(products, {
    'رنگ': ['قرمز', 'آبی'],
    'سایز': ['بزرگ', 'متوسط']
})
```

## Best Practices

### 1. Attribute Organization

- Group related attributes together
- Use consistent naming conventions
- Order attributes by importance

### 2. Performance Optimization

- Use database indexing for frequently queried attributes
- Cache attribute combinations
- Optimize variant generation for products with many attributes

### 3. User Experience

- Show visual representations for color/pattern attributes
- Provide clear pricing information for variants
- Indicate stock availability for each variant

### 4. Inventory Management

- Track stock separately for each variant
- Set up low stock alerts for variants
- Provide bulk inventory update tools

## Migration Guide

### From Simple Products to Variants

1. **Backup existing data**
2. **Create attributes for existing product variations**
3. **Generate variants from existing products**
4. **Migrate inventory data to variants**
5. **Update frontend to use variant selector**

```python
# Migration script example
def migrate_to_variants():
    for product in Product.objects.filter(has_variants=False):
        # Create default variant
        default_variant = ProductVariant.objects.create(
            product=product,
            sku=product.sku,
            stock_quantity=product.stock_quantity,
            price_adjustment=0
        )
        
        # Mark product as having variants
        product.has_variants = True
        product.save()
```

## API Response Examples

### Product with Variants

```json
{
  "id": 1,
  "name": "تی‌شرت کلاسیک",
  "base_price": 50000,
  "attributes": [
    {
      "id": 1,
      "name": "رنگ",
      "type": "color",
      "values": [
        {
          "id": 1,
          "value": "red",
          "display_name": "قرمز",
          "color_code": "#FF0000",
          "extra_cost": 0
        },
        {
          "id": 2,
          "value": "blue",
          "display_name": "آبی",
          "color_code": "#0000FF",
          "extra_cost": 5000
        }
      ]
    }
  ],
  "variants": [
    {
      "id": 1,
      "sku": "TSH-001-RED-L",
      "attribute_values": [1, 3],
      "price_adjustment": 0,
      "stock_quantity": 10,
      "final_price": 50000
    }
  ]
}
```
