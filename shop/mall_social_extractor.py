# Mall Platform Social Media Integration
import requests
import json
import re
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from .mall_product_models import ProductMedia
import logging

logger = logging.getLogger(__name__)


class SocialMediaExtractor:
    """Extract content from Instagram and Telegram for product creation"""
    
    def __init__(self):
        # Instagram API configuration
        self.instagram_config = {
            'access_token': getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', ''),
            'business_id': getattr(settings, 'INSTAGRAM_BUSINESS_ID', ''),
            'api_version': 'v18.0',
            'base_url': 'https://graph.facebook.com'
        }
        
        # Telegram Bot API configuration
        self.telegram_config = {
            'bot_token': getattr(settings, 'TELEGRAM_BOT_TOKEN', ''),
            'api_url': 'https://api.telegram.org/bot'
        }
        
        # Content filtering keywords (Persian and English)
        self.product_keywords = [
            'محصول', 'کالا', 'فروش', 'خرید', 'قیمت', 'تخفیف', 'جدید', 'موجود',
            'product', 'sale', 'buy', 'price', 'discount', 'new', 'available',
            'پوشاک', 'لباس', 'کفش', 'کیف', 'ساعت', 'عطر', 'آرایش',
            'clothing', 'fashion', 'shoes', 'bag', 'watch', 'perfume', 'makeup'
        ]
    
    def extract_instagram_content(self, username_or_url, limit=5):
        """Extract latest posts and stories from Instagram"""
        try:
            # Parse username from URL if needed
            username = self._extract_username_from_instagram_url(username_or_url)
            
            if not self.instagram_config['access_token']:
                return self._mock_instagram_content(username, limit)
            
            # Get user media using Instagram Basic Display API
            user_id = self._get_instagram_user_id(username)
            if not user_id:
                return {'success': False, 'message': 'کاربر اینستاگرام یافت نشد'}
            
            media_data = self._fetch_instagram_media(user_id, limit)
            
            # Process and categorize content
            processed_content = self._process_instagram_media(media_data)
            
            return {
                'success': True,
                'platform': 'instagram',
                'username': username,
                'content': processed_content
            }
            
        except Exception as e:
            logger.error(f"Instagram extraction error: {str(e)}")
            return {
                'success': False,
                'message': 'خطا در استخراج محتوا از اینستاگرام',
                'error': str(e)
            }
    
    def extract_telegram_content(self, channel_username, limit=5):
        """Extract latest posts from Telegram channel"""
        try:
            # Clean channel username
            channel_username = channel_username.replace('@', '').replace('https://t.me/', '')
            
            if not self.telegram_config['bot_token']:
                return self._mock_telegram_content(channel_username, limit)
            
            # Get channel info and recent messages
            channel_info = self._get_telegram_channel_info(channel_username)
            if not channel_info:
                return {'success': False, 'message': 'کانال تلگرام یافت نشد'}
            
            messages = self._fetch_telegram_messages(channel_username, limit)
            
            # Process and categorize content
            processed_content = self._process_telegram_messages(messages)
            
            return {
                'success': True,
                'platform': 'telegram',
                'channel': channel_username,
                'content': processed_content
            }
            
        except Exception as e:
            logger.error(f"Telegram extraction error: {str(e)}")
            return {
                'success': False,
                'message': 'خطا در استخراج محتوا از تلگرام',
                'error': str(e)
            }
    
    def _extract_username_from_instagram_url(self, url_or_username):
        """Extract username from Instagram URL"""
        if url_or_username.startswith('http'):
            # Extract from URL like https://instagram.com/username
            match = re.search(r'instagram\.com/([^/?]+)', url_or_username)
            return match.group(1) if match else url_or_username
        return url_or_username.replace('@', '')
    
    def _get_instagram_user_id(self, username):
        """Get Instagram user ID from username"""
        try:
            # This would require Instagram Basic Display API setup
            # For now, return mock data
            return f"mock_user_id_{username}"
        except Exception as e:
            logger.error(f"Error getting Instagram user ID: {e}")
            return None
    
    def _fetch_instagram_media(self, user_id, limit):
        """Fetch media from Instagram API"""
        try:
            url = f"{self.instagram_config['base_url']}/{self.instagram_config['api_version']}/{user_id}/media"
            params = {
                'fields': 'id,media_type,media_url,thumbnail_url,caption,timestamp,permalink',
                'limit': limit,
                'access_token': self.instagram_config['access_token']
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json().get('data', [])
            else:
                logger.error(f"Instagram API error: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching Instagram media: {e}")
            return []
    
    def _get_telegram_channel_info(self, channel_username):
        """Get Telegram channel information"""
        try:
            url = f"{self.telegram_config['api_url']}{self.telegram_config['bot_token']}/getChat"
            params = {'chat_id': f"@{channel_username}"}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('result') if result.get('ok') else None
            return None
            
        except Exception as e:
            logger.error(f"Error getting Telegram channel info: {e}")
            return None
    
    def _fetch_telegram_messages(self, channel_username, limit):
        """Fetch recent messages from Telegram channel"""
        try:
            # Note: This requires the bot to be added to the channel
            # Or use unofficial Telegram APIs (not recommended for production)
            
            # For demo purposes, return mock data
            return self._mock_telegram_messages(channel_username, limit)
            
        except Exception as e:
            logger.error(f"Error fetching Telegram messages: {e}")
            return []
    
    def _process_instagram_media(self, media_data):
        """Process and categorize Instagram media"""
        images = []
        videos = []
        texts = []
        
        for item in media_data:
            # Extract text content
            caption = item.get('caption', '')
            if caption and self._is_product_related(caption):
                texts.append({
                    'id': item['id'],
                    'text': caption,
                    'timestamp': item.get('timestamp'),
                    'url': item.get('permalink'),
                    'source': 'instagram'
                })
            
            # Process media based on type
            if item.get('media_type') == 'IMAGE':
                images.append({
                    'id': item['id'],
                    'url': item.get('media_url'),
                    'thumbnail': item.get('thumbnail_url'),
                    'caption': caption,
                    'timestamp': item.get('timestamp'),
                    'source': 'instagram',
                    'type': 'image'
                })
            elif item.get('media_type') == 'VIDEO':
                videos.append({
                    'id': item['id'],
                    'url': item.get('media_url'),
                    'thumbnail': item.get('thumbnail_url'),
                    'caption': caption,
                    'timestamp': item.get('timestamp'),
                    'source': 'instagram',
                    'type': 'video'
                })
        
        return {
            'images': images,
            'videos': videos,
            'texts': texts,
            'total_items': len(media_data)
        }
    
    def _process_telegram_messages(self, messages):
        """Process and categorize Telegram messages"""
        images = []
        videos = []
        texts = []
        
        for message in messages:
            # Extract text content
            text = message.get('text', '')
            if text and self._is_product_related(text):
                texts.append({
                    'id': message.get('message_id'),
                    'text': text,
                    'timestamp': message.get('date'),
                    'source': 'telegram',
                    'type': 'text'
                })
            
            # Process media
            if 'photo' in message:
                photo = message['photo'][-1]  # Get largest photo
                images.append({
                    'id': f"{message.get('message_id')}_photo",
                    'file_id': photo.get('file_id'),
                    'caption': message.get('caption', ''),
                    'timestamp': message.get('date'),
                    'source': 'telegram',
                    'type': 'image'
                })
            
            if 'video' in message:
                video = message['video']
                videos.append({
                    'id': f"{message.get('message_id')}_video",
                    'file_id': video.get('file_id'),
                    'thumbnail': video.get('thumb'),
                    'caption': message.get('caption', ''),
                    'duration': video.get('duration'),
                    'timestamp': message.get('date'),
                    'source': 'telegram',
                    'type': 'video'
                })
        
        return {
            'images': images,
            'videos': videos,
            'texts': texts,
            'total_items': len(messages)
        }
    
    def _is_product_related(self, text):
        """Check if text content is product-related"""
        if not text:
            return False
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.product_keywords)
    
    def _mock_instagram_content(self, username, limit):
        """Return mock Instagram content for development"""
        mock_content = {
            'images': [
                {
                    'id': f'mock_img_{i}',
                    'url': f'https://picsum.photos/800/600?random={i}',
                    'thumbnail': f'https://picsum.photos/300/300?random={i}',
                    'caption': f'محصول جدید شماره {i} - کیفیت عالی و قیمت مناسب',
                    'timestamp': (timezone.now() - timedelta(days=i)).isoformat(),
                    'source': 'instagram',
                    'type': 'image'
                }
                for i in range(1, min(limit + 1, 4))
            ],
            'videos': [
                {
                    'id': 'mock_video_1',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': 'https://picsum.photos/400/300?random=video',
                    'caption': 'ویدیو معرفی محصولات جدید',
                    'timestamp': (timezone.now() - timedelta(days=1)).isoformat(),
                    'source': 'instagram',
                    'type': 'video'
                }
            ],
            'texts': [
                {
                    'id': f'mock_text_{i}',
                    'text': f'🔥 فروش ویژه محصول {i}\n✅ کیفیت تضمینی\n💰 قیمت استثنائی\n📞 سفارش: ۰۹۱۲۳۴۵۶۷۸۹',
                    'timestamp': (timezone.now() - timedelta(days=i)).isoformat(),
                    'source': 'instagram',
                    'type': 'text'
                }
                for i in range(1, 3)
            ],
            'total_items': limit
        }
        
        return {
            'success': True,
            'platform': 'instagram',
            'username': username,
            'content': mock_content,
            'is_mock': True
        }
    
    def _mock_telegram_content(self, channel_username, limit):
        """Return mock Telegram content for development"""
        mock_content = {
            'images': [
                {
                    'id': f'mock_tg_img_{i}',
                    'file_id': f'mock_file_id_{i}',
                    'url': f'https://picsum.photos/600/600?random={i+10}',
                    'caption': f'کانال تلگرام - محصول {i}',
                    'timestamp': (timezone.now() - timedelta(hours=i*2)).isoformat(),
                    'source': 'telegram',
                    'type': 'image'
                }
                for i in range(1, min(limit + 1, 4))
            ],
            'videos': [
                {
                    'id': 'mock_tg_video_1',
                    'file_id': 'mock_video_file_id',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': 'https://picsum.photos/400/300?random=tgvideo',
                    'caption': 'ویدیو محصولات از کانال تلگرام',
                    'duration': 30,
                    'timestamp': (timezone.now() - timedelta(hours=6)).isoformat(),
                    'source': 'telegram',
                    'type': 'video'
                }
            ],
            'texts': [
                {
                    'id': f'mock_tg_text_{i}',
                    'text': f'📢 اعلان کانال تلگرام {i}\n🛍️ محصولات با کیفیت\n🚚 ارسال رایگان\n💎 گارانتی اصالت کالا',
                    'timestamp': (timezone.now() - timedelta(hours=i*3)).isoformat(),
                    'source': 'telegram',
                    'type': 'text'
                }
                for i in range(1, 3)
            ],
            'total_items': limit
        }
        
        return {
            'success': True,
            'platform': 'telegram',
            'channel': channel_username,
            'content': mock_content,
            'is_mock': True
        }
    
    def _mock_telegram_messages(self, channel_username, limit):
        """Mock Telegram messages for development"""
        return [
            {
                'message_id': i,
                'text': f'پیام نمونه {i} از کانال {channel_username}',
                'date': (timezone.now() - timedelta(hours=i)).timestamp(),
                'photo': [
                    {'file_id': f'photo_file_{i}', 'width': 800, 'height': 600}
                ] if i % 2 == 0 else None,
                'caption': f'توضیحات تصویر {i}' if i % 2 == 0 else None
            }
            for i in range(1, limit + 1)
        ]
    
    def download_and_save_media(self, media_item, store_id=None):
        """Download media file and save to ProductMedia"""
        try:
            media_url = media_item.get('url')
            if not media_url:
                return None
            
            # Download media file
            response = requests.get(media_url, timeout=30)
            if response.status_code != 200:
                return None
            
            # Determine media type
            media_type = 'video' if media_item.get('type') == 'video' else 'image'
            
            # Create ProductMedia instance
            media = ProductMedia.objects.create(
                media_type=media_type,
                title=media_item.get('caption', '')[:200],
                alt_text=media_item.get('caption', '')[:200],
                description=media_item.get('caption', ''),
                social_source=media_item.get('source'),
                social_url=media_item.get('url'),
                social_id=media_item.get('id', '')
            )
            
            # Save file content
            file_name = f"{media_type}_{media.uuid}.jpg"
            media.file.save(file_name, response.content, save=True)
            
            # Generate thumbnail for videos
            if media_type == 'video' and media_item.get('thumbnail'):
                try:
                    thumb_response = requests.get(media_item['thumbnail'], timeout=10)
                    if thumb_response.status_code == 200:
                        thumb_name = f"thumb_{media.uuid}.jpg"
                        media.thumbnail.save(thumb_name, thumb_response.content, save=True)
                except Exception:
                    pass
            
            return media
            
        except Exception as e:
            logger.error(f"Error downloading media: {e}")
            return None
    
    def extract_product_info_from_text(self, text):
        """Extract potential product information from text using NLP"""
        if not text:
            return {}
        
        # Simple extraction patterns (can be enhanced with NLP libraries)
        product_info = {}
        
        # Extract price information
        price_patterns = [
            r'(\d{1,3}(?:,\d{3})*)\s*(?:تومان|ریال|درهم)',
            r'قیمت[:\s]*(\d{1,3}(?:,\d{3})*)',
            r'(\d{1,3}(?:,\d{3})*)\s*(?:هزار\s*)?تومان'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    product_info['suggested_price'] = int(price_str)
                    break
                except ValueError:
                    continue
        
        # Extract product name (first line or before price)
        lines = text.split('\n')
        if lines:
            # Clean first line from emojis and extra characters
            first_line = re.sub(r'[^\w\s\u0600-\u06FF]', '', lines[0]).strip()
            if first_line and len(first_line) > 3:
                product_info['suggested_name'] = first_line[:100]
        
        # Extract features/description
        feature_keywords = ['ویژگی', 'مشخصات', 'توضیحات', 'جنس', 'سایز', 'رنگ']
        description_parts = []
        
        for line in lines[1:]:  # Skip first line (usually product name)
            line_clean = line.strip()
            if line_clean and not any(char in line_clean for char in ['@', '#', 'http']):
                if any(keyword in line_clean for keyword in feature_keywords):
                    description_parts.append(line_clean)
        
        if description_parts:
            product_info['suggested_description'] = '\n'.join(description_parts)
        
        # Extract hashtags as potential tags
        hashtags = re.findall(r'#(\w+)', text)
        if hashtags:
            product_info['suggested_tags'] = hashtags[:10]  # Limit to 10 tags
        
        return product_info
    
    def get_combined_content(self, instagram_url=None, telegram_channel=None, limit=5):
        """Get combined content from both Instagram and Telegram"""
        results = {
            'instagram': None,
            'telegram': None,
            'combined_summary': {
                'total_images': 0,
                'total_videos': 0,
                'total_texts': 0,
                'suggested_products': []
            }
        }
        
        # Extract from Instagram
        if instagram_url:
            instagram_result = self.extract_instagram_content(instagram_url, limit)
            results['instagram'] = instagram_result
            
            if instagram_result.get('success'):
                content = instagram_result['content']
                results['combined_summary']['total_images'] += len(content.get('images', []))
                results['combined_summary']['total_videos'] += len(content.get('videos', []))
                results['combined_summary']['total_texts'] += len(content.get('texts', []))
        
        # Extract from Telegram
        if telegram_channel:
            telegram_result = self.extract_telegram_content(telegram_channel, limit)
            results['telegram'] = telegram_result
            
            if telegram_result.get('success'):
                content = telegram_result['content']
                results['combined_summary']['total_images'] += len(content.get('images', []))
                results['combined_summary']['total_videos'] += len(content.get('videos', []))
                results['combined_summary']['total_texts'] += len(content.get('texts', []))
        
        # Generate product suggestions from text content
        all_texts = []
        if results['instagram'] and results['instagram'].get('success'):
            all_texts.extend(results['instagram']['content'].get('texts', []))
        if results['telegram'] and results['telegram'].get('success'):
            all_texts.extend(results['telegram']['content'].get('texts', []))
        
        for text_item in all_texts[:3]:  # Limit to 3 suggestions
            product_info = self.extract_product_info_from_text(text_item.get('text', ''))
            if product_info:
                product_info['source'] = text_item.get('source')
                product_info['original_text'] = text_item.get('text', '')[:200]
                results['combined_summary']['suggested_products'].append(product_info)
        
        return results


# Global instance
social_extractor = SocialMediaExtractor()
