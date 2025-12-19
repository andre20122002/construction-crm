from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def group_required(*group_names):
    """
    Декоратор для перевірки, чи входить користувач у вказані групи.
    Використання: @group_required('Finance', 'TopManager')
    """
    def in_groups(user):
        if user.is_authenticated:
            # Суперюзер бачить все
            if user.is_superuser:
                return True
            # Перевіряємо, чи є у користувача група з переданого списку
            if bool(user.groups.filter(name__in=group_names)):
                return True
        return False

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if in_groups(request.user):
                return view_func(request, *args, **kwargs)
            else:
                # Якщо немає доступу - 403 Forbidden
                raise PermissionDenied("⛔ У вас недостатньо прав для перегляду цієї сторінки.")
        return _wrapped_view
    return decorator