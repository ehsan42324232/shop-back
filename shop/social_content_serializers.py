from rest_framework import serializers
from .social_content_models import (
    SocialPlatform, Story, Post, ContentSelection, ContentSyncLog
)
from .models import Product, Store


class SocialPlatformSerializer(serializers.ModelSerializer):
    """Serializer for social media platforms"""
    platform_type_display = serializers.CharField(source='get_platform_type_display', read_only=True)
    
    class Meta:
        model = SocialPlatform
        fields = [
            'id', 'platform_type', 'platform_type_display', 'username', 
            'is_active', 'last_sync', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_sync']


class StorySerializer(serializers.ModelSerializer):
    """Serializer for stories"""
    platform_info = serializers.SerializerMethodField()
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    time_since_created = serializers.SerializerMethodField()
    
    class Meta:
        model = Story
        fields = [
            'id', 'external_id', 'content_type', 'content_type_display',
            'text_content', 'media_urls', 'thumbnail_url', 'view_count',
            'like_count', 'comment_count', 'share_count', 'expires_at',
            'is_highlighted', 'is_processed', 'processing_error',
            'extracted_images', 'extracted_videos', 'extracted_text',
            'created_at', 'updated_at', 'platform_info', 'time_since_created'
        ]
        read_only_fields = [
            'id', 'external_id', 'is_processed', 'processing_error',
            'extracted_images', 'extracted_videos', 'extracted_text',
            'created_at', 'updated_at'
        ]
    
    def get_platform_info(self, obj):
        """Get platform information"""
        return {
            'type': obj.platform.platform_type,
            'username': obj.platform.username,
            'display_name': obj.platform.get_platform_type_display()
        }
    
    def get_time_since_created(self, obj):
        """Get human-readable time since creation"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        else:
            return "همین الان"


class PostSerializer(serializers.ModelSerializer):
    """Serializer for posts"""
    platform_info = serializers.SerializerMethodField()
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    time_since_published = serializers.SerializerMethodField()
    engagement_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'external_id', 'content_type', 'content_type_display',
            'caption', 'hashtags', 'mentions', 'media_urls', 'thumbnail_url',
            'post_url', 'like_count', 'comment_count', 'share_count', 'save_count',
            'published_at', 'location', 'is_processed', 'processing_error',
            'extracted_images', 'extracted_videos', 'extracted_text',
            'created_at', 'updated_at', 'platform_info', 'time_since_published',
            'engagement_rate'
        ]
        read_only_fields = [
            'id', 'external_id', 'is_processed', 'processing_error',
            'extracted_images', 'extracted_videos', 'extracted_text',
            'created_at', 'updated_at'
        ]
    
    def get_platform_info(self, obj):
        """Get platform information"""
        return {
            'type': obj.platform.platform_type,
            'username': obj.platform.username,
            'display_name': obj.platform.get_platform_type_display()
        }
    
    def get_time_since_published(self, obj):
        """Get human-readable time since publication"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not obj.published_at:
            return "نامشخص"
        
        now = timezone.now()
        diff = now - obj.published_at
        
        if diff.days > 30:
            months = diff.days // 30
            return f"{months} ماه پیش"
        elif diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        else:
            return "همین الان"
    
    def get_engagement_rate(self, obj):
        """Calculate engagement rate"""
        total_engagement = obj.like_count + obj.comment_count + obj.share_count
        # This would need view count or follower count for accurate calculation
        # For now, return the total engagement
        return total_engagement


class ContentSelectionSerializer(serializers.ModelSerializer):
    """Serializer for content selections"""
    product_info = serializers.SerializerMethodField()
    source_content_info = serializers.SerializerMethodField()
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    selected_media_type_display = serializers.CharField(source='get_selected_media_type_display', read_only=True)
    
    class Meta:
        model = ContentSelection
        fields = [
            'id', 'product', 'content_type', 'content_type_display',
            'content_id', 'selected_media_type', 'selected_media_type_display',
            'selected_media_urls', 'selected_text', 'use_as_product_image',
            'use_in_description', 'use_as_gallery', 'selection_notes',
            'is_active', 'created_at', 'updated_at', 'product_info',
            'source_content_info'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_product_info(self, obj):
        """Get product information"""
        return {
            'id': str(obj.product.id),
            'title': obj.product.title,
            'slug': obj.product.slug,
            'price': obj.product.price
        }
    
    def get_source_content_info(self, obj):
        """Get source content information"""
        source = obj.source_content
        if not source:
            return None
        
        base_info = {
            'id': str(source.id),
            'external_id': source.external_id,
            'content_type': source.content_type,
            'platform': {
                'type': source.platform.platform_type,
                'username': source.platform.username
            },
            'created_at': source.created_at
        }
        
        if obj.content_type == 'story':
            base_info.update({
                'text_content': source.text_content,
                'view_count': source.view_count,
                'expires_at': source.expires_at
            })
        elif obj.content_type == 'post':
            base_info.update({
                'caption': source.caption,
                'hashtags': source.hashtags,
                'like_count': source.like_count,
                'published_at': source.published_at
            })
        
        return base_info


class ContentSyncLogSerializer(serializers.ModelSerializer):
    """Serializer for content sync logs"""
    platform_info = serializers.SerializerMethodField()
    sync_type_display = serializers.CharField(source='get_sync_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ContentSyncLog
        fields = [
            'id', 'sync_type', 'sync_type_display', 'status', 'status_display',
            'total_items_found', 'new_items_created', 'items_updated', 'items_failed',
            'error_details', 'started_at', 'completed_at', 'platform_info',
            'duration', 'success_rate'
        ]
        read_only_fields = '__all__'
    
    def get_platform_info(self, obj):
        """Get platform information"""
        return {
            'type': obj.platform.platform_type,
            'username': obj.platform.username,
            'display_name': obj.platform.get_platform_type_display()
        }
    
    def get_duration(self, obj):
        """Get sync duration"""
        if obj.completed_at and obj.started_at:
            duration = obj.completed_at - obj.started_at
            total_seconds = int(duration.total_seconds())
            
            if total_seconds >= 60:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                return f"{minutes}:{seconds:02d}"
            else:
                return f"{total_seconds} ثانیه"
        return "در حال انجام"
    
    def get_success_rate(self, obj):
        """Calculate success rate"""
        if obj.total_items_found == 0:
            return 0
        
        successful_items = obj.new_items_created + obj.items_updated
        return round((successful_items / obj.total_items_found) * 100, 1)


class ContentSummarySerializer(serializers.Serializer):
    """Serializer for content summary"""
    stories = serializers.ListField(child=StorySerializer(), read_only=True)
    posts = serializers.ListField(child=PostSerializer(), read_only=True)
    total_stories = serializers.IntegerField(read_only=True)
    total_posts = serializers.IntegerField(read_only=True)
    platforms = serializers.ListField(child=SocialPlatformSerializer(), read_only=True)


class ContentExtractionResultSerializer(serializers.Serializer):
    """Serializer for content extraction results"""
    content_id = serializers.UUIDField()
    content_type = serializers.ChoiceField(choices=['story', 'post'])
    
    images = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of extracted images with metadata"
    )
    videos = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of extracted videos with metadata"
    )
    text = serializers.CharField(
        help_text="Extracted and cleaned text content"
    )
    metadata = serializers.DictField(
        help_text="Additional metadata about the content"
    )


class SelectContentForProductSerializer(serializers.Serializer):
    """Serializer for selecting content for a product"""
    product_id = serializers.UUIDField()
    content_type = serializers.ChoiceField(choices=['story', 'post'])
    content_id = serializers.UUIDField()
    selected_media_type = serializers.ChoiceField(choices=['image', 'video', 'text'])
    selected_media_urls = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=list
    )
    selected_text = serializers.CharField(required=False, allow_blank=True)
    use_as_product_image = serializers.BooleanField(default=False)
    use_in_description = serializers.BooleanField(default=False)
    use_as_gallery = serializers.BooleanField(default=False)
    selection_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_product_id(self, value):
        """Validate that product exists and belongs to current store"""
        try:
            # This would be validated based on the current store context
            product = Product.objects.get(id=value)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")
    
    def validate(self, data):
        """Cross-field validation"""
        # Ensure at least one usage option is selected
        usage_options = [
            data.get('use_as_product_image', False),
            data.get('use_in_description', False),
            data.get('use_as_gallery', False)
        ]
        
        if not any(usage_options):
            raise serializers.ValidationError(
                "At least one usage option must be selected"
            )
        
        # Validate media selection based on type
        selected_media_type = data.get('selected_media_type')
        
        if selected_media_type in ['image', 'video']:
            if not data.get('selected_media_urls'):
                raise serializers.ValidationError(
                    f"Media URLs required for {selected_media_type} selection"
                )
        elif selected_media_type == 'text':
            if not data.get('selected_text'):
                raise serializers.ValidationError(
                    "Text content required for text selection"
                )
        
        return data


