# shop/sms_campaign_urls.py
"""
Mall Platform - SMS Campaign URL Configuration
URL patterns for SMS campaign management
"""
from django.urls import path
from . import sms_campaign_views

urlpatterns = [
    # SMS Templates
    path('sms/templates/', sms_campaign_views.sms_templates, name='sms_templates'),
    path('sms/templates/<int:template_id>/', sms_campaign_views.sms_template_detail, name='sms_template_detail'),
    path('sms/template-variables/', sms_campaign_views.template_variables, name='template_variables'),
    path('sms/preview-template/', sms_campaign_views.preview_template, name='preview_template'),
    
    # Customer Segments
    path('sms/segments/', sms_campaign_views.customer_segments, name='customer_segments'),
    path('sms/segments/<int:segment_id>/', sms_campaign_views.customer_segment_detail, name='customer_segment_detail'),
    path('sms/segments/<int:segment_id>/refresh/', sms_campaign_views.refresh_segment_count, name='refresh_segment_count'),
    path('sms/segments/<int:segment_id>/preview/', sms_campaign_views.segment_preview, name='segment_preview'),
    
    # SMS Campaigns
    path('sms/campaigns/', sms_campaign_views.sms_campaigns, name='sms_campaigns'),
    path('sms/campaigns/<int:campaign_id>/', sms_campaign_views.sms_campaign_detail, name='sms_campaign_detail'),
    path('sms/campaigns/<int:campaign_id>/start/', sms_campaign_views.start_campaign, name='start_campaign'),
    path('sms/campaigns/<int:campaign_id>/pause/', sms_campaign_views.pause_campaign, name='pause_campaign'),
    path('sms/campaigns/<int:campaign_id>/resume/', sms_campaign_views.resume_campaign, name='resume_campaign'),
    path('sms/campaigns/<int:campaign_id>/delivery-report/', sms_campaign_views.campaign_delivery_report, name='campaign_delivery_report'),
    
    # Analytics & Dashboard
    path('sms/analytics/', sms_campaign_views.sms_analytics, name='sms_analytics'),
    path('sms/dashboard/', sms_campaign_views.sms_dashboard, name='sms_dashboard'),
    
    # Utilities
    path('sms/test/', sms_campaign_views.test_sms, name='test_sms'),
    path('sms/bulk-import/', sms_campaign_views.bulk_import_recipients, name='bulk_import_recipients'),
]
