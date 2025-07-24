# Mall Platform Product Models with Hierarchical Attributes
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .mall_user_models import Store, MallUser
import uuid


class ProductClass(models.Model):
    """Root product class with hierarchical structure"""
    name = models.CharField(max_length=200, db_index=True)
    name_en = models.CharField(max_length=200, blank=True)  # English name for SEO
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    
    # Hierarchical structure
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    level = models.PositiveIntegerField(default=0, db_index=True)
    path = models.CharField(max_length=500, db_index=True)  # Materialized path for efficient queries
    
    # Basic information
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Media
    icon = models.ImageField(upload_to='product_class_icons/', blank=True, null=True)
    image = models.ImageField(upload_to='product_class_images/', blank=True, null=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Statistics
    product_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_classes'
        verbose_name = 'Product Class'
        verbose_name_plural = 'Product Classes'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['parent']),
            models.Index(fields=['level']),
            models.Index(fields=['path']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Update level and path based on parent
        if self.parent:
            self.level = self.parent.level + 1
            self.path = f"{self.parent.path}/{self.slug}"
        else:
            self.level = 0
            self.path = self.slug
        
        super().save(*args, **kwargs)
        
        # Update children paths if path changed
        if self.pk:
            self._update_children_paths()
    
    def _update_children_paths(self):
        """Update paths for all children"""
        for child in self.children.all():
            child.save()  # This will trigger path update
    
    def get_ancestors(self):
        """Get all ancestors of this class"""
        if not self.parent:
            return ProductClass.objects.none()
        
        return ProductClass.objects.filter(
            path__in=[p for p in self.path.split('/') if p]
        ).exclude(pk=self.pk)
    
    def get_descendants(self):
        """Get all descendants of this class"""
        return ProductClass.objects.filter(
            path__startswith=f"{self.path}/"
        )
    
    def get_children(self):
        """Get direct children"""
        return self.children.filter(is_active=True).order_by('sort_order', 'name')
    
    def is_leaf(self):
        """Check if this is a leaf node (no children)"""
        return not self.children.exists()
    
    def can_have_products(self):
        """Only leaf nodes can have product instances"""
        return self.is_leaf()
    
    def get_full_name(self):
        """Get full hierarchical name"""
        if self.parent:
            return f"{self.parent.get_full_name()} > {self.name}"
        return self.name
    
    def update_product_count(self):
        """Update product count for this class and ancestors"""
        # Count products in this class and all descendants
        from .models_product_instances import Product
        
        descendant_classes = list(self.get_descendants()) + [self]
        self.product_count = Product.objects.filter(
            product_class__in=descendant_classes,
            is_active=True
        ).count()
        self.save(update_fields=['product_count'])
        
        # Update parent counts
        if self.parent:
            self.parent.update_product_count()


class ProductAttribute(models.Model):
    """Product attributes that can be assigned to product classes"""
    ATTRIBUTE_TYPES = [
        ('text', 'متن'),
        ('number', 'عدد'),
        ('decimal', 'اعشار'),
        ('boolean', 'بله/خیر'),
        ('choice', 'انتخاب از لیست'),
        ('multi_choice', 'انتخاب چندگانه'),
        ('color', 'رنگ'),
        ('image', 'تصویر'),
        ('file', 'فایل'),
        ('date', 'تاریخ'),
        ('datetime', 'تاریخ و زمان'),
        ('url', 'لینک'),
        ('email', 'ایمیل'),
        ('phone', 'تلفن'),
    ]
    
    name = models.CharField(max_length=200, db_index=True)
    name_en = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    
    # Attribute configuration
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, default='text')
    is_required = models.BooleanField(default=False)
    is_categorizer = models.BooleanField(default=False)  # Level 1 children can use this for subcategorization
    is_filterable = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=False)
    
    # Display settings
    display_name = models.CharField(max_length=200, blank=True)
    help_text = models.TextField(blank=True)
    placeholder = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=50, blank=True)  # e.g., 'سانتی‌متر', 'کیلوگرم'
    
    # Validation settings
    min_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_length = models.PositiveIntegerField(null=True, blank=True)
    max_length = models.PositiveIntegerField(null=True, blank=True)
    regex_pattern = models.CharField(max_length=500, blank=True)
    
    # For choice/multi_choice types
    choices_json = models.JSONField(blank=True, null=True)
    
    # Display order
    sort_order = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_attributes'
        verbose_name = 'Product Attribute'
        verbose_name_plural = 'Product Attributes'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_choices(self):
        """Get choices for choice/multi_choice attributes"""
        if self.attribute_type in ['choice', 'multi_choice'] and self.choices_json:
            return self.choices_json
        return []
    
    def validate_value(self, value):
        """Validate attribute value based on type and constraints"""
        if self.is_required and not value:
            return False, "این فیلد الزامی است"
        
        if not value:  # Optional field with no value
            return True, None
        
        # Type-specific validation
        if self.attribute_type == 'number':
            try:
                num_value = int(value)
                if self.min_value and num_value < self.min_value:
                    return False, f"مقدار نباید کمتر از {self.min_value} باشد"
                if self.max_value and num_value > self.max_value:
                    return False, f"مقدار نباید بیشتر از {self.max_value} باشد"
            except ValueError:
                return False, "مقدار باید عددی باشد"
        
        elif self.attribute_type == 'decimal':
            try:
                decimal_value = float(value)
                if self.min_value and decimal_value < float(self.min_value):
                    return False, f"مقدار نباید کمتر از {self.min_value} باشد"
                if self.max_value and decimal_value > float(self.max_value):
                    return False, f"مقدار نباید بیشتر از {self.max_value} باشد"
            except ValueError:
                return False, "مقدار باید عددی باشد"
        
        elif self.attribute_type == 'text':
            if self.min_length and len(str(value)) < self.min_length:
                return False, f"متن باید حداقل {self.min_length} کاراکتر باشد"
            if self.max_length and len(str(value)) > self.max_length:
                return False, f"متن نباید بیشتر از {self.max_length} کاراکتر باشد"
        
        elif self.attribute_type in ['choice', 'multi_choice']:
            choices = self.get_choices()
            if self.attribute_type == 'choice':
                if value not in [choice['value'] for choice in choices]:
                    return False, "انتخاب نامعتبر است"
            else:  # multi_choice
                if isinstance(value, list):
                    valid_choices = [choice['value'] for choice in choices]
                    for v in value:
                        if v not in valid_choices:
                            return False, f"انتخاب '{v}' نامعتبر است"
        
        return True, None


