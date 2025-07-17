from django.http import Http404, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .models_with_attributes import Store


class DomainMiddleware(MiddlewareMixin):
    """
    Enhanced middleware to resolve store by domain and add to request context
    """
    
    def process_request(self, request):
        # Get the host from the request
        host = request.get_host()
        
        # Remove port if present
        if ':' in host:
            host = host.split(':')[0]
        
        # Remove www. prefix if present
        if host.startswith('www.'):
            host = host[4:]
        
        # Skip for admin, API, and static requests to main domain
        main_domain = getattr(settings, 'MAIN_DOMAIN', 'localhost')
        
        if (host == main_domain or 
            host.startswith('admin.') or 
            host.startswith('api.') or 
            request.path.startswith('/admin/') or
            request.path.startswith('/api/') or
            request.path.startswith('/static/') or
            request.path.startswith('/media/')):
            request.store = None
            return None
        
        # Try to find store by domain
        try:
            store = Store.objects.get(domain=host, is_active=True)
            request.store = store
            
            # Add store context to all requests
            request.store_context = {
                'store_id': str(store.id),
                'store_name': store.name,
                'store_domain': store.domain,
                'store_currency': store.currency,
                'store_settings': {
                    'tax_rate': float(store.tax_rate),
                    'email': store.email,
                    'phone': store.phone,
                    'address': store.address,
                }
            }
            
        except Store.DoesNotExist:
            # Store not found for this domain
            if request.path.startswith('/api/'):
                # For API requests, return 404 JSON response
                return JsonResponse({
                    'error': 'Store not found',
                    'message': f'No store found for domain: {host}'
                }, status=404)
            else:
                # For web requests, you might want to redirect to a "store not found" page
                # or show a 404 page
                request.store = None
                request.store_context = None
        
        return None


class StoreContextMiddleware(MiddlewareMixin):
    """
    Middleware to add store context to API responses
    """
    
    def process_request(self, request):
        # For API requests, check for X-Store-Domain header as fallback
        if request.path.startswith('/api/') and not hasattr(request, 'store'):
            store_domain = request.META.get('HTTP_X_STORE_DOMAIN')
            if store_domain:
                try:
                    store = Store.objects.get(domain=store_domain, is_active=True)
                    request.store = store
                    request.store_context = {
                        'store_id': str(store.id),
                        'store_name': store.name,
                        'store_domain': store.domain,
                        'store_currency': store.currency,
                    }
                except Store.DoesNotExist:
                    request.store = None
                    request.store_context = None
            else:
                request.store = None
                request.store_context = None
        
        return None
    
    def process_response(self, request, response):
        # Add store context to API responses
        if (request.path.startswith('/api/') and 
            hasattr(request, 'store_context') and 
            request.store_context and
            response.get('Content-Type', '').startswith('application/json')):
            
            # Add store context header
            response['X-Store-Context'] = str(request.store_context)
        
        return response


class CORSMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware to handle multiple domains
    """
    
    def process_response(self, request, response):
        # Allow requests from any store domain
        origin = request.META.get('HTTP_ORIGIN')
        
        if origin:
            # Check if origin is from a valid store domain
            try:
                # Extract domain from origin (remove protocol)
                domain = origin.replace('https://', '').replace('http://', '')
                if ':' in domain:
                    domain = domain.split(':')[0]
                
                # Check if this is a valid store domain
                store = Store.objects.get(domain=domain, is_active=True)
                response['Access-Control-Allow-Origin'] = origin
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-Store-Domain'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                
            except Store.DoesNotExist:
                # Fallback to main domain CORS settings
                main_domain = getattr(settings, 'MAIN_DOMAIN', 'localhost')
                if domain == main_domain:
                    response['Access-Control-Allow-Origin'] = origin
                    response['Access-Control-Allow-Credentials'] = 'true'
                    response['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept, Authorization'
                    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        
        return response


class StoreThemeMiddleware(MiddlewareMixin):
    """
    Middleware to inject store-specific theme and branding
    """
    
    def process_request(self, request):
        if hasattr(request, 'store') and request.store:
            # Add theme context
            request.theme_context = {
                'store_name': request.store.name,
                'store_logo': request.store.logo.url if request.store.logo else None,
                'primary_color': getattr(request.store, 'primary_color', '#007bff'),
                'secondary_color': getattr(request.store, 'secondary_color', '#6c757d'),
                'font_family': getattr(request.store, 'font_family', 'Arial, sans-serif'),
                'custom_css': getattr(request.store, 'custom_css', ''),
                'favicon': getattr(request.store, 'favicon', None),
            }
        
        return None
