from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        id_field = 'email' if '@' in username else 'username'

        try:
            kwargs = {
                '{0}'.format(id_field): username,
            }
            user = UserModel.objects.get(**kwargs)
        except UserModel.DoesNotExist:
            return None
        else:
            if (
                getattr(user, 'is_active', False) and
                user.check_password(password)
            ):
                return user
        return None
