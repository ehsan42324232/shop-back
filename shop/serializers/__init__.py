from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Store, Category, Product, ProductImage, Comment, Rating
from ..storefront_models import Basket, Order, OrderItem, CustomerAddress, Wishlist


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class StoreSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'description', 'domain', 'created_at', 'owner', 'products_count']
        read_only_fields = ['id', 'created_at']
    
    def get_products_count(self, obj):
        return obj.products.count()


class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'store', 'products_count']
        read_only_fields = ['id']
    
    def get_products_count(self, obj):
        return obj.products.count()


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'sort_order']
        read_only_fields = ['id']


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'user', 'text', 'title', 'is_approved', 'created_at']
        read_only_fields = ['id', 'created_at']


class RatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Rating
        fields = ['id', 'user', 'score']
        read_only_fields = ['id']


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'price', 'stock', 'created_at', 
                 'category', 'images', 'average_rating', 'rating_count', 'is_featured']
        read_only_fields = ['id', 'created_at']
    
    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings:
            return sum(r.score for r in ratings) / len(ratings)
        return 0
    
    def get_rating_count(self, obj):
        return obj.ratings.count()


class ProductDetailSerializer(ProductListSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    ratings = RatingSerializer(many=True, read_only=True)
    
    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ['comments', 'ratings', 'short_description', 'meta_title', 'meta_description']


class ProductSerializer(serializers.ModelSerializer):
    """Basic product serializer for backward compatibility"""
    images = ProductImageSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'price', 'stock', 'category', 'images']


class BasketSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Basket
        fields = ['id', 'product', 'product_id', 'quantity', 'total_price']
        read_only_fields = ['id']
    
    def get_total_price(self, obj):
        return obj.total_price


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price_at_order', 'total_price', 'product_title']
        read_only_fields = ['id']
    
    def get_total_price(self, obj):
        return obj.total_price


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    store = StoreSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    final_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'user', 'store', 'created_at', 'status', 
                 'payment_status', 'total_amount', 'final_amount', 'items']
        read_only_fields = ['id', 'created_at', 'order_number']
    
    def get_final_amount(self, obj):
        return obj.final_amount


class CreateOrderSerializer(serializers.Serializer):
    store_id = serializers.UUIDField()
    
    def validate_store_id(self, value):
        try:
            Store.objects.get(id=value)
            return value
        except Store.DoesNotExist:
            raise serializers.ValidationError("Store does not exist")


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = ['id', 'title', 'recipient_name', 'phone', 'province', 'city', 
                 'address', 'postal_code', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'product_id', 'created_at']
        read_only_fields = ['id', 'created_at']
