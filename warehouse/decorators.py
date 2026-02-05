from functools import wraps
from django.contrib.auth.decorators import user_passes_test, login_required
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    """
    Декоратор для перевірки, чи є користувач staff (менеджером).
    Комбінує login_required + is_staff перевірку.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            from django.conf import settings
            return redirect(settings.LOGIN_URL)
        if not request.user.is_staff:
            raise PermissionDenied("У вас недостатньо прав для перегляду цієї сторінки.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


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