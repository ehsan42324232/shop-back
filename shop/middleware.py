from django.http import Http404
from django.utils.deprecation import MiddlewareMixin
from .models_with_attributes import Store


class DomainMiddleware(MiddlewareMixin):
    """
    Middleware to resolve store by domain and add to request context
    """
    
    def process_request(self, request):
        # Get the host from the request
        host = request.get_host()
        
        # Remove port if present
        if ':' in host:
            host = host.split(':')[0]
        
        # Skip for admin and API requests to main domain
        if (host.startswith('admin.') or 
            host.startswith('api.') or 
            request.path.startswith('/admin/') or
            request.path.startswith('/api/')):
            return None
        
        # Try to find store by domain
        try:
            store = Store.objects.get(domain=host, is_active=True)
            request.store = store
        except Store.DoesNotExist:
            # If no store found, set store to None
            request.store = None
        
        return None


class StoreContextMiddleware(MiddlewareMixin):
    """
    Middleware to add store context to API responses
    """
    
    def process_request(self, request):
        # For API requests, check for X-Store-Domain header
        if request.path.startswith('/api/'):
            store_domain = request.META.get('HTTP_X_STORE_DOMAIN')
            if store_domain:
                try:
                    store = Store.objects.get(domain=store_domain, is_active=True)
                    request.store = store
                except Store.DoesNotExist:
                    request.store = None
            else:
                request.store = None
        
        return None
