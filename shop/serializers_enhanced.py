from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models_enhanced import (
    Store, StoreRequest, Category, ProductAttribute, 
    Product, ProductAttributeValue, ProductImage, BulkImportLog
)


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for store owner info"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'username', 'date_joined']


class StoreRequestSerializer(serializers.ModelSerializer):
    """Serializer for store creation requests"""
    applicant = UserSerializer(read_only=True)
    
    class Meta:
        model = StoreRequest
        fields = [
            'id', 'applicant', 'store_name', 'desired_domain', 'business_type',
            'description', 'business_license_file', 'tax_certificate_file',
            'status', 'reviewed_by', 'reviewed_at', 'review_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'applicant', 'status', 'reviewed_by', 'reviewed_at',
            'review_notes', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        validated_data['applicant'] = self.context['request'].user
        return super().create(validated_data)


class StoreBasicSerializer(serializers.ModelSerializer):
    """Basic store info for listings"""
    owner = UserSerializer(read_only=True)
    full_domain = serializers.ReadOnlyField()
    
    class Meta:
        model = Store
        fields = [
            'id', 'name', 'name_en', 'slug', 'description', 'logo',
            'domain', 'full_domain', 'status', 'is_active', 'owner',
            'created_at', 'approved_at'
        ]


class StoreDetailSerializer(serializers.ModelSerializer):
    """Detailed store info for store owners and admins"""
    owner = UserSerializer(read_only=True)
    full_domain = serializers.ReadOnlyField()
    
    class Meta:
        model = Store
        fields = [
            'id', 'owner', 'name', 'name_en', 'slug', 'description', 'logo',
            'domain', 'full_domain', 'is_ssl_enabled', 'status', 'is_active',
            'business_license', 'tax_id', 'currency', 'tax_rate',
            'email', 'phone', 'address', 'primary_color', 'secondary_color',
            'custom_css', 'admin_notes', 'requested_at', 'approved_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'owner', 'slug', 'full_domain', 'status', 'is_active',
            'admin_notes', 'requested_at', 'approved_at', 'created_at', 'updated_at'
        ]


class StoreAdminSerializer(serializers.ModelSerializer):
    """Full store info for platform admins"""
    owner = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    full_domain = serializers.ReadOnlyField()
    
    class Meta:
        model = Store
        fields = '__all__'
        read_only_fields = ['id', 'slug', 'full_domain', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        # Handle status changes
        old_status = instance.status
        new_status = validated_data.get('status', old_status)
        
        if old_status != 'approved' and new_status == 'approved':
            validated_data['approved_at'] = timezone.now()
            validated_data['approved_by'] = self.context['request'].user
            validated_data['is_active'] = True
        elif new_status != 'approved':
            validated_data['is_active'] = False
            
        return super().update(instance, validated_data)


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer with hierarchy support"""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    children_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'store', 'name', 'slug', 'description', 'parent', 'parent_name',
            'image', 'is_active', 'sort_order', 'meta_title', 'meta_description',
            'children_count', 'products_count', 'full_path', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_children_count(self, obj):
        return obj.children.filter(is_active=True).count()
    
    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()

    def validate_parent(self, value):
        if value and value.store != self.context.get('store'):
            raise serializers.ValidationError("دسته‌بندی والد باید متعلق به همین فروشگاه باشد")
        return value


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Hierarchical category tree"""
    children = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'image', 'is_active',
            'sort_order', 'products_count', 'children'
        ]
    
    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('sort_order', 'name')
        return CategoryTreeSerializer(children, many=True).data
    
    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Product attribute serializer"""
    
    class Meta:
        model = ProductAttribute
        fields = [
            'id', 'store', 'name', 'slug', 'attribute_type', 'is_required',
            'is_filterable', 'is_searchable', 'choices', 'unit', 'sort_order',
            'min_value', 'max_value', 'max_length', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_choices(self, value):
        if self.instance and self.instance.attribute_type == 'choice' and not value:
            raise serializers.ValidationError("گزینه‌ها برای نوع انتخابی اجباری است")
        return value


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Product attribute value serializer"""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    attribute_unit = serializers.CharField(source='attribute.unit', read_only=True)
    
    class Meta:
        model = ProductAttributeValue
        fields = [
            'id', 'product', 'attribute', 'attribute_name', 'attribute_type',
            'attribute_unit', 'value', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductImageSerializer(serializers.ModelSerializer):
    """Product image serializer"""
    
    class Meta:
        model = ProductImage
        fields = [
            'id', 'product', 'image', 'alt_text', 'is_primary', 'sort_order',
            'width', 'height', 'file_size', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'width', 'height', 'file_size', 'created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    """Product list serializer for catalog views"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    can_purchase = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'short_description', 'price', 'compare_price',
            'category', 'category_name', 'primary_image', 'is_active', 'is_featured',
            'is_digital', 'stock', 'is_on_sale', 'discount_percentage',
            'is_low_stock', 'is_out_of_stock', 'can_purchase', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed product serializer"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    attribute_values = ProductAttributeValueSerializer(many=True, read_only=True)
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    can_purchase = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'store', 'category', 'category_name', 'title', 'slug',
            'description', 'short_description', 'price', 'compare_price', 'cost_price',
            'sku', 'barcode', 'stock', 'low_stock_threshold', 'track_inventory',
            'allow_backorders', 'weight', 'length', 'width', 'height',
            'is_active', 'is_featured', 'is_digital', 'requires_shipping',
            'meta_title', 'meta_description', 'focus_keyword', 'published_at',
            'images', 'attribute_values', 'is_on_sale', 'discount_percentage',
            'is_low_stock', 'is_out_of_stock', 'can_purchase',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'is_on_sale', 'discount_percentage', 'is_low_stock',
            'is_out_of_stock', 'can_purchase', 'created_at', 'updated_at'
        ]

    def validate_category(self, value):
        if value and value.store != self.context.get('store'):
            raise serializers.ValidationError("دسته‌بندی باید متعلق به همین فروشگاه باشد")
        return value

    def validate_sku(self, value):
        if value:
            store = self.context.get('store')
            queryset = Product.objects.filter(store=store, sku=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("این کد محصول قبلاً در فروشگاه شما استفاده شده است")
        return value


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Product serializer for create/update operations"""
    attribute_values = ProductAttributeValueSerializer(many=True, required=False)
    
    class Meta:
        model = Product
        fields = [
            'id', 'category', 'title', 'description', 'short_description',
            'price', 'compare_price', 'cost_price', 'sku', 'barcode',
            'stock', 'low_stock_threshold', 'track_inventory', 'allow_backorders',
            'weight', 'length', 'width', 'height', 'is_active', 'is_featured',
            'is_digital', 'requires_shipping', 'meta_title', 'meta_description',
            'focus_keyword', 'attribute_values'
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        attribute_values_data = validated_data.pop('attribute_values', [])
        validated_data['store'] = self.context['store']
        product = Product.objects.create(**validated_data)
        
        # Create attribute values
        for attr_value_data in attribute_values_data:
            attr_value_data['product'] = product
            ProductAttributeValue.objects.create(**attr_value_data)
        
        return product

    def update(self, instance, validated_data):
        attribute_values_data = validated_data.pop('attribute_values', [])
        product = super().update(instance, validated_data)
        
        # Update attribute values
        if attribute_values_data:
            # Remove existing values
            product.attribute_values.all().delete()
            # Create new values
            for attr_value_data in attribute_values_data:
                attr_value_data['product'] = product
                ProductAttributeValue.objects.create(**attr_value_data)
        
        return product


class BulkImportLogSerializer(serializers.ModelSerializer):
    """Bulk import log serializer"""
    user = UserSerializer(read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    duration_seconds = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = BulkImportLog
        fields = [
            'id', 'store', 'store_name', 'user', 'filename', 'file_size',
            'status', 'total_rows', 'processed_rows', 'successful_rows', 'failed_rows',
            'categories_created', 'categories_updated', 'products_created',
            'products_updated', 'attributes_created', 'error_details', 'warning_details',
            'duration_seconds', 'success_rate', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'


class StoreStatsSerializer(serializers.Serializer):
    """Store statistics serializer"""
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    featured_products = serializers.IntegerField()
    out_of_stock_products = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    total_categories = serializers.IntegerField()
    active_categories = serializers.IntegerField()
    total_attributes = serializers.IntegerField()
    recent_imports = serializers.IntegerField()


class CategoryImportSerializer(serializers.Serializer):
    """Category import data serializer"""
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    parent_path = serializers.CharField(required=False, allow_blank=True, help_text="مسیر کامل دسته‌بندی والد با جداکننده >")
    image_url = serializers.URLField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    sort_order = serializers.IntegerField(default=0)


class ProductImportSerializer(serializers.Serializer):
    """Product import data serializer"""
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    short_description = serializers.CharField(required=False, allow_blank=True, max_length=500)
    category_path = serializers.CharField(required=False, allow_blank=True, help_text="مسیر کامل دسته‌بندی با جداکننده >")
    price = serializers.DecimalField(max_digits=12, decimal_places=0)
    compare_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False, allow_null=True)
    sku = serializers.CharField(required=False, allow_blank=True, max_length=100)
    barcode = serializers.CharField(required=False, allow_blank=True, max_length=100)
    stock = serializers.IntegerField(default=0)
    weight = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    is_featured = serializers.BooleanField(default=False)
    is_digital = serializers.BooleanField(default=False)
    # Dynamic attribute fields will be added during processing


class BulkImportPreviewSerializer(serializers.Serializer):
    """Bulk import preview serializer"""
    file = serializers.FileField()
    has_header = serializers.BooleanField(default=True)
    delimiter = serializers.CharField(default=',', max_length=1)


class BulkImportExecuteSerializer(serializers.Serializer):
    """Bulk import execution serializer"""
    file = serializers.FileField()
    has_header = serializers.BooleanField(default=True)
    delimiter = serializers.CharField(default=',', max_length=1)
    update_existing = serializers.BooleanField(default=True, help_text="آپدیت محصولات موجود")
    create_categories = serializers.BooleanField(default=True, help_text="ایجاد دسته‌بندی‌های جدید")
    create_attributes = serializers.BooleanField(default=True, help_text="ایجاد ویژگی‌های جدید")
