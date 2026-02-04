import random
import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.db import transaction
from django.conf import settings

# Імпорт моделей
from warehouse.models import (
    Warehouse, Category, Material, Supplier, Transaction, 
    UserProfile, Order, OrderItem, ConstructionStage, StageLimit,
    SupplierPrice, AuditLog
)

# Імпорт сервісів
from warehouse.services import inventory

class Command(BaseCommand):
    help = 'Наповнює базу даних демо-даними для презентації (Users, Warehouses, Materials, Transactions)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Видалити всі дані перед наповненням (Тільки для DEV!)',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=6,
            help='Кількість користувачів для створення (default: 6)',
        )
        parser.add_argument(
            '--orders',
            type=int,
            default=25,
            help='Кількість заявок для створення (default: 25)',
        )

    def handle(self, *args, **options):
        # Перевірка на RESET
        if options['reset']:
            if not settings.DEBUG:
                self.stdout.write(self.style.ERROR('RESET дозволено тільки в DEBUG режимі!'))
                return
            self.stdout.write(self.style.WARNING('Видалення всіх даних...'))
            self.clear_data()
            self.stdout.write(self.style.SUCCESS('Дані видалено.'))

        self.stdout.write('Починаємо генерацію демо-даних...')

        try:
            with transaction.atomic():
                self.create_groups()
                self.create_users(options['users'])
                self.create_warehouses()
                self.create_suppliers()
                self.create_catalog()
                self.create_stages_and_limits()
                
                # Генерація руху (важливий порядок!)
                self.generate_initial_stock()  # IN
                self.generate_orders(options['orders']) # Orders + IN
                self.generate_transfers()      # TRANSFER
                self.generate_usage()          # OUT (Write-offs)
                
                self.stdout.write(self.style.SUCCESS(f'\nУспішно завершено!'))
                self.stdout.write(f"Пароль для всіх демо-юзерів: 'demo12345'")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Помилка при генерації даних: {e}'))
            import traceback
            traceback.print_exc()

    def clear_data(self):
        """Очищення таблиць у правильному порядку."""
        Transaction.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        StageLimit.objects.all().delete()
        ConstructionStage.objects.all().delete()
        SupplierPrice.objects.all().delete()
        Material.objects.all().delete()
        Category.objects.all().delete()
        Supplier.objects.all().delete()
        
        # Очищаємо профіль перед юзером, хоча on_delete=CASCADE має спрацювати
        UserProfile.objects.all().delete()
        
        # Видаляємо тільки демо юзерів (щоб не вбити реального адміна, якщо скрипт запущено бездумно)
        User.objects.filter(username__startswith='demo_').delete()
        User.objects.filter(username__in=['manager', 'foreman']).delete()

    def create_groups(self):
        self.group_manager, _ = Group.objects.get_or_create(name='Manager')
        self.group_foreman, _ = Group.objects.get_or_create(name='Foreman')

    def create_users(self, count):
        self.users_managers = []
        self.users_foremen = []

        # 1. Admin / Manager (Staff)
        admin, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
        if created:
            admin.set_password('demo12345')
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            # Профіль створюється сигналом, але про всяк випадок перевіримо
            if not hasattr(admin, 'profile'):
                UserProfile.objects.create(user=admin)
            admin.profile.position = 'Головний Адміністратор'
            admin.profile.save()
        self.users_managers.append(admin)

        # 2. Managers (Staff)
        for i in range(1, 3):
            username = f'demo_manager_{i}'
            u, created = User.objects.get_or_create(username=username, defaults={'email': f'{username}@example.com'})
            if created:
                u.set_password('demo12345')
                u.is_staff = True
                u.groups.add(self.group_manager)
                u.save()
                u.profile.position = 'Менеджер з постачання'
                u.profile.save()
            self.users_managers.append(u)

        # 3. Foremen (Non-Staff)
        for i in range(1, count + 1):
            username = f'demo_foreman_{i}'
            u, created = User.objects.get_or_create(username=username, defaults={'email': f'{username}@example.com'})
            if created:
                u.set_password('demo12345')
                u.is_staff = False
                u.groups.add(self.group_foreman)
                u.save()
                u.profile.position = 'Виконроб'
                u.profile.save()
            self.users_foremen.append(u)

        self.stdout.write(f' > Користувачі: {len(self.users_managers)} менеджерів, {len(self.users_foremen)} прорабів.')

    def create_warehouses(self):
        self.warehouses = []
        
        data = [
            ('Головний Склад', 'вул. Промислова 10', '1000000.00'),
            ('ЖК "Сонячний"', 'вул. Сонячна 42', '5000000.00'),
            ('ТРЦ "Київ"', 'пр. Перемоги 1', '8500000.00'),
            ('Склад "Захід"', 'Кільцева дорога', '200000.00'),
        ]

        for name, addr, budget in data:
            wh, _ = Warehouse.objects.get_or_create(
                name=name,
                defaults={
                    'address': addr,
                    'budget_limit': Decimal(budget),
                    'responsible_user': self.users_managers[0]
                }
            )
            self.warehouses.append(wh)

        # Роздаємо доступи прорабам
        for foreman in self.users_foremen:
            # Кожен прораб має доступ до 1-2 складів
            assigned_whs = random.sample(self.warehouses, k=random.randint(1, 2))
            foreman.profile.warehouses.set(assigned_whs)

        self.stdout.write(f' > Склади: {len(self.warehouses)} об\'єктів.')

    def create_suppliers(self):
        self.suppliers = []
        names = ['Епіцентр К', 'Метінвест', 'Бетон від Ковальської', 'Альянс Буд', 'Техно-Світ']
        
        for name in names:
            s, _ = Supplier.objects.get_or_create(
                name=name,
                defaults={
                    'contact_person': f'Менеджер {name}',
                    'phone': '+380501234567',
                    'rating': random.randint(80, 100)
                }
            )
            self.suppliers.append(s)
        
        self.stdout.write(f' > Постачальники: {len(self.suppliers)} компаній.')

    def create_catalog(self):
        self.materials = []
        
        categories_data = {
            'Сипучі матеріали': [
                ('Цемент М-500', 'кг', 'CM-500', '180.00'),
                ('Пісок річковий', 'т', 'SND-01', '450.00'),
                ('Щебінь 5-20', 'т', 'GRV-20', '650.00'),
            ],
            'Метал/Арматура': [
                ('Арматура А500С d12', 'т', 'ARM-12', '28000.00'),
                ('Арматура А500С d16', 'т', 'ARM-16', '27500.00'),
                ('Дріт в\'язальний', 'кг', 'WR-01', '60.00'),
            ],
            'Бетон': [
                ('Бетон В25 (М350)', 'м3', 'BTN-25', '3200.00'),
                ('Бетон В30 (М400)', 'м3', 'BTN-30', '3500.00'),
            ],
            'Спецтехніка': [
                ('Послуги крана 25т', 'год', 'SRV-CRN', '1500.00'),
                ('Послуги екскаватора', 'год', 'SRV-EXC', '1200.00'),
            ],
            'Загальнобудівельні': [
                ('Цегла рядова', 'шт', 'BRK-01', '8.50'),
                ('Газоблок D500', 'м3', 'BLK-500', '2800.00'),
                ('Пінопласт 100мм', 'м2', 'ISO-100', '150.00'),
            ]
        }

        for cat_name, items in categories_data.items():
            cat, _ = Category.objects.get_or_create(name=cat_name)
            
            for name, unit, article, price in items:
                mat, _ = Material.objects.get_or_create(
                    name=name,
                    defaults={
                        'unit': unit,
                        'article': article,
                        'category': cat,
                        'current_avg_price': Decimal(price),
                        'min_limit': Decimal('10.000') # Критичний залишок
                    }
                )
                self.materials.append(mat)
                
                # Додаємо ціни постачальників
                for sup in random.sample(self.suppliers, k=2):
                    SupplierPrice.objects.update_or_create(
                        supplier=sup,
                        material=mat,
                        defaults={'price': Decimal(price) * Decimal(random.uniform(0.9, 1.1))}
                    )

        self.stdout.write(f' > Каталог: {len(self.materials)} матеріалів.')

    def create_stages_and_limits(self):
        """Створюємо етапи та ліміти для аналітики."""
        stage_names = ['Підготовчі роботи', 'Фундамент', 'Каркас 1-й поверх', 'Перекриття']
        
        for wh in self.warehouses:
            for s_name in stage_names:
                stage, _ = ConstructionStage.objects.get_or_create(
                    name=s_name,
                    warehouse=wh,
                    defaults={
                        'start_date': timezone.now().date(),
                        'end_date': timezone.now().date() + timezone.timedelta(days=30)
                    }
                )
                
                # Додаємо ліміти (кошторис) для Бетону та Арматури
                target_mats = [m for m in self.materials if m.category.name in ['Бетон', 'Метал/Арматура']]
                for tm in target_mats:
                    StageLimit.objects.get_or_create(
                        stage=stage,
                        material=tm,
                        defaults={
                            'planned_quantity': Decimal(random.randint(100, 1000))
                        }
                    )
        
        self.stdout.write(' > Етапи та ліміти створено.')

    def generate_initial_stock(self):
        """Генеруємо початкові залишки (IN) на Головному складі."""
        main_wh = self.warehouses[0] # Головний склад
        admin = self.users_managers[0]
        
        for mat in self.materials:
            qty = Decimal(random.randint(500, 5000))
            inventory.create_incoming(
                material=mat,
                warehouse=main_wh,
                quantity=qty,
                user=admin,
                price=mat.current_avg_price,
                description="Початковий залишок (Demo Seed)",
                date=timezone.now().date() - timezone.timedelta(days=60)
            )
            
        self.stdout.write(' > Початкові залишки нараховано.')

    def generate_orders(self, count):
        """Генеруємо заявки (Orders). Частина з них completed (створює IN)."""
        statuses = ['new', 'approved', 'purchasing', 'transit', 'completed', 'rejected']
        
        for _ in range(count):
            wh = random.choice(self.warehouses)
            creator = random.choice(self.users_foremen + self.users_managers)
            status = random.choice(statuses)
            
            order = Order.objects.create(
                warehouse=wh,
                status=status,
                priority=random.choice(['low', 'medium', 'high', 'critical']),
                created_by=creator,
                expected_date=timezone.now().date() + timezone.timedelta(days=random.randint(1, 10)),
                note="Демонстраційна заявка"
            )
            
            # Додаємо товари
            items_count = random.randint(1, 5)
            order_items_data = {} # Для process_order_receipt
            
            for _ in range(items_count):
                mat = random.choice(self.materials)
                qty = Decimal(random.randint(10, 100))
                
                item = OrderItem.objects.create(
                    order=order,
                    material=mat,
                    quantity=qty,
                    supplier=random.choice(self.suppliers) if status in ['purchasing', 'transit', 'completed'] else None,
                    supplier_price=mat.current_avg_price if status in ['purchasing', 'transit', 'completed'] else None
                )
                
                # Якщо completed — значить треба нарахувати залишок
                if status == 'completed':
                    order_items_data[item.id] = qty # Факт = План

            # Якщо статус completed — проводимо через сервіс (створює IN транзакції)
            if status == 'completed':
                # Тимчасово змінюємо статус назад, щоб сервіс відпрацював
                order.status = 'transit' 
                order.save()
                inventory.process_order_receipt(order, order_items_data, self.users_managers[0], comment="Автоматичний прийом по заявці")

        self.stdout.write(f' > Створено {count} заявок (частина виконана).')

    def generate_transfers(self):
        """Переміщення з Головного складу на об'єкти."""
        main_wh = self.warehouses[0]
        other_whs = self.warehouses[1:]
        user = self.users_managers[0]
        
        for _ in range(10):
            target = random.choice(other_whs)
            mat = random.choice(self.materials)
            qty = Decimal(random.randint(10, 50))
            
            # Перевіряємо, чи є на головному складі (щоб не впало в помилку)
            # В реальному тесті ми знаємо що є, бо нагенерили initial stock
            try:
                inventory.create_transfer(
                    user=user,
                    material=mat,
                    source_warehouse=main_wh,
                    target_warehouse=target,
                    quantity=qty,
                    description=f"Переміщення на {target.name}",
                    date=timezone.now().date() - timezone.timedelta(days=random.randint(1, 20))
                )
            except Exception:
                # Ігноруємо нестачу для демо-скрипта, йдемо далі
                pass

        self.stdout.write(' > Згенеровано переміщення між складами.')

    def generate_usage(self):
        """Списання матеріалів на роботи (OUT) на об'єктах."""
        user = self.users_foremen[0]
        
        for wh in self.warehouses[1:]: # Списуємо на об'єктах (не на головному)
            stages = wh.stages.all()
            if not stages: continue
            
            for _ in range(15):
                mat = random.choice(self.materials)
                qty = Decimal(random.randint(1, 20))
                stage = random.choice(stages)
                
                try:
                    inventory.create_writeoff(
                        material=mat,
                        warehouse=wh,
                        quantity=qty,
                        user=user,
                        transaction_type='OUT',
                        description=f"Використання на етапі {stage.name}",
                        stage=stage,
                        date=timezone.now().date() - timezone.timedelta(days=random.randint(1, 15))
                    )
                except Exception:
                    pass

        self.stdout.write(' > Згенеровано списання на роботи.')