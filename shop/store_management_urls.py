from django.urls import path
from . import store_management_views

app_name = 'store_management'

urlpatterns = [
    # Store request management
    path('request/create/', store_management_views.CreateStoreRequestView.as_view(), name='create-request'),
    path('request/my/', store_management_views.MyStoreRequestView.as_view(), name='my-request'),
    path('request/wizard-data/', store_management_views.store_creation_wizard_data, name='wizard-data'),
    path('subdomain/check/', store_management_views.check_subdomain_availability, name='check-subdomain'),
    
    # Store management
    path('my-store/', store_management_views.MyStoreView.as_view(), name='my-store'),
    path('dashboard/', store_management_views.StoreDashboardView.as_view(), name='dashboard'),
    
    # Store customization
    path('theme/', store_management_views.StoreThemeView.as_view(), name='theme'),
    path('settings/', store_management_views.StoreSettingView.as_view(), name='settings'),
    
    # Analytics
    path('analytics/', store_management_views.StoreAnalyticsView.as_view(), name='analytics'),
]
