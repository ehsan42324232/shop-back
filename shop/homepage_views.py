from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import TemplateView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Store


class HomePageView(TemplateView):
    """Modern homepage with live chat integration"""
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get platform statistics
        context.update({
            'total_stores': Store.objects.filter(is_active=True).count(),
            'platform_name': 'شاپ پلاس',  # Shop Plus in Persian
            'platform_tagline': 'پلتفرم هوشمند فروشگاه‌سازی',
            'features': [
                {
                    'title': 'فروشگاه حرفه‌ای',
                    'description': 'ساخت فروشگاه آنلاین با امکانات پیشرفته',
                    'icon': 'store'
                },
                {
                    'title': 'مدیریت موجودی',
                    'description': 'کنترل کامل موجودی و محصولات',
                    'icon': 'inventory'
                },
                {
                    'title': 'پشتیبانی ۲۴/۷',
                    'description': 'چت آنلاین و پشتیبانی مداوم',
                    'icon': 'support'
                },
                {
                    'title': 'تحلیل فروش',
                    'description': 'گزارش‌های تفصیلی و آنالیز دقیق',
                    'icon': 'analytics'
                }
            ]
        })
        return context


@api_view(['POST'])
def start_free_trial(request):
    """Handle free trial registration"""
    try:
        store_name = request.data.get('store_name', '')
        email = request.data.get('email', '')
        phone = request.data.get('phone', '')
        
        if not store_name or not email:
            return Response({
                'success': False,
                'message': 'نام فروشگاه و ایمیل الزامی است'
            }, status=400)
        
        # Check if store name already exists
        if Store.objects.filter(name=store_name).exists():
            return Response({
                'success': False,
                'message': 'این نام فروشگاه قبلاً استفاده شده است'
            }, status=400)
        
        # Create trial store (you can add more logic here)
        store = Store.objects.create(
            name=store_name,
            description=f'فروشگاه {store_name}',
            # Add other necessary fields
        )
        
        return Response({
            'success': True,
            'message': 'فروشگاه شما با موفقیت ایجاد شد!',
            'store_id': store.id,
            'redirect_url': f'/admin/'  # Redirect to admin or dashboard
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطا در ایجاد فروشگاه. لطفاً دوباره تلاش کنید.'
        }, status=500)


def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, '404.html', status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, '500.html', status=500)
