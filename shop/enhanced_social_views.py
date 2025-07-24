"""
Enhanced Social Media Content API Views for Mall Platform
Provides endpoints for fetching content from Telegram and Instagram
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
import asyncio
import logging
from typing import Dict, Any, List

from .enhanced_social_extractor import fetch_social_media_content
from .authentication import MallTokenAuthentication
from .serializers import SocialMediaContentSerializer

logger = logging.getLogger(__name__)

class SocialMediaContentFetchView(APIView):
    """
    API endpoint to fetch content from social media platforms
    Supports Telegram channels and Instagram accounts
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Fetch content from social media platforms
        
        Expected payload:
        {
            "telegram": "@channel_name or https://t.me/channel_name",
            "instagram": "@username or https://instagram.com/username"
        }
        """
        try:
            # Validate input
            telegram_channel = request.data.get('telegram', '').strip()
            instagram_account = request.data.get('instagram', '').strip()
            
            if not telegram_channel and not instagram_account:
                return Response({
                    'success': False,
                    'message': 'حداقل یک کانال تلگرام یا اکانت اینستاگرام را وارد کنید',
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create cache key based on channels
            cache_key = f"social_content_{hash(f'{telegram_channel}_{instagram_account}')}"
            
            # Check cache first (cache for 30 minutes)
            cached_content = cache.get(cache_key)
            if cached_content:
                logger.info(f"Returning cached social media content for channels: {telegram_channel}, {instagram_account}")
                return Response({
                    'success': True,
                    'message': 'محتوا با موفقیت دریافت شد (از کش)',
                    'data': cached_content,
                    'cached': True
                })
            
            # Prepare channels dict
            channels = {}
            if telegram_channel:
                channels['telegram'] = telegram_channel
            if instagram_account:
                channels['instagram'] = instagram_account
            
            # Fetch content asynchronously
            logger.info(f"Fetching social media content from: {channels}")
            
            try:
                # Run async function in thread pool
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                content_items = loop.run_until_complete(fetch_social_media_content(channels))
                loop.close()
                
            except Exception as fetch_error:
                logger.error(f"Error fetching social media content: {fetch_error}")
                return Response({
                    'success': False,
                    'message': 'خطا در دریافت محتوا از شبکه‌های اجتماعی',
                    'error': str(fetch_error),
                    'data': []
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Validate and serialize content
            try:
                serializer = SocialMediaContentSerializer(data=content_items, many=True)
                if serializer.is_valid():
                    validated_content = serializer.validated_data
                else:
                    logger.warning(f"Content validation errors: {serializer.errors}")
                    validated_content = content_items  # Use raw content if validation fails
                
            except Exception as validation_error:
                logger.error(f"Content validation error: {validation_error}")
                validated_content = content_items  # Use raw content
            
            # Cache the result
            cache.set(cache_key, validated_content, 1800)  # 30 minutes
            
            logger.info(f"Successfully fetched {len(validated_content)} items from social media")
            
            return Response({
                'success': True,
                'message': f'محتوا با موفقیت دریافت شد ({len(validated_content)} مورد)',
                'data': validated_content,
                'cached': False,
                'channels': channels
            })
            
        except Exception as e:
            logger.error(f"Unexpected error in social media content fetch: {e}")
            return Response({
                'success': False,
                'message': 'خطای غیرمنتظره در دریافت محتوا',
                'error': str(e),
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SocialMediaChannelValidationView(APIView):
    """
    Validate social media channel/account URLs
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Validate channel/account URLs and return cleaned names
        
        Expected payload:
        {
            "telegram": "@channel_name or https://t.me/channel_name",
            "instagram": "@username or https://instagram.com/username"
        }
        """
        try:
            telegram_channel = request.data.get('telegram', '').strip()
            instagram_account = request.data.get('instagram', '').strip()
            
            result = {
                'success': True,
                'message': 'اعتبارسنجی با موفقیت انجام شد',
                'channels': {}
            }
            
            # Validate Telegram channel
            if telegram_channel:
                cleaned_telegram = self._clean_telegram_channel(telegram_channel)
                if cleaned_telegram:
                    result['channels']['telegram'] = {
                        'original': telegram_channel,
                        'cleaned': cleaned_telegram,
                        'url': f'https://t.me/{cleaned_telegram}',
                        'valid': True
                    }
                else:
                    result['channels']['telegram'] = {
                        'original': telegram_channel,
                        'valid': False,
                        'error': 'فرمت کانال تلگرام صحیح نیست'
                    }
            
            # Validate Instagram account
            if instagram_account:
                cleaned_instagram = self._clean_instagram_account(instagram_account)
                if cleaned_instagram:
                    result['channels']['instagram'] = {
                        'original': instagram_account,
                        'cleaned': cleaned_instagram,
                        'url': f'https://instagram.com/{cleaned_instagram}',
                        'valid': True
                    }
                else:
                    result['channels']['instagram'] = {
                        'original': instagram_account,
                        'valid': False,
                        'error': 'فرمت اکانت اینستاگرام صحیح نیست'
                    }
            
            if not result['channels']:
                return Response({
                    'success': False,
                    'message': 'هیچ کانال یا اکانتی برای اعتبارسنجی ارسال نشده',
                    'channels': {}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error in channel validation: {e}")
            return Response({
                'success': False,
                'message': 'خطا در اعتبارسنجی کانال‌ها',
                'error': str(e),
                'channels': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _clean_telegram_channel(self, channel: str) -> str:
        """Clean and validate Telegram channel name"""
        if not channel:
            return ""
        
        # Remove common prefixes
        if channel.startswith('https://t.me/'):
            channel = channel.replace('https://t.me/', '').replace('s/', '')
        elif channel.startswith('t.me/'):
            channel = channel.replace('t.me/', '').replace('s/', '')
        elif channel.startswith('@'):
            channel = channel[1:]
        
        # Validate channel name format
        if channel and channel.replace('_', '').replace('-', '').isalnum():
            return channel
        
        return ""

    def _clean_instagram_account(self, account: str) -> str:
        """Clean and validate Instagram account name"""
        if not account:
            return ""
        
        # Remove common prefixes
        if account.startswith('https://instagram.com/'):
            account = account.replace('https://instagram.com/', '').rstrip('/')
        elif account.startswith('https://www.instagram.com/'):
            account = account.replace('https://www.instagram.com/', '').rstrip('/')
        elif account.startswith('instagram.com/'):
            account = account.replace('instagram.com/', '').rstrip('/')
        elif account.startswith('@'):
            account = account[1:]
        
        # Validate account name format
        if account and len(account) <= 30 and account.replace('_', '').replace('.', '').isalnum():
            return account
        
        return ""

class SocialMediaContentHistoryView(APIView):
    """
    Get history of fetched social media content for the authenticated user
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get user's social media content fetch history
        """
        try:
            # This would typically fetch from database
            # For now, return empty history as it's not implemented in the backend
            
            return Response({
                'success': True,
                'message': 'تاریخچه دریافت محتوا',
                'data': {
                    'total_fetches': 0,
                    'recent_channels': [],
                    'last_fetch': None,
                    'most_used_platforms': {
                        'telegram': 0,
                        'instagram': 0
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"Error fetching social media history: {e}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت تاریخچه',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SocialMediaContentPreviewView(APIView):
    """
    Get a quick preview of content from social media channels without full fetch
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def post(self, request):
        """
        Get a quick preview of channel content
        
        Expected payload:
        {
            "telegram": "@channel_name",
            "instagram": "@username"
        }
        """
        try:
            telegram_channel = request.data.get('telegram', '').strip()
            instagram_account = request.data.get('instagram', '').strip()
            
            if not telegram_channel and not instagram_account:
                return Response({
                    'success': False,
                    'message': 'حداقل یک کانال یا اکانت را وارد کنید',
                    'preview': {}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            preview = {}
            
            # Generate preview info (this would typically check if channels exist)
            if telegram_channel:
                cleaned_telegram = self._clean_telegram_channel(telegram_channel)
                preview['telegram'] = {
                    'channel': cleaned_telegram,
                    'url': f'https://t.me/{cleaned_telegram}',
                    'estimated_posts': '10-50 پست اخیر',
                    'content_types': ['متن', 'تصویر', 'ویدیو'],
                    'accessible': True  # This would be checked in real implementation
                }
            
            if instagram_account:
                cleaned_instagram = self._clean_instagram_account(instagram_account)
                preview['instagram'] = {
                    'account': cleaned_instagram,
                    'url': f'https://instagram.com/{cleaned_instagram}',
                    'estimated_posts': '5-20 پست اخیر',
                    'content_types': ['تصویر', 'ویدیو', 'کپشن'],
                    'accessible': True  # This would be checked in real implementation
                }
            
            return Response({
                'success': True,
                'message': 'پیش‌نمایش کانال‌ها آماده شد',
                'preview': preview
            })
            
        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            return Response({
                'success': False,
                'message': 'خطا در تولید پیش‌نمایش',
                'error': str(e),
                'preview': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _clean_telegram_channel(self, channel: str) -> str:
        """Clean Telegram channel name"""
        if channel.startswith('https://t.me/'):
            return channel.replace('https://t.me/', '').replace('s/', '')
        elif channel.startswith('@'):
            return channel[1:]
        return channel

    def _clean_instagram_account(self, account: str) -> str:
        """Clean Instagram account name"""
        if account.startswith('https://instagram.com/'):
            return account.replace('https://instagram.com/', '').rstrip('/')
        elif account.startswith('https://www.instagram.com/'):
            return account.replace('https://www.instagram.com/', '').rstrip('/')
        elif account.startswith('@'):
            return account[1:]
        return account