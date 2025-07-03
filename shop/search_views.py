
from rest_framework import generics
from shop.models import Product
from shop.serializers import ProductSerializer
from django.db.models import Q

class ProductSearchFilterSortView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        domain = self.request.headers.get("X-Store-Domain")
        queryset = Product.objects.filter(store__domain=domain)

        # Search by title or description
        query = self.request.query_params.get("q")
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query))

        # Filter by category
        category_id = self.request.query_params.get("category")
        if category_id:
            queryset = queryset.filter(category__id=category_id)

        # Sort by price or rating
        sort_by = self.request.query_params.get("sort")
        if sort_by == "price_asc":
            queryset = queryset.order_by("price")
        elif sort_by == "price_desc":
            queryset = queryset.order_by("-price")
        elif sort_by == "rating":
            queryset = sorted(queryset, key=lambda p: p.average_rating(), reverse=True)

        return queryset
