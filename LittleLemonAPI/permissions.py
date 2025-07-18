from rest_framework.permissions import BasePermission

class IsManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Manager').exists()

class IsDeliveryCrew(BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Delivery crew').exists()

class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        # Assuming customers are users who do not belong to any specific group
        return not request.user.groups.exists()
class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return (request.user and request.user.is_staff) or request.user.groups.filter(name="Manager").exists()