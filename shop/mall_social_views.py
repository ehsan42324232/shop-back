# Mall Platform Social Media Integration Views
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .mall_user_models import Store, MallUser
from .mall_product_models import ProductMedia
from .mall_social_extractor import social_extractor
import json


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_social_media_content(request):
    """Get content from social media for product creation - 'Get from social media' button"""
    try:
        # Verify user is store owner
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند از این قابلیت استفاده کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get user's active store
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        instagram_url = data.get('instagram_url', '')
        telegram_channel = data.get('telegram_channel', '')
        limit = min(int(data.get('limit', 5)), 10)  # Max 10 items
        
        if not instagram_url and not telegram_channel:
            return Response({
                'success': False,
                'message': 'حداقل یک آدرس اینستاگرام یا کانال تلگرام وارد کنید'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract content from social media
        results = social_extractor.get_combined_content(
            instagram_url=instagram_url if instagram_url else None,
            telegram_channel=telegram_channel if telegram_channel else None,
            limit=limit
        )
        
        # Process results to make them more user-friendly
        processed_results = {
            'success': True,
            'message': 'محتوا با موفقیت از شبکه‌های اجتماعی دریافت شد',
            'data': {
                'summary': results['combined_summary'],
                'sources': {
                    'instagram': results['instagram'],
                    'telegram': results['telegram']
                },
                'content_categories': {
                    'images': [],
                    'videos': [],
                    'texts': []
                }
            }
        }
        
        # Combine all content into categories for easier selection
        all_images = []
        all_videos = []
        all_texts = []
        
        # From Instagram
        if results['instagram'] and results['instagram'].get('success'):
            instagram_content = results['instagram']['content']
            all_images.extend(instagram_content.get('images', []))
            all_videos.extend(instagram_content.get('videos', []))
            all_texts.extend(instagram_content.get('texts', []))
        
        # From Telegram
        if results['telegram'] and results['telegram'].get('success'):
            telegram_content = results['telegram']['content']
            all_images.extend(telegram_content.get('images', []))
            all_videos.extend(telegram_content.get('videos', []))
            all_texts.extend(telegram_content.get('texts', []))
        
        # Sort by timestamp (newest first)
        all_images.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        all_videos.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        all_texts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        processed_results['data']['content_categories'] = {
            'images': all_images,
            'videos': all_videos,
            'texts': all_texts
        }
        
        return Response(processed_results, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در دریافت محتوا از شبکه‌های اجتماعی',
            'error': str(e) if request.user.is_staff else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def select_social_content_for_product(request):
    """Select materials from social media for product definition"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند از این قابلیت استفاده کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        selected_images = data.get('selected_images', [])
        selected_videos = data.get('selected_videos', [])
        selected_texts = data.get('selected_texts', [])
        
        if not (selected_images or selected_videos or selected_texts):
            return Response({
                'success': False,
                'message': 'حداقل یک مورد برای انتخاب مشخص کنید'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        processed_content = {
            'images': [],
            'videos': [],
            'texts': [],
            'suggested_product_data': {}
        }
        
        with transaction.atomic():
            # Process selected images
            for image_data in selected_images:
                try:
                    # Download and save image
                    media = social_extractor.download_and_save_media(image_data, store.id)
                    if media:
                        processed_content['images'].append({
                            'id': media.id,
                            'uuid': str(media.uuid),
                            'url': media.file.url,
                            'thumbnail': media.get_thumbnail_url(),
                            'caption': media.description,
                            'source': media.social_source,
                            'original_id': image_data.get('id')
                        })
                except Exception as e:
                    continue  # Skip failed downloads
            
            # Process selected videos
            for video_data in selected_videos:
                try:
                    media = social_extractor.download_and_save_media(video_data, store.id)
                    if media:
                        processed_content['videos'].append({
                            'id': media.id,
                            'uuid': str(media.uuid),
                            'url': media.file.url,
                            'thumbnail': media.get_thumbnail_url(),
                            'caption': media.description,
                            'source': media.social_source,
                            'duration': video_data.get('duration'),
                            'original_id': video_data.get('id')
                        })
                except Exception as e:
                    continue
            
            # Process selected texts and extract product information
            combined_text = ""
            for text_data in selected_texts:
                text_content = text_data.get('text', '')
                combined_text += text_content + "\n\n"
                processed_content['texts'].append({
                    'id': text_data.get('id'),
                    'text': text_content,
                    'source': text_data.get('source'),
                    'timestamp': text_data.get('timestamp')
                })
            
            # Extract product information from combined text
            if combined_text.strip():
                product_info = social_extractor.extract_product_info_from_text(combined_text)
                processed_content['suggested_product_data'] = product_info
        
        return Response({
            'success': True,
            'message': f'محتوا پردازش شد: {len(processed_content["images"])} تصویر، {len(processed_content["videos"])} ویدیو، {len(processed_content["texts"])} متن',
            'data': processed_content
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در پردازش محتوای انتخاب شده',
            'error': str(e) if request.user.is_staff else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_product_from_social_content(request):
    """Create product using selected social media content"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند محصول ایجاد کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
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
        from .mall_product_models import ProductClass
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
            from .mall_product_instances import Product, ProductAttributeValue, ProductMediaAssignment
            
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
            
            # Process attributes from social content and manual input
            attributes_data = data.get('attributes', {})
            
            # Add suggested description from social content if not provided
            if 'description' not in attributes_data:
                suggested_description = data.get('suggested_description', '')
                if suggested_description:
                    attributes_data['description'] = suggested_description
            
            # Create attribute values
            if attributes_data:
                from .mall_product_models import ProductAttribute
                
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
            
            # Assign social media files to product
            social_media_ids = data.get('social_media_ids', [])
            if social_media_ids:
                for i, media_id in enumerate(social_media_ids):
                    try:
                        media = ProductMedia.objects.get(id=media_id)
                        ProductMediaAssignment.objects.create(
                            product=product,
                            media=media,
                            is_primary=(i == 0),  # First media is primary
                            sort_order=i
                        )
                    except ProductMedia.DoesNotExist:
                        continue
            
            return Response({
                'success': True,
                'message': 'محصول با استفاده از محتوای شبکه‌های اجتماعی با موفقیت ایجاد شد',
                'data': {
                    'id': product.id,
                    'uuid': str(product.uuid),
                    'name': product.name,
                    'slug': product.slug,
                    'price': str(product.price),
                    'status': product.status,
                    'url': product.get_absolute_url(),
                    'admin_url': product.get_admin_url(),
                    'social_media_count': len(social_media_ids)
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در ایجاد محصول از محتوای شبکه‌های اجتماعی',
            'error': str(e) if request.user.is_staff else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_store_social_media_settings(request):
    """Get store's social media integration settings"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند تنظیمات را مشاهده کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        settings_data = {
            'instagram_url': store.instagram_url,
            'telegram_url': store.telegram_url,
            'whatsapp_number': store.whatsapp_number,
            'auto_import_enabled': False,  # Could be added as a store setting
            'last_import_date': None,  # Could track last social import
            'supported_platforms': [
                {
                    'name': 'Instagram',
                    'slug': 'instagram',
                    'enabled': bool(store.instagram_url),
                    'description': 'واردات تصاویر و ویدیوها از اینستاگرام'
                },
                {
                    'name': 'Telegram',
                    'slug': 'telegram',
                    'enabled': bool(store.telegram_url),
                    'description': 'واردات محتوا از کانال تلگرام'
                }
            ]
        }
        
        return Response({
            'success': True,
            'data': settings_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در دریافت تنظیمات شبکه‌های اجتماعی'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_store_social_media_settings(request):
    """Update store's social media integration settings"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند تنظیمات را ویرایش کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        
        # Update social media URLs
        if 'instagram_url' in data:
            store.instagram_url = data['instagram_url']
        
        if 'telegram_url' in data:
            store.telegram_url = data['telegram_url']
        
        if 'whatsapp_number' in data:
            store.whatsapp_number = data['whatsapp_number']
        
        store.save()
        
        return Response({
            'success': True,
            'message': 'تنظیمات شبکه‌های اجتماعی با موفقیت به‌روزرسانی شد',
            'data': {
                'instagram_url': store.instagram_url,
                'telegram_url': store.telegram_url,
                'whatsapp_number': store.whatsapp_number
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در به‌روزرسانی تنظیمات شبکه‌های اجتماعی'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_imported_social_media(request):
    """Get list of media imported from social networks"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند رسانه‌های وارد شده را مشاهده کنند'
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
        source_filter = request.GET.get('source', '')  # 'instagram' or 'telegram'
        media_type_filter = request.GET.get('type', '')  # 'image' or 'video'
        
        # Get social media imported to this store's products
        media_query = ProductMedia.objects.filter(
            social_source__isnull=False,
            product_assignments__product__store=store
        ).distinct()
        
        if source_filter:
            media_query = media_query.filter(social_source=source_filter)
        
        if media_type_filter:
            media_query = media_query.filter(media_type=media_type_filter)
        
        # Pagination
        total_count = media_query.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        media_page = media_query[start_index:end_index]
        
        # Serialize media
        media_data = []
        for media in media_page:
            # Get associated products
            products = [
                {
                    'id': assignment.product.id,
                    'name': assignment.product.name,
                    'slug': assignment.product.slug
                }
                for assignment in media.product_assignments.filter(product__store=store)
            ]
            
            media_data.append({
                'id': media.id,
                'uuid': str(media.uuid),
                'type': media.media_type,
                'title': media.title,
                'description': media.description,
                'url': media.file.url if media.file else None,
                'thumbnail': media.get_thumbnail_url(),
                'social_source': media.social_source,
                'social_url': media.social_url,
                'social_id': media.social_id,
                'file_size': media.file_size,
                'width': media.width,
                'height': media.height,
                'duration': media.duration,
                'products': products,
                'created_at': media.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': {
                'media': media_data,
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
            'message': 'خطا در دریافت رسانه‌های وارد شده'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_social_media(request, media_id):
    """Delete imported social media"""
    try:
        mall_user = request.user.mall_profile
        if not mall_user.is_store_owner:
            return Response({
                'success': False,
                'message': 'فقط صاحبان فروشگاه می‌توانند رسانه‌ها را حذف کنند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        store = mall_user.owned_stores.filter(status='active').first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه فعالی یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            # Ensure media belongs to store's products
            media = ProductMedia.objects.filter(
                id=media_id,
                product_assignments__product__store=store
            ).first()
            
            if not media:
                return Response({
                    'success': False,
                    'message': 'رسانه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            media_title = media.title or 'رسانه'
            media.delete()
            
            return Response({
                'success': True,
                'message': f'"{media_title}" با موفقیت حذف شد'
            }, status=status.HTTP_200_OK)
            
        except ProductMedia.DoesNotExist:
            return Response({
                'success': False,
                'message': 'رسانه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در حذف رسانه'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
