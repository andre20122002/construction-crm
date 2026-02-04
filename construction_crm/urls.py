"""
URL configuration for construction_crm project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
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