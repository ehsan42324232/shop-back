from django.http import HttpResponse, Http404
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache
from .models import Store
import logging

logger = logging.getLogger(__name__)


def get_current_store(request):
    """
    تابع کمکی برای دریافت فروشگاه فعلی از درخواست
    """
    if hasattr(request, 'store') and request.store:
        return request.store
    return None


class DomainBasedStoreMiddleware(MiddlewareMixin):
    """
    میدل‌ور برای مدیریت چند فروشگاه بر اساس دامنه
    هر فروشگاه روی دامنه خودش سرو می‌شود
    """
    
    def process_request(self, request):
        """
        پردازش درخواست و تشخیص فروشگاه بر اساس دامنه
        """
        try:
            # دریافت دامنه از درخواست
            host = request.get_host()
            
            # حذف www از ابتدای دامنه
            if host.startswith('www.'):
                host = host[4:]
            
            # حذف پورت از دامنه برای محیط توسعه
            if ':' in host:
                host = host.split(':')[0]
            
            # دامنه اصلی پلتفرم (برای پنل مدیریت)
            platform_domain = getattr(settings, 'PLATFORM_DOMAIN', 'localhost')
            
            # اگر دامنه پلتفرم اصلی است
            if host == platform_domain or host == 'localhost' or host == '127.0.0.1':
                request.is_platform_request = True
                request.store = None
                request.store_domain = None
                return None
            
            # جستجو در کش برای بهتر شدن عملکرد
            cache_key = f'store_domain_{host}'
            store = cache.get(cache_key)
            
            if store is None:
                try:
                    # جستجوی فروشگاه بر اساس دامنه
                    store = Store.objects.select_related('owner').get(
                        domain=host,
                        is_active=True,
                        is_approved=True
                    )
                    # ذخیره در کش برای 1 ساعت
                    cache.set(cache_key, store, 3600)
                    
                except Store.DoesNotExist:
                    # فروشگاه با این دامنه یافت نشد
                    logger.warning(f'Store not found for domain: {host}')
                    
                    # نمایش پیام خطا
                    return HttpResponse(
                        f'<h1>فروشگاه یافت نشد</h1>'
                        f'<p>فروشگاهی با دامنه <strong>{host}</strong> یافت نشد.</p>'
                        f'<p>لطفاً دامنه را بررسی کنید یا با مدیر تماس بگیرید.</p>',
                        status=404,
                        content_type='text/html; charset=utf-8'
                    )
                
                except Store.MultipleObjectsReturned:
                    # چندین فروشگاه با یک دامنه - مشکل در دیتابیس
                    logger.error(f'Multiple stores found for domain: {host}')
                    return HttpResponse(
                        '<h1>خطا در سیستم</h1>'
                        '<p>مشکل در پیکربندی فروشگاه. لطفاً با مدیر تماس بگیرید.</p>',
                        status=500,
                        content_type='text/html; charset=utf-8'
                    )
            
            # اگر فروشگاه غیرفعال است
            if not store.is_active:
                return HttpResponse(
                    f'<h1>فروشگاه غیرفعال</h1>'
                    f'<p>فروشگاه <strong>{store.name}</strong> در حال حاضر غیرفعال است.</p>'
                    f'<p>لطفاً بعداً تلاش کنید.</p>',
                    status=503,
                    content_type='text/html; charset=utf-8'
                )
            
            # اگر فروشگاه تایید نشده است
            if not store.is_approved:
                return HttpResponse(
                    f'<h1>فروشگاه در انتظار تایید</h1>'
                    f'<p>فروشگاه <strong>{store.name}</strong> هنوز تایید نشده است.</p>'
                    f'<p>لطفاً تا تایید مدیر پلتفرم صبر کنید.</p>',
                    status=503,
                    content_type='text/html; charset=utf-8'
                )
            
            # اختصاص فروشگاه به درخواست
            request.is_platform_request = False
            request.store = store
            request.store_domain = host
            
            # اطلاعات اضافی برای استفاده در ویوها
            request.store_owner = store.owner
            request.store_settings = {
                'currency': store.currency,
                'tax_rate': store.tax_rate,
                'name': store.name,
                'description': store.description,
                'logo': store.logo.url if store.logo else None,
                'email': store.email,
                'phone': store.phone,
                'address': store.address,
            }
            
            return None
            
        except Exception as e:
            logger.error(f'Error in DomainBasedStoreMiddleware: {str(e)}')
            return HttpResponse(
                '<h1>خطا در سیستم</h1>'
                '<p>مشکلی در پردازش درخواست رخ داده است.</p>',
                status=500,
                content_type='text/html; charset=utf-8'
            )
    
    def process_response(self, request, response):
        """
        پردازش پاسخ و افزودن هدرهای مربوط به فروشگاه
        """
        try:
            # افزودن هدر نام فروشگاه
            if hasattr(request, 'store') and request.store:
                response['X-Store-Name'] = request.store.name
                response['X-Store-Domain'] = request.store.domain
                response['X-Store-Currency'] = request.store.currency
            
            # افزودن هدر پلتفرم
            if hasattr(request, 'is_platform_request') and request.is_platform_request:
                response['X-Platform-Request'] = 'true'
            
            return response
            
        except Exception as e:
            logger.error(f'Error in process_response: {str(e)}')
            return response


