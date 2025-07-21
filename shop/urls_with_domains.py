# Domain-specific URLs for Multi-Store Platform
# This file contains URL patterns that handle domain-based routing

from django.urls import path, include
from django.conf import settings
from . import views, authentication, storefront_views
from . import domain_views  # Domain management views

# Domain management URLs (Platform Admin)
domain_admin_patterns = [
    # Platform domain management
    path('api/admin/domains/', domain_views.DomainListView.as_view(), name='admin_domains'),
    path('api/admin/domains/<int:pk>/', domain_views.DomainDetailView.as_view(), name='admin_domain_detail'),
    path('api/admin/domains/<int:pk>/approve/', domain_views.approve_domain, name='approve_domain'),
    path('api/admin/domains/<int:pk>/revoke/', domain_views.revoke_domain, name='revoke_domain'),
    
    # SSL Certificate management
    path('api/admin/ssl/certificates/', domain_views.SSLCertificateListView.as_view(), name='ssl_certificates'),
    path('api/admin/ssl/certificates/<int:pk>/', domain_views.SSLCertificateDetailView.as_view(), name='ssl_certificate_detail'),
    path('api/admin/ssl/renew/', domain_views.renew_ssl_certificates, name='renew_ssl'),
    
    # Domain monitoring
    path('api/admin/domains/health/', domain_views.domain_health_check, name='domain_health'),
    path('api/admin/domains/analytics/', domain_views.domain_analytics, name='domain_analytics'),
]

# Store owner domain management
store_domain_patterns = [
    # Store domain settings
    path('api/store/domain/', domain_views.StoreDomainView.as_view(), name='store_domain'),
    path('api/store/domain/verify/', domain_views.verify_domain_ownership, name='verify_domain'),
    path('api/store/domain/check/', domain_views.check_domain_availability, name='check_domain'),
    path('api/store/domain/status/', domain_views.get_domain_status, name='domain_status'),
    
    # SSL management for store owners
    path('api/store/ssl/request/', domain_views.request_ssl_certificate, name='request_ssl'),
    path('api/store/ssl/status/', domain_views.get_ssl_status, name='ssl_status'),
]

# Public domain verification endpoints
public_domain_patterns = [
    # Domain verification endpoints
    path('.well-known/platform-verification.html', domain_views.domain_verification_file, name='domain_verification'),
    path('api/public/domain/verify/<str:token>/', domain_views.public_domain_verification, name='public_domain_verification'),
]

# Dynamic subdomain patterns
subdomain_patterns = [
    # Subdomain-specific routes
    path('', storefront_views.subdomain_home, name='subdomain_home'),
    path('api/subdomain/info/', storefront_views.get_subdomain_info, name='subdomain_info'),
]

# Custom domain patterns  
custom_domain_patterns = [
    # Custom domain routes
    path('', storefront_views.custom_domain_home, name='custom_domain_home'),
    path('api/domain/info/', storefront_views.get_custom_domain_info, name='custom_domain_info'),
]

# Main URL patterns based on domain type
urlpatterns = []

# Add domain-specific patterns based on current domain
if hasattr(settings, 'DOMAIN_ROUTING_ENABLED') and settings.DOMAIN_ROUTING_ENABLED:
    # Platform domain patterns
    if 'PLATFORM_DOMAIN' in dir(settings):
        urlpatterns += [
            path('admin/domains/', include(domain_admin_patterns)),
        ]
    
    # Store domain patterns
    urlpatterns += [
        path('store/domain/', include(store_domain_patterns)),
    ]
    
    # Public patterns (available on all domains)
    urlpatterns += public_domain_patterns

# Domain utility URLs
utility_patterns = [
    # Domain utilities
    path('api/utils/domain/parse/', domain_views.parse_domain, name='parse_domain'),
    path('api/utils/domain/suggest/', domain_views.suggest_domains, name='suggest_domains'),
    path('api/utils/dns/check/', domain_views.check_dns_records, name='check_dns'),
    
    # Redirect management
    path('api/redirects/', domain_views.RedirectListCreateView.as_view(), name='redirects'),
    path('api/redirects/<int:pk>/', domain_views.RedirectDetailView.as_view(), name='redirect_detail'),
]

urlpatterns += utility_patterns

# Error handling for domain issues
error_patterns = [
    path('domain-error/', domain_views.domain_error_page, name='domain_error'),
    path('ssl-error/', domain_views.ssl_error_page, name='ssl_error'),
    path('verification-pending/', domain_views.verification_pending_page, name='verification_pending'),
]

urlpatterns += error_patterns