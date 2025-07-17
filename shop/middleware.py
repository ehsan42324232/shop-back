from django.utils.deprecation import MiddlewareMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from .models import Store
import threading

# Thread-local storage for current store
_thread_locals = threading.local()


class MultiTenantMiddleware(MiddlewareMixin):
    """
    Middleware to handle multi-tenant functionality based on domain
    """
    
    def process_request(self, request):
        # Get the domain from the request
        domain = self.get_domain_from_request(request)
        
        # Set current store based on domain
        store = self.get_store_by_domain(domain)
        
        # Store the current store in thread-local storage
        _thread_locals.store = store
        
        # Add store to request for easy access
        request.store = store
        
        return None
    
    def get_domain_from_request(self, request):
        """Extract domain from request"""
        # Get host from request
        host = request.get_host()
        
        # Remove port if present
        if ':' in host:
            host = host.split(':')[0]
        
        # Handle development/localhost cases
        if host in ['localhost', '127.0.0.1', 'testserver']:
            # For development, check for a subdomain or use a default
            subdomain = request.META.get('HTTP_X_FORWARDED_HOST')
            if subdomain:
                return subdomain
            # You can also check for a specific header or query parameter
            # For testing purposes, return a test domain
            return request.GET.get('domain', 'default.local')
        
        return host
    
    def get_store_by_domain(self, domain):
        """Get store by domain with caching"""
        # Try to get from cache first
        cache_key = f'store_domain_{domain}'
        store = cache.get(cache_key)
        
        if store is None:
            try:
                store = Store.objects.select_related('owner').get(
                    domain=domain,
                    is_active=True,
                    is_approved=True
                )
                # Cache for 5 minutes
                cache.set(cache_key, store, 300)
            except Store.DoesNotExist:
                store = None
        
        return store


def get_current_store(request=None):
    """
    Get current store from thread-local storage or request
    """
    if request and hasattr(request, 'store'):
        return request.store
    
    return getattr(_thread_locals, 'store', None)


class APITenantMiddleware(MiddlewareMixin):
    """
    Middleware for API requests to handle store identification
    For API requests, we can use different methods to identify the store
    """
    
    def process_request(self, request):
        # Skip if not an API request
        if not request.path.startswith('/api/'):
            return None
        
        store = None
        
        # Method 1: Domain-based (same as web)
        domain = self.get_domain_from_request(request)
        if domain:
            store = self.get_store_by_domain(domain)
        
        # Method 2: Header-based (for API clients)
        if not store:
            store_id = request.META.get('HTTP_X_STORE_ID')
            if store_id:
                try:
                    store = Store.objects.get(
                        id=store_id,
                        is_active=True,
                        is_approved=True
                    )
                except Store.DoesNotExist:
                    pass
        
        # Method 3: Authorization header with store info
        if not store and request.user.is_authenticated:
            # For authenticated users, try to get their default store
            user_stores = Store.objects.filter(
                owner=request.user,
                is_active=True,
                is_approved=True
            )
            if user_stores.exists():
                store = user_stores.first()
        
        # Store in thread-local storage and request
        _thread_locals.store = store
        request.store = store
        
        return None
    
    def get_domain_from_request(self, request):
        """Extract domain from request"""
        host = request.get_host()
        if ':' in host:
            host = host.split(':')[0]
        
        # Handle development cases
        if host in ['localhost', '127.0.0.1', 'testserver']:
            return request.GET.get('domain') or request.META.get('HTTP_X_DOMAIN')
        
        return host
    
    def get_store_by_domain(self, domain):
        """Get store by domain with caching"""
        if not domain:
            return None
            
        cache_key = f'store_domain_{domain}'
        store = cache.get(cache_key)
        
        if store is None:
            try:
                store = Store.objects.select_related('owner').get(
                    domain=domain,
                    is_active=True,
                    is_approved=True
                )
                cache.set(cache_key, store, 300)
            except Store.DoesNotExist:
                store = None
        
        return store


class CORSMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware that handles store-specific domains
    """
    
    def process_response(self, request, response):
        # Get current store
        store = get_current_store(request)
        
        if store:
            # Allow requests from the store's domain
            origin = request.META.get('HTTP_ORIGIN')
            if origin:
                # Check if origin matches store domain
                store_origins = [
                    f'http://{store.domain}',
                    f'https://{store.domain}',
                ]
                
                if origin in store_origins or origin.endswith(f'.{store.domain}'):
                    response['Access-Control-Allow-Origin'] = origin
                    response['Access-Control-Allow-Credentials'] = 'true'
                    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                    response['Access-Control-Allow-Headers'] = 'Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, X-Store-ID, X-Domain'
        
        # For development, allow localhost
        if 'localhost' in request.get_host() or '127.0.0.1' in request.get_host():
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, X-Store-ID, X-Domain'
        
        return response


class SecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for store isolation
    """
    
    def process_request(self, request):
        # Add security headers
        store = get_current_store(request)
        
        if store and hasattr(request, 'user') and request.user.is_authenticated:
            # Check if user has access to this store
            if request.path.startswith('/admin/') and not request.user.is_superuser:
                # Only store owners can access their store's admin
                if not store.owner == request.user:
                    raise Http404("Store not found")
        
        return None
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Add CSP for store domains
        store = get_current_store(request)
        if store:
            csp = f"default-src 'self' https://{store.domain} http://{store.domain}; " \
                  f"script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; " \
                  f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " \
                  f"font-src 'self' https://fonts.gstatic.com; " \
                  f"img-src 'self' data: https:; " \
                  f"connect-src 'self' https://{store.domain} http://{store.domain}"
            response['Content-Security-Policy'] = csp
        
        return response


class LocalizationMiddleware(MiddlewareMixin):
    """
    Middleware to handle RTL/LTR and Farsi localization
    """
    
    def process_request(self, request):
        # Set default language to Farsi for store fronts
        store = get_current_store(request)
        
        if store:
            # Set language and timezone based on store settings
            request.LANGUAGE_CODE = 'fa'  # Farsi
            request.TEXT_DIRECTION = 'rtl'  # Right-to-left
        
        # For admin panel, keep English for platform admin
        if request.path.startswith('/admin/') and request.user.is_authenticated:
            if request.user.is_superuser:
                request.LANGUAGE_CODE = 'en'
                request.TEXT_DIRECTION = 'ltr'
        
        return None


class PerformanceMiddleware(MiddlewareMixin):
    """
    Performance optimization middleware
    """
    
    def process_request(self, request):
        # Add query optimization hints
        request._query_count = 0
        return None
    
    def process_response(self, request, response):
        # Add performance headers for debugging
        if hasattr(request, '_query_count'):
            response['X-DB-Queries'] = str(request._query_count)
        
        # Add caching headers for static content
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            response['Cache-Control'] = 'public, max-age=31536000'  # 1 year
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware per store
    """
    
    def process_request(self, request):
        # Skip rate limiting for admin users
        if request.user.is_authenticated and request.user.is_superuser:
            return None
        
        # Get client IP
        ip = self.get_client_ip(request)
        store = get_current_store(request)
        
        # Create cache key
        cache_key = f'rate_limit_{ip}_{store.id if store else "global"}'
        
        # Check current request count
        current_requests = cache.get(cache_key, 0)
        
        # Rate limit: 100 requests per minute per IP per store
        if current_requests >= 100:
            from django.http import HttpResponse
            return HttpResponse('Rate limit exceeded', status=429)
        
        # Increment counter
        cache.set(cache_key, current_requests + 1, 60)  # 60 seconds
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
