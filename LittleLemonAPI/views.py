from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User, Group
from django.db import IntegrityError
from .models import Cart, Category, MenuItem, Order, OrderItem
from .serializers import CartSerializer, CategorySerializer, MenuItemSerializer, OrderSerializer
from .permissions import IsAdminOrManager, IsAuthenticated, IsCustomer, IsDeliveryCrew, IsManager
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
# CategoryViewSet:
#   - CRUD operations for menu categories.
#   - Only Admins/Managers can access.
#   - GET lists all categories.
#   - POST creates a new category.
#   - PUT/PATCH updates an existing category.
#   - DELETE removes a category.
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrManager]
# MenuItemViewSet:
#   - CRUD operations for menu items.
#   - Filtering, searching, and ordering supported.
#   - Only Admins/Managers can modify; anyone can view.
#   - GET lists all menu items.
#   - POST creates a new menu item.
#   - PUT/PATCH updates an existing menu item.
#   - DELETE removes a menu item.
class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['title', 'price']  # filter by exact match
    search_fields = ['title']              # full-text search
    ordering_fields = ['price', 'title']   # sort by fields

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return [IsAdminOrManager()]
        return []
# CartViewSet:
#   - View, add, and clear cart items for authenticated customers.
#   - Permissions: IsAuthenticated and IsCustomer.
#   - GET lists cart items.
#   - POST adds a menu item to the cart with quantity and calculates price.
#   - DELETE clears the cart.
class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def list(self, request):
        cart_items = Cart.objects.filter(user=request.user)
        serializer = CartSerializer(cart_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request):
        menu_item_id = request.data.get("menuitem")
        quantity = int(request.data.get("quantity", 1))

        try:
            item = MenuItem.objects.get(id=menu_item_id)
        except MenuItem.DoesNotExist:
            return Response({"detail": "Menu item not found"}, status=404)

        price = quantity * item.price

        cart_item = Cart.objects.create(
            user=request.user,
            menuitem=item,
            quantity=quantity,
            unit_price=item.price,
            price=price
        )
        serializer = CartSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        Cart.objects.filter(user=request.user).delete()
        return Response({"detail": "Cart cleared"}, status=status.HTTP_200_OK)
# OrderViewSet:
#   - CRUD operations for orders.
#   - Permissions and queryset filtered by user group:
#       - Managers: all orders.
#       - Delivery crew: assigned orders.
#       - Customers: own orders.
#   - POST creates an order from the user's cart.
#   - PATCH allows managers to assign delivery crew and update status;
#     delivery crew can update status only.
#   - GET returns orders based on user group.
#   - Filtering, searching, and ordering supported.
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    queryset = Order.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Filtering by fields
    filterset_fields = ['status', 'delivery_crew', 'date', 'user']
    # Search fields (e.g., by username or delivery crew username)
    search_fields = ['user__username', 'delivery_crew__username']
    # Allow ordering
    ordering_fields = ['date', 'total', 'status']

    def get_permissions(self):
        if self.request.method in ['PUT', 'DELETE']:
            return [IsManager()]
        elif self.request.method == 'GET':
            if self.request.user.groups.filter(name='Manager').exists():
                return [permissions.IsAuthenticated()]
            elif self.request.user.groups.filter(name='Delivery crew').exists():
                return [IsDeliveryCrew()]
            else:
                return [IsCustomer()]
        elif self.request.method == 'PATCH':
            if self.request.user.groups.filter(name='Manager').exists():
                return [permissions.IsAuthenticated()]
            elif self.request.user.groups.filter(name='Delivery crew').exists():
                return [IsDeliveryCrew()]
        elif self.request.method == 'POST':
            if self.request.user.groups.filter(name='Manager').exists():
                return [permissions.IsAuthenticated()]
            else:
                return [IsCustomer()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Manager').exists():
            return Order.objects.all()
        elif user.groups.filter(name='Delivery crew').exists():
            return Order.objects.filter(delivery_crew=user)
        else:
            return Order.objects.filter(user=user)

    def create(self, request):
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            return Response({"detail": "Cart is empty"}, status=400)

        total = sum(item.price for item in cart_items)
        order = Order.objects.create(user=request.user, total=total, date=timezone.now().date())

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                menuitem=item.menuitem,
                quantity=item.quantity,
                unit_price=item.unit_price,
                price=item.price
            )

        cart_items.delete()

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found"}, status=404)

        user = request.user
        if user.groups.filter(name='Manager').exists():
            delivery_crew_id = request.data.get('delivery_crew')
            status_value = request.data.get('status')
            if delivery_crew_id:
                try:
                    delivery_user = User.objects.get(id=delivery_crew_id)
                    order.delivery_crew = delivery_user
                except User.DoesNotExist:
                    return Response({"detail": "Delivery crew user not found"}, status=404)
            if status_value in [0, 1]:
                order.status = bool(status_value)
            order.save()
            return Response({"detail": "Order updated"}, status=200)

        elif user.groups.filter(name='Delivery crew').exists():
            if 'status' in request.data:
                order.status = bool(request.data['status'])
                order.save()
                return Response({"detail": "Status updated"}, status=200)
            return Response({"detail": "Only status can be updated"}, status=403)

        return Response({"detail": "Permission denied"}, status=403)


# Utility function
def get_group(name):
    return Group.objects.get(name=name)

# ManagerGroupView / ManagerGroupDetailView:
#   - GET: List users in Manager group.
#   - POST: Add user to Manager group.
#   - DELETE: Remove user from Manager group.
#
# /api/groups/manager/users
class ManagerGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def get(self, request):
        group = get_group("Manager")
        users = group.user_set.all()
        data = [{"id": u.id, "username": u.username} for u in users]
        return Response(data)

    def post(self, request):
        user_id = request.data.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
            group = get_group("Manager")
            group.user_set.add(user)
            return Response({"message": "User added to Manager group"}, status=201)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
# /api/groups/manager/users/{userId}
class ManagerGroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def delete(self, request, userId):
        try:
            user = User.objects.get(pk=userId)
            group = get_group("Manager")
            group.user_set.remove(user)
            return Response({"message": "User removed from Manager group"}, status=200)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

# DeliveryCrewGroupView / DeliveryCrewGroupDetailView:
#   - GET: List users in Delivery crew group.
#   - POST: Add user to Delivery crew group.
#   - DELETE: Remove user from Delivery crew group.
#
# /api/groups/delivery-crew/users
class DeliveryCrewGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def get(self, request):
        group = get_group("Delivery crew")
        users = group.user_set.all()
        data = [{"id": u.id, "username": u.username} for u in users]
        return Response(data)

    def post(self, request):
        user_id = request.data.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
            group = get_group("Delivery crew")
            group.user_set.add(user)
            return Response({"message": "User added to Delivery crew group"}, status=201)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

# /api/groups/delivery-crew/users/{userId}
class DeliveryCrewGroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def delete(self, request, userId):
        try:
            user = User.objects.get(pk=userId)
            group = get_group("Delivery crew")
            group.user_set.remove(user)
            return Response({"message": "User removed from Delivery crew group"}, status=200)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)