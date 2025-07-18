from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, CategoryViewSet, DeliveryCrewGroupDetailView, DeliveryCrewGroupView, ManagerGroupDetailView, ManagerGroupView, MenuItemViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'category', CategoryViewSet, basename='category')
router.register(r'menu-items', MenuItemViewSet, basename='menu-items')
router.register(r'cart/menu-items', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='orders')

urlpatterns = [
    path('', include(router.urls)),
    path('groups/manager/users', ManagerGroupView.as_view(), name='manager-users'),
    path('groups/manager/users/<int:userId>', ManagerGroupDetailView.as_view(), name='manager-users-detail'),

    path('groups/delivery-crew/users', DeliveryCrewGroupView.as_view(), name='delivery-crew-users'),
    path('groups/delivery-crew/users/<int:userId>', DeliveryCrewGroupDetailView.as_view(), name='delivery-crew-users-detail'),

]
