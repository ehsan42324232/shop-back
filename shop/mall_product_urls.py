# Mall Platform URL Patterns for Products and Social Media
from django.urls import path, include
from . import mall_product_views as product_views
from . import mall_social_views as social_views

# Product management URL patterns
product_patterns = [
    # Product classes and categories
    path('classes/', product_views.get_product_classes, name='get_product_classes'),
    path('classes/<int:class_id>/attributes/', product_views.get_product_attributes, name='get_product_attributes'),
    
    # Product creation and management
    path('create/', product_views.create_product, name='create_product'),
    path('<int:product_id>/copy/', product_views.create_product_copy, name='create_product_copy'),
    path('list/', product_views.get_store_products, name='get_store_products'),
    path('<int:product_id>/', product_views.get_product_detail, name='get_product_detail'),
    path('<int:product_id>/status/', product_views.update_product_status, name='update_product_status'),
    path('<int:product_id>/delete/', product_views.delete_product, name='delete_product'),
    
    # Predefined attributes
    path('initialize-attributes/', product_views.initialize_predefined_attributes, name='initialize_predefined_attributes'),
]

# Social media integration URL patterns
social_patterns = [
    # Content extraction
    path('extract/', social_views.get_social_media_content, name='get_social_media_content'),
    path('select/', social_views.select_social_content_for_product, name='select_social_content'),
    path('create-product/', social_views.create_product_from_social_content, name='create_product_from_social'),
    
    # Settings and management
    path('settings/', social_views.get_store_social_media_settings, name='get_social_settings'),
    path('settings/update/', social_views.update_store_social_media_settings, name='update_social_settings'),
    path('imported/', social_views.get_imported_social_media, name='get_imported_social_media'),
    path('media/<int:media_id>/delete/', social_views.delete_social_media, name='delete_social_media'),
]

# Main URL patterns for Mall platform
urlpatterns = [
    # Product management
    path('products/', include(product_patterns)),
    
    # Social media integration
    path('social/', include(social_patterns)),
]
