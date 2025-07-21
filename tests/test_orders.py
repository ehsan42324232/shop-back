from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from shop.models import Store, Product, Category
from shop.storefront_models import Order, OrderItem, CustomerAddress


class OrderManagementTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create test users
        self.store_owner = User.objects.create_user(
            username='storeowner',
            email='owner@example.com',
            password='testpass123'
        )
        
        self.customer = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='testpass123'
        )
        
        # Create test store
        self.store = Store.objects.create(
            name='Test Store',
            owner=self.store_owner,
            domain='teststore.com',
            is_active=True
        )
        
        # Create test category and product
        self.category = Category.objects.create(
            name='Test Category',
            store=self.store
        )
        
        self.product = Product.objects.create(
            name='Test Product',
            price=100000,
            store=self.store,
            category=self.category,
            stock_quantity=10,
            is_active=True
        )
        
        # Create test address
        self.address = CustomerAddress.objects.create(
            customer=self.customer,
            store=self.store,
            full_name='مشتری تست',
            address_line_1='خیابان تست',
            city='تهران',
            state='تهران',
            postal_code='1234567890',
            phone='09123456789'
        )
        
        # Create test order
        self.order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            order_number='ORD-001',
            status='pending',
            total_amount=100000,
            delivery_address=self.address
        )
        
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=100000
        )

    def test_get_orders_as_store_owner(self):
        """Test store owner can view all orders"""
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.get('/api/orders/', HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_get_orders_as_customer(self):
        """Test customer can only view their own orders"""
        self.client.force_authenticate(user=self.customer)
        
        response = self.client.get('/api/orders/', HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_update_order_status(self):
        """Test updating order status by store owner"""
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.post(f'/api/orders/{self.order.id}/update-status/', {
            'status': 'confirmed',
            'notes': 'سفارش تأیید شد'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh order from database
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'confirmed')

    def test_cancel_order_by_customer(self):
        """Test order cancellation by customer"""
        self.client.force_authenticate(user=self.customer)
        
        response = self.client.post(f'/api/orders/{self.order.id}/cancel/', {
            'reason': 'تغییر نظر'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh order from database
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')

    def test_order_tracking_info(self):
        """Test getting order tracking information"""
        self.client.force_authenticate(user=self.customer)
        
        response = self.client.get(f'/api/orders/{self.order.id}/tracking/', 
                                   HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('order_number', response.data)
        self.assertIn('status', response.data)
        self.assertIn('timeline', response.data)

    def test_order_analytics(self):
        """Test order analytics for store owner"""
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.get('/api/orders/analytics/', 
                                   HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('status_distribution', response.data)

    def test_bulk_update_orders(self):
        """Test bulk updating multiple orders"""
        # Create another order
        order2 = Order.objects.create(
            customer=self.customer,
            store=self.store,
            order_number='ORD-002',
            status='pending',
            total_amount=50000,
            delivery_address=self.address
        )
        
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.post('/api/orders/bulk-update/', {
            'order_ids': [self.order.id, order2.id],
            'action': 'update_status',
            'status': 'confirmed'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 2)

    def test_export_orders(self):
        """Test exporting orders to CSV"""
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.get('/api/orders/export/', 
                                   HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

    def test_unauthorized_order_access(self):
        """Test unauthorized access to order management"""
        # Customer trying to update order status
        self.client.force_authenticate(user=self.customer)
        
        response = self.client.post(f'/api/orders/{self.order.id}/update-status/', {
            'status': 'confirmed'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_order_status_validation(self):
        """Test invalid order status update"""
        self.client.force_authenticate(user=self.store_owner)
        
        response = self.client.post(f'/api/orders/{self.order.id}/update-status/', {
            'status': 'invalid_status'
        }, HTTP_HOST='teststore.com')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)