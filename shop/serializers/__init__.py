from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Store, Category, Product, Media, Comment, Rating, Basket, Order, OrderItem


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


class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = ['id', 'media_type', 'file']
        read_only_fields = ['id']


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'user', 'text', 'created_at']
        read_only_fields = ['id', 'created_at']


class RatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Rating
        fields = ['id', 'user', 'score']
        read_only_fields = ['id']


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    media = MediaSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'price', 'stock', 'created_at', 
                 'category', 'media', 'average_rating', 'rating_count']
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
        fields = ProductListSerializer.Meta.fields + ['comments', 'ratings']


class ProductSerializer(serializers.ModelSerializer):
    """Basic product serializer for backward compatibility"""
    media = MediaSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'price', 'stock', 'category', 'media']


class BasketSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Basket
        fields = ['id', 'product', 'product_id', 'quantity', 'total_price']
        read_only_fields = ['id']
    
    def get_total_price(self, obj):
        return obj.product.price * obj.quantity


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price_at_order']
        read_only_fields = ['id']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    store = StoreSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = ['id', 'user', 'store', 'created_at', 'is_paid', 'logistics_status', 
                 'items', 'total_amount']
        read_only_fields = ['id', 'created_at']
    
    def get_total_amount(self, obj):
        return sum(item.quantity * item.price_at_order for item in obj.items.all())


class CreateOrderSerializer(serializers.Serializer):
    store_id = serializers.IntegerField()
    
    def validate_store_id(self, value):
        try:
            Store.objects.get(id=value)
            return value
        except Store.DoesNotExist:
            raise serializers.ValidationError("Store does not exist")
