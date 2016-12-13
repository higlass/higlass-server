from rest_framework import permissions

class IsRequestMethodGet(permissions.BasePermission):
    """
    The request is a GET request.
    """

    def has_permission(self, request, view):
        if request.method == 'GET':
		return True
		#return obj.owner == request.user # Returns True if GET request

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        #if request.method in permissions.SAFE_METHODS:
        # Write permissions are only allowed to the owner of the snippet.
        if request.user.is_staff:
		return True
	else:
		return obj.owner == request.user
