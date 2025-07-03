
from rest_framework import generics, permissions
from shop.models import Comment, Rating, Product
from shop.serializers import CommentSerializer, RatingSerializer

class CommentCreateView(generics.CreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        product_id = self.request.data.get("product_id")
        product = Product.objects.get(id=product_id)
        serializer.save(user=self.request.user, product=product)

class ProductCommentListView(generics.ListAPIView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        product_id = self.kwargs["product_id"]
        return Comment.objects.filter(product__id=product_id)

class RatingCreateView(generics.CreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        product_id = self.request.data.get("product_id")
        product = Product.objects.get(id=product_id)
        serializer.save(user=self.request.user, product=product)

class ProductRatingListView(generics.ListAPIView):
    serializer_class = RatingSerializer

    def get_queryset(self):
        product_id = self.kwargs["product_id"]
        return Rating.objects.filter(product__id=product_id)
