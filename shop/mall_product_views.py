from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Prefetch
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Store, Category, Product, ProductAttribute, ProductAttributeValue, ProductImage
from .serializers import (
    CategorySerializer, ProductSerializer, 
    ProductAttributeSerializer, ProductAttributeValueSerializer
)
import logging

logger = logging.getLogger(__name__)

class MallProductHierarchyViewSet(viewsets.ModelViewSet):
    """
    Mall Platform Product Hierarchy Management
    Supports the flexible tree structure with categorization by attributes
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user's store"""
        if hasattr(self.request.user, 'stores'):
            store = self.request.user.stores.first()
            if store:
                return Category.objects.filter(store=store).prefetch_related(
                    'children', 'products', 'attribute_definitions'
                )
        return Category.objects.none()
    
    def get_serializer_class(self):
        return CategorySerializer
    
    def get_user_store(self, user):
        """Get user's store"""
        return user.stores.first() if hasattr(user, 'stores') else None
    
    @action(detail=False, methods=['get'])
    def hierarchy(self, request):
        """Get complete category hierarchy as tree structure"""
        try:
            store = self.get_user_store(request.user)
            if not store:
                return Response({
                    'success': False,
                    'message': 'فروشگاه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get root categories (no parent) with full tree
            root_categories = Category.objects.filter(
                store=store, 
                parent=None
            ).prefetch_related(
                Prefetch('children', queryset=Category.objects.prefetch_related('children')),
                'attribute_definitions'
            ).order_by('sort_order', 'name')
            
            # Build hierarchical structure
            hierarchy_data = []
            for category in root_categories:
                hierarchy_data.append(self.build_category_tree(category))
            
            return Response({
                'success': True,
                'data': hierarchy_data
            })
            
        except Exception as e:
            logger.error(f"Error in hierarchy view: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت ساختار دسته‌بندی'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def build_category_tree(self, category):
        """Recursively build category tree with product counts"""
        children_data = []
        for child in category.children.all():
            children_data.append(self.build_category_tree(child))
        
        # Check if this is a leaf node (can have product instances)
        is_leaf = not category.children.exists()
        
        # Get categorizer attribute (the attribute marked for categorization)
        categorizer_attribute = category.attribute_definitions.filter(
            is_categorizer=True
        ).first()
        
        return {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'parent_id': category.parent_id,
            'level': self.get_category_level(category),
            'is_leaf': is_leaf,
            'is_active': category.is_active,
            'sort_order': category.sort_order,
            'product_count': category.products.filter(is_active=True).count() if is_leaf else 0,
            'children': children_data,
            'attributes': self.get_category_attributes(category),
            'categorizer_attribute': categorizer_attribute.id if categorizer_attribute else None,
            'can_create_products': is_leaf,
        }
    
    def get_category_level(self, category):
        """Calculate category level in hierarchy"""
        level = 0
        current = category
        while current.parent:
            level += 1
            current = current.parent
        return level
    
    def get_category_attributes(self, category):
        """Get all attributes for this category"""
        attributes = []
        for attr in category.attribute_definitions.all():
            attributes.append({
                'id': attr.id,
                'name': attr.name,
                'type': attr.attribute_type,
                'is_required': attr.is_required,
                'is_categorizer': attr.is_categorizer,
                'is_filterable': attr.is_filterable,
                'choices': attr.choices if attr.attribute_type == 'choice' else [],
                'unit': attr.unit,
            })
        return attributes
    
    @action(detail=True, methods=['post'])
    def create_product(self, request, pk=None):
        """Create product instance in a leaf category"""
        try:
            category = self.get_object()
            store = self.get_user_store(request.user)
            
            # Validate that this is a leaf category
            if category.children.exists():
                return Response({
                    'success': False,
                    'message': 'فقط در دسته‌های پایانی می‌توان محصول ایجاد کرد'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            data = request.data
            
            # Validate required fields
            required_fields = ['title', 'price']
            for field in required_fields:
                if not data.get(field):
                    return Response({
                        'success': False,
                        'message': f'فیلد {field} الزامی است'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Create product
                product = Product.objects.create(
                    store=store,
                    category=category,
                    title=data['title'],
                    description=data.get('description', ''),
                    short_description=data.get('short_description', ''),
                    price=data['price'],
                    compare_price=data.get('compare_price'),
                    sku=data.get('sku', ''),
                    stock=data.get('stock', 0),
                    track_inventory=data.get('track_inventory', True),
                    is_active=data.get('is_active', True),
                    is_featured=data.get('is_featured', False),
                    weight=data.get('weight'),
                    dimensions=data.get('dimensions', ''),
                )
                
                # Add attribute values
                attributes = data.get('attributes', {})
                for attr_id, attr_value in attributes.items():
                    try:
                        attribute = ProductAttribute.objects.get(
                            id=attr_id, 
                            store=store
                        )
                        ProductAttributeValue.objects.create(
                            product=product,
                            attribute=attribute,
                            value=str(attr_value)
                        )
                    except ProductAttribute.DoesNotExist:
                        logger.warning(f"Attribute {attr_id} not found for store {store.id}")
                
                # Handle images
                images = data.get('images', [])
                for i, image_url in enumerate(images):
                    ProductImage.objects.create(
                        product=product,
                        image=image_url,
                        is_primary=(i == 0),
                        sort_order=i
                    )
                
                # Check for "create another" flag (for easier bulk creation)
                create_another = data.get('create_another', False)
                
                response_data = {
                    'id': str(product.id),
                    'title': product.title,
                    'price': float(product.price),
                    'sku': product.sku,
                    'stock': product.stock,
                    'create_another': create_another,
                }
                
                message = 'محصول با موفقیت ایجاد شد'
                if create_another:
                    message += '. آماده ایجاد محصول بعدی با همین اطلاعات'
                
                return Response({
                    'success': True,
                    'message': message,
                    'data': response_data
                })
                
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در ایجاد محصول'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products for a leaf category"""
        try:
            category = self.get_object()
            store = self.get_user_store(request.user)
            
            if category.children.exists():  # Only leaf categories can have products
                return Response({
                    'success': False,
                    'message': 'این دسته نمی‌تواند محصول داشته باشد'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get query parameters
            sort_by = request.GET.get('sort_by', 'created_at')
            search_query = request.GET.get('search', '')
            
            # Base queryset
            products = Product.objects.filter(
                store=store,
                category=category,
                is_active=True
            ).prefetch_related(
                'images',
                'attribute_values__attribute'
            )
            
            # Apply search
            if search_query:
                products = products.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(sku__icontains=search_query)
                )
            
            # Apply sorting
            sort_options = {
                'created_at': '-created_at',
                'price': 'price',
                'price_desc': '-price',
                'name': 'title',
                'stock': '-stock',
            }
            if sort_by in sort_options:
                products = products.order_by(sort_options[sort_by])
            
            # Serialize products
            products_data = []
            for product in products:
                product_data = {
                    'id': str(product.id),
                    'title': product.title,
                    'description': product.description,
                    'price': float(product.price),
                    'compare_price': float(product.compare_price) if product.compare_price else None,
                    'stock': product.stock,
                    'sku': product.sku,
                    'is_active': product.is_active,
                    'is_featured': product.is_featured,
                    'images': [img.image.url for img in product.images.all()[:3]],
                    'attributes': self.get_product_attributes(product),
                    'created_at': product.created_at.isoformat(),
                    'is_low_stock': product.is_low_stock,
                    'is_out_of_stock': product.is_out_of_stock,
                    'stock_warning': product.stock == 1,  # Mall platform specific feature
                }
                products_data.append(product_data)
            
            return Response({
                'success': True,
                'data': products_data,
                'meta': {
                    'total': len(products_data),
                    'category': category.name,
                    'can_create_products': True,
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting category products: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت محصولات'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_product_attributes(self, product):
        """Get formatted product attributes for display"""
        attributes = {}
        for attr_value in product.attribute_values.all():
            attr = attr_value.attribute
            display_value = attr_value.value
            
            # Special handling for color attributes
            if attr.attribute_type == 'color':
                attributes[attr.name] = {
                    'value': display_value,
                    'type': 'color',
                    'display': f'🎨 {display_value}',
                    'is_categorizer': attr.is_categorizer,
                }
            else:
                attributes[attr.name] = {
                    'value': display_value,
                    'type': attr.attribute_type,
                    'display': f'{display_value} {attr.unit}'.strip(),
                    'is_categorizer': attr.is_categorizer,
                }
        return attributes

class MallStoreStatsViewSet(viewsets.ViewSet):
    """Store statistics and analytics for Mall platform"""
    
    permission_classes = [IsAuthenticated]
    
    def get_user_store(self, user):
        """Get user's store"""
        return user.stores.first() if hasattr(user, 'stores') else None
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard statistics"""
        try:
            store = self.get_user_store(request.user)
            if not store:
                return Response({
                    'success': False,
                    'message': 'فروشگاه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            today = now.date()
            thirty_days_ago = now - timedelta(days=30)
            
            # Basic counts
            total_products = Product.objects.filter(store=store).count()
            active_products = Product.objects.filter(store=store, is_active=True).count()
            
            # Low stock products (Mall platform specific feature)
            low_stock_products = Product.objects.filter(
                store=store,
                is_active=True,
                track_inventory=True,
                stock__lte=models.F('low_stock_threshold')
            ).count()
            
            # Orders (if Order model exists)
            total_orders = 0
            pending_orders = 0
            try:
                from .models import Order
                total_orders = Order.objects.filter(store=store).count()
                pending_orders = Order.objects.filter(
                    store=store, 
                    status='pending'
                ).count()
            except:
                pass
            
            # Revenue calculations (placeholder)
            total_revenue = 0
            monthly_revenue = 0
            daily_revenue = 0
            
            # Customer count (placeholder)
            total_customers = 0
            
            stats = {
                'total_products': total_products,
                'active_products': active_products,
                'low_stock_products': low_stock_products,
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'total_revenue': total_revenue,
                'monthly_revenue': monthly_revenue,
                'daily_revenue': daily_revenue,
                'total_customers': total_customers,
                'average_order_value': 0,
                'conversion_rate': 0.0,
                'store_active_since': store.created_at.isoformat(),
            }
            
            return Response({
                'success': True,
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت آمار'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def recent_orders(self, request):
        """Get recent orders for dashboard"""
        try:
            store = self.get_user_store(request.user)
            if not store:
                return Response({
                    'success': False,
                    'message': 'فروشگاه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Placeholder for recent orders
            recent_orders = []
            
            try:
                from .models import Order
                orders = Order.objects.filter(
                    store=store
                ).order_by('-created_at')[:10]
                
                for order in orders:
                    recent_orders.append({
                        'id': order.id,
                        'order_number': order.order_number,
                        'customer_name': order.customer_name,
                        'customer_phone': order.customer_phone,
                        'total_amount': float(order.total_amount),
                        'status': order.status,
                        'created_at': order.created_at.isoformat(),
                        'items_count': order.items.count(),
                    })
            except:
                pass
            
            return Response({
                'success': True,
                'data': recent_orders
            })
            
        except Exception as e:
            logger.error(f"Error getting recent orders: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت سفارشات'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
