# shop app urls
from django.urls import path
urlpatterns = []

from .logistics_views import LogisticsRegisterView

# Add to urlpatterns:
path('logistics/<int:order_id>/', LogisticsRegisterView.as_view(), name='logistics-register'),