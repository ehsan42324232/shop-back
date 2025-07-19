import re
import requests
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
import mimetypes
from PIL import Image
import cv2
import tempfile
import os
from django.core.files.storage import default_storage
from django.conf import settings
from .social_content_models import Story, Post, ContentSyncLog


class ContentExtractor:
    """Extract and categorize content from social media posts and stories"""
    
    # Supported image formats
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    # Supported video formats
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'}
    
    # Text patterns for extraction
    TEXT_PATTERNS = {
        'hashtags': r'#[^\s#]+',
        'mentions': r'@[^\s@]+',
        'urls': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        'price': r'[\d,]+\s*(?:تومان|ریال|درهم|دلار|\$|€|£)',
        'phone': r'(?:\+98|0)?9\d{9}',
    }

    @staticmethod
    def extract_content_from_story(story: Story) -> Dict:
        """Extract and categorize content from a story"""
        extracted = {
            'images': [],
            'videos': [],
            'text': '',
            'metadata': {}
        }
        
        try:
            # Extract text content
            if story.text_content:
                extracted['text'] = ContentExtractor._clean_text(story.text_content)
                extracted['metadata']['text_analysis'] = ContentExtractor._analyze_text(story.text_content)
            
            # Process media URLs
            for media_url in story.media_urls:
                media_type = ContentExtractor._detect_media_type(media_url)
                
                if media_type == 'image':
                    image_info = ContentExtractor._process_image(media_url)
                    if image_info:
                        extracted['images'].append(image_info)
                
                elif media_type == 'video':
                    video_info = ContentExtractor._process_video(media_url)
                    if video_info:
                        extracted['videos'].append(video_info)
            
            # Update story with extracted content
            story.extracted_images = extracted['images']
            story.extracted_videos = extracted['videos']
            story.extracted_text = extracted['text']
            story.is_processed = True
            story.save()
            
        except Exception as e:
            story.processing_error = str(e)
            story.save()
            
        return extracted

    @staticmethod
    def extract_content_from_post(post: Post) -> Dict:
        """Extract and categorize content from a post"""
        extracted = {
            'images': [],
            'videos': [],
            'text': '',
            'metadata': {}
        }
        
        try:
            # Extract text content from caption
            if post.caption:
                extracted['text'] = ContentExtractor._clean_text(post.caption)
                extracted['metadata']['text_analysis'] = ContentExtractor._analyze_text(post.caption)
                extracted['metadata']['hashtags'] = post.hashtags
                extracted['metadata']['mentions'] = post.mentions
            
            # Process media URLs
            for media_url in post.media_urls:
                media_type = ContentExtractor._detect_media_type(media_url)
                
                if media_type == 'image':
                    image_info = ContentExtractor._process_image(media_url)
                    if image_info:
                        extracted['images'].append(image_info)
                
                elif media_type == 'video':
                    video_info = ContentExtractor._process_video(media_url)
                    if video_info:
                        extracted['videos'].append(video_info)
            
            # Update post with extracted content
            post.extracted_images = extracted['images']
            post.extracted_videos = extracted['videos']
            post.extracted_text = extracted['text']
            post.is_processed = True
            post.save()
            
        except Exception as e:
            post.processing_error = str(e)
            post.save()
            
        return extracted

    @staticmethod
    def _detect_media_type(url: str) -> str:
        """Detect if URL is image, video, or other"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()
            
            # Check file extension
            for ext in ContentExtractor.IMAGE_EXTENSIONS:
                if path.endswith(ext):
                    return 'image'
            
            for ext in ContentExtractor.VIDEO_EXTENSIONS:
                if path.endswith(ext):
                    return 'video'
            
            # Try to get content type from headers
            try:
                response = requests.head(url, timeout=10)
                content_type = response.headers.get('content-type', '').lower()
                
                if content_type.startswith('image/'):
                    return 'image'
                elif content_type.startswith('video/'):
                    return 'video'
            except:
                pass
                
        except Exception:
            pass
            
        return 'unknown'

    @staticmethod
    def _process_image(url: str) -> Optional[Dict]:
        """Process and analyze an image"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            try:
                # Analyze image with PIL
                with Image.open(temp_path) as img:
                    width, height = img.size
                    format_name = img.format
                    
                    # Get dominant colors
                    dominant_colors = ContentExtractor._get_dominant_colors(img)
                    
                    # Calculate file size
                    file_size = len(response.content)
                    
                    return {
                        'url': url,
                        'width': width,
                        'height': height,
                        'format': format_name,
                        'file_size': file_size,
                        'aspect_ratio': round(width / height, 2),
                        'dominant_colors': dominant_colors,
                        'is_portrait': height > width,
                        'is_square': abs(width - height) < min(width, height) * 0.1,
                    }
                    
            finally:
                # Clean up temp file
                os.unlink(temp_path)
                
        except Exception as e:
            print(f"Error processing image {url}: {e}")
            return None

    @staticmethod
    def _process_video(url: str) -> Optional[Dict]:
        """Process and analyze a video"""
        try:
            response = requests.head(url, timeout=10)
            response.raise_for_status()
            
            # Get basic info from headers
            file_size = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', '')
            
            video_info = {
                'url': url,
                'content_type': content_type,
                'file_size': file_size,
            }
            
            # Try to get video metadata (this would require downloading the video)
            # For now, we'll return basic info
            return video_info
            
        except Exception as e:
            print(f"Error processing video {url}: {e}")
            return None

    @staticmethod
    def _get_dominant_colors(img: Image.Image, num_colors: int = 5) -> List[str]:
        """Extract dominant colors from an image"""
        try:
            # Resize image for faster processing
            img = img.convert('RGB')
            img.thumbnail((150, 150))
            
            # Get colors
            colors = img.getcolors(maxcolors=256*256*256)
            
            if colors:
                # Sort by frequency and get top colors
                colors.sort(key=lambda x: x[0], reverse=True)
                dominant_colors = []
                
                for count, color in colors[:num_colors]:
                    hex_color = '#%02x%02x%02x' % color
                    dominant_colors.append(hex_color)
                
                return dominant_colors
                
        except Exception:
            pass
            
        return []

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove special characters but keep Persian/Arabic text
        text = re.sub(r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF#@.,!?()-]', '', text)
        
        return text

    @staticmethod
    def _analyze_text(text: str) -> Dict:
        """Analyze text content for useful patterns"""
        if not text:
            return {}
        
        analysis = {}
        
        # Extract patterns
        for pattern_name, pattern in ContentExtractor.TEXT_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                analysis[pattern_name] = list(set(matches))  # Remove duplicates
        
        # Count words
        words = text.split()
        analysis['word_count'] = len(words)
        analysis['char_count'] = len(text)
        
        # Detect language (basic detection)
        persian_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if persian_chars > english_chars:
            analysis['primary_language'] = 'persian'
        else:
            analysis['primary_language'] = 'english'
        
        return analysis

    @staticmethod
    def get_content_summary(content_type: str, content_id: str) -> Dict:
        """Get a summary of extracted content for UI display"""
        try:
            if content_type == 'story':
                content = Story.objects.get(id=content_id)
            elif content_type == 'post':
                content = Post.objects.get(id=content_id)
            else:
                return {}
            
            summary = {
                'id': str(content.id),
                'type': content_type,
                'platform': content.platform.platform_type,
                'created_at': content.created_at.isoformat(),
                'is_processed': content.is_processed,
                'images': {
                    'count': len(content.extracted_images),
                    'items': content.extracted_images
                },
                'videos': {
                    'count': len(content.extracted_videos),
                    'items': content.extracted_videos
                },
                'text': {
                    'content': content.extracted_text,
                    'length': len(content.extracted_text) if content.extracted_text else 0
                }
            }
            
            # Add specific fields
            if content_type == 'story':
                summary.update({
                    'view_count': content.view_count,
                    'expires_at': content.expires_at.isoformat() if content.expires_at else None,
                })
            elif content_type == 'post':
                summary.update({
                    'caption': content.caption,
                    'hashtags': content.hashtags,
                    'like_count': content.like_count,
                    'published_at': content.published_at.isoformat(),
                })
            
            return summary
            
        except Exception as e:
            return {'error': str(e)}


class SocialContentSyncer:
    """Sync content from social media platforms"""
    
    def __init__(self, platform):
        self.platform = platform
    
    def sync_stories(self, limit: int = 5) -> ContentSyncLog:
        """Sync latest stories from platform"""
        sync_log = ContentSyncLog.objects.create(
            platform=self.platform,
            sync_type='stories',
            status='started'
        )
        
        try:
            # This would integrate with actual social media APIs
            # For now, we'll create a mock implementation
            stories_data = self._fetch_stories_from_api(limit)
            
            sync_log.total_items_found = len(stories_data)
            
            for story_data in stories_data:
                try:
                    story, created = Story.objects.update_or_create(
                        platform=self.platform,
                        external_id=story_data['id'],
                        defaults={
                            'content_type': story_data.get('content_type', 'mixed'),
                            'text_content': story_data.get('text', ''),
                            'media_urls': story_data.get('media_urls', []),
                            'thumbnail_url': story_data.get('thumbnail_url', ''),
                            'view_count': story_data.get('view_count', 0),
                            'expires_at': story_data.get('expires_at'),
                        }
                    )
                    
                    if created:
                        sync_log.new_items_created += 1
                    else:
                        sync_log.items_updated += 1
                    
                    # Process content extraction
                    ContentExtractor.extract_content_from_story(story)
                    
                except Exception as e:
                    sync_log.items_failed += 1
                    sync_log.error_details.append({
                        'item_id': story_data.get('id'),
                        'error': str(e)
                    })
            
            sync_log.status = 'completed' if sync_log.items_failed == 0 else 'partial'
            sync_log.completed_at = timezone.now()
            
        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_details.append({'general_error': str(e)})
            sync_log.completed_at = timezone.now()
        
        sync_log.save()
        return sync_log
    
    def sync_posts(self, limit: int = 5) -> ContentSyncLog:
        """Sync latest posts from platform"""
        sync_log = ContentSyncLog.objects.create(
            platform=self.platform,
            sync_type='posts',
            status='started'
        )
        
        try:
            # This would integrate with actual social media APIs
            posts_data = self._fetch_posts_from_api(limit)
            
            sync_log.total_items_found = len(posts_data)
            
            for post_data in posts_data:
                try:
                    post, created = Post.objects.update_or_create(
                        platform=self.platform,
                        external_id=post_data['id'],
                        defaults={
                            'content_type': post_data.get('content_type', 'mixed'),
                            'caption': post_data.get('caption', ''),
                            'hashtags': post_data.get('hashtags', []),
                            'mentions': post_data.get('mentions', []),
                            'media_urls': post_data.get('media_urls', []),
                            'thumbnail_url': post_data.get('thumbnail_url', ''),
                            'post_url': post_data.get('post_url', ''),
                            'like_count': post_data.get('like_count', 0),
                            'comment_count': post_data.get('comment_count', 0),
                            'published_at': post_data.get('published_at'),
                        }
                    )
                    
                    if created:
                        sync_log.new_items_created += 1
                    else:
                        sync_log.items_updated += 1
                    
                    # Process content extraction
                    ContentExtractor.extract_content_from_post(post)
                    
                except Exception as e:
                    sync_log.items_failed += 1
                    sync_log.error_details.append({
                        'item_id': post_data.get('id'),
                        'error': str(e)
                    })
            
            sync_log.status = 'completed' if sync_log.items_failed == 0 else 'partial'
            sync_log.completed_at = timezone.now()
            
        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_details.append({'general_error': str(e)})
            sync_log.completed_at = timezone.now()
        
        sync_log.save()
        return sync_log
    
    def _fetch_stories_from_api(self, limit: int) -> List[Dict]:
        """Mock method to fetch stories from social media API"""
        # This would be replaced with actual API calls to Instagram, Telegram, etc.
        # For demo purposes, returning mock data
        from datetime import datetime, timedelta
        import uuid
        
        mock_stories = []
        for i in range(limit):
            mock_stories.append({
                'id': f'story_{uuid.uuid4().hex[:8]}',
                'content_type': 'image' if i % 2 == 0 else 'video',
                'text': f'Sample story text {i+1} with some #hashtags and @mentions',
                'media_urls': [f'https://example.com/story_media_{i+1}.jpg'],
                'thumbnail_url': f'https://example.com/story_thumb_{i+1}.jpg',
                'view_count': (i+1) * 100,
                'expires_at': datetime.now() + timedelta(hours=24-i),
            })
        
        return mock_stories
    
    def _fetch_posts_from_api(self, limit: int) -> List[Dict]:
        """Mock method to fetch posts from social media API"""
        # This would be replaced with actual API calls
        from datetime import datetime, timedelta
        import uuid
        
        mock_posts = []
        for i in range(limit):
            mock_posts.append({
                'id': f'post_{uuid.uuid4().hex[:8]}',
                'content_type': 'carousel' if i % 3 == 0 else 'image',
                'caption': f'Sample post caption {i+1} with product description #product #sale @store',
                'hashtags': ['#product', '#sale', '#store', f'#item{i+1}'],
                'mentions': ['@store', '@customer'],
                'media_urls': [
                    f'https://example.com/post_media_{i+1}_1.jpg',
                    f'https://example.com/post_media_{i+1}_2.jpg'
                ],
                'thumbnail_url': f'https://example.com/post_thumb_{i+1}.jpg',
                'post_url': f'https://instagram.com/p/{uuid.uuid4().hex[:8]}',
                'like_count': (i+1) * 50,
                'comment_count': (i+1) * 10,
                'published_at': datetime.now() - timedelta(days=i+1),
            })
        
        return mock_posts


# Import timezone for proper datetime handling
from django.utils import timezone
