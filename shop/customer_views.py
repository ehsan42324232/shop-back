from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .customer_models import (
    CustomerProfile, CustomerAddress, WalletTransaction, 
    CustomerNotification, CustomerWishlist, CustomerReview
)
from .customer_serializers import (
    CustomerProfileSerializer, CustomerAddressSerializer,
    WalletTransactionSerializer, CustomerNotificationSerializer,
    CustomerWishlistSerializer, CustomerReviewSerializer
)
from .models import Order, Product, ProductInstance
from .sms_service import SMSService
from .live_sms_provider import LiveSMSProvider


class CustomerProfileViewSet(viewsets.ModelViewSet):
    """Enhanced customer profile management"""
    
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CustomerProfile.objects.filter(user=self.request.user)
    
    def get_object(self):
        profile, created = CustomerProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get customer dashboard statistics"""
        try:
            profile = self.get_object()
            
            # Calculate recent orders stats
            recent_orders = Order.objects.filter(customer=profile.user).order_by('-created_at')[:5]
            
            # Calculate monthly spending
            now = timezone.now()
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_spent = Order.objects.filter(
                customer=profile.user,
                created_at__gte=current_month_start,
                status='DELIVERED'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Get unread notifications count
            unread_notifications = CustomerNotification.objects.filter(
                customer=profile,
                is_read=False
            ).count()
            
            # Get wishlist count
            wishlist_count = CustomerWishlist.objects.filter(customer=profile).count()
            
            # Recent transactions
            recent_wallet_transactions = WalletTransaction.objects.filter(
                customer=profile
            ).order_by('-created_at')[:5]
            
            stats = {
                'profile': CustomerProfileSerializer(profile).data,
                'recent_orders': [
                    {
                        'id': order.order_number,
                        'date': order.created_at.strftime('%Y/%m/%d'),
                        'status': order.status,
                        'status_display': order.get_status_display(),
                        'total': float(order.total_amount),
                        'items_count': order.items.count()
                    } for order in recent_orders
                ],
                'monthly_stats': {
                    'spent_this_month': float(monthly_spent),
                    'orders_this_month': recent_orders.filter(created_at__gte=current_month_start).count(),
                    'points_earned_this_month': profile.loyalty_points
                },
                'account_summary': {
                    'wallet_balance': float(profile.wallet_balance),
                    'loyalty_points': profile.loyalty_points,
                    'total_orders': profile.total_orders,
                    'total_spent': float(profile.total_spent),
                    'status': profile.get_status_display_persian(),
                    'member_since': profile.registration_date.strftime('%Y/%m/%d')
                },
                'notifications': {
                    'unread_count': unread_notifications,
                    'total_count': CustomerNotification.objects.filter(customer=profile).count()
                },
                'wishlist_count': wishlist_count,
                'recent_wallet_transactions': [
                    {
                        'id': str(trans.transaction_id),
                        'type': trans.get_transaction_type_display(),
                        'amount': float(trans.amount),
                        'date': trans.created_at.strftime('%Y/%m/%d %H:%M'),
                        'description': trans.description
                    } for trans in recent_wallet_transactions
                ]
            }
            
            return Response(stats)
            
        except Exception as e:
            return Response(
                {'error': f'خطا در بارگیری اطلاعات: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def charge_wallet(self, request):
        """Charge customer wallet"""
        try:
            profile = self.get_object()
            amount = Decimal(request.data.get('amount', 0))
            payment_method = request.data.get('payment_method', 'ONLINE')
            
            if amount <= 0:
                return Response(
                    {'error': 'مبلغ باید بیشتر از صفر باشد'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create wallet transaction
            balance_before = profile.wallet_balance
            profile.wallet_balance += amount
            profile.save()
            
            transaction = WalletTransaction.objects.create(
                customer=profile,
                transaction_type='CHARGE',
                amount=amount,
                balance_before=balance_before,
                balance_after=profile.wallet_balance,
                description=f'شارژ کیف پول به روش {payment_method}'
            )
            
            # Send notification
            CustomerNotification.objects.create(
                customer=profile,
                notification_type='WALLET',
                title='شارژ کیف پول',
                message=f'کیف پول شما با مبلغ {amount:,.0f} تومان شارژ شد.'
            )
            
            return Response({
                'message': 'کیف پول با موفقیت شارژ شد',
                'new_balance': float(profile.wallet_balance),
                'transaction_id': str(transaction.transaction_id)
            })
            
        except Exception as e:
            return Response(
                {'error': f'خطا در شارژ کیف پول: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def redeem_points(self, request):
        """Redeem loyalty points for wallet credit"""
        try:
            profile = self.get_object()
            points = int(request.data.get('points', 0))
            
            if points <= 0:
                return Response(
                    {'error': 'تعداد امتیاز باید بیشتر از صفر باشد'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if profile.loyalty_points < points:
                return Response(
                    {'error': 'امتیاز کافی ندارید'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            wallet_credit = profile.redeem_points(points)
            
            if wallet_credit > 0:
                # Send notification
                CustomerNotification.objects.create(
                    customer=profile,
                    notification_type='WALLET',
                    title='استفاده از امتیاز وفاداری',
                    message=f'{points} امتیاز شما به {wallet_credit:,.0f} تومان تبدیل و به کیف پول اضافه شد.'
                )
                
                return Response({
                    'message': 'امتیاز با موفقیت به اعتبار کیف پول تبدیل شد',
                    'points_redeemed': points,
                    'wallet_credit': float(wallet_credit),
                    'remaining_points': profile.loyalty_points,
                    'new_wallet_balance': float(profile.wallet_balance)
                })
            else:
                return Response(
                    {'error': 'خطا در تبدیل امتیاز'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            return Response(
                {'error': f'خطا در استفاده از امتیاز: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def order_history(self, request):
        """Get customer order history with filters"""
        try:
            profile = self.get_object()
            
            # Query parameters
            status_filter = request.query_params.get('status', None)
            date_from = request.query_params.get('date_from', None)
            date_to = request.query_params.get('date_to', None)
            page = int(request.query_params.get('page', 1))
            per_page = int(request.query_params.get('per_page', 10))
            
            # Build query
            orders = Order.objects.filter(customer=profile.user)
            
            if status_filter:
                orders = orders.filter(status=status_filter)
            
            if date_from:
                orders = orders.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
            
            if date_to:
                orders = orders.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d'))
            
            orders = orders.order_by('-created_at')
            
            # Pagination
            total = orders.count()
            start = (page - 1) * per_page
            end = start + per_page
            paginated_orders = orders[start:end]
            
            orders_data = []
            for order in paginated_orders:
                orders_data.append({
                    'id': order.order_number,
                    'date': order.created_at.strftime('%Y/%m/%d'),
                    'status': order.status,
                    'status_display': order.get_status_display(),
                    'total': float(order.total_amount),
                    'items_count': order.items.count(),
                    'payment_method': order.payment_method,
                    'shipping_address': order.shipping_address,
                    'tracking_number': getattr(order, 'tracking_number', None),
                    'items': [
                        {
                            'product_name': item.product.name,
                            'quantity': item.quantity,
                            'price': float(item.price),
                            'total': float(item.quantity * item.price)
                        } for item in order.items.all()
                    ]
                })
            
            return Response({
                'orders': orders_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
            
        except Exception as e:
            return Response(
                {'error': f'خطا در بارگیری تاریخچه سفارشات: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerAddressViewSet(viewsets.ModelViewSet):
    """Customer address management"""
    
    serializer_class = CustomerAddressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        return CustomerAddress.objects.filter(customer=profile, is_active=True)
    
    def perform_create(self, serializer):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        serializer.save(customer=profile)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set address as default"""
        try:
            address = self.get_object()
            
            # Remove default from other addresses
            CustomerAddress.objects.filter(
                customer=address.customer
            ).update(is_default=False)
            
            # Set this address as default
            address.is_default = True
            address.save()
            
            return Response({'message': 'آدرس به عنوان پیش‌فرض تنظیم شد'})
            
        except Exception as e:
            return Response(
                {'error': f'خطا در تنظیم آدرس پیش‌فرض: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Customer wallet transaction history"""
    
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        return WalletTransaction.objects.filter(customer=profile)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get wallet transaction summary"""
        try:
            profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
            
            # Calculate summary stats
            transactions = WalletTransaction.objects.filter(customer=profile)
            
            summary = {
                'current_balance': float(profile.wallet_balance),
                'total_charged': float(transactions.filter(
                    transaction_type='CHARGE'
                ).aggregate(total=Sum('amount'))['total'] or 0),
                'total_spent': float(transactions.filter(
                    transaction_type='PURCHASE'
                ).aggregate(total=Sum('amount'))['total'] or 0),
                'total_refunded': float(transactions.filter(
                    transaction_type='REFUND'
                ).aggregate(total=Sum('amount'))['total'] or 0),
                'points_redeemed_value': float(transactions.filter(
                    transaction_type='POINTS_REDEMPTION'
                ).aggregate(total=Sum('amount'))['total'] or 0),
                'transaction_count': transactions.count(),
                'last_transaction': None
            }
            
            last_transaction = transactions.first()
            if last_transaction:
                summary['last_transaction'] = {
                    'date': last_transaction.created_at.strftime('%Y/%m/%d %H:%M'),
                    'type': last_transaction.get_transaction_type_display(),
                    'amount': float(last_transaction.amount)
                }
            
            return Response(summary)
            
        except Exception as e:
            return Response(
                {'error': f'خطا در بارگیری خلاصه تراکنش‌ها: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerNotificationViewSet(viewsets.ModelViewSet):
    """Customer notifications management"""
    
    serializer_class = CustomerNotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        return CustomerNotification.objects.filter(customer=profile)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'message': 'اطلاعیه به عنوان خوانده شده علامت‌گذاری شد'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        try:
            profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
            
            updated_count = CustomerNotification.objects.filter(
                customer=profile,
                is_read=False
            ).update(is_read=True)
            
            return Response({
                'message': f'{updated_count} اطلاعیه به عنوان خوانده شده علامت‌گذاری شد',
                'updated_count': updated_count
            })
            
        except Exception as e:
            return Response(
                {'error': f'خطا در علامت‌گذاری اطلاعیه‌ها: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread notifications count"""
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        count = CustomerNotification.objects.filter(
            customer=profile,
            is_read=False
        ).count()
        return Response({'unread_count': count})


class CustomerWishlistViewSet(viewsets.ModelViewSet):
    """Customer wishlist management"""
    
    serializer_class = CustomerWishlistSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        return CustomerWishlist.objects.filter(customer=profile).select_related('product')
    
    def perform_create(self, serializer):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        serializer.save(customer=profile)
    
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle product in wishlist"""
        try:
            profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
            product_id = request.data.get('product_id')
            
            if not product_id:
                return Response(
                    {'error': 'شناسه محصول الزامی است'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response(
                    {'error': 'محصول یافت نشد'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            wishlist_item, created = CustomerWishlist.objects.get_or_create(
                customer=profile,
                product=product
            )
            
            if not created:
                wishlist_item.delete()
                return Response({
                    'message': 'محصول از لیست علاقه‌مندی‌ها حذف شد',
                    'in_wishlist': False
                })
            else:
                return Response({
                    'message': 'محصول به لیست علاقه‌مندی‌ها اضافه شد',
                    'in_wishlist': True
                })
                
        except Exception as e:
            return Response(
                {'error': f'خطا در تغییر وضعیت علاقه‌مندی: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerReviewViewSet(viewsets.ModelViewSet):
    """Customer product reviews"""
    
    serializer_class = CustomerReviewSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        return CustomerReview.objects.filter(customer=profile)
    
    def perform_create(self, serializer):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        serializer.save(customer=profile)
    
    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """Get customer's own reviews"""
        try:
            profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
            reviews = CustomerReview.objects.filter(customer=profile).select_related('product')
            
            reviews_data = []
            for review in reviews:
                reviews_data.append({
                    'id': review.id,
                    'product': {
                        'id': review.product.id,
                        'name': review.product.name,
                        'image': review.product.images.first().image.url if review.product.images.exists() else None
                    },
                    'rating': review.rating,
                    'title': review.title,
                    'comment': review.comment,
                    'date': review.created_at.strftime('%Y/%m/%d'),
                    'is_verified_purchase': review.is_verified_purchase,
                    'is_approved': review.is_approved,
                    'helpful_count': review.helpful_count
                })
            
            return Response({'reviews': reviews_data})
            
        except Exception as e:
            return Response(
                {'error': f'خطا در بارگیری نظرات: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
