from functools import wraps
from django.contrib.auth.decorators import user_passes_test, login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.core.cache import cache
import time


def rate_limit(requests_per_minute=60, key_prefix='rl'):
    """
    Декоратор для rate limiting.
    Обмежує кількість запитів на хвилину для кожного користувача/IP.

    Використання: @rate_limit(requests_per_minute=30)
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Визначаємо ключ: user_id для авторизованих, IP для анонімних
            if request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
            else:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR', 'unknown')
                identifier = f"ip_{ip}"

            cache_key = f"{key_prefix}:{view_func.__name__}:{identifier}"

            # Отримуємо поточний лічильник
            request_count = cache.get(cache_key, 0)

            if request_count >= requests_per_minute:
                return JsonResponse({
                    'error': 'Too many requests. Please try again later.',
                    'retry_after': 60
                }, status=429)

            # Збільшуємо лічильник
            cache.set(cache_key, request_count + 1, timeout=60)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


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