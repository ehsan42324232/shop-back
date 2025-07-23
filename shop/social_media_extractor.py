import requests
import json
import re
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SocialMediaExtractor:
    """Extract content from Instagram and Telegram for Mall platform"""
    
    @staticmethod
    def extract_instagram_content(username):
        """Extract recent posts from Instagram"""
        try:
            # Remove @ if present
            username = username.replace('@', '')
            
            # This would integrate with Instagram Basic Display API
            # For now, returning mock data structure
            posts = []
            
            # Mock data for demonstration
            for i in range(5):
                post = {
                    'id': f'ig_post_{i}',
                    'type': 'image',
                    'caption': f'نمونه محتوای اینستاگرام {i+1}',
                    'images': [f'https://picsum.photos/400/400?random={i}'],
                    'videos': [],
                    'timestamp': (datetime.now() - timedelta(days=i)).isoformat(),
                    'engagement': {
                        'likes': 100 + i * 20,
                        'comments': 10 + i * 5
                    }
                }
                posts.append(post)
            
            return {
                'success': True,
                'platform': 'instagram',
                'username': username,
                'posts': posts,
                'extracted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Instagram extraction error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در دریافت محتوا از اینستاگرام'
            }
    
    @staticmethod
    def extract_telegram_content(channel_name):
        """Extract recent posts from Telegram channel"""
        try:
            # Remove @ if present
            channel_name = channel_name.replace('@', '')
            
            # This would integrate with Telegram Bot API
            # For now, returning mock data structure
            posts = []
            
            # Mock data for demonstration
            for i in range(5):
                post = {
                    'id': f'tg_post_{i}',
                    'type': 'mixed',
                    'text': f'محتوای نمونه تلگرام {i+1}\n\nاین یک متن تست است برای نمایش قابلیت استخراج محتوا.',
                    'images': [f'https://picsum.photos/300/300?random={i+10}'] if i % 2 == 0 else [],
                    'videos': [f'https://sample-videos.com/zip/10/mp4/SampleVideo_{i}.mp4'] if i % 3 == 0 else [],
                    'timestamp': (datetime.now() - timedelta(hours=i*2)).isoformat(),
                    'views': 500 + i * 100
                }
                posts.append(post)
            
            return {
                'success': True,
                'platform': 'telegram',
                'channel': channel_name,
                'posts': posts,
                'extracted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Telegram extraction error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در دریافت محتوا از تلگرام'
            }
    
    @staticmethod
    def separate_content(posts):
        """Separate images, videos, and text from posts"""
        separated = {
            'images': [],
            'videos': [],
            'texts': [],
            'combined': []
        }
        
        for post in posts:
            # Extract and clean text
            text = post.get('caption') or post.get('text', '')
            if text:
                # Clean text from hashtags and mentions for product descriptions
                clean_text = re.sub(r'#\w+', '', text)
                clean_text = re.sub(r'@\w+', '', clean_text)
                clean_text = clean_text.strip()
                
                if clean_text:
                    separated['texts'].append({
                        'text': clean_text,
                        'original': text,
                        'post_id': post['id'],
                        'timestamp': post['timestamp']
                    })
            
            # Extract images
            for image in post.get('images', []):
                separated['images'].append({
                    'url': image,
                    'post_id': post['id'],
                    'timestamp': post['timestamp']
                })
            
            # Extract videos
            for video in post.get('videos', []):
                separated['videos'].append({
                    'url': video,
                    'post_id': post['id'],
                    'timestamp': post['timestamp']
                })
            
            # Combined content for easy selection
            separated['combined'].append({
                'post_id': post['id'],
                'text': text,
                'images': post.get('images', []),
                'videos': post.get('videos', []),
                'timestamp': post['timestamp'],
                'platform': post.get('platform', 'unknown')
            })
        
        return separated
    
    @staticmethod
    def extract_product_info(content):
        """Extract potential product information from social media content"""
        product_info = {
            'suggested_title': '',
            'description': '',
            'potential_price': None,
            'attributes': {}
        }
        
        text = content.get('text', '')
        if not text:
            return product_info
        
        # Extract potential product title (first line or first sentence)
        lines = text.split('\n')
        if lines:
            product_info['suggested_title'] = lines[0][:100]  # Limit title length
        
        # Use full text as description
        product_info['description'] = text
        
        # Try to extract price (Iranian Toman patterns)
        price_patterns = [
            r'(\d+(?:,\d{3})*)\s*تومان',
            r'(\d+(?:,\d{3})*)\s*ت',
            r'قیمت[:\s]*(\d+(?:,\d{3})*)',
            r'(\d+)هزار\s*تومان'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    if 'هزار' in match.group(0):
                        product_info['potential_price'] = int(price_str) * 1000
                    else:
                        product_info['potential_price'] = int(price_str)
                    break
                except ValueError:
                    continue
        
        # Extract potential attributes
        color_patterns = [
            r'رنگ[:\s]*([\w\s]+)',
            r'(قرمز|آبی|سبز|زرد|مشکی|سفید|صورتی|بنفش|نارنجی|خاکستری)',
            r'(قهوه‌ای|کرم|طلایی|نقره‌ای|یاسی|زیتونی)'
        ]
        
        for pattern in color_patterns:
            match = re.search(pattern, text)
            if match:
                product_info['attributes']['رنگ'] = match.group(1).strip()
                break
        
        # Extract size information
        size_patterns = [
            r'سایز[:\s]*([\w\s]+)',
            r'اندازه[:\s]*([\w\s]+)',
            r'(XS|S|M|L|XL|XXL)',
            r'(\d+(?:-\d+)?)',
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, text)
            if match:
                product_info['attributes']['سایز'] = match.group(1).strip()
                break
        
        return product_info
