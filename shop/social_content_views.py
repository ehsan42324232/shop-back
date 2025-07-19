from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta

from .social_content_models import (
    SocialPlatform, Story, Post, ContentSelection, ContentSyncLog
)
from .social_content_serializers import (
    SocialPlatformSerializer, StorySerializer, PostSerializer,
    ContentSelectionSerializer, ContentSyncLogSerializer,
    ContentSummarySerializer, ContentExtractionResultSerializer,
    SelectContentForProductSerializer, BulkContentSelectionSerializer,
    ContentSearchSerializer, ProductContentSummarySerializer
)
from .content_extractor import ContentExtractor, SocialContentSyncer
from .models import Store, Product
from .authentication import StorePermissionMixin


class SocialContentPagination(PageNumberPagination):
    """Custom pagination for social content"""
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


class SocialPlatformViewSet(StorePermissionMixin, viewsets.ModelViewSet):
    """ViewSet for managing social media platforms"""
    serializer_class = SocialPlatformSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SocialContentPagination
    
    def get_queryset(self):
        """Filter by current store"""
        return SocialPlatform.objects.filter(
            store=self.get_current_store()
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        """Associate platform with current store"""
        serializer.save(store=self.get_current_store())
    
    @action(detail=True, methods=['post'])
    def sync_content(self, request, pk=None):
        """Sync content from this platform"""
        platform = self.get_object()
        content_type = request.data.get('content_type', 'both')  # 'stories', 'posts', 'both'
        limit = min(int(request.data.get('limit', 5)), 10)  # Max 10 items
        
        syncer = SocialContentSyncer(platform)
        sync_logs = []
        
        try:
            if content_type in ['stories', 'both']:
                story_log = syncer.sync_stories(limit=limit)
                sync_logs.append(ContentSyncLogSerializer(story_log).data)
            
            if content_type in ['posts', 'both']:
                post_log = syncer.sync_posts(limit=limit)
                sync_logs.append(ContentSyncLogSerializer(post_log).data)
            
            # Update platform last sync time
            platform.last_sync = timezone.now()
            platform.save()
            
            return Response({
                'message': 'Content sync initiated successfully',
                'sync_logs': sync_logs
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Sync failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def sync_history(self, request, pk=None):
        """Get sync history for this platform"""
        platform = self.get_object()
        logs = ContentSyncLog.objects.filter(platform=platform).order_by('-started_at')[:10]
        
        return Response(
            ContentSyncLogSerializer(logs, many=True).data,
            status=status.HTTP_200_OK
        )


class StoryViewSet(StorePermissionMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing stories"""
    serializer_class = StorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SocialContentPagination
    
    def get_queryset(self):
        """Filter stories by current store's platforms"""
        store = self.get_current_store()
        return Story.objects.filter(
            platform__store=store
        ).select_related('platform').order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """List stories with filtering options"""
        queryset = self.get_queryset()
        
        # Apply filters
        platform_type = request.query_params.get('platform_type')
        if platform_type and platform_type != 'all':
            queryset = queryset.filter(platform__platform_type=platform_type)
        
        content_type = request.query_params.get('content_type')
        if content_type and content_type != 'all':
            queryset = queryset.filter(content_type=content_type)
        
        is_processed = request.query_params.get('is_processed')
        if is_processed is not None:
            queryset = queryset.filter(is_processed=is_processed.lower() == 'true')
        
        # Search in text content
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(text_content__icontains=search) |
                Q(extracted_text__icontains=search)
            )
        
        # Date filtering
        days_ago = request.query_params.get('days_ago')
        if days_ago:
            try:
                date_threshold = timezone.now() - timedelta(days=int(days_ago))
                queryset = queryset.filter(created_at__gte=date_threshold)
            except ValueError:
                pass
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def extract_content(self, request, pk=None):
        """Extract content from a specific story"""
        story = self.get_object()
        
        try:
            extracted = ContentExtractor.extract_content_from_story(story)
            
            return Response(
                ContentExtractionResultSerializer({
                    'content_id': story.id,
                    'content_type': 'story',
                    **extracted
                }).data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response({
                'error': f'Content extraction failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class PostViewSet(StorePermissionMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing posts"""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SocialContentPagination
    
    def get_queryset(self):
        """Filter posts by current store's platforms"""
        store = self.get_current_store()
        return Post.objects.filter(
            platform__store=store
        ).select_related('platform').order_by('-published_at')
    
    def list(self, request, *args, **kwargs):
        """List posts with filtering options"""
        queryset = self.get_queryset()
        
        # Apply filters
        platform_type = request.query_params.get('platform_type')
        if platform_type and platform_type != 'all':
            queryset = queryset.filter(platform__platform_type=platform_type)
        
        content_type = request.query_params.get('content_type')
        if content_type and content_type != 'all':
            queryset = queryset.filter(content_type=content_type)
        
        is_processed = request.query_params.get('is_processed')
        if is_processed is not None:
            queryset = queryset.filter(is_processed=is_processed.lower() == 'true')
        
        # Search in caption and hashtags
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(caption__icontains=search) |
                Q(extracted_text__icontains=search) |
                Q(hashtags__contains=[search])
            )
        
        # Engagement filtering
        min_engagement = request.query_params.get('min_engagement')
        if min_engagement:
            try:
                min_val = int(min_engagement)
                queryset = queryset.filter(
                    like_count__gte=min_val
                )
            except ValueError:
                pass
        
        # Date filtering
        days_ago = request.query_params.get('days_ago')
        if days_ago:
            try:
                date_threshold = timezone.now() - timedelta(days=int(days_ago))
                queryset = queryset.filter(published_at__gte=date_threshold)
            except ValueError:
                pass
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def extract_content(self, request, pk=None):
        """Extract content from a specific post"""
        post = self.get_object()
        
        try:
            extracted = ContentExtractor.extract_content_from_post(post)
            
            return Response(
                ContentExtractionResultSerializer({
                    'content_id': post.id,
                    'content_type': 'post',
                    **extracted
                }).data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response({
                'error': f'Content extraction failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class ContentSelectionViewSet(StorePermissionMixin, viewsets.ModelViewSet):
    """ViewSet for managing content selections"""
    serializer_class = ContentSelectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SocialContentPagination
    
    def get_queryset(self):
        """Filter by current store's products"""
        store = self.get_current_store()
        return ContentSelection.objects.filter(
            product__store=store
        ).select_related('product').order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """List content selections with filtering"""
        queryset = self.get_queryset()
        
        # Filter by product
        product_id = request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by content type
        content_type = request.query_params.get('content_type')
        if content_type and content_type != 'all':
            queryset = queryset.filter(content_type=content_type)
        
        # Filter by media type
        media_type = request.query_params.get('media_type')
        if media_type and media_type != 'all':
            queryset = queryset.filter(selected_media_type=media_type)
        
        # Filter by usage
        usage_filter = request.query_params.get('usage')
        if usage_filter == 'product_image':
            queryset = queryset.filter(use_as_product_image=True)
        elif usage_filter == 'description':
            queryset = queryset.filter(use_in_description=True)
        elif usage_filter == 'gallery':
            queryset = queryset.filter(use_as_gallery=True)
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['post'])
    def select_content(self, request):
        """Select content for a product"""
        serializer = SelectContentForProductSerializer(data=request.data)
        
        if serializer.is_valid():
            validated_data = serializer.validated_data
            
            # Get the product and validate store ownership
            product = get_object_or_404(
                Product,
                id=validated_data['product_id'],
                store=self.get_current_store()
            )
            
            # Create content selection
            selection = ContentSelection.objects.create(
                product=product,
                content_type=validated_data['content_type'],
                content_id=validated_data['content_id'],
                selected_media_type=validated_data['selected_media_type'],
                selected_media_urls=validated_data.get('selected_media_urls', []),
                selected_text=validated_data.get('selected_text', ''),
                use_as_product_image=validated_data.get('use_as_product_image', False),
                use_in_description=validated_data.get('use_in_description', False),
                use_as_gallery=validated_data.get('use_as_gallery', False),
                selection_notes=validated_data.get('selection_notes', '')
            )
            
            return Response(
                ContentSelectionSerializer(selection).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_select(self, request):
        """Bulk select content for a product"""
        serializer = BulkContentSelectionSerializer(data=request.data)
        
        if serializer.is_valid():
            validated_data = serializer.validated_data
            
            # Get the product and validate store ownership
            product = get_object_or_404(
                Product,
                id=validated_data['product_id'],
                store=self.get_current_store()
            )
            
            created_selections = []
            
            for selection_data in validated_data['selections']:
                selection = ContentSelection.objects.create(
                    product=product,
                    content_type=selection_data['content_type'],
                    content_id=selection_data['content_id'],
                    selected_media_type=selection_data['selected_media_type'],
                    selected_media_urls=selection_data.get('selected_media_urls', []),
                    selected_text=selection_data.get('selected_text', ''),
                    use_as_product_image=selection_data.get('use_as_product_image', False),
                    use_in_description=selection_data.get('use_in_description', False),
                    use_as_gallery=selection_data.get('use_as_gallery', False),
                    selection_notes=selection_data.get('selection_notes', '')
                )
                created_selections.append(selection)
            
            return Response({
                'message': f'Successfully created {len(created_selections)} content selections',
                'selections': ContentSelectionSerializer(created_selections, many=True).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SocialContentAPIViewSet(StorePermissionMixin, viewsets.ViewSet):
    """Main API for social content management"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary of all social content for the store"""
        store = self.get_current_store()
        
        # Get platforms
        platforms = SocialPlatform.objects.filter(store=store, is_active=True)
        
        # Get recent stories (last 5)
        recent_stories = Story.objects.filter(
            platform__store=store,
            is_processed=True
        ).select_related('platform').order_by('-created_at')[:5]
        
        # Get recent posts (last 5)
        recent_posts = Post.objects.filter(
            platform__store=store,
            is_processed=True
        ).select_related('platform').order_by('-published_at')[:5]
        
        # Get totals
        total_stories = Story.objects.filter(platform__store=store).count()
        total_posts = Post.objects.filter(platform__store=store).count()
        
        summary_data = {
            'stories': StorySerializer(recent_stories, many=True).data,
            'posts': PostSerializer(recent_posts, many=True).data,
            'total_stories': total_stories,
            'total_posts': total_posts,
            'platforms': SocialPlatformSerializer(platforms, many=True).data
        }
        
        return Response(
            ContentSummarySerializer(summary_data).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'])
    def search_content(self, request):
        """Search through stories and posts"""
        serializer = ContentSearchSerializer(data=request.data)
        
        if serializer.is_valid():
            validated_data = serializer.validated_data
            store = self.get_current_store()
            
            results = {
                'stories': [],
                'posts': [],
                'total_count': 0
            }
            
            # Search stories
            if validated_data['content_type'] in ['story', 'both']:
                story_queryset = Story.objects.filter(
                    platform__store=store,
                    is_processed=True
                ).select_related('platform')
                
                # Apply filters
                if validated_data.get('query'):
                    story_queryset = story_queryset.filter(
                        Q(text_content__icontains=validated_data['query']) |
                        Q(extracted_text__icontains=validated_data['query'])
                    )
                
                if validated_data.get('platform_type') != 'all':
                    story_queryset = story_queryset.filter(
                        platform__platform_type=validated_data['platform_type']
                    )
                
                if validated_data.get('media_type') != 'all':
                    story_queryset = story_queryset.filter(
                        content_type=validated_data['media_type']
                    )
                
                if validated_data.get('date_from'):
                    story_queryset = story_queryset.filter(
                        created_at__gte=validated_data['date_from']
                    )
                
                if validated_data.get('date_to'):
                    story_queryset = story_queryset.filter(
                        created_at__lte=validated_data['date_to']
                    )
                
                stories = story_queryset.order_by('-created_at')[
                    validated_data['offset']:validated_data['offset'] + validated_data['limit']
                ]
                
                results['stories'] = StorySerializer(stories, many=True).data
            
            # Search posts
            if validated_data['content_type'] in ['post', 'both']:
                post_queryset = Post.objects.filter(
                    platform__store=store,
                    is_processed=True
                ).select_related('platform')
                
                # Apply filters
                if validated_data.get('query'):
                    post_queryset = post_queryset.filter(
                        Q(caption__icontains=validated_data['query']) |
                        Q(extracted_text__icontains=validated_data['query']) |
                        Q(hashtags__contains=[validated_data['query']])
                    )
                
                if validated_data.get('platform_type') != 'all':
                    post_queryset = post_queryset.filter(
                        platform__platform_type=validated_data['platform_type']
                    )
                
                if validated_data.get('media_type') != 'all':
                    post_queryset = post_queryset.filter(
                        content_type=validated_data['media_type']
                    )
                
                if validated_data.get('date_from'):
                    post_queryset = post_queryset.filter(
                        published_at__gte=validated_data['date_from']
                    )
                
                if validated_data.get('date_to'):
                    post_queryset = post_queryset.filter(
                        published_at__lte=validated_data['date_to']
                    )
                
                if validated_data.get('min_engagement'):
                    post_queryset = post_queryset.filter(
                        like_count__gte=validated_data['min_engagement']
                    )
                
                if validated_data.get('has_hashtags'):
                    post_queryset = post_queryset.exclude(hashtags=[])
                
                posts = post_queryset.order_by('-published_at')[
                    validated_data['offset']:validated_data['offset'] + validated_data['limit']
                ]
                
                results['posts'] = PostSerializer(posts, many=True).data
            
            results['total_count'] = len(results['stories']) + len(results['posts'])
            
            return Response(results, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def product_content_summary(self, request):
        """Get content summary for a specific product"""
        product_id = request.query_params.get('product_id')
        
        if not product_id:
            return Response({
                'error': 'product_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(
                id=product_id,
                store=self.get_current_store()
            )
        except Product.DoesNotExist:
            return Response({
                'error': 'Product not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get content selections for this product
        selections = ContentSelection.objects.filter(
            product=product,
            is_active=True
        ).order_by('-created_at')
        
        # Count by type
        content_breakdown = {
            'total': selections.count(),
            'images': selections.filter(selected_media_type='image').count(),
            'videos': selections.filter(selected_media_type='video').count(),
            'text': selections.filter(selected_media_type='text').count(),
            'stories': selections.filter(content_type='story').count(),
            'posts': selections.filter(content_type='post').count(),
        }
        
        # Get recent selections
        recent_selections = selections[:5]
        
        # TODO: Add suggested content based on product attributes/category
        suggested_content = []
        
        summary_data = {
            'product_id': str(product.id),
            'product_title': product.title,
            'selected_content_count': content_breakdown['total'],
            'content_breakdown': content_breakdown,
            'recent_selections': ContentSelectionSerializer(recent_selections, many=True).data,
            'suggested_content': suggested_content
        }
        
        return Response(
            ProductContentSummarySerializer(summary_data).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'])
    def sync_all_platforms(self, request):
        """Sync content from all active platforms"""
        store = self.get_current_store()
        platforms = SocialPlatform.objects.filter(store=store, is_active=True)
        
        if not platforms.exists():
            return Response({
                'error': 'No active platforms configured'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        sync_results = []
        
        for platform in platforms:
            try:
                syncer = SocialContentSyncer(platform)
                
                # Sync both stories and posts (limited to 3 each for bulk operation)
                story_log = syncer.sync_stories(limit=3)
                post_log = syncer.sync_posts(limit=3)
                
                sync_results.append({
                    'platform': {
                        'id': platform.id,
                        'type': platform.platform_type,
                        'username': platform.username
                    },
                    'story_sync': ContentSyncLogSerializer(story_log).data,
                    'post_sync': ContentSyncLogSerializer(post_log).data
                })
                
                # Update platform last sync time
                platform.last_sync = timezone.now()
                platform.save()
                
            except Exception as e:
                sync_results.append({
                    'platform': {
                        'id': platform.id,
                        'type': platform.platform_type,
                        'username': platform.username
                    },
                    'error': str(e)
                })
        
        return Response({
            'message': f'Sync completed for {len(platforms)} platforms',
            'results': sync_results
        }, status=status.HTTP_200_OK)
