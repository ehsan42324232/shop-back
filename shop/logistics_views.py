from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
# Removed GIS imports to avoid GDAL dependency
# from django.contrib.gis.measure import Distance
# from django.contrib.gis.geos import Point
import requests
import json

from .models import Store
from .storefront_models import Order, DeliveryZone, CustomerAddress
from .middleware import get_current_store


class DeliveryMethod(models.Model):
    """
    Delivery methods for stores
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_methods')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Delivery types
    TYPE_CHOICES = [
        ('standard', 'ارسال عادی'),
        ('express', 'ارسال سریع'),
        ('overnight', 'ارسال فوری'),
        ('pickup', 'تحویل حضوری'),
        ('courier', 'پیک'),
    ]
    delivery_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Pricing
    base_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    cost_per_kg = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    
    # Time estimates
    min_delivery_days = models.PositiveIntegerField(default=1)
    max_delivery_days = models.PositiveIntegerField(default=3)
    
    # Availability
    is_active = models.BooleanField(default=True)
    available_zones = models.ManyToManyField(DeliveryZone, blank=True)
    
    # Working hours
    works_weekends = models.BooleanField(default=True)
    cutoff_time = models.TimeField(help_text='زمان آخرین سفارش برای ارسال در همان روز')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['delivery_type', 'name']

    def __str__(self):
        return f'{self.name} - {self.store.name}'

    def calculate_cost(self, order_total, weight=0, delivery_zone=None):
        """Calculate delivery cost for an order"""
        # Free shipping check
        if self.free_shipping_threshold and order_total >= self.free_shipping_threshold:
            return 0
        
        cost = self.base_cost
        
        # Add weight-based cost
        if weight > 0 and self.cost_per_kg > 0:
            cost += weight * self.cost_per_kg
        
        # Zone-based adjustments
        if delivery_zone and hasattr(delivery_zone, 'delivery_multiplier'):
            cost *= delivery_zone.delivery_multiplier
        
        return cost

    def get_estimated_delivery(self):
        """Get estimated delivery date range"""
        from datetime import timedelta
        now = timezone.now()
        
        # Add business days
        min_date = now + timedelta(days=self.min_delivery_days)
        max_date = now + timedelta(days=self.max_delivery_days)
        
        return {
            'min_date': min_date.date(),
            'max_date': max_date.date(),
            'description': f'{self.min_delivery_days}-{self.max_delivery_days} روز کاری'
        }


class Shipment(models.Model):
    """
    Shipment tracking
    """
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    delivery_method = models.ForeignKey(DeliveryMethod, on_delete=models.CASCADE)
    
    # Shipment details
    tracking_number = models.CharField(max_length=100, unique=True)
    carrier = models.CharField(max_length=100, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    dimensions = models.JSONField(default=dict, blank=True)  # {length, width, height}
    
    # Status tracking
    STATUS_CHOICES = [
        ('preparing', 'در حال آماده‌سازی'),
        ('picked_up', 'تحویل به پست'),
        ('in_transit', 'در حال ارسال'),
        ('out_for_delivery', 'در مسیر تحویل'),
        ('delivered', 'تحویل داده شده'),
        ('failed_delivery', 'عدم تحویل'),
        ('returned', 'مرجوع شده'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='preparing')
    
    # Dates
    shipped_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery details
    delivery_notes = models.TextField(blank=True)
    signature_required = models.BooleanField(default=False)
    delivered_to = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'ارسال {self.tracking_number} - سفارش {self.order.order_number}'

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_tracking_number()
        super().save(*args, **kwargs)

    def generate_tracking_number(self):
        """Generate unique tracking number"""
        import random
        import string
        
        prefix = self.order.store.name[:2].upper()
        random_part = ''.join(random.choices(string.digits, k=10))
        return f'{prefix}{random_part}'


class ShipmentTracking(models.Model):
    """
    Detailed shipment tracking events
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=20, choices=Shipment.STATUS_CHOICES)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.shipment.tracking_number} - {self.get_status_display()}'


# Serializers
from rest_framework import serializers

