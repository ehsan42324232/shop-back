# Complete Social Media Integration
# Instagram and Telegram content fetching with media download

import requests
import json
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

class InstagramIntegrator:
    """Instagram content fetcher"""
    
    def __init__(self, store):
        self.store = store
        self.access_token = getattr(store, 'instagram_token', None)
    
    def fetch_content(self, limit=5):
        """Fetch recent Instagram posts"""
        if not self.access_token:
            return []
        
        try:
            # Instagram Basic Display API
            url = f"https://graph.instagram.com/me/media"
            params = {
                'fields': 'id,caption,media_type,media_url,thumbnail_url,timestamp',
                'access_token': self.access_token,
                'limit': limit
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            content_list = []
            
            for item in data.get('data', []):
                content_data = {
                    'platform': 'instagram',
                    'external_id': item['id'],
                    'content_type': 'image' if item['media_type'] == 'IMAGE' else 'video',
                    'text_content': item.get('caption', ''),
                    'media_urls': [item.get('media_url', '')],
                    'post_date': datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')),
                    'raw_data': item
                }
                content_list.append(content_data)
            
            return content_list
            
        except Exception as e:
            logger.error(f"Instagram fetch error: {str(e)}")
            return []

class TelegramBotIntegrator:
    """Telegram bot integration for channel content"""
    
    def __init__(self, store):
        self.store = store
        self.bot_token = getattr(store, 'telegram_bot_token', None)
        self.channel_id = getattr(store, 'telegram_channel_id', None)
    
    def fetch_content(self, limit=5):
        """Fetch recent Telegram channel posts"""
        if not self.bot_token or not self.channel_id:
            return []
        
        try:
            # Use getUpdates to get recent messages
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'limit': limit, 'offset': -limit}
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            content_list = []
            
            for update in data.get('result', []):
                if 'channel_post' in update:
                    post = update['channel_post']
                    content_data = {
                        'platform': 'telegram',
                        'external_id': str(post['message_id']),
                        'content_type': self._get_content_type(post),
                        'text_content': post.get('text', post.get('caption', '')),
                        'media_urls': self._extract_media_urls(post),
                        'post_date': datetime.fromtimestamp(post['date']),
                        'raw_data': post
                    }
                    content_list.append(content_data)
            
            return content_list
            
        except Exception as e:
            logger.error(f"Telegram fetch error: {str(e)}")
            return []
    
    def _get_content_type(self, post):
        if 'photo' in post:
            return 'image'
        elif 'video' in post:
            return 'video'
        else:
            return 'post'
    
    def _extract_media_urls(self, post):
        urls = []
        if 'photo' in post:
            # Get largest photo
            largest = max(post['photo'], key=lambda x: x['file_size'])
            file_info = self._get_file_info(largest['file_id'])
            if file_info:
                urls.append(f"https://api.telegram.org/file/bot{self.bot_token}/{file_info['file_path']}")
        elif 'video' in post:
            file_info = self._get_file_info(post['video']['file_id'])
            if file_info:
                urls.append(f"https://api.telegram.org/file/bot{self.bot_token}/{file_info['file_path']}")
        return urls
    
    def _get_file_info(self, file_id):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getFile"
            params = {'file_id': file_id}
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json().get('result')
        except:
            return None