from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
# 🔥 ВИПРАВЛЕНО: Імпорт з warehouse.views.utils (де файл лежить фізично)
# Завдяки пустому views/__init__.py це тепер безпечно і не викличе помилку.
from warehouse.views.utils import log_audit 

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    log_audit(request, 'LOGIN', user, new_val="Успішний вхід")

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    log_audit(request, 'LOGOUT', user, new_val="Вихід з системи")

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    pass