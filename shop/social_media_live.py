# shop/social_media_live.py
"""
Mall Platform - Live Social Media Integration
Real API integration with Instagram and Telegram
"""
import requests
import logging
from typing import Dict, List, Any, Optional
from django.conf import settings
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class InstagramAPI:
    """Live Instagram API integration"""
    
    def __init__(self, access_token: str, business_account_id: str):
        self.access_token = access_token
        self.business_account_id = business_account_id
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def get_recent_posts(self, limit: int = 5) -> Dict[str, Any]:
        """Get recent Instagram posts"""
        try:
            url = f"{self.base_url}/{self.business_account_id}/media"
            params = {
                'fields': 'id,caption,media_type,media_url,permalink,timestamp',
                'limit': limit,
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if 'data' in data:
                posts = []
                for post in data['data']:
                    extracted_content = self._extract_content_from_post(post)
                    posts.append(extracted_content)
                
                return {
                    'success': True,
                    'posts': posts,
                    'count': len(posts)
                }
            else:
                return {
                    'success': False,
                    'error': data.get('error', {}).get('message', 'خطا در دریافت پست‌ها')
                }
                
        except Exception as e:
            logger.error(f"Instagram API error: {e}")
            return {
                'success': False,
                'error': 'خطا در اتصال به Instagram'
            }
    
    def get_stories(self) -> Dict[str, Any]:
        """Get Instagram stories"""
        try:
            url = f"{self.base_url}/{self.business_account_id}/stories"
            params = {
                'fields': 'id,media_type,media_url,timestamp',
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if 'data' in data:
                stories = []
                for story in data['data']:
                    stories.append({
                        'id': story.get('id'),
                        'media_type': story.get('media_type'),
                        'media_url': story.get('media_url'),
                        'timestamp': story.get('timestamp'),
                        'platform': 'instagram'
                    })
                
                return {
                    'success': True,
                    'stories': stories,
                    'count': len(stories)
                }
            else:
                return {
                    'success': False,
                    'error': 'خطا در دریافت استوری‌ها'
                }
                
        except Exception as e:
            logger.error(f"Instagram Stories API error: {e}")
            return {
                'success': False,
                'error': 'خطا در دریافت استوری‌ها'
            }
    
    def _extract_content_from_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Extract useful content from Instagram post"""
        caption = post.get('caption', '')
        media_url = post.get('media_url', '')
        media_type = post.get('media_type', 'IMAGE')
        
        # Extract hashtags and mentions
        hashtags = re.findall(r'#\w+', caption)
        mentions = re.findall(r'@\w+', caption)
        
        # Clean caption for product description
        clean_caption = re.sub(r'#\w+|@\w+', '', caption).strip()
        clean_caption = re.sub(r'\s+', ' ', clean_caption)
        
        # Detect product-related keywords
        product_keywords = self._detect_product_keywords(caption)
        
        return {
            'id': post.get('id'),
            'caption': caption,
            'clean_description': clean_caption,
            'media_url': media_url,
            'media_type': media_type,
            'hashtags': hashtags,
            'mentions': mentions,
            'product_keywords': product_keywords,
            'timestamp': post.get('timestamp'),
            'permalink': post.get('permalink'),
            'platform': 'instagram',
            'suggested_product_name': self._suggest_product_name(clean_caption),
            'price_mentions': self._extract_prices(caption)
        }
    
    def _detect_product_keywords(self, text: str) -> List[str]:
        """Detect product-related keywords in Persian and English"""
        keywords = {
            'clothing': ['لباس', 'پیراهن', 'شلوار', 'کت', 'مانتو', 'تیشرت', 'dress', 'shirt', 'pants'],
            'electronics': ['موبایل', 'گوشی', 'تبلت', 'لپ‌تاپ', 'هدفون', 'phone', 'tablet', 'laptop'],
            'beauty': ['آرایش', 'کرم', 'لوسیون', 'شامپو', 'makeup', 'cream', 'beauty'],
            'home': ['خانه', 'آشپزخانه', 'دکوراسیون', 'مبل', 'home', 'kitchen', 'furniture'],
            'food': ['غذا', 'خوراکی', 'شیرینی', 'نوشیدنی', 'food', 'snack', 'drink']
        }
        
        detected = []
        text_lower = text.lower()
        
        for category, words in keywords.items():
            for word in words:
                if word in text_lower:
                    detected.append(category)
                    break
        
        return list(set(detected))
    
    def _suggest_product_name(self, text: str) -> str:
        """Suggest product name from text"""
        # Remove common words and keep meaningful parts
        words = text.split()
        meaningful_words = []
        
        stop_words = ['در', 'با', 'به', 'از', 'که', 'این', 'آن', 'و', 'the', 'a', 'an', 'in', 'on', 'at']
        
        for word in words[:5]:  # Take first 5 words
            if word.lower() not in stop_words and len(word) > 2:
                meaningful_words.append(word)
        
        return ' '.join(meaningful_words)
    
    def _extract_prices(self, text: str) -> List[Dict[str, Any]]:
        """Extract price mentions from text"""
        # Persian number patterns
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        english_digits = '0123456789'
        
        price_patterns = [
            r'(\d+)\s*تومان',
            r'(\d+)\s*ريال',
            r'([۰-۹]+)\s*تومان',
            r'([۰-۹]+)\s*ريال',
            r'قیمت[:\s]*(\d+)',
            r'قیمت[:\s]*([۰-۹]+)'
        ]
        
        prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Convert Persian digits to English
                price_str = match
                for i, persian_digit in enumerate(persian_digits):
                    price_str = price_str.replace(persian_digit, english_digits[i])
                
                try:
                    price_value = int(price_str)
                    prices.append({
                        'value': price_value,
                        'currency': 'تومان' if 'تومان' in pattern else 'ریال',
                        'original_text': match
                    })
                except ValueError:
                    continue
        
        return prices


class TelegramAPI:
    """Live Telegram Bot API integration"""
    
    def __init__(self, bot_token: str, channel_username: str):
        self.bot_token = bot_token
        self.channel_username = channel_username
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def get_channel_posts(self, limit: int = 5) -> Dict[str, Any]:
        """Get recent channel posts"""
        try:
            # Get channel info first
            channel_info = self._get_channel_info()
            if not channel_info['success']:
                return channel_info
            
            # Get recent messages
            url = f"{self.base_url}/getUpdates"
            params = {
                'limit': limit * 2,  # Get more to filter channel posts
                'offset': -1
            }
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if data.get('ok'):
                posts = []
                for update in data.get('result', []):
                    message = update.get('message') or update.get('channel_post')
                    if message and self._is_channel_message(message):
                        extracted_content = self._extract_content_from_message(message)
                        posts.append(extracted_content)
                
                return {
                    'success': True,
                    'posts': posts[:limit],  # Return only requested limit
                    'count': len(posts)
                }
            else:
                return {
                    'success': False,
                    'error': data.get('description', 'خطا در دریافت پیام‌ها')
                }
                
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return {
                'success': False,
                'error': 'خطا در اتصال به Telegram'
            }
    
    def _get_channel_info(self) -> Dict[str, Any]:
        """Get channel information"""
        try:
            url = f"{self.base_url}/getChat"
            params = {'chat_id': f"@{self.channel_username}"}
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if data.get('ok'):
                return {
                    'success': True,
                    'channel_info': data.get('result')
                }
            else:
                return {
                    'success': False,
                    'error': 'کانال یافت نشد یا دسترسی وجود ندارد'
                }
                
        except Exception as e:
            logger.error(f"Telegram channel info error: {e}")
            return {
                'success': False,
                'error': 'خطا در دریافت اطلاعات کانال'
            }
    
    def _is_channel_message(self, message: Dict[str, Any]) -> bool:
        """Check if message is from the target channel"""
        chat = message.get('chat', {})
        return chat.get('username') == self.channel_username
    
    def _extract_content_from_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content from Telegram message"""
        text = message.get('text', '')
        photo = message.get('photo')
        video = message.get('video')
        document = message.get('document')
        
        # Get media information
        media_info = None
        media_type = 'text'
        
        if photo:
            # Get largest photo
            largest_photo = max(photo, key=lambda p: p.get('file_size', 0))
            media_info = {
                'file_id': largest_photo.get('file_id'),
                'file_size': largest_photo.get('file_size'),
                'width': largest_photo.get('width'),
                'height': largest_photo.get('height')
            }
            media_type = 'photo'
        elif video:
            media_info = {
                'file_id': video.get('file_id'),
                'duration': video.get('duration'),
                'width': video.get('width'),
                'height': video.get('height')
            }
            media_type = 'video'
        elif document:
            media_info = {
                'file_id': document.get('file_id'),
                'file_name': document.get('file_name'),
                'file_size': document.get('file_size')
            }
            media_type = 'document'
        
        # Extract hashtags and mentions
        hashtags = re.findall(r'#\w+', text)
        mentions = re.findall(r'@\w+', text)
        
        # Clean text
        clean_text = re.sub(r'#\w+|@\w+', '', text).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        return {
            'message_id': message.get('message_id'),
            'text': text,
            'clean_description': clean_text,
            'media_type': media_type,
            'media_info': media_info,
            'hashtags': hashtags,
            'mentions': mentions,
            'date': message.get('date'),
            'platform': 'telegram',
            'suggested_product_name': self._suggest_product_name(clean_text),
            'product_keywords': self._detect_product_keywords(text),
            'price_mentions': self._extract_prices(text)
        }
    
    def _suggest_product_name(self, text: str) -> str:
        """Suggest product name from text"""
        words = text.split()
        meaningful_words = []
        
        stop_words = ['در', 'با', 'به', 'از', 'که', 'این', 'آن', 'و']
        
        for word in words[:5]:
            if word not in stop_words and len(word) > 2:
                meaningful_words.append(word)
        
        return ' '.join(meaningful_words)
    
    def _detect_product_keywords(self, text: str) -> List[str]:
        """Detect product keywords"""
        # Same logic as Instagram
        keywords = {
            'clothing': ['لباس', 'پیراهن', 'شلوار', 'کت', 'مانتو', 'تیشرت'],
            'electronics': ['موبایل', 'گوشی', 'تبلت', 'لپ‌تاپ', 'هدفون'],
            'beauty': ['آرایش', 'کرم', 'لوسیون', 'شامپو'],
            'home': ['خانه', 'آشپزخانه', 'دکوراسیون', 'مبل'],
            'food': ['غذا', 'خوراکی', 'شیرینی', 'نوشیدنی']
        }
        
        detected = []
        text_lower = text.lower()
        
        for category, words in keywords.items():
            for word in words:
                if word in text_lower:
                    detected.append(category)
                    break
        
        return list(set(detected))
    
    def _extract_prices(self, text: str) -> List[Dict[str, Any]]:
        """Extract prices from text"""
        # Same logic as Instagram
        price_patterns = [
            r'(\d+)\s*تومان',
            r'(\d+)\s*ريال',
            r'([۰-۹]+)\s*تومان',
            r'قیمت[:\s]*(\d+)'
        ]
        
        prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # Convert Persian digits
                    price_str = match
                    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
                    english_digits = '0123456789'
                    
                    for i, persian_digit in enumerate(persian_digits):
                        price_str = price_str.replace(persian_digit, english_digits[i])
                    
                    price_value = int(price_str)
                    prices.append({
                        'value': price_value,
                        'currency': 'تومان',
                        'original_text': match
                    })
                except ValueError:
                    continue
        
        return prices


class SocialMediaLiveManager:
    """Live social media content manager"""
    
    def __init__(self):
        self.instagram_api = None
        self.telegram_api = None
        self._load_apis()
    
    def _load_apis(self):
        """Load API configurations"""
        try:
            social_config = getattr(settings, 'LIVE_SOCIAL_MEDIA', {})
            
            # Instagram
            instagram_config = social_config.get('instagram', {})
            if instagram_config.get('enabled'):
                self.instagram_api = InstagramAPI(
                    instagram_config['access_token'],
                    instagram_config['business_account_id']
                )
            
            # Telegram
            telegram_config = social_config.get('telegram', {})
            if telegram_config.get('enabled'):
                self.telegram_api = TelegramAPI(
                    telegram_config['bot_token'],
                    telegram_config['channel_username']
                )
                
        except Exception as e:
            logger.error(f"Failed to load social media APIs: {e}")
    
    def get_social_content(self, platforms: List[str] = None, limit: int = 5) -> Dict[str, Any]:
        """Get content from social media platforms"""
        if platforms is None:
            platforms = ['instagram', 'telegram']
        
        all_content = {
            'posts': [],
            'stories': [],
            'total_posts': 0,
            'total_stories': 0,
            'success': True,
            'errors': []
        }
        
        # Instagram content
        if 'instagram' in platforms and self.instagram_api:
            try:
                posts_result = self.instagram_api.get_recent_posts(limit)
                if posts_result['success']:
                    all_content['posts'].extend(posts_result['posts'])
                    all_content['total_posts'] += posts_result['count']
                else:
                    all_content['errors'].append(f"Instagram: {posts_result['error']}")
                
                # Get stories
                stories_result = self.instagram_api.get_stories()
                if stories_result['success']:
                    all_content['stories'].extend(stories_result['stories'])
                    all_content['total_stories'] += stories_result['count']
                    
            except Exception as e:
                all_content['errors'].append(f"Instagram error: {e}")
        
        # Telegram content
        if 'telegram' in platforms and self.telegram_api:
            try:
                posts_result = self.telegram_api.get_channel_posts(limit)
                if posts_result['success']:
                    all_content['posts'].extend(posts_result['posts'])
                    all_content['total_posts'] += posts_result['count']
                else:
                    all_content['errors'].append(f"Telegram: {posts_result['error']}")
                    
            except Exception as e:
                all_content['errors'].append(f"Telegram error: {e}")
        
        # Sort posts by date
        all_content['posts'].sort(
            key=lambda x: x.get('timestamp') or x.get('date', 0), 
            reverse=True
        )
        
        return all_content


# Global social media manager
live_social_manager = SocialMediaLiveManager()
