# Social Media Integration Services
# Implements Instagram and Telegram content fetching as described

import requests
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import urllib.parse
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SocialMediaIntegrator:
    """Base class for social media integrations"""
    
    def __init__(self, store):
        self.store = store
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_content(self, limit=5) -> List[Dict]:
        """Fetch recent content from social media platform"""
        raise NotImplementedError
    
    def download_media(self, url: str, filename: str) -> Optional[str]:
        """Download media file and return local path"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            file_path = f"social_media/{self.store.id}/{filename}"
            saved_path = default_storage.save(file_path, ContentFile(response.content))
            return saved_path
            
        except Exception as e:
            logger.error(f"Failed to download media {url}: {str(e)}")
            return None