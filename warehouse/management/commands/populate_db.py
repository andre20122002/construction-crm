import random
from decimal import Decimal
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from warehouse.models import (
    Warehouse, Category, Material, Supplier, Transaction, 
    UserProfile, Order, OrderItem
)
from django.utils import timezone

class Command(BaseCommand):
    help = 'Наповнює базу даних тестовими даними'

    def handle(self, *args, **kwargs):
        self.stdout.write('Запускаємо міграції...')
        call_command('migrate')
        
        self.stdout.write('Починаємо наповнення бази даних...')

        # 1. Створення груп
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        foreman_group, _ = Group.objects.get_or_create(name='Foreman')

        # 2. Створення користувачів
        # Суперюзер
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write('Створено суперюзера: admin/admin')

        # Менеджери
        managers = []
        for i in range(1, 4):
            username = f'manager{i}'
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(username, f'{username}@example.com', 'password')
                u.groups.add(manager_group)
                u.is_staff = True # Менеджери мають доступ до адмінки (або розширені права)
                u.save()
                
                # Профіль
                if not hasattr(u, 'profile'):
                    UserProfile.objects.create(user=u, position='Менеджер з постачання')
                else:
                    u.profile.position = 'Менеджер з постачання'
                    u.profile.save()
                
                managers.append(u)
                self.stdout.write(f'Створено менеджера: {username}/password')

        # Виконроби
        foremen = []
        for i in range(1, 6):
            username = f'foreman{i}'
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(username, f'{username}@example.com', 'password')
                u.groups.add(foreman_group)
                
                # Профіль
                if not hasattr(u, 'profile'):
                    UserProfile.objects.create(user=u, position='Виконроб')
                else:
                    u.profile.position = 'Виконроб'
                    u.profile.save()
                
                foremen.append(u)
                self.stdout.write(f'Створено виконроба: {username}/password')

        # 3. Склади (Об'єкти)
        warehouses_data = [
            ('Головний Склад', 'вул. Промислова, 1'),
            ('ЖК "Сонячний"', 'вул. Сонячна, 12'),
            ('ТРЦ "Мегаполіс"', 'пр. Перемоги, 50'),
            ('Котеджне містечко', 'с. Лісове'),
        ]
        
        warehouses = []
        for name, addr in warehouses_data:
            wh, created = Warehouse.objects.get_or_create(
                name=name,
                defaults={
                    'address': addr, 
                    'budget_limit': Decimal(random.randint(100000, 5000000))
                }
            )
            warehouses.append(wh)
            
        # Прив'язуємо виконробів до складів
        # (припустимо, що у виконроба є доступ до випадкових 1-2 складів)
        if foremen and warehouses:
            for f in foremen:
                # Оновлюємо профіль, додаючи склади
                whs = random.sample(warehouses, k=random.randint(1, 2))
                f.profile.warehouses.set(whs)
                f.profile.save()

        # 4. Категорії та Матеріали
        categories_data = {
            'Сипучі': [
                ('Цемент М-500', 'кг', 'D001'), ('Пісок річковий', 'т', 'D002'), 
                ('Щебінь 5-20', 'т', 'D003'), ('Керамзит', 'м3', 'D004')
            ],
            'Метал': [
                ('Арматура 12мм', 'т', 'M001'), ('Арматура 10мм', 'т', 'M002'), 
                ('Труба профільна 40x40', 'м', 'M003'), ('Кутник 50x50', 'м', 'M004')
            ],
            'Блоки та Цегла': [
                ('Цегла рядова', 'шт', 'B001'), ('Газоблок 300', 'шт', 'B002'), 
                ('Цегла облицювальна', 'шт', 'B003')
            ],
            'Пиломатеріали': [
                ('Дошка обрізна 50x150', 'м3', 'W001'), ('Брус 100x100', 'м3', 'W002'), 
                ('Фанера вологостійка', 'лист', 'W003')
            ],
            'Інструмент': [
                ('Лопата совкова', 'шт', 'T001'), ('Молоток', 'шт', 'T002'), 
                ('Рулетка 5м', 'шт', 'T003'), ('Рукавиці робочі', 'пара', 'T004')
            ]
        }

        materials = []
        for cat_name, items in categories_data.items():
            cat, _ = Category.objects.get_or_create(name=cat_name)
            for mat_name, unit, art in items:
                mat, created = Material.objects.get_or_create(
                    article=art,
                    defaults={
                        'name': mat_name,
                        'unit': unit,
                        'category': cat,
                        'min_limit': Decimal(random.randint(10, 100)),
                        'current_avg_price': Decimal(random.randint(50, 5000))
                    }
                )
                materials.append(mat)

        # 5. Постачальники
        suppliers_names = ['Епіцентр К', 'Метал-Холдинг', 'Бетон-Сервіс', 'Ліс-Трейд', 'БудМайстер']
        suppliers = []
        for name in suppliers_names:
            sup, _ = Supplier.objects.get_or_create(
                name=name,
                defaults={
                    'contact_person': f'Менеджер {name}',
                    'phone': f'+38050{random.randint(1000000, 9999999)}',
                    'rating': random.randint(70, 100)
                }
            )
            suppliers.append(sup)

        # 6. Транзакції (Початкові залишки та рух)
        # Створимо ~50 транзакцій для наповнення історії
        if not Transaction.objects.exists():
            admin_user = User.objects.get(username='admin')
            
            # Вхідні залишки (IN)
            for _ in range(30):
                wh = random.choice(warehouses)
                mat = random.choice(materials)
                qty = Decimal(random.randint(50, 500))
                price = mat.current_avg_price
                
                Transaction.objects.create(
                    transaction_type='IN',
                    warehouse=wh,
                    material=mat,
                    quantity=qty,
                    price=price,
                    created_by=admin_user,
                    date=timezone.now() - timezone.timedelta(days=random.randint(1, 60)),
                    description="Початковий залишок / Закупівля"
                )
            
            # Витрати (OUT)
            for _ in range(20):
                wh = random.choice(warehouses)
                mat = random.choice(materials)
                # Перевіряємо, чи є що списувати (прощено для сідінгу, але бажано)
                
                qty = Decimal(random.randint(5, 50))
                price = mat.current_avg_price
                
                Transaction.objects.create(
                    transaction_type='OUT',
                    warehouse=wh,
                    material=mat,
                    quantity=qty,
                    price=price,
                    created_by=random.choice(foremen) if foremen else admin_user,
                    date=timezone.now() - timezone.timedelta(days=random.randint(1, 30)),
                    description="Використання на об'єкті"
                )

        self.stdout.write(self.style.SUCCESS('Базу даних успішно наповнено!'))