class BulkContentSelectionSerializer(serializers.Serializer):
    """Serializer for bulk content selection"""
    product_id = serializers.UUIDField()
    selections = serializers.ListField(
        child=SelectContentForProductSerializer(),
        min_length=1,
        max_length=20
    )
    
    def validate_product_id(self, value):
        """Validate that product exists"""
        try:
            Product.objects.get(id=value)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")


class ContentSearchSerializer(serializers.Serializer):
    """Serializer for content search parameters"""
    query = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.ChoiceField(
        choices=['story', 'post', 'both'],
        default='both'
    )
    platform_type = serializers.ChoiceField(
        choices=['instagram', 'telegram', 'twitter', 'facebook', 'tiktok', 'youtube', 'all'],
        default='all'
    )
    media_type = serializers.ChoiceField(
        choices=['image', 'video', 'text', 'all'],
        default='all'
    )
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    min_engagement = serializers.IntegerField(required=False, min_value=0)
    has_hashtags = serializers.BooleanField(required=False)
    limit = serializers.IntegerField(default=10, min_value=1, max_value=50)
    offset = serializers.IntegerField(default=0, min_value=0)
    
    def validate(self, data):
        """Validate date range"""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "date_from must be before date_to"
            )
        
        return data


class ProductContentSummarySerializer(serializers.Serializer):
    """Serializer for product content summary"""
    product_id = serializers.UUIDField()
    product_title = serializers.CharField()
    selected_content_count = serializers.IntegerField()
    content_breakdown = serializers.DictField()
    recent_selections = serializers.ListField(
        child=ContentSelectionSerializer()
    )
    suggested_content = serializers.ListField(
        child=serializers.DictField()
    )
