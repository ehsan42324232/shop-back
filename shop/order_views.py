
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from shop.models import Product, Basket, Order, OrderItem, Store
from shop.serializers import BasketSerializer, OrderSerializer

class BasketView(generics.ListAPIView):
    serializer_class = BasketSerializer

    def get_queryset(self):
        return Basket.objects.filter(user=self.request.user)

class AddToBasketView(APIView):
    def post(self, request):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)
        product = Product.objects.get(id=product_id)
        basket_item, created = Basket.objects.get_or_create(user=request.user, product=product)
        if not created:
            basket_item.quantity += int(quantity)
            basket_item.save()
        return Response({"message": "Added to basket."})

class CheckoutView(APIView):
    def post(self, request):
        basket_items = Basket.objects.filter(user=request.user)
        if not basket_items.exists():
            return Response({"message": "Basket is empty."}, status=status.HTTP_400_BAD_REQUEST)

        store = basket_items.first().product.store
        order = Order.objects.create(user=request.user, store=store)
        for item in basket_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_order=item.product.price
            )
        basket_items.delete()
        return Response({"message": "Order placed successfully."})

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

class StoreOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        store = Store.objects.get(owner=self.request.user)
        return Order.objects.filter(store=store)
