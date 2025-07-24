# Mall Platform Product Management Views
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .mall_user_models import Store, MallUser
from .mall_product_models import ProductClass, ProductAttribute, ProductMedia, PredefinedAttributes
from .mall_product_instances import Product, ProductAttributeValue, ProductVariant, ProductMediaAssignment
from .mall_serializers import MallUserSerializer
import json
from datetime import datetime


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_classes(request):
    """Get hierarchical product classes"""
    try:
        # Get root classes (level 0)
        root_classes = ProductClass.objects.filter(
            parent=None,
            is_active=True
        ).order_by('sort_order', 'name')
        
        def build_tree(classes):
            result = []
            for cls in classes:
                children = cls.get_children()
                result.append({
                    'id': cls.id,
                    'name': cls.name,
                    'slug': cls.slug,
                    'level': cls.level,
                    'path': cls.path,
                    'is_leaf': cls.is_leaf(),
                    'can_have_products': cls.can_have_products(),
                    'product_count': cls.product_count,
                    'icon': cls.icon.url if cls.icon else None,
                    'children': build_tree(children) if children.exists() else []
                })
            return result
        
        tree_data = build_tree(root_classes)
        
        return Response({
            'success': True,
            'data': tree_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در دریافت دسته‌بندی محصولات'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_attributes(request, class_id):
    """Get attributes for a specific product class"""
    try:
        product_class = get_object_or_404(ProductClass, id=class_id)
        
        # Get all attributes assigned to this class and its ancestors
        classes_in_hierarchy = [product_class] + list(product_class.get_ancestors())
        
        class_attributes = []
        for cls in classes_in_hierarchy:
            for class_attr in cls.class_attributes.select_related('attribute').order_by('sort_order'):
                attribute = class_attr.attribute
                
                # Check if we already have this attribute
                if not any(ca['id'] == attribute.id for ca in class_attributes):
                    choices = class_attr.get_all_choices()
                    
                    class_attributes.append({
                        'id': attribute.id,
                        'name': attribute.name,
                        'slug': attribute.slug,
                        'type': attribute.attribute_type,
                        'display_name': attribute.display_name or attribute.name,
                        'help_text': attribute.help_text,
                        'placeholder': attribute.placeholder,
                        'unit': attribute.unit,
                        'is_required': class_attr.get_effective_is_required(),
                        'is_categorizer': class_attr.get_effective_is_categorizer(),
                        'is_filterable': attribute.is_filterable,
                        'choices': choices,
                        'min_value': str(attribute.min_value) if attribute.min_value else None,
                        'max_value': str(attribute.max_value) if attribute.max_value else None,
                        'min_length': attribute.min_length,
                        'max_length': attribute.max_length,
                        'sort_order': class_attr.sort_order,
                        'from_class': cls.name
                    })
        
        return Response({
            'success': True,
            'data': {
                'class': {
                    'id': product_class.id,
                    'name': product_class.name,
                    'full_name': product_class.get_full_name(),
                    'is_leaf': product_class.is_leaf(),
                    'can_have_products': product_class.can_have_products()
                },
                'attributes': sorted(class_attributes, key=lambda x: x['sort_order'])
            }
        }, status=status.HTTP_200_OK)
        
    except ProductClass.DoesNotExist:
        return Response({
            'success': False,
            'message': 'دسته‌بندی محصول یافت نشد'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در دریافت ویژگی‌های محصول'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_product(request):
    """Create new product with attributes"""
    try:
        # Get user's store
        try:
            mall_user = request.user.mall_profile
            if not mall_user.is_store_owner:
                return Response({
                    'success': False,
                    'message': 'فقط صاحبان فروشگاه می‌توانند محصول ایجاد کنند'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get user's active store
            store = mall_user.owned_stores.filter(status='active').first()
            if not store:
                return Response({
                    'success': False,
                    'message': 'فروشگاه فعالی یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except MallUser.DoesNotExist:
            return Response({
                'success': False,
                'message': 'پروفایل کاربری یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'product_class_id', 'price']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'message': f'فیلد {field} الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get and validate product class
        try:
            product_class = ProductClass.objects.get(id=data['product_class_id'])
            if not product_class.is_leaf():
                return Response({
                    'success': False,
                    'message': 'محصول تنها می‌تواند در دسته‌های پایانی ایجاد شود'
                }, status=status.HTTP_400_BAD_REQUEST)
        except ProductClass.DoesNotExist:
            return Response({
                'success': False,
                'message': 'دسته‌بندی محصول یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        with transaction.atomic():
            # Create product
            product = Product.objects.create(
                store=store,
                product_class=product_class,
                name=data['name'],
                price=data['price'],
                compare_price=data.get('compare_price'),
                cost_per_item=data.get('cost_per_item'),
                sku=data.get('sku', ''),
                inventory_quantity=data.get('inventory_quantity', 0),
                low_stock_threshold=data.get('low_stock_threshold', 5),
                track_inventory=data.get('track_inventory', True),
                allow_backorders=data.get('allow_backorders', False),
                requires_shipping=data.get('requires_shipping', True),
                status=data.get('status', 'draft'),
                meta_title=data.get('meta_title', ''),
                meta_description=data.get('meta_description', '')
            )
            
            # Process attributes
            attributes_data = data.get('attributes', {})
            if attributes_data:
                # Get required attributes for this class
                required_attrs = []
                classes_in_hierarchy = [product_class] + list(product_class.get_ancestors())
                
                for cls in classes_in_hierarchy:
                    for class_attr in cls.class_attributes.select_related('attribute'):
                        if class_attr.get_effective_is_required():
                            required_attrs.append(class_attr.attribute.slug)
                
                # Validate required attributes
                for attr_slug in required_attrs:
                    if attr_slug not in attributes_data or not attributes_data[attr_slug]:
                        try:
                            attr = ProductAttribute.objects.get(slug=attr_slug)
                            return Response({
                                'success': False,
                                'message': f'ویژگی "{attr.name}" الزامی است'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        except ProductAttribute.DoesNotExist:
                            continue
                
                # Create attribute values
                for attr_slug, value in attributes_data.items():
                    try:
                        attribute = ProductAttribute.objects.get(slug=attr_slug)
                        
                        # Validate attribute value
                        is_valid, error_message = attribute.validate_value(value)
                        if not is_valid:
                            return Response({
                                'success': False,
                                'message': f'خطا در ویژگی "{attribute.name}": {error_message}'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Create attribute value
                        attr_value = ProductAttributeValue.objects.create(
                            product=product,
                            attribute=attribute
                        )
                        attr_value.set_value(value)
                        attr_value.save()
                        
                    except ProductAttribute.DoesNotExist:
                        continue
            
            # Process media files
            media_ids = data.get('media_ids', [])
            if media_ids:
                for i, media_id in enumerate(media_ids):
                    try:
                        media = ProductMedia.objects.get(id=media_id)
                        ProductMediaAssignment.objects.create(
                            product=product,
                            media=media,
                            is_primary=(i == 0),  # First image is primary
                            sort_order=i
                        )
                    except ProductMedia.DoesNotExist:
                        continue
            
            return Response({
                'success': True,
                'message': 'محصول با موفقیت ایجاد شد',
                'data': {
                    'id': product.id,
                    'uuid': str(product.uuid),
                    'name': product.name,
                    'slug': product.slug,
                    'price': str(product.price),
                    'status': product.status,
                    'url': product.get_absolute_url(),
                    'admin_url': product.get_admin_url()
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در ایجاد محصول'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_product_copy(request, product_id):
    """Create copy of existing product with identical form data"""
    try:
        # Get original product
        try:
            mall_user = request.user.mall_profile
            original_product = Product.objects.get(
                id=product_id,
                store__owner=mall_user
            )
        except Product.DoesNotExist:
            return Response({
                'success': False,
                'message': 'محصول یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        
        with transaction.atomic():
            # Create new product with similar data
            new_product = Product.objects.create(
                store=original_product.store,
                product_class=original_product.product_class,
                name=data.get('name', f"{original_product.name} - کپی"),
                price=original_product.price,
                compare_price=original_product.compare_price,
                cost_per_item=original_product.cost_per_item,
                sku=data.get('sku', ''),  # SKU should be unique
                inventory_quantity=data.get('inventory_quantity', original_product.inventory_quantity),
                low_stock_threshold=original_product.low_stock_threshold,
                track_inventory=original_product.track_inventory,
                allow_backorders=original_product.allow_backorders,
                requires_shipping=original_product.requires_shipping,
                status='draft',  # New products start as draft
                meta_title=original_product.meta_title,
                meta_description=original_product.meta_description
            )
            
            # Copy attribute values
            for attr_value in original_product.attribute_values.all():
                new_attr_value = ProductAttributeValue.objects.create(
                    product=new_product,
                    attribute=attr_value.attribute
                )
                new_attr_value.set_value(attr_value.get_value())
                new_attr_value.save()
            
            # Copy media assignments
            for assignment in original_product.media_assignments.all():
                ProductMediaAssignment.objects.create(
                    product=new_product,
                    media=assignment.media,
                    is_primary=assignment.is_primary,
                    sort_order=assignment.sort_order,
                    alt_text=assignment.alt_text
                )
            
            return Response({
                'success': True,
                'message': 'کپی محصول با موفقیت ایجاد شد',
                'data': {
                    'id': new_product.id,
                    'uuid': str(new_product.uuid),
                    'name': new_product.name,
                    'slug': new_product.slug,
                    'price': str(new_product.price),
                    'status': new_product.status,
                    'url': new_product.get_absolute_url(),
                    'admin_url': new_product.get_admin_url()
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در کپی کردن محصول'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_store_products(request):
    """Get products for store owner dashboard"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند محصولات را مشاهده کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        class_filter = request.GET.get('class', '')
        sort_by = request.GET.get('sort', '-created_at')
        
        # Build query
        products = Product.objects.filter(store=store)
        
        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search)
            )
        
        if status_filter:
            products = products.filter(status=status_filter)
        
        if class_filter:
            try:
                product_class = ProductClass.objects.get(id=class_filter)
                # Include products from this class and all its descendants
                descendant_classes = list(product_class.get_descendants()) + [product_class]
                products = products.filter(product_class__in=descendant_classes)
            except ProductClass.DoesNotExist:
                pass
        
        # Apply sorting
        if sort_by in ['name', '-name', 'price', '-price', 'created_at', '-created_at', 'inventory_quantity', '-inventory_quantity']:
            products = products.order_by(sort_by)
        else:
            products = products.order_by('-created_at')
        
        # Pagination
        total_count = products.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        products_page = products[start_index:end_index]
        
        # Serialize products
        products_data = []
        for product in products_page:
            main_image = product.get_main_image()
            
            products_data.append({
                'id': product.id,
                'uuid': str(product.uuid),
                'name': product.name,
                'slug': product.slug,
                'sku': product.sku,
                'price': str(product.price),
                'compare_price': str(product.compare_price) if product.compare_price else None,
                'inventory_quantity': product.inventory_quantity,
                'status': product.status,
                'status_display': dict(Product.STATUS_CHOICES)[product.status],
                'is_featured': product.is_featured,
                'is_in_stock': product.is_in_stock(),
                'is_low_stock': product.is_low_stock(),
                'discount_percentage': product.get_discount_percentage(),
                'view_count': product.view_count,
                'order_count': product.order_count,
                'favorite_count': product.favorite_count,
                'main_image': main_image.get_thumbnail_url() if main_image else None,
                'product_class': {
                    'id': product.product_class.id,
                    'name': product.product_class.name,
                    'full_name': product.product_class.get_full_name()
                },
                'created_at': product.created_at.isoformat(),
                'updated_at': product.updated_at.isoformat(),
                'urls': {
                    'view': product.get_absolute_url(),
                    'edit': product.get_admin_url()
                }
            })
        
        return Response({
            'success': True,
            'data': {
                'products': products_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': end_index < total_count,
                    'has_previous': page > 1
                }
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در دریافت محصولات'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_calls([IsAuthenticated])
def get_product_detail(request, product_id):
    """Get detailed product information for editing"""
    try:
        mall_user = request.user.mall_profile
        
        try:
            product = Product.objects.select_related(
                'store', 'product_class'
            ).prefetch_related(
                'attribute_values__attribute',
                'media_assignments__media',
                'variants'
            ).get(
                id=product_id,
                store__owner=mall_user
            )
        except Product.DoesNotExist:
            return Response({
                'success': False,
                'message': 'محصول یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get product attributes with values
        attributes_data = []
        for attr_value in product.attribute_values.all():
            attribute = attr_value.attribute
            
            attributes_data.append({
                'id': attribute.id,
                'name': attribute.name,
                'slug': attribute.slug,
                'type': attribute.attribute_type,
                'display_name': attribute.display_name or attribute.name,
                'help_text': attribute.help_text,
                'unit': attribute.unit,
                'is_required': attribute.is_required,
                'choices': attribute.get_choices(),
                'value': attr_value.get_value(),
                'display_value': attr_value.get_display_value()
            })
        
        # Get product media
        media_data = []
        for assignment in product.media_assignments.all():
            media = assignment.media
            media_data.append({
                'id': media.id,
                'uuid': str(media.uuid),
                'type': media.media_type,
                'title': media.title,
                'alt_text': assignment.alt_text or media.alt_text,
                'is_primary': assignment.is_primary,
                'sort_order': assignment.sort_order,
                'url': media.file.url,
                'thumbnail_url': media.get_thumbnail_url(),
                'width': media.width,
                'height': media.height,
                'file_size': media.file_size
            })
        
        # Get product variants
        variants_data = []
        for variant in product.variants.all():
            variants_data.append({
                'id': variant.id,
                'name': variant.name,
                'sku': variant.sku,
                'price': str(variant.price) if variant.price else None,
                'compare_price': str(variant.compare_price) if variant.compare_price else None,
                'inventory_quantity': variant.inventory_quantity,
                'is_active': variant.is_active,
                'attributes': variant.attributes_json,
                'attribute_display': variant.get_attribute_display(),
                'effective_price': str(variant.get_effective_price()),
                'is_in_stock': variant.is_in_stock(),
                'discount_percentage': variant.get_discount_percentage(),
                'image': variant.image.get_thumbnail_url() if variant.image else None
            })
        
        main_image = product.get_main_image()
        
        product_data = {
            'id': product.id,
            'uuid': str(product.uuid),
            'name': product.name,
            'slug': product.slug,
            'sku': product.sku,
            'price': str(product.price),
            'compare_price': str(product.compare_price) if product.compare_price else None,
            'cost_per_item': str(product.cost_per_item) if product.cost_per_item else None,
            'inventory_quantity': product.inventory_quantity,
            'low_stock_threshold': product.low_stock_threshold,
            'track_inventory': product.track_inventory,
            'allow_backorders': product.allow_backorders,
            'requires_shipping': product.requires_shipping,
            'status': product.status,
            'status_display': dict(Product.STATUS_CHOICES)[product.status],
            'is_featured': product.is_featured,
            'meta_title': product.meta_title,
            'meta_description': product.meta_description,
            'view_count': product.view_count,
            'order_count': product.order_count,
            'favorite_count': product.favorite_count,
            'is_in_stock': product.is_in_stock(),
            'is_low_stock': product.is_low_stock(),
            'discount_percentage': product.get_discount_percentage(),
            'main_image': main_image.get_thumbnail_url() if main_image else None,
            'product_class': {
                'id': product.product_class.id,
                'name': product.product_class.name,
                'full_name': product.product_class.get_full_name(),
                'path': product.product_class.path
            },
            'attributes': attributes_data,
            'media': media_data,
            'variants': variants_data,
            'created_at': product.created_at.isoformat(),
            'updated_at': product.updated_at.isoformat(),
            'published_at': product.published_at.isoformat() if product.published_at else None,
            'urls': {
                'view': product.get_absolute_url(),
                'edit': product.get_admin_url()
            }
        }
        
        return Response({
            'success': True,
            'data': product_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در دریافت جزئیات محصول'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_predefined_attributes(request):
    """Initialize predefined attributes (color, description, etc.)"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند این عملیات را انجام دهند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create all predefined attributes
        predefined_attrs = PredefinedAttributes.create_all_predefined()
        
        return Response({
            'success': True,
            'message': 'ویژگی‌های پیش‌فرض با موفقیت ایجاد شدند',
            'data': {
                'created_attributes': [
                    {
                        'id': attr.id,
                        'name': attr.name,
                        'slug': attr.slug,
                        'type': attr.attribute_type
                    }
                    for attr in predefined_attrs.values()
                ]
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در ایجاد ویژگی‌های پیش‌فرض'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_product_status(request, product_id):
    """Update product status"""
    try:
        mall_user = request.user.mall_profile
        
        try:
            product = Product.objects.get(
                id=product_id,
                store__owner=mall_user
            )
        except Product.DoesNotExist:
            return Response({
                'success': False,
                'message': 'محصول یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        new_status = request.data.get('status')
        if new_status not in [choice[0] for choice in Product.STATUS_CHOICES]:
            return Response({
                'success': False,
                'message': 'وضعیت نامعتبر است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = product.status
        product.status = new_status
        product.save()
        
        # Show stock warning if product has only one instance remaining
        warning_message = None
        if product.track_inventory and product.inventory_quantity == 1:
            warning_message = 'هشدار: تنها یک نمونه از این محصول باقی مانده است'
        
        return Response({
            'success': True,
            'message': f'وضعیت محصول به "{dict(Product.STATUS_CHOICES)[new_status]}" تغییر یافت',
            'warning': warning_message,
            'data': {
                'old_status': old_status,
                'new_status': new_status,
                'inventory_quantity': product.inventory_quantity
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در به‌روزرسانی وضعیت محصول'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_product(request, product_id):
    """Delete product"""
    try:
        mall_user = request.user.mall_profile
        
        try:
            product = Product.objects.get(
                id=product_id,
                store__owner=mall_user
            )
        except Product.DoesNotExist:
            return Response({
                'success': False,
                'message': 'محصول یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        product_name = product.name
        product.delete()
        
        return Response({
            'success': True,
            'message': f'محصول "{product_name}" با موفقیت حذف شد'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در حذف محصول'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