class ProductClassAttribute(models.Model):
    """Association between product classes and attributes"""
    product_class = models.ForeignKey(ProductClass, on_delete=models.CASCADE, related_name='class_attributes')
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name='class_assignments')
    
    # Override attribute settings for this class
    is_required = models.BooleanField(null=True, blank=True)  # Override default
    is_categorizer = models.BooleanField(null=True, blank=True)  # Override default
    sort_order = models.PositiveIntegerField(default=0)
    
    # Additional choices specific to this class
    additional_choices_json = models.JSONField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_class_attributes'
        verbose_name = 'Product Class Attribute'
        verbose_name_plural = 'Product Class Attributes'
        unique_together = ['product_class', 'attribute']
        ordering = ['sort_order', 'attribute__sort_order']
    
    def __str__(self):
        return f"{self.product_class.name} - {self.attribute.name}"
    
    def get_effective_is_required(self):
        """Get effective is_required setting"""
        return self.is_required if self.is_required is not None else self.attribute.is_required
    
    def get_effective_is_categorizer(self):
        """Get effective is_categorizer setting"""
        return self.is_categorizer if self.is_categorizer is not None else self.attribute.is_categorizer
    
    def get_all_choices(self):
        """Get combined choices from attribute and class-specific additions"""
        base_choices = self.attribute.get_choices()
        additional_choices = self.additional_choices_json or []
        return base_choices + additional_choices


