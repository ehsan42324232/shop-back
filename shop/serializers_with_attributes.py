"""
Serializers for product attributes system
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models_with_attributes import (
    Store, Product, Category, ProductImage, 
    ProductAttribute, ProductAttributeValue, BulkImportLog
)
from .storefront_models import Basket, Order, OrderItem, CustomerAddress


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Product attribute definition"""
    
    class Meta:
        model = ProductAttribute
        fields = ['id', 'name', 'attribute_type', 'is_required', 'is_filterable',
                 'is_searchable', 'choices', 'unit', 'sort_order', 'store']
        read_only_fields = ['id']
    
    def validate_choices(self, value):
        """Validate choices for choice type attributes"""
        if self.instance:
            attribute_type = self.instance.attribute_type
        else:
            attribute_type = self.initial_data.get('attribute_type')
        
        if attribute_type == 'choice' and not value:
            raise serializers.ValidationError(
                "Choices are required for choice type attributes"
            )
        return value


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Product attribute value"""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    attribute_unit = serializers.CharField(source='attribute.unit', read_only=True)
    
    class Meta:
        model = ProductAttributeValue
        fields = ['id', 'attribute', 'attribute_name', 'attribute_type', 
                 'attribute_unit', 'value']
        read_only_fields = ['id']


class ProductWithAttributesSerializer(serializers.ModelSerializer):
    """Product with attributes"""
    category = serializers.StringRelatedField(read_only=True)
    store = serializers.StringRelatedField(read_only=True)
    attributes = ProductAttributeValueSerializer(many=True, read_only=True)
    images = serializers.StringRelatedField(many=True, read_only=True)
    main_image = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'title', 'slug', 'description', 'price', 'stock',
                 'sku', 'category', 'store', 'attributes', 'images',
                 'main_image', 'is_active', 'created_at']
        read_only_fields = ['id', 'slug', 'created_at']
    
    def get_main_image(self, obj):
        main_image = obj.images.first()
        if main_image:
            request = self.context.get('request')
            if request and main_image.image:
                return request.build_absolute_uri(main_image.image.url)
        return None


class ProductCreateWithAttributesSerializer(serializers.ModelSerializer):
    """Create product with attributes"""
    attributes = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Product
        fields = ['title', 'description', 'price', 'stock', 'sku',
                 'weight', 'dimensions', 'category', 'attributes']
    
    def create(self, validated_data):
        attributes_data = validated_data.pop('attributes', [])
        product = Product.objects.create(**validated_data)
        
        # Create attribute values
        for attr_data in attributes_data:
            ProductAttributeValue.objects.create(
                product=product,
                attribute_id=attr_data['attribute_id'],
                value=attr_data['value']
            )
        
        return product
    
    def update(self, instance, validated_data):
        attributes_data = validated_data.pop('attributes', [])
        
        # Update product
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update attributes
        if attributes_data:
            # Clear existing attribute values
            instance.attribute_values.all().delete()
            
            # Create new attribute values
            for attr_data in attributes_data:
                ProductAttributeValue.objects.create(
                    product=instance,
                    attribute_id=attr_data['attribute_id'],
                    value=attr_data['value']
                )
        
        return instance


class BulkImportLogSerializer(serializers.ModelSerializer):
    """Bulk import log"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = BulkImportLog
        fields = ['id', 'filename', 'store', 'store_name', 'uploaded_by',
                 'uploaded_by_name', 'status', 'total_rows', 'successful_rows',
                 'failed_rows', 'products_created', 'products_updated',
                 'error_details', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class CategoryWithAttributesSerializer(serializers.ModelSerializer):
    """Category with available attributes"""
    attributes = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent',
                 'sort_order', 'is_active', 'attributes', 'product_count']
    
    def get_attributes(self, obj):
        """Get all attributes available for this category's store"""
        store_attributes = ProductAttribute.objects.filter(store=obj.store)
        return ProductAttributeSerializer(store_attributes, many=True).data
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class StoreWithAttributesSerializer(serializers.ModelSerializer):
    """Store with its attributes"""
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    total_products = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'domain', 'description', 'logo',
                 'is_approved', 'attributes', 'total_products', 'settings']
    
    def get_total_products(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductFilterSerializer(serializers.Serializer):
    """Product filtering options"""
    category = serializers.CharField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    in_stock = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False)
    
    # Dynamic attribute filters
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add dynamic attribute fields
        store_id = self.context.get('store_id')
        if store_id:
            attributes = ProductAttribute.objects.filter(
                store_id=store_id,
                is_filterable=True
            )
            
            for attr in attributes:
                field_name = f"attr_{attr.id}"
                if attr.attribute_type == 'choice':
                    self.fields[field_name] = serializers.ChoiceField(
                        choices=[(choice, choice) for choice in attr.choices],
                        required=False
                    )
                elif attr.attribute_type == 'number':
                    self.fields[f"{field_name}_min"] = serializers.FloatField(required=False)
                    self.fields[f"{field_name}_max"] = serializers.FloatField(required=False)
                elif attr.attribute_type == 'boolean':
                    self.fields[field_name] = serializers.BooleanField(required=False)
                else:
                    self.fields[field_name] = serializers.CharField(required=False)


class AttributeValueStatsSerializer(serializers.Serializer):
    """Attribute value statistics for filtering"""
    attribute_id = serializers.IntegerField()
    attribute_name = serializers.CharField()
    values = serializers.ListField(child=serializers.DictField())


class ProductSearchResultSerializer(serializers.ModelSerializer):
    """Search result with highlighting"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    main_image = serializers.SerializerMethodField()
    attributes = ProductAttributeValueSerializer(many=True, read_only=True)
    match_score = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'title', 'slug', 'price', 'stock', 'category_name',
                 'main_image', 'attributes', 'match_score', 'is_active']
    
    def get_main_image(self, obj):
        main_image = obj.images.first()
        if main_image:
            request = self.context.get('request')
            if request and main_image.image:
                return request.build_absolute_uri(main_image.image.url)
        return None
