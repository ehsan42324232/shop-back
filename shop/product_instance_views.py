# Product Instance Management Views
# API views for managing product instances with attributes

from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q

from .mall_models import (
    EnhancedProduct, ProductInstance, ProductAttributeDefinition,
    ProductAttributeValue, EnhancedProductCategory
)
from .models import Store


class ProductInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for product instances"""
    
    def get_queryset(self):
        user = self.request.user
        store_id = self.request.query_params.get('store_id')
        
        if store_id:
            return ProductInstance.objects.filter(
                product__store__owner=user,
                product__store_id=store_id
            ).select_related('product', 'product__store')
        
        return ProductInstance.objects.filter(
            product__store__owner=user
        ).select_related('product', 'product__store')
    
    def list(self, request, *args, **kwargs):
        """List product instances with filtering"""
        try:
            queryset = self.get_queryset()
            
            # Apply filters
            product_id = request.query_params.get('product_id')
            if product_id:
                queryset = queryset.filter(product_id=product_id)
            
            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(sku__icontains=search) |
                    Q(product__name__icontains=search)
                )
            
            # Pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serialized_data = self.serialize_instances(page)
                return self.get_paginated_response(serialized_data)
            
            serialized_data = self.serialize_instances(queryset)
            return Response(serialized_data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        """Create new product instance"""
        try:
            data = request.data
            product_id = data.get('product_id')
            
            # Verify product ownership
            product = get_object_or_404(
                EnhancedProduct,
                id=product_id,
                store__owner=request.user,
                is_leaf=True,
                can_have_instances=True
            )
            
            with transaction.atomic():
                # Create instance
                instance = ProductInstance.objects.create(
                    product=product,
                    price=data.get('price'),
                    compare_price=data.get('compare_price'),
                    cost_price=data.get('cost_price'),
                    stock_quantity=data.get('stock_quantity', 0),
                    low_stock_threshold=data.get('low_stock_threshold', 1),
                    weight=data.get('weight'),
                    dimensions=data.get('dimensions', {}),
                    is_active=data.get('is_active', True),
                    is_default=data.get('is_default', False)
                )
                
                # Set as default if it's the first instance
                if product.instances.count() == 1:
                    instance.is_default = True
                    instance.save()
                
                # Create attribute values
                attributes = data.get('attributes', [])
                for attr_data in attributes:
                    self.create_attribute_value(instance, attr_data)
                
                # Handle "create another" functionality
                create_another = data.get('create_another', False)
                
                response_data = {
                    'success': True,
                    'instance': self.serialize_instance(instance),
                    'message': 'نمونه محصول با موفقیت ایجاد شد'
                }
                
                if create_another:
                    response_data['form_data'] = {
                        'product_id': product_id,
                        'price': data.get('price'),
                        'compare_price': data.get('compare_price'),
                        'cost_price': data.get('cost_price'),
                        'stock_quantity': data.get('stock_quantity', 0),
                        'attributes': attributes
                    }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update product instance"""
        try:
            instance = self.get_object()
            data = request.data
            
            with transaction.atomic():
                # Update basic fields
                for field in ['price', 'compare_price', 'cost_price', 
                             'stock_quantity', 'low_stock_threshold', 
                             'weight', 'dimensions', 'is_active', 'is_default']:
                    if field in data:
                        setattr(instance, field, data[field])
                
                instance.save()
                
                # Update attribute values
                if 'attributes' in data:
                    # Remove existing attribute values
                    instance.attribute_values.all().delete()
                    
                    # Create new ones
                    for attr_data in data['attributes']:
                        self.create_attribute_value(instance, attr_data)
                
                return Response({
                    'success': True,
                    'instance': self.serialize_instance(instance),
                    'message': 'نمونه محصول به‌روزرسانی شد'
                })
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create_attribute_value(self, instance, attr_data):
        """Create attribute value for instance"""
        attribute_id = attr_data.get('attribute_id')
        value = attr_data.get('value')
        
        if not attribute_id or value is None:
            return
        
        attribute = ProductAttributeDefinition.objects.get(id=attribute_id)
        
        attr_value = ProductAttributeValue.objects.create(
            instance=instance,
            attribute=attribute
        )
        
        # Set value based on attribute type
        if attribute.attribute_type == 'text' or attribute.attribute_type == 'description':
            attr_value.text_value = str(value)
        elif attribute.attribute_type == 'number':
            attr_value.number_value = float(value)
        elif attribute.attribute_type == 'boolean':
            attr_value.boolean_value = bool(value)
        elif attribute.attribute_type == 'color':
            attr_value.color_value = str(value)
        elif attribute.attribute_type == 'choice':
            attr_value.choice_value = str(value)
        
        attr_value.save()
    
    def serialize_instance(self, instance):
        """Serialize single instance"""
        return {
            'id': instance.id,
            'sku': instance.sku,
            'product': {
                'id': instance.product.id,
                'name': instance.product.name,
                'store_name': instance.product.store.name
            },
            'price': str(instance.price),
            'compare_price': str(instance.compare_price) if instance.compare_price else None,
            'cost_price': str(instance.cost_price) if instance.cost_price else None,
            'stock_quantity': instance.stock_quantity,
            'low_stock_threshold': instance.low_stock_threshold,
            'weight': str(instance.weight) if instance.weight else None,
            'dimensions': instance.dimensions,
            'is_active': instance.is_active,
            'is_default': instance.is_default,
            'is_on_sale': instance.is_on_sale,
            'discount_percentage': instance.discount_percentage,
            'is_low_stock': instance.is_low_stock,
            'is_out_of_stock': instance.is_out_of_stock,
            'attributes': [{
                'id': av.id,
                'attribute': {
                    'id': av.attribute.id,
                    'name': av.attribute.name,
                    'type': av.attribute.attribute_type
                },
                'value': av.get_display_value()
            } for av in instance.attribute_values.all()],
            'created_at': instance.created_at,
            'updated_at': instance.updated_at
        }
    
    def serialize_instances(self, instances):
        """Serialize list of instances"""
        return [self.serialize_instance(instance) for instance in instances]
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create instances with different attribute combinations"""
        try:
            data = request.data
            product_id = data.get('product_id')
            combinations = data.get('combinations', [])
            
            product = get_object_or_404(
                EnhancedProduct,
                id=product_id,
                store__owner=request.user,
                is_leaf=True,
                can_have_instances=True
            )
            
            created_instances = []
            
            with transaction.atomic():
                for combo in combinations:
                    instance = ProductInstance.objects.create(
                        product=product,
                        price=combo.get('price'),
                        compare_price=combo.get('compare_price'),
                        cost_price=combo.get('cost_price'),
                        stock_quantity=combo.get('stock_quantity', 0),
                        low_stock_threshold=combo.get('low_stock_threshold', 1),
                        weight=combo.get('weight'),
                        is_active=combo.get('is_active', True)
                    )
                    
                    # Create attribute values
                    for attr_data in combo.get('attributes', []):
                        self.create_attribute_value(instance, attr_data)
                    
                    created_instances.append(instance)
            
            return Response({
                'success': True,
                'created_count': len(created_instances),
                'instances': self.serialize_instances(created_instances),
                'message': f'{len(created_instances)} نمونه محصول ایجاد شد'
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def low_stock_alert(self, request):
        """Get instances with low stock"""
        try:
            store_id = request.query_params.get('store_id')
            queryset = self.get_queryset()
            
            if store_id:
                queryset = queryset.filter(product__store_id=store_id)
            
            # Filter low stock items
            low_stock_instances = []
            for instance in queryset:
                if instance.is_low_stock:
                    low_stock_instances.append(instance)
            
            return Response({
                'low_stock_count': len(low_stock_instances),
                'instances': self.serialize_instances(low_stock_instances)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_for_instances(request, product_id):
    """Get product details for instance creation"""
    try:
        product = get_object_or_404(
            EnhancedProduct,
            id=product_id,
            store__owner=request.user
        )
        
        if not product.is_leaf or not product.can_have_instances:
            return Response(
                {'error': 'این محصول نمی‌تواند نمونه داشتع باشد'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get available attributes for this product/category
        attributes = ProductAttributeDefinition.objects.filter(
            Q(category=product.category) | Q(category__isnull=True),
            store=product.store,
            is_active=True,
            is_variant_attribute=True
        ).order_by('display_order')
        
        return Response({
            'product': {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'category': product.category.name if product.category else None,
                'base_price': str(product.base_price) if product.base_price else None,
                'images': product.images,
                'videos': product.videos
            },
            'attributes': [{
                'id': attr.id,
                'name': attr.name,
                'type': attr.attribute_type,
                'is_required': attr.is_required,
                'choices': attr.choices if attr.attribute_type == 'choice' else [],
                'unit': attr.unit
            } for attr in attributes],
            'existing_instances_count': product.instances.count()
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instance_stock_warning(request, instance_id):
    """Check if instance needs stock warning for customers"""
    try:
        instance = get_object_or_404(
            ProductInstance,
            id=instance_id,
            product__store__owner=request.user
        )
        
        # Count identical instances (same attribute values)
        identical_instances = ProductInstance.objects.filter(
            product=instance.product,
            is_active=True
        )
        
        # Filter by same attribute values
        for attr_value in instance.attribute_values.all():
            identical_instances = identical_instances.filter(
                attribute_values__attribute=attr_value.attribute,
                attribute_values__text_value=attr_value.text_value,
                attribute_values__choice_value=attr_value.choice_value,
                attribute_values__color_value=attr_value.color_value
            )
        
        total_stock = sum(inst.stock_quantity for inst in identical_instances)
        
        return Response({
            'instance_stock': instance.stock_quantity,
            'identical_instances_count': identical_instances.count(),
            'total_identical_stock': total_stock,
            'show_warning': total_stock == 1,
            'warning_message': 'تنها یک عدد باقی مانده!' if total_stock == 1 else None
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )