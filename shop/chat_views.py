from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Q, Count, F
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

from .chat_models import SupportAgent, ChatSession, ChatMessage, ChatNotification, SupportSettings
from .chat_serializers import (
    ChatSessionSerializer, ChatMessageSerializer, 
    SupportAgentSerializer, ChatNotificationSerializer
)

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@api_view(['GET'])
def get_support_status(request):
    """Get current support online status"""
    try:
        settings = SupportSettings.get_settings()
        online_agents = SupportAgent.objects.filter(is_online=True).count()
        available_agents = SupportAgent.objects.filter(
            is_online=True
        ).annotate(
            active_chats=Count('assigned_chats', filter=Q(assigned_chats__status__in=['active', 'waiting']))
        ).filter(
            active_chats__lt=F('max_concurrent_chats')
        ).count()
        
        return Response({
            'is_online': settings.is_support_online(),
            'is_24_7': settings.is_24_7,
            'online_agents': online_agents,
            'available_agents': available_agents,
            'welcome_message': settings.welcome_message,
            'offline_message': settings.offline_message,
            'estimated_wait_time': get_estimated_wait_time()
        })
    except Exception as e:
        logger.error(f"Error getting support status: {e}")
        return Response({'error': 'خطا در دریافت وضعیت پشتیبانی'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_chat_session(request):
    """Start a new chat session"""
    try:
        data = request.data
        
        # Check if user already has an active session
        existing_session = ChatSession.objects.filter(
            customer=request.user,
            status__in=['waiting', 'active']
        ).first()
        
        if existing_session:
            return Response({
                'session': ChatSessionSerializer(existing_session).data,
                'message': 'شما در حال حاضر یک چت فعال دارید'
            })
        
        # Create new session
        session = ChatSession.objects.create(
            customer=request.user,
            subject=data.get('subject', ''),
            priority=data.get('priority', 'normal'),
            customer_name=data.get('customer_name', request.user.get_full_name()),
            customer_email=data.get('customer_email', request.user.email),
            customer_phone=data.get('customer_phone', ''),
            customer_ip=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer_url=data.get('referrer_url', '')
        )
        
        # Try to assign to available agent
        available_agent = find_available_agent()
        if available_agent:
            session.agent = available_agent
            session.status = 'active'
            session.save()
            
            # Send notification to agent
            send_chat_notification(
                recipient=available_agent.user,
                session=session,
                notification_type='chat_assigned',
                title='چت جدید واگذار شد',
                body=f'چت جدید از {session.customer_name} واگذار شد'
            )
            
            # Send welcome message
            create_system_message(session, SupportSettings.get_settings().welcome_message)
        else:
            # Send to waiting queue
            create_system_message(session, 'شما در صف انتظار قرار گرفتید. یکی از پشتیبان‌های ما به زودی با شما در ارتباط خواهد بود.')
        
        # Notify all online agents about new chat request
        notify_agents_new_chat(session)
        
        return Response({
            'session': ChatSessionSerializer(session).data,
            'message': 'چت با موفقیت شروع شد'
        }, status=201)
        
    except Exception as e:
        logger.error(f"Error starting chat session: {e}")
        return Response({'error': 'خطا در شروع چت'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """Send a chat message"""
    try:
        data = request.data
        session_id = data.get('session_id')
        content = data.get('content')
        message_type = data.get('message_type', 'text')
        
        if not session_id or not content:
            return Response({'error': 'session_id و content الزامی هستند'}, status=400)
        
        session = ChatSession.objects.get(id=session_id)
        
        # Check if user can send message to this session
        if not (session.customer == request.user or 
                (hasattr(request.user, 'support_agent') and session.agent and session.agent.user == request.user)):
            return Response({'error': 'شما مجاز به ارسال پیام در این چت نیستید'}, status=403)
        
        # Create message
        message = ChatMessage.objects.create(
            session=session,
            sender=request.user,
            content=content,
            message_type=message_type
        )
        
        # Handle file attachment if present
        if 'file_attachment' in request.FILES:
            message.file_attachment = request.FILES['file_attachment']
            message.save()
        
        # Update session timestamp
        session.updated_at = timezone.now()
        session.save()
        
        # Send real-time notification via WebSocket
        send_realtime_message(session, message)
        
        # Send push notification to other party
        if session.customer == request.user and session.agent:
            # Customer sent message, notify agent
            send_chat_notification(
                recipient=session.agent.user,
                session=session,
                message=message,
                notification_type='new_message',
                title=f'پیام جدید از {session.customer_name}',
                body=content[:100] + ('...' if len(content) > 100 else '')
            )
        elif session.agent and session.agent.user == request.user:
            # Agent sent message, notify customer
            send_chat_notification(
                recipient=session.customer,
                session=session,
                message=message,
                notification_type='new_message',
                title='پیام جدید از پشتیبانی',
                body=content[:100] + ('...' if len(content) > 100 else '')
            )
        
        return Response({
            'message': ChatMessageSerializer(message).data,
            'status': 'پیام ارسال شد'
        }, status=201)
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'جلسه چت یافت نشد'}, status=404)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return Response({'error': 'خطا در ارسال پیام'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_messages(request, session_id):
    """Get messages for a chat session"""
    try:
        session = ChatSession.objects.get(id=session_id)
        
        # Check permission
        if not (session.customer == request.user or 
                (hasattr(request.user, 'support_agent') and session.agent and session.agent.user == request.user)):
            return Response({'error': 'شما مجاز به مشاهده این چت نیستید'}, status=403)
        
        messages = session.messages.all().order_by('created_at')
        
        # Mark messages as read for the requesting user
        unread_messages = messages.filter(is_read=False).exclude(sender=request.user)
        for msg in unread_messages:
            msg.mark_as_read(request.user)
        
        return Response({
            'session': ChatSessionSerializer(session).data,
            'messages': ChatMessageSerializer(messages, many=True).data
        })
        
    except ChatSession.DoesNotExist:
        return Response({'error': 'جلسه چت یافت نشد'}, status=404)
    except Exception as e:
        logger.error(f"Error getting chat messages: {e}")
        return Response({'error': 'خطا در دریافت پیام‌ها'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_set_online_status(request):
    """Set agent online/offline status"""
    try:
        if not hasattr(request.user, 'support_agent'):
            return Response({'error': 'شما پشتیبان نیستید'}, status=403)
        
        is_online = request.data.get('is_online', False)
        agent = request.user.support_agent
        agent.is_online = is_online
        agent.save()
        
        # Notify waiting customers if agent comes online
        if is_online:
            assign_waiting_chats(agent)
        
        return Response({
            'message': f'وضعیت شما به {"آنلاین" if is_online else "آفلاین"} تغییر کرد',
            'is_online': is_online
        })
        
    except Exception as e:
        logger.error(f"Error setting agent status: {e}")
        return Response({'error': 'خطا در تغییر وضعیت'}, status=500)


# Helper functions
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def find_available_agent():
    """Find an available support agent"""
    return SupportAgent.objects.filter(
        is_online=True,
        auto_accept_chats=True
    ).annotate(
        active_chats=Count('assigned_chats', filter=Q(assigned_chats__status__in=['active', 'waiting']))
    ).filter(
        active_chats__lt=F('max_concurrent_chats')
    ).order_by('active_chats').first()


def assign_waiting_chats(agent):
    """Assign waiting chats to newly online agent"""
    if agent.is_available:
        waiting_sessions = ChatSession.objects.filter(
            status='waiting',
            agent__isnull=True
        ).order_by('started_at')
        
        slots_available = agent.max_concurrent_chats - agent.active_chats_count
        
        for session in waiting_sessions[:slots_available]:
            session.agent = agent
            session.status = 'active'
            session.save()
            
            # Notify customer
            send_chat_notification(
                recipient=session.customer,
                session=session,
                notification_type='chat_assigned',
                title='پشتیبان متصل شد',
                body=f'{agent.user.get_full_name()} اکنون آماده کمک به شما است'
            )
            
            # Send real-time update
            send_realtime_session_update(session)


def create_system_message(session, content):
    """Create a system message"""
    from django.contrib.auth.models import User
    system_user, _ = User.objects.get_or_create(username='system', defaults={
        'first_name': 'سیستم',
        'is_active': False
    })
    
    return ChatMessage.objects.create(
        session=session,
        sender=system_user,
        content=content,
        message_type='system'
    )


def send_chat_notification(recipient, session, notification_type, title, body, message=None):
    """Send chat notification with push support"""
    try:
        notification = ChatNotification.objects.create(
            recipient=recipient,
            session=session,
            message=message,
            notification_type=notification_type,
            title=title,
            body=body
        )
        
        # Send browser push notification
        send_browser_push_notification(notification)
        
        # Send real-time WebSocket notification
        send_realtime_notification(notification)
        
        return notification
        
    except Exception as e:
        logger.error(f"Error sending chat notification: {e}")


def send_browser_push_notification(notification):
    """Send browser push notification"""
    try:
        # This would integrate with a push notification service like FCM
        # For now, we'll send via WebSocket
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{notification.recipient.id}",
                {
                    'type': 'push_notification',
                    'notification': {
                        'title': notification.title,
                        'body': notification.body,
                        'icon': '/static/icons/chat-icon.png',
                        'badge': '/static/icons/badge.png',
                        'data': {
                            'session_id': str(notification.session.id) if notification.session else None,
                            'type': notification.notification_type
                        }
                    }
                }
            )
        
        notification.is_sent = True
        notification.sent_at = timezone.now()
        notification.save()
        
    except Exception as e:
        logger.error(f"Error sending browser push notification: {e}")


def send_realtime_message(session, message):
    """Send real-time message via WebSocket"""
    try:
        if channel_layer:
            # Send to session group
            async_to_sync(channel_layer.group_send)(
                f"chat_{session.id}",
                {
                    'type': 'chat_message',
                    'message': ChatMessageSerializer(message).data
                }
            )
            
    except Exception as e:
        logger.error(f"Error sending real-time message: {e}")


def send_realtime_session_update(session):
    """Send real-time session update"""
    try:
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{session.id}",
                {
                    'type': 'session_update',
                    'session': ChatSessionSerializer(session).data
                }
            )
            
    except Exception as e:
        logger.error(f"Error sending real-time session update: {e}")


def send_realtime_notification(notification):
    """Send real-time notification to user"""
    try:
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{notification.recipient.id}",
                {
                    'type': 'chat_notification',
                    'notification': ChatNotificationSerializer(notification).data
                }
            )
            
    except Exception as e:
        logger.error(f"Error sending real-time notification: {e}")


def notify_agents_new_chat(session):
    """Notify all online agents about new chat request"""
    try:
        online_agents = SupportAgent.objects.filter(is_online=True)
        for agent in online_agents:
            send_chat_notification(
                recipient=agent.user,
                session=session,
                notification_type='customer_joined',
                title='مشتری جدید درخواست چت کرد',
                body=f'{session.customer_name} درخواست چت جدید ارسال کرد'
            )
            
    except Exception as e:
        logger.error(f"Error notifying agents: {e}")


def get_estimated_wait_time():
    """Calculate estimated wait time"""
    try:
        waiting_count = ChatSession.objects.filter(status='waiting').count()
        available_agents = SupportAgent.objects.filter(is_online=True).annotate(
            active_chats=Count('assigned_chats', filter=Q(assigned_chats__status__in=['active', 'waiting']))
        ).filter(active_chats__lt=F('max_concurrent_chats')).count()
        
        if available_agents > 0:
            return 1  # Almost immediate
        elif waiting_count == 0:
            return 2  # Very quick
        elif waiting_count <= 5:
            return 5  # Few minutes
        else:
            return 10  # Several minutes
            
    except Exception as e:
        logger.error(f"Error calculating wait time: {e}")
        return 5  # Default


# Push notification registration
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_push_token(request):
    """Register push notification token for user"""
    try:
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token الزامی است'}, status=400)
        
        # Store token in user profile or separate model
        # This is a simplified version - in production you'd have a proper token model
        request.user.profile.push_token = token
        request.user.profile.save()
        
        return Response({'message': 'توکن با موفقیت ثبت شد'})
        
    except Exception as e:
        logger.error(f"Error registering push token: {e}")
        return Response({'error': 'خطا در ثبت توکن'}, status=500)


# Analytics for chat system
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_analytics(request):
    """Get chat analytics (for admin users)"""
    try:
        if not request.user.is_staff:
            return Response({'error': 'شما مجاز نیستید'}, status=403)
        
        from datetime import datetime, timedelta
        
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        analytics = {
            'today': {
                'total_sessions': ChatSession.objects.filter(started_at__date=today).count(),
                'active_sessions': ChatSession.objects.filter(status='active').count(),
                'waiting_sessions': ChatSession.objects.filter(status='waiting').count(),
                'completed_sessions': ChatSession.objects.filter(
                    started_at__date=today, 
                    status='closed'
                ).count()
            },
            'week': {
                'total_sessions': ChatSession.objects.filter(started_at__date__gte=week_ago).count(),
                'avg_rating': ChatSession.objects.filter(
                    started_at__date__gte=week_ago,
                    customer_rating__isnull=False
                ).aggregate(avg_rating=models.Avg('customer_rating'))['avg_rating'] or 0
            },
            'month': {
                'total_sessions': ChatSession.objects.filter(started_at__date__gte=month_ago).count(),
                'total_messages': ChatMessage.objects.filter(
                    session__started_at__date__gte=month_ago
                ).count()
            },
            'agents': {
                'online_count': SupportAgent.objects.filter(is_online=True).count(),
                'total_count': SupportAgent.objects.count()
            }
        }
        
        return Response(analytics)
        
    except Exception as e:
        logger.error(f"Error getting chat analytics: {e}")
        return Response({'error': 'خطا در دریافت آمار'}, status=500)
