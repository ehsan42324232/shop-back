from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Store, Category, Product, ProductAttribute, ProductAttributeValue,
    ProductImage, Comment, Rating, BulkImportLog
)
from .storefront_models import (
    Basket, Order, OrderItem, DeliveryZone, PaymentGateway,
    CustomerAddress, Wishlist
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active']
        read_only_fields = ['id']


class StoreSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    product_count = serializers.SerializerMethodField()
    category_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = [
            'id', 'name', 'name_en', 'slug', 'description', 'domain', 'logo',
            'is_active', 'is_approved', 'currency', 'tax_rate',
            'email', 'phone', 'address', 'owner', 'owner_name',
            'product_count', 'category_count', 'created_at', 'updated_at',
            'requested_at', 'approved_at'
        ]
        read_only_fields = ['id', 'slug', 'owner', 'created_at', 'updated_at', 'requested_at']

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

    def get_category_count(self, obj):
        return obj.categories.filter(is_active=True).count()


class StoreCreateSerializer(serializers.ModelSerializer):
    """Serializer for store creation requests"""
    
    class Meta:
        model = Store
        fields = [
            'name', 'name_en', 'description', 'domain', 'logo',
            'email', 'phone', 'address'
        ]

    def validate_domain(self, value):
        """Validate domain format and uniqueness"""
        import re
        
        # Basic domain validation
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, value):
            raise serializers.ValidationError("فرمت دامنه صحیح نیست")
        
        # Check uniqueness
        if Store.objects.filter(domain=value).exists():
            raise serializers.ValidationError("این دامنه قبلاً ثبت شده است")
        
        return value

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    full_path = serializers.CharField(source='get_full_path', read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 'image',
            'is_active', 'sort_order', 'children', 'full_path',
            'product_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('sort_order', 'name')
        return CategorySerializer(children, many=True, context=self.context).data

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = [
            'id', 'name', 'slug', 'attribute_type', 'is_required',
            'is_filterable', 'is_searchable', 'choices', 'unit',
            'sort_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    attribute_unit = serializers.CharField(source='attribute.unit', read_only=True)

    class Meta:
        model = ProductAttributeValue
        fields = [
            'id', 'attribute', 'attribute_name', 'attribute_type',
            'attribute_unit', 'value'
        ]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = [
            'id', 'image', 'alt_text', 'is_primary', 'sort_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for product list views"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    is_on_sale = serializers.BooleanField(read_only=True)
    discount_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'short_description', 'price',
            'compare_price', 'stock', 'category_name', 'primary_image',
            'is_active', 'is_featured', 'is_on_sale', 'discount_percentage',
            'created_at', 'updated_at'
        ]

    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer for product detail views"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_full_path = serializers.CharField(source='category.get_full_path', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    attribute_values = ProductAttributeValueSerializer(many=True, read_only=True)
    is_on_sale = serializers.BooleanField(read_only=True)
    discount_percentage = serializers.FloatField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'description', 'short_description',
            'price', 'compare_price', 'cost_price', 'sku', 'barcode',
            'stock', 'low_stock_threshold', 'track_inventory',
            'weight', 'dimensions', 'category', 'category_name',
            'category_full_path', 'is_active', 'is_featured', 'is_digital',
            'meta_title', 'meta_description', 'images', 'attribute_values',
            'is_on_sale', 'discount_percentage', 'is_low_stock',
            'is_out_of_stock', 'published_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'is_on_sale', 'discount_percentage',
            'is_low_stock', 'is_out_of_stock', 'created_at', 'updated_at'
        ]


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating products"""
    attribute_values = ProductAttributeValueSerializer(many=True, required=False)
    images = ProductImageSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'title', 'description', 'short_description', 'price',
            'compare_price', 'cost_price', 'sku', 'barcode', 'stock',
            'low_stock_threshold', 'track_inventory', 'weight',
            'dimensions', 'category', 'is_active', 'is_featured',
            'is_digital', 'meta_title', 'meta_description',
            'attribute_values', 'images'
        ]

    def create(self, validated_data):
        attribute_values_data = validated_data.pop('attribute_values', [])
        images_data = validated_data.pop('images', [])
        
        validated_data['store'] = self.context['store']
        product = Product.objects.create(**validated_data)
        
        # Create attribute values
        for attr_value_data in attribute_values_data:
            ProductAttributeValue.objects.create(product=product, **attr_value_data)
        
        # Create images
        for image_data in images_data:
            ProductImage.objects.create(product=product, **image_data)
        
        return product

    def update(self, instance, validated_data):
        attribute_values_data = validated_data.pop('attribute_values', [])
        images_data = validated_data.pop('images', [])
        
        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update attribute values
        if attribute_values_data:
            instance.attribute_values.all().delete()
            for attr_value_data in attribute_values_data:
                ProductAttributeValue.objects.create(product=instance, **attr_value_data)
        
        # Update images
        if images_data:
            instance.images.all().delete()
            for image_data in images_data:
                ProductImage.objects.create(product=instance, **image_data)
        
        return instance


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = Comment
        fields = [
            'id', 'user', 'user_name', 'title', 'text',
            'is_verified_purchase', 'is_approved', 'helpful_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'helpful_count', 'created_at', 'updated_at']


class RatingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = Rating
        fields = [
            'id', 'user', 'user_name', 'score', 'comment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class BulkImportLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = BulkImportLog
        fields = [
            'id', 'user', 'user_name', 'filename', 'status',
            'total_rows', 'successful_rows', 'failed_rows',
            'categories_created', 'products_created', 'products_updated',
            'error_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


# Storefront Serializers
class BasketSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = Basket
        fields = [
            'id', 'product', 'product_title', 'product_slug',
            'product_image', 'quantity', 'price_at_add',
            'total_price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'price_at_add', 'created_at', 'updated_at']

    def get_product_image(self, obj):
        primary_image = obj.product.images.filter(is_primary=True).first()
        if primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
        return None


class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_title', 'product_sku',
            'product_attributes', 'quantity', 'price_at_order',
            'total_price', 'created_at'
        ]


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for order list views"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    item_count = serializers.SerializerMethodField()
    final_amount = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'store_name', 'status', 'payment_status',
            'total_amount', 'tax_amount', 'shipping_amount', 'discount_amount',
            'final_amount', 'delivery_method', 'expected_delivery_date',
            'item_count', 'created_at', 'updated_at'
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Serializer for order detail views"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    final_amount = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'store', 'store_name', 'status',
            'payment_status', 'total_amount', 'tax_amount',
            'shipping_amount', 'discount_amount', 'final_amount',
            'payment_method', 'payment_id', 'payment_gateway',
            'delivery_method', 'expected_delivery_date', 'tracking_number',
            'shipping_address', 'billing_address', 'customer_name',
            'customer_phone', 'customer_email', 'customer_notes',
            'admin_notes', 'items', 'created_at', 'updated_at',
            'confirmed_at', 'shipped_at', 'delivered_at'
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders"""
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            'delivery_method', 'expected_delivery_date', 'shipping_address',
            'billing_address', 'customer_name', 'customer_phone',
            'customer_email', 'customer_notes', 'items'
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        validated_data['user'] = self.context['request'].user
        validated_data['store'] = self.context['store']
        
        # Calculate totals
        total_amount = sum(
            item_data['quantity'] * item_data['price_at_order']
            for item_data in items_data
        )
        validated_data['total_amount'] = total_amount
        
        order = Order.objects.create(**validated_data)
        
        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        
        return order


class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = [
            'id', 'name', 'description', 'standard_price', 'express_price',
            'same_day_price', 'standard_days', 'express_days',
            'same_day_available', 'free_delivery_threshold', 'is_active',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PaymentGatewaySerializer(serializers.ModelSerializer):
    gateway_display = serializers.CharField(source='get_gateway_type_display', read_only=True)

    class Meta:
        model = PaymentGateway
        fields = [
            'id', 'gateway_type', 'gateway_display', 'is_active',
            'settings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = [
            'id', 'title', 'recipient_name', 'phone', 'province',
            'city', 'address', 'postal_code', 'is_default', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        
        # If this is set as default, remove default from other addresses
        if validated_data.get('is_default'):
            CustomerAddress.objects.filter(
                user=validated_data['user'], 
                is_default=True
            ).update(is_default=False)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # If this is set as default, remove default from other addresses
        if validated_data.get('is_default'):
            CustomerAddress.objects.filter(
                user=instance.user, 
                is_default=True
            ).exclude(id=instance.id).update(is_default=False)
        
        return super().update(instance, validated_data)


class WishlistSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=12, decimal_places=0, read_only=True)
    product_image = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = [
            'id', 'product', 'product_title', 'product_slug',
            'product_price', 'product_image', 'is_in_stock', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_product_image(self, obj):
        primary_image = obj.product.images.filter(is_primary=True).first()
        if primary_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
        return None

    def get_is_in_stock(self, obj):
        return not obj.product.is_out_of_stock

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


# CSV Import Serializer
class BulkImportSerializer(serializers.Serializer):
    """Serializer for handling CSV/Excel file uploads"""
    file = serializers.FileField()
    
    def validate_file(self, value):
        """Validate uploaded file"""
        import os
        
        # Check file extension
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ['.csv', '.xlsx', '.xls']:
            raise serializers.ValidationError("فقط فایل‌های CSV و Excel پشتیبانی می‌شوند")
        
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("حجم فایل نباید بیشتر از ۱۰ مگابایت باشد")
        
        return value