# Predefined attributes as mentioned in product description
class PredefinedAttributes:
    """Factory for creating predefined attributes"""
    
    @staticmethod
    def create_color_attribute():
        """Create predefined color attribute"""
        color_choices = [
            {'value': 'red', 'label': 'قرمز', 'color': '#dc2626'},
            {'value': 'blue', 'label': 'آبی', 'color': '#2563eb'},
            {'value': 'green', 'label': 'سبز', 'color': '#16a34a'},
            {'value': 'yellow', 'label': 'زرد', 'color': '#eab308'},
            {'value': 'black', 'label': 'مشکی', 'color': '#000000'},
            {'value': 'white', 'label': 'سفید', 'color': '#ffffff'},
            {'value': 'gray', 'label': 'خاکستری', 'color': '#6b7280'},
            {'value': 'brown', 'label': 'قهوه‌ای', 'color': '#a16207'},
            {'value': 'pink', 'label': 'صورتی', 'color': '#ec4899'},
            {'value': 'purple', 'label': 'بنفش', 'color': '#9333ea'},
            {'value': 'orange', 'label': 'نارنجی', 'color': '#ea580c'},
            {'value': 'navy', 'label': 'سرمه‌ای', 'color': '#1e40af'},
        ]
        
        attribute, created = ProductAttribute.objects.get_or_create(
            slug='color',
            defaults={
                'name': 'رنگ',
                'name_en': 'Color',
                'attribute_type': 'choice',
                'display_name': 'رنگ',
                'is_filterable': True,
                'is_categorizer': False,
                'choices_json': color_choices,
                'help_text': 'رنگ محصول را انتخاب کنید'
            }
        )
        
        return attribute
    
    @staticmethod
    def create_description_attribute():
        """Create predefined description attribute"""
        attribute, created = ProductAttribute.objects.get_or_create(
            slug='description',
            defaults={
                'name': 'توضیحات',
                'name_en': 'Description',
                'attribute_type': 'text',
                'display_name': 'توضیحات محصول',
                'is_required': True,
                'is_searchable': True,
                'min_length': 10,
                'max_length': 2000,
                'help_text': 'توضیحات کامل محصول را وارد کنید'
            }
        )
        
        return attribute
    
    @staticmethod
    def create_size_attribute():
        """Create predefined size attribute for clothing"""
        size_choices = [
            {'value': 'xs', 'label': 'XS (۳۴)'},
            {'value': 's', 'label': 'S (۳۶)'},
            {'value': 'm', 'label': 'M (۳۸)'},
            {'value': 'l', 'label': 'L (۴۰)'},
            {'value': 'xl', 'label': 'XL (۴۲)'},
            {'value': 'xxl', 'label': 'XXL (۴۴)'},
            {'value': 'xxxl', 'label': 'XXXL (۴۶)'},
        ]
        
        attribute, created = ProductAttribute.objects.get_or_create(
            slug='size',
            defaults={
                'name': 'سایز',
                'name_en': 'Size',
                'attribute_type': 'choice',
                'display_name': 'سایز',
                'is_filterable': True,
                'is_categorizer': False,
                'choices_json': size_choices,
                'help_text': 'سایز محصول را انتخاب کنید'
            }
        )
        
        return attribute
    
    @staticmethod
    def create_sex_attribute():
        """Create predefined sex attribute for clothing categorization"""
        sex_choices = [
            {'value': 'male', 'label': 'مردانه'},
            {'value': 'female', 'label': 'زنانه'},
            {'value': 'unisex', 'label': 'مشترک'},
        ]
        
        attribute, created = ProductAttribute.objects.get_or_create(
            slug='sex',
            defaults={
                'name': 'جنسیت',
                'name_en': 'Sex',
                'attribute_type': 'choice',
                'display_name': 'مناسب برای',
                'is_filterable': True,
                'is_categorizer': True,  # This can be used for categorization
                'choices_json': sex_choices,
                'help_text': 'این محصول مناسب چه جنسیتی است'
            }
        )
        
        return attribute
    
    @staticmethod
    def create_all_predefined():
        """Create all predefined attributes"""
        return {
            'color': PredefinedAttributes.create_color_attribute(),
            'description': PredefinedAttributes.create_description_attribute(),
            'size': PredefinedAttributes.create_size_attribute(),
            'sex': PredefinedAttributes.create_sex_attribute(),
        }


class ProductMedia(models.Model):
    """Media files for products (images/videos)"""
    MEDIA_TYPES = [
        ('image', 'تصویر'),
        ('video', 'ویدیو'),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image')
    
    # File fields
    file = models.FileField(upload_to='product_media/')
    thumbnail = models.ImageField(upload_to='product_media_thumbs/', blank=True, null=True)
    
    # Metadata
    title = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # Technical details
    file_size = models.PositiveIntegerField(null=True, blank=True)  # in bytes
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)  # for videos, in seconds
    
    # Social media source (if imported)
    social_source = models.CharField(max_length=50, blank=True)  # 'instagram', 'telegram'
    social_url = models.URLField(blank=True)
    social_id = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_media'
        verbose_name = 'Product Media'
        verbose_name_plural = 'Product Media'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['media_type']),
            models.Index(fields=['social_source']),
        ]
    
    def __str__(self):
        return f"{self.get_media_type_display()} - {self.title or self.uuid}"
    
    def get_thumbnail_url(self):
        """Get thumbnail URL, create if needed"""
        if self.thumbnail:
            return self.thumbnail.url
        elif self.media_type == 'image':
            return self.file.url
        return None
    
    def is_image(self):
        return self.media_type == 'image'
    
    def is_video(self):
        return self.media_type == 'video'
