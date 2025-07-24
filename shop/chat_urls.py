# shop/chat_urls.py
"""
Mall Platform - Chat URL Configuration
"""
from django.urls import path
from . import realtime_chat_views

urlpatterns = [
    # Chat rooms
    path('chat/create/', realtime_chat_views.create_chat_room, name='create_chat_room'),
    path('chat/rooms/', realtime_chat_views.get_chat_rooms, name='get_chat_rooms'),
    path('chat/rooms/<uuid:room_id>/messages/', realtime_chat_views.get_chat_messages, name='get_chat_messages'),
    path('chat/rooms/<uuid:room_id>/send/', realtime_chat_views.send_message, name='send_message'),
    path('chat/rooms/<uuid:room_id>/close/', realtime_chat_views.close_chat, name='close_chat'),
    path('chat/rooms/<uuid:room_id>/rate/', realtime_chat_views.rate_chat, name='rate_chat'),
    
    # Templates
    path('chat/templates/', realtime_chat_views.get_chat_templates, name='get_chat_templates'),
]
