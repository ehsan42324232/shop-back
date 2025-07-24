# shop/realtime_chat_views.py
"""
Mall Platform - Real-time Chat Views
WebSocket and REST API views for chat system
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
import json
import logging

from .models import Store
from .realtime_chat_models import (
    ChatRoom, ChatMessage, ChatAgent, ChatSession, 
    ChatNotification, ChatTemplate, ChatSettings
)

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_chat_room(request):
    """Create new chat room"""
    try:
        store_id = request.data.get('store_id')
        subject = request.data.get('subject', 'سوال عمومی')
        
        store = get_object_or_404(Store, id=store_id)
        
        # Check if user already has active chat with this store
        existing_room = ChatRoom.objects.filter(
            store=store,
            customer=request.user,
            status__in=['active', 'waiting']
        ).first()
        
        if existing_room:
            return Response({
                'success': True,
                'room_id': str(existing_room.id),
                'message': 'گفتگوی فعال موجود است'
            })
        
        # Create new chat room
        room = ChatRoom.objects.create(
            store=store,
            customer=request.user,
            subject=subject,
            status='waiting'
        )
        
        # Send welcome message
        welcome_msg = store.chat_settings.welcome_message if hasattr(store, 'chat_settings') else 'سلام! چطور می‌تونم کمکتون کنم؟'
        
        ChatMessage.objects.create(
            room=room,
            sender=request.user,  # System message
            message_type='system',
            content=welcome_msg
        )
        
        # Try to assign agent
        agent = assign_available_agent(store)
        if agent:
            room.agent = agent.user
            room.status = 'active'
            room.save()
            
            # Create notification for agent
            ChatNotification.objects.create(
                recipient=agent.user,
                room=room,
                notification_type='customer_waiting',
                title='مشتری جدید',
                message=f'مشتری جدید منتظر پاسخ شماست: {subject}'
            )
        
        return Response({
            'success': True,
            'room_id': str(room.id),
            'status': room.status,
            'message': 'گفتگو ایجاد شد'
        })
        
    except Exception as e:
        logger.error(f"Create chat room error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در ایجاد گفتگو'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_rooms(request):
    """Get user's chat rooms"""
    try:
        # Different views for customers vs agents
        if hasattr(request.user, 'chat_agent'):
            # Agent view - show assigned chats
            rooms = ChatRoom.objects.filter(
                agent=request.user,
                status__in=['active', 'waiting']
            ).order_by('-updated_at')
        else:
            # Customer view - show their chats
            rooms = ChatRoom.objects.filter(
                customer=request.user
            ).order_by('-updated_at')
        
        room_data = []
        for room in rooms:
            last_message = room.messages.filter(
                is_deleted=False
            ).last()
            
            unread_count = room.get_unread_count(request.user)
            
            room_data.append({
                'id': str(room.id),
                'store_name': room.store.name,
                'customer_name': room.customer.get_full_name(),
                'agent_name': room.agent.get_full_name() if room.agent else None,
                'subject': room.subject,
                'status': room.status,
                'priority': room.priority,
                'last_message': {
                    'content': last_message.content if last_message else '',
                    'created_at': last_message.created_at if last_message else room.created_at,
                    'sender_name': last_message.sender.get_full_name() if last_message else ''
                },
                'unread_count': unread_count,
                'created_at': room.created_at,
                'updated_at': room.updated_at
            })
        
        return Response({
            'success': True,
            'rooms': room_data
        })
        
    except Exception as e:
        logger.error(f"Get chat rooms error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت گفتگوها'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_messages(request, room_id):
    """Get messages for a chat room"""
    try:
        room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check access permission
        if not (room.customer == request.user or room.agent == request.user):
            return Response({
                'success': False,
                'message': 'دسترسی غیرمجاز'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        start = (page - 1) * per_page
        end = start + per_page
        
        messages = room.messages.filter(
            is_deleted=False
        ).order_by('-created_at')[start:end]
        
        message_data = []
        for message in reversed(messages):
            message_data.append({
                'id': str(message.id),
                'sender_id': message.sender.id,
                'sender_name': message.sender.get_full_name(),
                'message_type': message.message_type,
                'content': message.content,
                'attachment': message.attachment.url if message.attachment else None,
                'attachment_name': message.attachment_name,
                'product': {
                    'id': message.product.id,
                    'name': message.product.name,
                    'image': message.product.images.first().image.url if message.product and message.product.images.exists() else None
                } if message.product else None,
                'is_read': message.is_read,
                'is_edited': message.is_edited,
                'created_at': message.created_at,
                'updated_at': message.updated_at
            })
            
            # Mark message as read
            message.mark_as_read(request.user)
        
        # Update session
        session, created = ChatSession.objects.get_or_create(
            room=room,
            user=request.user,
            is_active=True
        )
        
        return Response({
            'success': True,
            'messages': message_data,
            'room': {
                'id': str(room.id),
                'status': room.status,
                'subject': room.subject,
                'store_name': room.store.name,
                'customer_name': room.customer.get_full_name(),
                'agent_name': room.agent.get_full_name() if room.agent else None
            }
        })
        
    except Exception as e:
        logger.error(f"Get chat messages error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت پیام‌ها'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, room_id):
    """Send message in chat room"""
    try:
        room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check access permission
        if not (room.customer == request.user or room.agent == request.user):
            return Response({
                'success': False,
                'message': 'دسترسی غیرمجاز'
            }, status=status.HTTP_403_FORBIDDEN)
        
        message_type = request.data.get('message_type', 'text')
        content = request.data.get('content', '')
        product_id = request.data.get('product_id')
        
        if not content and message_type == 'text':
            return Response({
                'success': False,
                'message': 'محتوای پیام الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create message
        message = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            message_type=message_type,
            content=content
        )
        
        # Handle product reference
        if product_id:
            from .models import ProductInstance
            try:
                product = ProductInstance.objects.get(id=product_id)
                message.product = product
                message.save()
            except ProductInstance.DoesNotExist:
                pass
        
        # Handle file upload
        if 'attachment' in request.FILES:
            message.attachment = request.FILES['attachment']
            message.attachment_name = request.FILES['attachment'].name
            message.save()
        
        # Update room status
        if room.status == 'waiting':
            room.status = 'active'
        room.updated_at = timezone.now()
        room.save()
        
        # Create notification for recipient
        recipient = room.agent if request.user == room.customer else room.customer
        if recipient:
            ChatNotification.objects.create(
                recipient=recipient,
                room=room,
                notification_type='new_message',
                title='پیام جدید',
                message=f'{request.user.get_full_name()}: {content[:50]}'
            )
        
        return Response({
            'success': True,
            'message_id': str(message.id),
            'message': 'پیام ارسال شد'
        })
        
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در ارسال پیام'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_chat(request, room_id):
    """Close chat room"""
    try:
        room = get_object_or_404(ChatRoom, id=room_id)
        
        # Check permission (customer or assigned agent)
        if not (room.customer == request.user or room.agent == request.user):
            return Response({
                'success': False,
                'message': 'دسترسی غیرمجاز'
            }, status=status.HTTP_403_FORBIDDEN)
        
        room.status = 'closed'
        room.closed_at = timezone.now()
        room.save()
        
        # Add system message
        ChatMessage.objects.create(
            room=room,
            sender=request.user,
            message_type='system',
            content='گفتگو بسته شد'
        )
        
        # Update agent availability
        if room.agent and hasattr(room.agent, 'chat_agent'):
            agent = room.agent.chat_agent
            agent.current_chat_count = max(0, agent.current_chat_count - 1)
            agent.save()
        
        return Response({
            'success': True,
            'message': 'گفتگو بسته شد'
        })
        
    except Exception as e:
        logger.error(f"Close chat error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در بستن گفتگو'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_templates(request):
    """Get quick response templates"""
    try:
        # Get user's store (for agents)
        if hasattr(request.user, 'chat_agent'):
            store = request.user.chat_agent.store
            templates = ChatTemplate.objects.filter(
                store=store,
                is_active=True
            ).order_by('category', 'name')
            
            template_data = []
            for template in templates:
                template_data.append({
                    'id': template.id,
                    'name': template.name,
                    'content': template.content,
                    'category': template.category
                })
            
            return Response({
                'success': True,
                'templates': template_data
            })
        else:
            return Response({
                'success': False,
                'message': 'دسترسی غیرمجاز'
            }, status=status.HTTP_403_FORBIDDEN)
        
    except Exception as e:
        logger.error(f"Get chat templates error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت قالب‌ها'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def assign_available_agent(store):
    """Assign available agent to chat"""
    try:
        # Find available agent
        agent = ChatAgent.objects.filter(
            store=store,
            is_online=True
        ).annotate(
            active_chats=Count('user__agent_chats', filter=Q(user__agent_chats__status='active'))
        ).filter(
            active_chats__lt=models.F('max_concurrent_chats')
        ).first()
        
        if agent:
            agent.current_chat_count += 1
            agent.save()
        
        return agent
        
    except Exception as e:
        logger.error(f"Assign agent error: {e}")
        return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_chat(request, room_id):
    """Rate chat satisfaction"""
    try:
        room = get_object_or_404(ChatRoom, id=room_id, customer=request.user)
        rating = request.data.get('rating')
        
        if not rating or not (1 <= int(rating) <= 5):
            return Response({
                'success': False,
                'message': 'امتیاز باید بین ۱ تا ۵ باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        room.customer_satisfaction = int(rating)
        room.save()
        
        # Update agent stats
        if room.agent and hasattr(room.agent, 'chat_agent'):
            agent = room.agent.chat_agent
            # Recalculate average rating
            rated_chats = ChatRoom.objects.filter(
                agent=room.agent,
                customer_satisfaction__isnull=False
            )
            avg_rating = rated_chats.aggregate(
                avg=models.Avg('customer_satisfaction')
            )['avg']
            agent.customer_rating = avg_rating or 0
            agent.save()
        
        return Response({
            'success': True,
            'message': 'امتیاز ثبت شد'
        })
        
    except Exception as e:
        logger.error(f"Rate chat error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در ثبت امتیاز'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
