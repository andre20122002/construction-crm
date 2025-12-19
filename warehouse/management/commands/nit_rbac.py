from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from warehouse.models import Order, Transaction

class Command(BaseCommand):
    help = 'Ініціалізація груп користувачів та прав доступу (RBAC)'

    def handle(self, *args, **options):
        # 1. Група "Logistics" (Логісти)
        # Мають доступ до складів, переміщень, але НЕ до фінансів
        logistics_group, created = Group.objects.get_or_create(name='Logistics')
        self.stdout.write(f"Група 'Logistics': {'Створена' if created else 'Вже існує'}")

        # 2. Група "Finance" (Фінансисти/Топи)
        # Бачать всі звіти, гроші, економію
        finance_group, created = Group.objects.get_or_create(name='Finance')
        self.stdout.write(f"Група 'Finance': {'Створена' if created else 'Вже існує'}")

        # 3. Група "Foreman" (Прораби)
        # Базовий доступ (вже регулюється кодом, але група корисна для маркування)
        foreman_group, created = Group.objects.get_or_create(name='Foreman')
        self.stdout.write(f"Група 'Foreman': {'Створена' if created else 'Вже існує'}")

        self.stdout.write(self.style.SUCCESS('✅ Ролі успішно налаштовані! Тепер призначте їх користувачам через Адмінку.'))