class DeliveryMethodSerializer(serializers.ModelSerializer):
    estimated_delivery = serializers.SerializerMethodField()
    
    class Meta:
        model = DeliveryMethod
        fields = [
            'id', 'name', 'description', 'delivery_type', 'base_cost',
            'free_shipping_threshold', 'min_delivery_days', 'max_delivery_days',
            'estimated_delivery', 'is_active'
        ]

    def get_estimated_delivery(self, obj):
        return obj.get_estimated_delivery()


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ShipmentTracking
        fields = ['status', 'status_display', 'location', 'description', 'occurred_at']


class ShipmentSerializer(serializers.ModelSerializer):
    tracking_events = ShipmentTrackingSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_method_name = serializers.CharField(source='delivery_method.name', read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'tracking_number', 'carrier', 'status', 'status_display',
            'weight', 'shipped_at', 'estimated_delivery', 'delivered_at',
            'delivery_notes', 'delivered_to', 'delivery_method_name',
            'tracking_events'
        ]


class DeliveryMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing delivery methods
    """
    serializer_class = DeliveryMethodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return DeliveryMethod.objects.none()
        
        # Store owners can manage all methods
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return DeliveryMethod.objects.filter(store=store)
        
        # Customers see only active methods
        return DeliveryMethod.objects.filter(store=store, is_active=True)

    def perform_create(self, serializer):
        store = get_current_store(self.request)
        if not store or not hasattr(self.request.user, 'owned_store'):
            raise serializers.ValidationError('فقط صاحبان فروشگاه می‌توانند روش ارسال اضافه کنند')
        
        serializer.save(store=store)

    @action(detail=True, methods=['post'])
    def calculate_cost(self, request, pk=None):
        """
        Calculate delivery cost for specific order
        """
        delivery_method = self.get_object()
        order_total = float(request.data.get('order_total', 0))
        weight = float(request.data.get('weight', 0))
        zone_id = request.data.get('zone_id')
        
        delivery_zone = None
        if zone_id:
            try:
                delivery_zone = DeliveryZone.objects.get(id=zone_id)
            except DeliveryZone.DoesNotExist:
                pass
        
        cost = delivery_method.calculate_cost(order_total, weight, delivery_zone)
        
        return Response({
            'delivery_cost': float(cost),
            'is_free': cost == 0,
            'estimated_delivery': delivery_method.get_estimated_delivery()
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def available_delivery_methods(request):
    """
    Get available delivery methods for an address
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Get customer location (simplified without GIS)
    latitude = request.GET.get('lat')
    longitude = request.GET.get('lng')
    address_id = request.GET.get('address_id')
    
    customer_location = None
    if address_id and request.user.is_authenticated:
        try:
            address = CustomerAddress.objects.get(
                id=address_id,
                customer=request.user
            )
            customer_location = (address.latitude, address.longitude) if address.longitude else None
        except CustomerAddress.DoesNotExist:
            pass
    elif latitude and longitude:
        try:
            customer_location = (float(latitude), float(longitude))
        except (ValueError, TypeError):
            pass

    # Get delivery methods
    delivery_methods = DeliveryMethod.objects.filter(
        store=store,
        is_active=True
    )

    # Filter by available zones if location provided
    # Note: Without GIS, we'll use a simplified distance calculation
    if customer_location:
        available_zones = DeliveryZone.objects.filter(
            store=store,
            is_active=True
        )
        
        # Find zones that contain the customer location (simplified)
        valid_zones = []
        for zone in available_zones:
            # Simple distance check instead of GIS
            if hasattr(zone, 'covers_location_simple'):
                if zone.covers_location_simple(customer_location[0], customer_location[1]):
                    valid_zones.append(zone.id)
        
        if valid_zones:
            delivery_methods = delivery_methods.filter(
                available_zones__id__in=valid_zones
            ).distinct()

    serializer = DeliveryMethodSerializer(delivery_methods, many=True)
    return Response({
        'delivery_methods': serializer.data,
        'location_provided': customer_location is not None
    })


class ShipmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing shipments
    """
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return Shipment.objects.none()
        
        # Store owners can see all shipments
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return Shipment.objects.filter(order__store=store).order_by('-created_at')
        
        # Customers can only see their own shipments
        return Shipment.objects.filter(
            order__store=store,
            order__customer=self.request.user
        ).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def update_tracking(self, request, pk=None):
        """
        Update shipment tracking status
        """
        shipment = self.get_object()
        store = get_current_store(request)
        
        # Check if user is store owner
        if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
            return Response(
                {'error': 'فقط صاحب فروشگاه می‌تواند وضعیت ارسال را به‌روزرسانی کند'},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')
        location = request.data.get('location', '')
        description = request.data.get('description', '')
        
        if new_status not in dict(Shipment.STATUS_CHOICES):
            return Response(
                {'error': 'وضعیت نامعتبر'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update shipment status
        old_status = shipment.status
        shipment.status = new_status
        
        # Set specific dates based on status
        if new_status == 'picked_up' and not shipment.shipped_at:
            shipment.shipped_at = timezone.now()
        elif new_status == 'delivered':
            shipment.delivered_at = timezone.now()
            shipment.delivered_to = request.data.get('delivered_to', '')
            # Also update the order status
            shipment.order.status = 'delivered'
            shipment.order.save()
        
        shipment.save()

        # Add tracking event
        ShipmentTracking.objects.create(
            shipment=shipment,
            status=new_status,
            location=location,
            description=description or f'وضعیت به {shipment.get_status_display()} تغییر کرد',
            occurred_at=timezone.now()
        )

        # Send notification to customer
        self.notify_tracking_update(shipment, old_status, new_status)

        return Response({
            'message': 'وضعیت ارسال با موفقیت به‌روزرسانی شد',
            'shipment': ShipmentSerializer(shipment).data
        })

    @action(detail=True, methods=['get'])
    def track(self, request, pk=None):
        """
        Get detailed tracking information
        """
        shipment = self.get_object()
        
        # Public tracking (no authentication required for tracking number)
        tracking_number = request.GET.get('tracking_number')
        if tracking_number and tracking_number == shipment.tracking_number:
            # Allow public access with tracking number
            pass
        elif shipment.order.customer != request.user and not (
            hasattr(request.user, 'owned_store') and 
            request.user.owned_store == shipment.order.store
        ):
            return Response(
                {'error': 'دسترسی غیرمجاز'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ShipmentSerializer(shipment)
        return Response(serializer.data)

    def notify_tracking_update(self, shipment, old_status, new_status):
        """
        Send tracking update notification to customer
        """
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            from django.conf import settings
            
            # Email notification
            if shipment.order.customer.email:
                subject = f'به‌روزرسانی وضعیت ارسال - {shipment.tracking_number}'
                html_message = render_to_string('emails/shipment_update.html', {
                    'shipment': shipment,
                    'old_status': old_status,
                    'new_status': new_status
                })
                send_mail(
                    subject,
                    '',
                    settings.DEFAULT_FROM_EMAIL,
                    [shipment.order.customer.email],
                    html_message=html_message
                )

            # SMS notification for important updates
            if shipment.order.customer.phone and new_status in ['shipped', 'out_for_delivery', 'delivered']:
                from .utils import send_sms_notification
                message = f'مرسوله {shipment.tracking_number} - {shipment.get_status_display()}'
                send_sms_notification(shipment.order.customer.phone, message)

        except Exception as e:
            print(f"Failed to send tracking notification: {e}")


@api_view(['GET'])
@permission_classes([AllowAny])
def track_shipment(request, tracking_number):
    """
    Public shipment tracking by tracking number
    """
    try:
        shipment = Shipment.objects.get(tracking_number=tracking_number)
    except Shipment.DoesNotExist:
        return Response(
            {'error': 'کد پیگیری یافت نشد'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Public tracking information (limited)
    tracking_data = {
        'tracking_number': shipment.tracking_number,
        'status': shipment.get_status_display(),
        'status_code': shipment.status,
        'order_number': shipment.order.order_number,
        'estimated_delivery': shipment.estimated_delivery,
        'delivered_at': shipment.delivered_at,
        'tracking_events': []
    }

    # Add tracking events
    for event in shipment.tracking_events.all():
        tracking_data['tracking_events'].append({
            'status': event.get_status_display(),
            'location': event.location,
            'description': event.description,
            'occurred_at': event.occurred_at
        })

    return Response(tracking_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shipment(request, order_id):
    """
    Create shipment for an order
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'سفارش یافت نشد'}, status=404)

    store = get_current_store(request)
    if not store or order.store != store:
        return Response({'error': 'دسترسی غیرمجاز'}, status=403)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'فقط صاحب فروشگاه می‌تواند مرسوله ایجاد کند'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Check if shipment already exists
    if hasattr(order, 'shipment'):
        return Response(
            {'error': 'برای این سفارش قبلاً مرسوله ایجاد شده'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get delivery method
    delivery_method_id = request.data.get('delivery_method_id')
    try:
        delivery_method = DeliveryMethod.objects.get(
            id=delivery_method_id,
            store=store,
            is_active=True
        )
    except DeliveryMethod.DoesNotExist:
        return Response(
            {'error': 'روش ارسال نامعتبر'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create shipment
    shipment = Shipment.objects.create(
        order=order,
        delivery_method=delivery_method,
        weight=request.data.get('weight', 0),
        dimensions=request.data.get('dimensions', {}),
        carrier=request.data.get('carrier', ''),
        estimated_delivery=delivery_method.get_estimated_delivery()['max_date']
    )

    # Add initial tracking event
    ShipmentTracking.objects.create(
        shipment=shipment,
        status='preparing',
        description='مرسوله ایجاد شد و در حال آماده‌سازی است',
        occurred_at=timezone.now()
    )

    # Update order status
    order.status = 'processing'
    order.save()

    return Response({
        'message': 'مرسوله با موفقیت ایجاد شد',
        'shipment': ShipmentSerializer(shipment).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def logistics_analytics(request):
    """
    Get logistics analytics for store owners
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can view analytics'},
            status=status.HTTP_403_FORBIDDEN
        )

    from django.db.models import Count, Avg, Sum
    from datetime import datetime, timedelta

    # Date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    shipments = Shipment.objects.filter(
        order__store=store,
        created_at__gte=start_date
    )

    # Delivery performance
    delivered_shipments = shipments.filter(status='delivered')
    avg_delivery_time = None
    
    if delivered_shipments.exists():
        delivery_times = []
        for shipment in delivered_shipments:
            if shipment.shipped_at and shipment.delivered_at:
                delta = shipment.delivered_at - shipment.shipped_at
                delivery_times.append(delta.days)
        
        if delivery_times:
            avg_delivery_time = sum(delivery_times) / len(delivery_times)

    # Status distribution
    status_distribution = shipments.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # Delivery method popularity
    method_stats = shipments.values('delivery_method__name').annotate(
        count=Count('id'),
        avg_cost=Avg('delivery_method__base_cost')
    ).order_by('-count')

    return Response({
        'summary': {
            'total_shipments': shipments.count(),
            'delivered_shipments': delivered_shipments.count(),
            'average_delivery_days': round(avg_delivery_time, 1) if avg_delivery_time else None,
            'delivery_success_rate': round(
                (delivered_shipments.count() / shipments.count() * 100), 1
            ) if shipments.count() > 0 else 0
        },
        'status_distribution': list(status_distribution),
        'delivery_methods': list(method_stats)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_shipments(request):
    """
    Bulk update shipment status
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can update shipments'},
            status=status.HTTP_403_FORBIDDEN
        )

    shipment_ids = request.data.get('shipment_ids', [])
    new_status = request.data.get('status')
    location = request.data.get('location', '')
    description = request.data.get('description', '')

    if not shipment_ids or not new_status:
        return Response(
            {'error': 'shipment_ids and status are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_status not in dict(Shipment.STATUS_CHOICES):
        return Response({'error': 'Invalid status'}, status=400)

    shipments = Shipment.objects.filter(
        id__in=shipment_ids,
        order__store=store
    )

    updated_count = 0
    with transaction.atomic():
        for shipment in shipments:
            old_status = shipment.status
            shipment.status = new_status
            
            if new_status == 'picked_up' and not shipment.shipped_at:
                shipment.shipped_at = timezone.now()
            elif new_status == 'delivered':
                shipment.delivered_at = timezone.now()
                shipment.order.status = 'delivered'
                shipment.order.save()
            
            shipment.save()

            # Add tracking event
            ShipmentTracking.objects.create(
                shipment=shipment,
                status=new_status,
                location=location,
                description=description or f'به‌روزرسانی انبوه - {shipment.get_status_display()}',
                occurred_at=timezone.now()
            )

            updated_count += 1

    return Response({
        'message': f'{updated_count} مرسوله با موفقیت به‌روزرسانی شد',
        'updated_count': updated_count
    })
