# shop/serializers.py - Core API Serializers
"""
API Serializers for the Mall Platform
Handles all API input/output serialization according to product description
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import *


class MallUserSerializer(serializers.ModelSerializer):
    """Serializer for Mall users (store owners and customers)"""
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = MallUser
        fields = ['id', 'username', 'email', 'phone', 'user_type', 
                 'first_name', 'last_name', 'first_name_persian', 'last_name_persian',
                 'profile_image', 'is_phone_verified', 'password']
        extra_kwargs = {'password': {'write_only': True}}
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = MallUser.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class StoreSerializer(serializers.ModelSerializer):
    """Store serializer for store management"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'name_english', 'slug', 'description', 'domain',
                 'custom_domain', 'logo', 'banner', 'theme', 'email', 'phone', 
                 'address', 'is_active', 'is_verified', 'owner_name', 'product_count',
                 'created_at', 'updated_at']
        read_only_fields = ['slug', 'owner_name', 'product_count']
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductClassSerializer(serializers.ModelSerializer):
    """Hierarchical product class serializer"""
    children = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()
    can_have_products = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductClass
        fields = ['id', 'name', 'name_english', 'slug', 'parent', 'level',
                 'description', 'image', 'is_active', 'sort_order',
                 'children', 'full_path', 'can_have_products', 'created_at']
        read_only_fields = ['level', 'slug']
    
    def get_children(self, obj):
        if obj.children.exists():
            return ProductClassSerializer(obj.children.filter(is_active=True), many=True).data
        return []
    
    def get_full_path(self, obj):
        path = [obj.name]
        parent = obj.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(path)
    
    def get_can_have_products(self, obj):
        return obj.is_leaf()


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Product attribute serializer"""
    
    class Meta:
        model = ProductAttribute
        fields = ['id', 'name', 'name_english', 'attribute_type', 'is_required',
                 'is_categorizer', 'is_filterable', 'choices', 'sort_order', 'is_active']


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """Product attribute value serializer"""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    
    class Meta:
        model = ProductAttributeValue
        fields = ['id', 'attribute', 'attribute_name', 'attribute_type', 'value']


class ProductMediaSerializer(serializers.ModelSerializer):
    """Product media (images/videos) serializer"""
    
    class Meta:
        model = ProductMedia
        fields = ['id', 'media_type', 'file', 'title', 'alt_text', 'sort_order',
                 'social_source', 'social_url', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    """Product serializer with all details"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    product_class_name = serializers.CharField(source='product_class.name', read_only=True)
    attribute_values = ProductAttributeValueSerializer(many=True, read_only=True)
    media = ProductMediaSerializer(many=True, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'price', 'compare_price',
                 'sku', 'stock_quantity', 'featured_image', 'meta_title', 'meta_description',
                 'is_active', 'is_featured', 'view_count', 'sales_count', 
                 'average_rating', 'review_count', 'store_name', 'product_class_name',
                 'attribute_values', 'media', 'is_in_stock', 'is_low_stock',
                 'created_at', 'updated_at']
        read_only_fields = ['slug', 'sku', 'view_count', 'sales_count', 
                           'average_rating', 'review_count']


class ProductCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for product creation"""
    attribute_values = serializers.JSONField(write_only=True, required=False)
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'compare_price', 'product_class',
                 'stock_quantity', 'featured_image', 'is_active', 'is_featured',
                 'attribute_values']
    
    def create(self, validated_data):
        attribute_values = validated_data.pop('attribute_values', {})
        store = self.context['request'].user.store
        product = Product.objects.create(store=store, **validated_data)
        
        # Create attribute values
        for attr_id, value in attribute_values.items():
            ProductAttributeValue.objects.create(
                product=product,
                attribute_id=attr_id,
                value=value
            )
        
        return product


class CartItemSerializer(serializers.ModelSerializer):
    """Cart item serializer"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=0, read_only=True)
    product_image = serializers.ImageField(source='product.featured_image', read_only=True)
    total = serializers.DecimalField(source='get_total', max_digits=10, decimal_places=0, read_only=True)
    
    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_name', 'product_price', 'product_image',
                 'quantity', 'total', 'created_at']