class StoreSecurityMiddleware(MiddlewareMixin):
    """
    میدل‌ور امنیتی برای فروشگاه‌ها
    """
    
    def process_request(self, request):
        """
        بررسی امنیت درخواست
        """
        try:
            # بررسی IP مشکوک (می‌تواند از تنظیمات خوانده شود)
            blocked_ips = getattr(settings, 'BLOCKED_IPS', [])
            client_ip = self.get_client_ip(request)
            
            if client_ip in blocked_ips:
                logger.warning(f'Blocked IP attempted access: {client_ip}')
                return HttpResponse(
                    '<h1>دسترسی مسدود</h1>'
                    '<p>دسترسی شما به این سایت مسدود شده است.</p>',
                    status=403,
                    content_type='text/html; charset=utf-8'
                )
            
            # بررسی تعداد درخواست‌ها (Rate Limiting ساده)
            if hasattr(request, 'store') and request.store:
                rate_limit_key = f'rate_limit_{client_ip}_{request.store.domain}'
                request_count = cache.get(rate_limit_key, 0)
                
                max_requests = getattr(settings, 'MAX_REQUESTS_PER_MINUTE', 100)
                
                if request_count >= max_requests:
                    logger.warning(f'Rate limit exceeded for IP: {client_ip}')
                    return HttpResponse(
                        '<h1>تعداد درخواست‌ها زیاد است</h1>'
                        '<p>لطفاً چند دقیقه صبر کنید.</p>',
                        status=429,
                        content_type='text/html; charset=utf-8'
                    )
                
                # افزایش شمارنده
                cache.set(rate_limit_key, request_count + 1, 60)
            
            return None
            
        except Exception as e:
            logger.error(f'Error in StoreSecurityMiddleware: {str(e)}')
            return None
    
    def get_client_ip(self, request):
        """
        دریافت IP کلاینت
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class StoreAPIMiddleware(MiddlewareMixin):
    """
    میدل‌ور برای مدیریت API درخواست‌های فروشگاه
    """
    
    def process_request(self, request):
        """
        پردازش درخواست‌های API
        """
        try:
            # بررسی درخواست‌های API
            if request.path.startswith('/api/'):
                
                # درخواست‌های مدیریت پلتفرم
                platform_api_paths = [
                    '/api/admin/',
                    '/api/auth/',
                    '/api/platform/',
                ]
                
                is_platform_api = any(
                    request.path.startswith(path) 
                    for path in platform_api_paths
                )
                
                if is_platform_api:
                    request.is_platform_api = True
                    return None
                
                # درخواست‌های مربوط به فروشگاه
                if hasattr(request, 'store') and request.store:
                    request.is_store_api = True
                    
                    # بررسی اینکه آیا کاربر مالک فروشگاه است
                    if request.user.is_authenticated:
                        request.is_store_owner = request.user == request.store.owner
                    else:
                        request.is_store_owner = False
                
                # افزودن هدرهای CORS برای API
                if request.method == 'OPTIONS':
                    response = HttpResponse()
                    response['Access-Control-Allow-Origin'] = '*'
                    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                    return response
            
            return None
            
        except Exception as e:
            logger.error(f'Error in StoreAPIMiddleware: {str(e)}')
            return None
    
    def process_response(self, request, response):
        """
        پردازش پاسخ API
        """
        try:
            # افزودن هدرهای CORS
            if request.path.startswith('/api/'):
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            
            return response
            
        except Exception as e:
            logger.error(f'Error in process_response: {str(e)}')
            return response


class StoreMaintenanceMiddleware(MiddlewareMixin):
    """
    میدل‌ور برای حالت تعمیر فروشگاه
    """
    
    def process_request(self, request):
        """
        بررسی حالت تعمیر
        """
        try:
            # بررسی حالت تعمیر عمومی
            if getattr(settings, 'MAINTENANCE_MODE', False):
                # اجازه دسترسی به مدیران
                if request.user.is_authenticated and request.user.is_superuser:
                    return None
                
                return HttpResponse(
                    '<h1>سایت در حال تعمیر</h1>'
                    '<p>سایت در حال حاضر در حال تعمیر است. لطفاً بعداً تلاش کنید.</p>',
                    status=503,
                    content_type='text/html; charset=utf-8'
                )
            
            # بررسی حالت تعمیر فروشگاه
            if hasattr(request, 'store') and request.store:
                store_maintenance = cache.get(f'maintenance_{request.store.id}', False)
                
                if store_maintenance:
                    # اجازه دسترسی به مالک فروشگاه
                    if request.user.is_authenticated and request.user == request.store.owner:
                        return None
                    
                    return HttpResponse(
                        f'<h1>فروشگاه در حال تعمیر</h1>'
                        f'<p>فروشگاه <strong>{request.store.name}</strong> در حال حاضر در حال تعمیر است.</p>'
                        f'<p>لطفاً بعداً تلاش کنید.</p>',
                        status=503,
                        content_type='text/html; charset=utf-8'
                    )
            
            return None
            
        except Exception as e:
            logger.error(f'Error in StoreMaintenanceMiddleware: {str(e)}')
            return None
