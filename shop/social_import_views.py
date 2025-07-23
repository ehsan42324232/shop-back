from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .social_media_extractor import SocialMediaExtractor
from .models import Store
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fetch_social_content(request):
    """Fetch content from social media platforms"""
    try:
        data = request.data
        platform = data.get('platform')
        username = data.get('username', '').strip()
        
        if not platform or not username:
            return Response({
                'success': False,
                'message': 'پلتفرم و نام کاربری الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's store
        store = request.user.stores.first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract content based on platform
        if platform == 'instagram':
            result = SocialMediaExtractor.extract_instagram_content(username)
        elif platform == 'telegram':
            result = SocialMediaExtractor.extract_telegram_content(username)
        else:
            return Response({
                'success': False,
                'message': 'پلتفرم پشتیبانی نمی‌شود'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not result['success']:
            return Response({
                'success': False,
                'message': result.get('error', 'خطا در دریافت محتوا')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Separate content types
        separated_content = SocialMediaExtractor.separate_content(result['posts'])
        
        # Process each post for product suggestions
        processed_posts = []
        for post in separated_content['combined']:
            product_info = SocialMediaExtractor.extract_product_info(post)
            
            processed_post = {
                'id': post['post_id'],
                'text': post['text'],
                'images': post['images'],
                'videos': post['videos'],
                'timestamp': post['timestamp'],
                'platform': platform,
                'suggested_product': product_info,
                'selected': False  # For frontend selection
            }
            processed_posts.append(processed_post)
        
        return Response({
            'success': True,
            'data': {
                'platform': platform,
                'username': username,
                'posts': processed_posts,
                'summary': {
                    'total_posts': len(processed_posts),
                    'total_images': len(separated_content['images']),
                    'total_videos': len(separated_content['videos']),
                    'total_texts': len(separated_content['texts'])
                },
                'extracted_at': result['extracted_at']
            }
        })
        
    except Exception as e:
        logger.error(f"Error in fetch_social_content: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطای سرور در دریافت محتوا'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_social_content(request):
    """Import selected social media content as products"""
    try:
        data = request.data
        selected_posts = data.get('selected_posts', [])
        category_id = data.get('category_id')
        
        if not selected_posts:
            return Response({
                'success': False,
                'message': 'محتوای انتخاب شده یافت نشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's store
        store = request.user.stores.first()
        if not store:
            return Response({
                'success': False,
                'message': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate category if provided
        category = None
        if category_id:
            try:
                from .models import Category
                category = Category.objects.get(id=category_id, store=store)
                
                # Check if category is leaf node
                if category.children.exists():
                    return Response({
                        'success': False,
                        'message': 'فقط در دسته‌های پایانی می‌توان محصول ایجاد کرد'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Category.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'دسته‌بندی یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Import products
        imported_products = []
        failed_imports = []
        
        from .models import Product, ProductImage
        from django.db import transaction
        
        for post_data in selected_posts:
            try:
                with transaction.atomic():
                    suggested = post_data.get('suggested_product', {})
                    
                    # Create product
                    product = Product.objects.create(
                        store=store,
                        category=category,
                        title=suggested.get('suggested_title') or f"محصول از {post_data.get('platform', 'شبکه اجتماعی')}",
                        description=suggested.get('description', ''),
                        short_description=suggested.get('description', '')[:200] if suggested.get('description') else '',
                        price=suggested.get('potential_price') or 0,
                        stock=0,  # Set to 0 initially for review
                        is_active=False,  # Inactive until reviewed
                        track_inventory=True
                    )
                    
                    # Add images
                    for i, image_url in enumerate(post_data.get('images', [])):
                        ProductImage.objects.create(
                            product=product,
                            image=image_url,
                            is_primary=(i == 0),
                            sort_order=i,
                            alt_text=product.title
                        )
                    
                    # Add attributes if extracted
                    attributes = suggested.get('attributes', {})
                    if attributes:
                        from .models import ProductAttribute, ProductAttributeValue
                        
                        for attr_name, attr_value in attributes.items():
                            # Find or create attribute
                            attribute, created = ProductAttribute.objects.get_or_create(
                                store=store,
                                name=attr_name,
                                defaults={
                                    'attribute_type': 'text',
                                    'is_required': False,
                                    'is_filterable': True
                                }
                            )
                            
                            # Create attribute value
                            ProductAttributeValue.objects.create(
                                product=product,
                                attribute=attribute,
                                value=attr_value
                            )
                    
                    imported_products.append({
                        'id': str(product.id),
                        'title': product.title,
                        'price': float(product.price),
                        'platform': post_data.get('platform'),
                        'post_id': post_data.get('id')
                    })
                    
            except Exception as e:
                logger.error(f"Failed to import post {post_data.get('id')}: {str(e)}")
                failed_imports.append({
                    'post_id': post_data.get('id'),
                    'error': str(e)
                })
        
        success_count = len(imported_products)
        failed_count = len(failed_imports)
        
        message = f'{success_count} محصول با موفقیت وارد شد'
        if failed_count > 0:
            message += f' و {failed_count} محصول با خطا مواجه شد'
        
        return Response({
            'success': True,
            'message': message,
            'data': {
                'imported_products': imported_products,
                'failed_imports': failed_imports,
                'summary': {
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'total_processed': len(selected_posts)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error in import_social_content: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطای سرور در وارد کردن محتوا'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
