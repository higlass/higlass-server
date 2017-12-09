from rest_framework import permissions


class IsRequestMethodGet(permissions.BasePermission):
    """The request is a GET request."""

    def has_permission(self, request, view):
        if request.method == 'GET':
            return True

        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow owners of an object to edit it."""

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        # if request.method in permissions.SAFE_METHODS:
        # Write permissions are only allowed to the owner of the snippet.
        if request.user.is_staff:
            return True
        else:
            return obj.owner == request.user


class UserPermission(permissions.BasePermission):
    # Taken from http://stackoverflow.com/a/34162842/899470

    def has_permission(self, request, view):
        if view.action in ['retrieve', 'list']:
            return True
        elif view.action in ['create', 'update', 'partial_update', 'destroy']:
            return request.user.is_authenticated
        else:
            return False

    def has_object_permission(self, request, view, obj):
        if view.action == 'retrieve':
            return (
                request.user.is_authenticated and
                (obj == request.user or request.user.is_superuser)
            )
        elif view.action in ['update', 'partial_update', 'destroy']:
            return request.user.is_authenticated and (
                request.user.is_superuser or request.user == obj.owner)
        else:
            return False


class UserPermissionReadOnly(UserPermission):
    """Custom permission to only allow read requests."""

    def has_permission(self, request, view):
        if view.action in ['retrieve', 'list']:
            return True
        else:
            return False

    def has_object_permission(self, request, view, obj):
        if view.action == 'retrieve':
            return (
                request.user.is_authenticated and
                (obj == request.user or request.user.is_superuser)
            )
        else:
            return False
