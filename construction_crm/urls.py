"""
URL configuration for construction_crm project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """Health check endpoint for load balancers and monitoring."""
    health = {'status': 'healthy', 'database': 'ok'}
    status_code = 200

    # Перевірка з'єднання з БД
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception as e:
        health['database'] = 'error'
        health['status'] = 'unhealthy'
        status_code = 503

    return JsonResponse(health, status=status_code)


urlpatterns = [
    # Health check (перед auth для доступу без логіну)
    path('health/', health_check, name='health_check'),

    # Адмінка Django
    path('admin/', admin.site.urls),

    # Маршрути вашого додатку (warehouse)
    path('', include('warehouse.urls')),

    # Стандартні маршрути аутентифікації (login, logout, password_change тощо)
    # Django шукатиме шаблони в registration/login.html, але ми їх перевизначили в warehouse/templates/registration
    path('accounts/', include('django.contrib.auth.urls')),
]

# --- MEDIA & STATIC SERVING (DEV MODE) ---
# Цей блок дозволяє відкривати завантажені фотографії (media) в браузері,
# коли проект запущено локально (DEBUG=True).
# У продакшені (Nginx/Apache) це налаштовується на рівні веб-сервера.

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)