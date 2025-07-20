from django.urls import path
from . import chat_views

# Live Chat API URLs
chat_urlpatterns = [
    # Support status and settings
    path('api/chat/status/', chat_views.get_support_status, name='chat_support_status'),
    
    # Chat sessions
    path('api/chat/start/', chat_views.start_chat_session, name='start_chat_session'),
    path('api/chat/sessions/<uuid:session_id>/messages/', chat_views.get_chat_messages, name='get_chat_messages'),
    path('api/chat/sessions/<uuid:session_id>/close/', chat_views.close_chat_session, name='close_chat_session'),
    path('api/chat/sessions/<uuid:session_id>/rate/', chat_views.rate_chat_session, name='rate_chat_session'),
    
    # Messaging
    path('api/chat/send/', chat_views.send_message, name='send_chat_message'),
    
    # Agent management
    path('api/chat/agent/status/', chat_views.agent_set_online_status, name='agent_set_status'),
    
    # Push notifications
    path('api/chat/push/register/', chat_views.register_push_token, name='register_push_token'),
    
    # Analytics (admin only)
    path('api/chat/analytics/', chat_views.get_chat_analytics, name='chat_analytics'),
]
