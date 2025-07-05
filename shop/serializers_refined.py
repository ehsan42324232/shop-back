from rest_framework import serializers
from django.contrib.auth.models import User
from .models_refined import (
    Store, Category, Product, ProductImage, Comment, 
    Rating, Basket, Order, OrderItem
)


class UserSerializer(serializers.ModelSerializer):
    """User serializer for authentication"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class StoreSerializer(serializers.ModelSerializer):
    """Store serializer"""
    owner = UserSerializer(read_only=True)
    
    class Meta:
        model = Store
        fields = [
            'id', 'owner', 'name', 'slug', 'description', 'domain', 
            'logo', 'is_active', 'currency', 'tax_rate', 'email', 
            'phone', 'address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'slug', 'created_at', 'updated_at']


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer with children support"""
    children = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'store', 'name', 'slug', 'description', 'parent',
            'image', 'is_active', 'sort_order', 'children', 'product_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'children', 'product_count', 'created_at', 'updated_at']
    
    def get_children(self, obj):
        if hasattr(obj, 'children'):
            return CategorySerializer(obj.children.filter(is_active=True), many=True).data
        return []
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductImageSerializer(serializers.ModelSerializer):
    """Product image serializer"""
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'sort_order', 'created_at']
        read_only_fields = ['id', 'created_at']


class RatingSerializer(serializers.ModelSerializer):
    """Rating serializer"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Rating
        fields = ['id', 'user', 'score', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class CommentSerializer(serializers.ModelSerializer):
    """Comment serializer"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = [
            'id', 'user', 'title', 'text', 'is_verified_purchase',
            'is_approved', 'helpful_count', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'is_verified_purchase', 'helpful_count', 'created_at']


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight product serializer for list views"""
    store = serializers.StringRelatedField()
    category = serializers.StringRelatedField()
    primary_image = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'store', 'category', 'title', 'slug', 'short_description',
            'price', 'compare_price', 'is_on_sale', 'discount_percentage',
            'primary_image', 'average_rating', 'rating_count', 'is_featured',
            'is_out_of_stock', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            return ProductImageSerializer(primary_image).data
        first_image = obj.images.first()
        if first_image:
            return ProductImageSerializer(first_image).data
        return None
    
    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings:
            return round(sum(r.score for r in ratings) / len(ratings), 1)
        return 0
    
    def get_rating_count(self, obj):
        return obj.ratings.count()


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed product serializer"""
    store = StoreSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'store', 'category', 'title', 'slug', 'description',
            'short_description', 'price', 'compare_price', 'cost_price',
            'sku', 'barcode', 'stock', 'low_stock_threshold', 'track_inventory',
            'weight', 'dimensions', 'is_active', 'is_featured', 'is_digital',
            'meta_title', 'meta_description', 'published_at', 'images',
            'comments', 'average_rating', 'rating_count', 'is_on_sale',
            'discount_percentage', 'is_low_stock', 'is_out_of_stock',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'is_on_sale', 'discount_percentage',
            'is_low_stock', 'is_out_of_stock', 'created_at', 'updated_at'
        ]
    
    def get_comments(self, obj):
        approved_comments = obj.comments.filter(is_approved=True).order_by('-created_at')[:10]
        return CommentSerializer(approved_comments, many=True).data
    
    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings:
            return round(sum(r.score for r in ratings) / len(ratings), 1)
        return 0
    
    def get_rating_count(self, obj):
        return obj.ratings.count()


class BasketItemSerializer(serializers.ModelSerializer):
    """Basket item serializer"""
    product = ProductListSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Basket
        fields = [
            'id', 'product', 'product_id', 'quantity', 
            'price_at_add', 'total_price', 'created_at'
        ]
        read_only_fields = ['id', 'price_at_add', 'total_price', 'created_at']
    
    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        try:
            product = Product.objects.get(id=product_id, is_active=True)
            validated_data['product'] = product
            validated_data['user'] = self.context['request'].user
            return super().create(validated_data)
        except Product.DoesNotExist:
            raise serializers.ValidationError('Product not found or inactive')


class OrderItemSerializer(serializers.ModelSerializer):
    """Order item serializer"""
    product = ProductListSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'quantity', 'price_at_order',
            'total_price', 'product_title', 'product_sku'
        ]
        read_only_fields = ['id', 'total_price', 'product_title', 'product_sku']


class OrderSerializer(serializers.ModelSerializer):
    """Order serializer"""
    user = UserSerializer(read_only=True)
    store = StoreSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'store', 'status',
            'total_amount', 'tax_amount', 'shipping_amount', 'discount_amount',
            'is_paid', 'payment_method', 'payment_id', 'shipping_address',
            'billing_address', 'tracking_number', 'confirmed_at',
            'shipped_at', 'delivered_at', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'user', 'confirmed_at',
            'shipped_at', 'delivered_at', 'created_at', 'updated_at'
        ]


class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating orders"""
    shipping_address = serializers.JSONField()
    billing_address = serializers.JSONField(required=False)
    payment_method = serializers.CharField(max_length=50)
    
    def validate_shipping_address(self, value):
        required_fields = ['name', 'address_line_1', 'city', 'postal_code', 'country']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f'{field} is required in shipping address')
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Get user's basket items
        basket_items = Basket.objects.filter(user=user).select_related('product', 'product__store')
        
        if not basket_items:
            raise serializers.ValidationError('No items in basket')
        
        # Group items by store
        stores_orders = {}
        for item in basket_items:
            store_id = item.product.store.id
            if store_id not in stores_orders:
                stores_orders[store_id] = {
                    'store': item.product.store,
                    'items': []
                }
            stores_orders[store_id]['items'].append(item)
        
        # Create separate orders for each store
        orders = []
        for store_data in stores_orders.values():
            total_amount = sum(item.total_price for item in store_data['items'])
            
            order = Order.objects.create(
                user=user,
                store=store_data['store'],
                total_amount=total_amount,
                shipping_address=validated_data['shipping_address'],
                billing_address=validated_data.get('billing_address', validated_data['shipping_address']),
                payment_method=validated_data['payment_method']
            )
            
            # Create order items
            for basket_item in store_data['items']:
                OrderItem.objects.create(
                    order=order,
                    product=basket_item.product,
                    quantity=basket_item.quantity,
                    price_at_order=basket_item.price_at_add
                )
            
            orders.append(order)
        
        # Clear basket
        basket_items.delete()
        
        return orders


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration serializer"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Password change serializer"""
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value
