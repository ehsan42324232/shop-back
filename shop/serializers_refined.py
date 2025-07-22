"""
Refined serializers with enhanced functionality for API responses
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Store, Product, Category, ProductImage
from .storefront_models import Basket, Order, OrderItem, CustomerAddress


class UserProfileSerializer(serializers.ModelSerializer):
    """Enhanced user profile serializer with additional fields"""
    full_name = serializers.SerializerMethodField()
    is_store_owner = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'full_name', 'is_store_owner', 'date_joined', 'is_active']
        read_only_fields = ['id', 'username', 'date_joined', 'is_active']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_is_store_owner(self, obj):
        return hasattr(obj, 'owned_stores') and obj.owned_stores.exists()


class StoreProfileSerializer(serializers.ModelSerializer):
    """Enhanced store profile with metrics and settings"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    total_products = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'domain', 'owner_name', 'description', 
                 'logo', 'created_at', 'is_approved', 'is_active',
                 'total_products', 'total_orders', 'settings']
        read_only_fields = ['id', 'created_at', 'is_approved']
    
    def get_total_products(self, obj):
        return obj.products.count()
    
    def get_total_orders(self, obj):
        return Order.objects.filter(items__product__store=obj).distinct().count()
    
    def get_is_active(self, obj):
        return obj.is_approved and obj.products.exists()


class ProductImageSerializer(serializers.ModelSerializer):
    """Product image with full URL"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'image_url', 'alt_text', 'sort_order']
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Hierarchical category serializer"""
    children = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'parent_name',
                 'sort_order', 'is_active', 'children', 'product_count']
    
    def get_children(self, obj):
        if obj.children.exists():
            return CategoryTreeSerializer(obj.children.all(), many=True, context=self.context).data
        return []
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductListSerializer(serializers.ModelSerializer):
    """Optimized product list serializer"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    main_image = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'title', 'slug', 'price', 'discounted_price', 
                 'stock', 'is_in_stock', 'category_name', 'store_name',
                 'main_image', 'created_at', 'is_active']
    
    def get_main_image(self, obj):
        main_image = obj.images.first()
        if main_image:
            return ProductImageSerializer(main_image, context=self.context).data
        return None
    
    def get_is_in_stock(self, obj):
        return obj.stock > 0
    
    def get_discounted_price(self, obj):
        # Add discount logic here if needed
        return obj.price


class ProductDetailSerializer(serializers.ModelSerializer):
    """Complete product details with all related data"""
    category = CategoryTreeSerializer(read_only=True)
    store = StoreProfileSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    related_products = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'title', 'slug', 'description', 'price', 'stock',
                 'sku', 'weight', 'dimensions', 'meta_title', 'meta_description',
                 'category', 'store', 'images', 'related_products',
                 'created_at', 'updated_at', 'is_active']
    
    def get_related_products(self, obj):
        related = Product.objects.filter(
            category=obj.category,
            store=obj.store,
            is_active=True
        ).exclude(id=obj.id)[:4]
        return ProductListSerializer(related, many=True, context=self.context).data


class BasketItemSerializer(serializers.ModelSerializer):
    """Shopping cart item with product details"""
    product = ProductListSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Basket
        fields = ['id', 'product', 'quantity', 'total_price', 'added_at']
    
    def get_total_price(self, obj):
        return obj.quantity * obj.product.price


class CustomerAddressSerializer(serializers.ModelSerializer):
    """Customer address with validation"""
    
    class Meta:
        model = CustomerAddress
        fields = ['id', 'title', 'first_name', 'last_name', 'phone',
                 'address_line_1', 'address_line_2', 'city', 'state',
                 'postal_code', 'country', 'is_default']


class OrderItemSerializer(serializers.ModelSerializer):
    """Order item with product snapshot"""
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_image = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_title', 'product_image',
                 'quantity', 'price', 'total_price']
    
    def get_product_image(self, obj):
        main_image = obj.product.images.first()
        if main_image:
            return ProductImageSerializer(main_image, context=self.context).data
        return None
    
    def get_total_price(self, obj):
        return obj.quantity * obj.price


class OrderSerializer(serializers.ModelSerializer):
    """Complete order details"""
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    delivery_address = CustomerAddressSerializer(read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer', 'customer_name',
                 'status', 'total_amount', 'delivery_address', 'items',
                 'created_at', 'updated_at', 'notes']
        read_only_fields = ['id', 'order_number', 'created_at', 'updated_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    """Order creation serializer"""
    items = serializers.ListField(child=serializers.DictField(), write_only=True)
    
    class Meta:
        model = Order
        fields = ['delivery_address', 'items', 'notes']
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        
        for item_data in items_data:
            OrderItem.objects.create(
                order=order,
                product_id=item_data['product_id'],
                quantity=item_data['quantity'],
                price=item_data['price']
            )
        
        return order


class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard statistics"""
    total_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_orders = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    recent_orders = OrderSerializer(many=True)
    top_products = ProductListSerializer(many=True)