class CartSerializer(serializers.ModelSerializer):
    """Shopping cart serializer"""
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(source='get_total', max_digits=10, decimal_places=0, read_only=True)
    item_count = serializers.IntegerField(source='get_item_count', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    
    class Meta:
        model = Cart
        fields = ['id', 'store', 'store_name', 'items', 'total', 'item_count',
                 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    """Order item serializer"""
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_sku', 'quantity',
                 'unit_price', 'total_price']


class OrderSerializer(serializers.ModelSerializer):
    """Order serializer"""
    items = OrderItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'store', 'store_name', 'customer', 'customer_username',
                 'status', 'payment_status', 'subtotal', 'tax_amount', 'shipping_amount',
                 'total_amount', 'customer_name', 'customer_phone', 'customer_email',
                 'shipping_address', 'shipping_city', 'shipping_postal_code',
                 'customer_notes', 'admin_notes', 'items', 'created_at', 'updated_at']
        read_only_fields = ['order_number']


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders"""
    cart_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Order
        fields = ['customer_name', 'customer_phone', 'customer_email',
                 'shipping_address', 'shipping_city', 'shipping_postal_code',
                 'customer_notes', 'cart_id']
    
    def create(self, validated_data):
        cart_id = validated_data.pop('cart_id')
        cart = Cart.objects.get(id=cart_id, user=self.context['request'].user)
        
        # Calculate totals
        subtotal = cart.get_total()
        tax_amount = 0  # Implement tax calculation
        shipping_amount = 0  # Implement shipping calculation
        total_amount = subtotal + tax_amount + shipping_amount
        
        order = Order.objects.create(
            store=cart.store,
            customer=self.context['request'].user,
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_amount=shipping_amount,
            total_amount=total_amount,
            **validated_data
        )
        
        # Create order items from cart
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.price,
                total_price=cart_item.get_total()
            )
        
        # Clear cart
        cart.items.all().delete()
        
        return order


# OTP Authentication Serializers
class OTPRequestSerializer(serializers.Serializer):
    """OTP request serializer"""
    phone = serializers.CharField(max_length=15)
    user_type = serializers.ChoiceField(choices=MallUser.USER_TYPES, default='customer')


class OTPVerifySerializer(serializers.Serializer):
    """OTP verification serializer"""
    phone = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)
    user_type = serializers.ChoiceField(choices=MallUser.USER_TYPES, default='customer')


# Social Media Integration Serializers
class SocialMediaPostSerializer(serializers.Serializer):
    """Social media post data serializer"""
    platform = serializers.ChoiceField(choices=[('instagram', 'Instagram'), ('telegram', 'Telegram')])
    post_id = serializers.CharField()
    caption = serializers.CharField(allow_blank=True)
    media_urls = serializers.ListField(child=serializers.URLField())
    media_type = serializers.ChoiceField(choices=[('image', 'Image'), ('video', 'Video')])
    post_url = serializers.URLField()
    created_at = serializers.DateTimeField()


class SocialContentSelectionSerializer(serializers.Serializer):
    """Serializer for selecting social media content for products"""
    product_id = serializers.UUIDField()
    selected_posts = serializers.ListField(child=serializers.CharField())
    extract_text = serializers.BooleanField(default=True)
    extract_media = serializers.BooleanField(default=True)


# Analytics Serializers
class StoreAnalyticsSerializer(serializers.Serializer):
    """Store analytics data serializer"""
    total_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=0)
    total_customers = serializers.IntegerField()
    monthly_revenue = serializers.ListField()
    top_products = serializers.ListField()
    recent_orders = OrderSerializer(many=True)


class ProductListSerializer(serializers.ModelSerializer):
    """Simplified product serializer for lists"""
    store_name = serializers.CharField(source='store.name', read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'price', 'featured_image', 'store_name',
                 'is_featured', 'average_rating', 'review_count', 'is_in_stock',
                 'is_low_stock']


# Search and Filter Serializers
class ProductSearchSerializer(serializers.Serializer):
    """Product search parameters"""
    q = serializers.CharField(required=False, allow_blank=True)
    category = serializers.IntegerField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=0, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=0, required=False)
    sort_by = serializers.ChoiceField(
        choices=[
            ('recent', 'Recent'),
            ('price_low', 'Price: Low to High'),
            ('price_high', 'Price: High to Low'),
            ('most_viewed', 'Most Viewed'),
            ('bestselling', 'Best Selling'),
            ('rating', 'Highest Rated')
        ],
        default='recent'
    )
    store = serializers.CharField(required=False)


# Example Product Creation (تیشرت یقه گرد نخی)
class ExampleProductSerializer(serializers.Serializer):
    """Example serializer for creating the product mentioned in description"""
    
    def create_example_product(self, store):
        """Create the example product: تیشرت یقه گرد نخی"""
        
        # Get or create product class hierarchy
        clothing, created = ProductClass.objects.get_or_create(
            name='پوشاک',
            defaults={'name_english': 'Clothing', 'description': 'انواع لباس و پوشاک'}
        )
        
        tshirts, created = ProductClass.objects.get_or_create(
            name='تیشرت',
            parent=clothing,
            defaults={'name_english': 'T-Shirts', 'description': 'انواع تیشرت'}
        )
        
        cotton_tshirts, created = ProductClass.objects.get_or_create(
            name='تیشرت یقه گرد نخی',
            parent=tshirts,
            defaults={
                'name_english': 'Round Neck Cotton T-Shirts',
                'description': 'تیشرت های یقه گرد نخی با کیفیت بالا'
            }
        )
        
        # Create the example product
        product = Product.objects.create(
            store=store,
            product_class=cotton_tshirts,
            name='تیشرت یقه گرد نخی',
            description='ترکی اصل',  # Original Turkish as mentioned
            price=50000,  # Example price
            stock_quantity=10
        )
        
        # Add color and size attributes
        from .models import create_predefined_attributes
        color_attr, desc_attr, sex_attr, size_attr = create_predefined_attributes()
        
        # Add color values (red, yellow as mentioned)
        ProductAttributeValue.objects.create(
            product=product,
            attribute=color_attr,
            value='red'
        )
        
        # Add size values (XL, XXL as mentioned)
        ProductAttributeValue.objects.create(
            product=product,
            attribute=size_attr,
            value='xl'
        )
        
        return product
