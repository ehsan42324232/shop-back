# Import ViewSets from the main views.py file
from ..views import StoreViewSet, CategoryViewSet, ProductViewSet, BasketViewSet, OrderViewSet

# Keep the existing generic views for backward compatibility
from rest_framework import generics, permissions
from django.contrib.auth.models import User
from shop.models import Store, Product, Category, Comment, Rating, Basket, Order, OrderItem
from shop.serializers import (
    StoreSerializer, ProductSerializer, CategorySerializer,
    CommentSerializer, RatingSerializer, BasketSerializer, OrderSerializer
)

class StoreListAPIView(generics.ListAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer

class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'

class StoreDomainProductListAPIView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        domain = self.request.headers.get('X-Store-Domain')
        return Product.objects.filter(store__domain=domain)

class CategoryListByDomainAPIView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        domain = self.request.headers.get('X-Store-Domain')
        return Category.objects.filter(store__domain=domain)

class StoreInfoByDomainAPIView(generics.RetrieveAPIView):
    serializer_class = StoreSerializer

    def get_object(self):
        domain = self.request.headers.get('X-Store-Domain')
        return Store.objects.get(domain=domain)
