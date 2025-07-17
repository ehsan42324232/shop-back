from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models_with_attributes import (
    Store, Category, Product, ProductAttribute, ProductAttributeValue,
    ProductImage, Comment, Rating, Basket, Order, OrderItem, BulkImportLog
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value


class StoreSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    product_count = serializers.SerializerMethodField()
    category_count = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            'id', 'owner', 'name', 'slug', 'description', 'domain', 'logo',
            'is_active', 'currency', 'tax_rate', 'email', 'phone', 'address',
            'created_at', 'updated_at', 'product_count', 'category_count'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

    def get_category_count(self, obj):
        return obj.categories.filter(is_active=True).count()


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    full_path = serializers.CharField(source='get_full_path', read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'store', 'name', 'slug', 'description', 'parent', 'parent_name',
            'full_path', 'image', 'is_active', 'sort_order', 'children',
            'product_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_children(self, obj):
        if hasattr(obj, 'children'):
            return CategorySerializer(obj.children.filter(is_active=True), many=True).data
        return []

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = [
            'id', 'store', 'name', 'slug', 'attribute_type', 'is_required',
            'is_filterable', 'is_searchable', 'choices', 'unit', 'sort_order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_choices(self, value):
        if self.instance:
            attribute_type = self.instance.attribute_type
        else:
            attribute_type = self.initial_data.get('attribute_type')
        
        if attribute_type == 'choice' and not value:
            raise serializers.ValidationError("Choices are required for choice type attributes")
        return value


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_type = serializers.CharField(source='attribute.attribute_type', read_only=True)
    attribute_choices = serializers.ListField(source='attribute.choices', read_only=True)
    attribute_unit = serializers.CharField(source='attribute.unit', read_only=True)

    class Meta:
        model = ProductAttributeValue
        fields = [
            'id', 'attribute', 'attribute_name', 'attribute_type', 
            'attribute_choices', 'attribute_unit', 'value', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_value(self, value):
        attribute = self.initial_data.get('attribute')
        if attribute:
            try:
                attr_obj = ProductAttribute.objects.get(id=attribute)
                if attr_obj.attribute_type == 'choice' and value not in attr_obj.choices:
                    raise serializers.ValidationError(f"Value must be one of: {', '.join(attr_obj.choices)}")
                elif attr_obj.attribute_type == 'boolean' and value.lower() not in ['true', 'false', '1', '0']:
                    raise serializers.ValidationError("Value must be true/false or 1/0")
                elif attr_obj.attribute_type == 'number':
                    try:
                        float(value)
                    except ValueError:
                        raise serializers.ValidationError("Value must be a valid number")
            except ProductAttribute.DoesNotExist:
                pass
        return value


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'sort_order', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductListSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    attributes = ProductAttributeValueSerializer(source='attribute_values', many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'store', 'store_name', 'category', 'category_name', 'title', 'slug',
            'short_description', 'price', 'compare_price', 'sku', 'stock',
            'is_active', 'is_featured', 'is_digital', 'is_on_sale', 'discount_percentage',
            'is_low_stock', 'is_out_of_stock', 'primary_image', 'average_rating',
            'attributes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_primary_image(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            return ProductImageSerializer(primary_image).data
        return None

    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings:
            return sum(r.score for r in ratings) / len(ratings)
        return 0


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    ratings_distribution = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            'description', 'weight', 'dimensions', 'barcode', 'low_stock_threshold',
            'track_inventory', 'meta_title', 'meta_description', 'published_at',
            'images', 'comments', 'ratings_distribution'
        ]

    def get_comments(self, obj):
        approved_comments = obj.comments.filter(is_approved=True)
        return CommentSerializer(approved_comments, many=True).data

    def get_ratings_distribution(self, obj):
        ratings = obj.ratings.all()
        distribution = {i: 0 for i in range(1, 6)}
        for rating in ratings:
            distribution[rating.score] += 1
        return distribution


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'user', 'title', 'text', 'is_verified_purchase',
            'is_approved', 'helpful_count', 'rating', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'is_approved', 'helpful_count', 'created_at', 'updated_at']

    def get_rating(self, obj):
        if hasattr(obj, 'rating_set') and obj.rating_set.exists():
            return obj.rating_set.first().score
        return None


class RatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = ['id', 'user', 'score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class BasketItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Basket
        fields = ['id', 'product', 'product_id', 'quantity', 'price_at_add', 'total_price', 'created_at', 'updated_at']
        read_only_fields = ['id', 'price_at_add', 'total_price', 'created_at', 'updated_at']

    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        product = Product.objects.get(id=product_id)
        validated_data['product'] = product
        validated_data['price_at_add'] = product.price
        return super().create(validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'quantity', 'price_at_order', 'total_price',
            'product_title', 'product_sku', 'created_at'
        ]
        read_only_fields = ['id', 'total_price', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    store = StoreSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'store', 'status', 'total_amount',
            'tax_amount', 'shipping_amount', 'discount_amount', 'is_paid',
            'payment_method', 'payment_id', 'shipping_address', 'billing_address',
            'tracking_number', 'items', 'created_at', 'updated_at', 'confirmed_at',
            'shipped_at', 'delivered_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at', 'updated_at']


class CreateOrderSerializer(serializers.Serializer):
    store_id = serializers.UUIDField()
    shipping_address = serializers.JSONField()
    billing_address = serializers.JSONField(required=False)
    payment_method = serializers.CharField(max_length=50)

    def validate_store_id(self, value):
        try:
            Store.objects.get(id=value, is_active=True)
        except Store.DoesNotExist:
            raise serializers.ValidationError("Store not found")
        return value

    def create(self, validated_data):
        from django.db import transaction
        
        user = self.context['request'].user
        store_id = validated_data['store_id']
        
        # Get basket items for this store
        basket_items = Basket.objects.filter(
            user=user,
            product__store_id=store_id
        ).select_related('product')
        
        if not basket_items.exists():
            raise serializers.ValidationError("No items in basket for this store")
        
        orders = []
        
        with transaction.atomic():
            # Group basket items by store (in case of multiple stores)
            store_items = {}
            for item in basket_items:
                store_id = item.product.store_id
                if store_id not in store_items:
                    store_items[store_id] = []
                store_items[store_id].append(item)
            
            # Create order for each store
            for store_id, items in store_items.items():
                store = Store.objects.get(id=store_id)
                
                # Calculate totals
                subtotal = sum(item.total_price for item in items)
                tax_amount = subtotal * store.tax_rate
                total_amount = subtotal + tax_amount
                
                # Create order
                order = Order.objects.create(
                    user=user,
                    store=store,
                    total_amount=total_amount,
                    tax_amount=tax_amount,
                    shipping_address=validated_data['shipping_address'],
                    billing_address=validated_data.get('billing_address', validated_data['shipping_address']),
                    payment_method=validated_data['payment_method']
                )
                
                # Create order items
                for basket_item in items:
                    OrderItem.objects.create(
                        order=order,
                        product=basket_item.product,
                        quantity=basket_item.quantity,
                        price_at_order=basket_item.product.price,
                        product_title=basket_item.product.title,
                        product_sku=basket_item.product.sku
                    )
                    
                    # Update product stock
                    product = basket_item.product
                    if product.track_inventory:
                        product.stock -= basket_item.quantity
                        product.save()
                
                orders.append(order)
            
            # Clear basket
            basket_items.delete()
        
        return orders


class BulkImportLogSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = BulkImportLog
        fields = [
            'id', 'store', 'store_name', 'user', 'user_name', 'filename', 'status',
            'total_rows', 'successful_rows', 'failed_rows', 'categories_created',
            'products_created', 'products_updated', 'error_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BulkImportSerializer(serializers.Serializer):
    file = serializers.FileField()
    store_id = serializers.UUIDField()
    update_existing = serializers.BooleanField(default=True)
    create_categories = serializers.BooleanField(default=True)

    def validate_file(self, value):
        if not value.name.endswith(('.csv', '.xlsx', '.xls')):
            raise serializers.ValidationError("File must be CSV or Excel format")
        return value

    def validate_store_id(self, value):
        try:
            Store.objects.get(id=value, is_active=True)
        except Store.DoesNotExist:
            raise serializers.ValidationError("Store not found")
        return value
