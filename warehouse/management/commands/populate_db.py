import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from warehouse.models import Material, Warehouse, Supplier, SupplierPrice, Transaction, Category

class Command(BaseCommand):
    help = 'Заповнює базу даних тестовими даними (Матеріали, Склади, Постачальники, Залишки)'

    def handle(self, *args, **kwargs):
        self.stdout.write("⏳ Починаю наповнення бази...")

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write(self.style.SUCCESS('✅ Створено адміна (login: admin, pass: admin)'))
        
        user = User.objects.get(username='admin')

        # --- 1. КАТЕГОРІЇ ---
        categories = {
            'Загальнобудівельні': ['Цемент', 'Цегла', 'Газоблок', 'Пісок', 'Бетон'],
            'Металопрокат': ['Арматура', 'Труба', 'Швелер', 'Кутник'],
            'Оздоблення': ['Гіпсокартон', 'Шпаклівка', 'Фарба', 'Грунтовка', 'Клей'],
            'Витратні матеріали': ['Дюбель', 'Саморізи', 'Диск', 'Рукавиці'],
            'Інструмент': ['Шпатель', 'Валик', 'Рівень']
        }
        
        cat_objs = {}
        for cat_name in categories:
            c, _ = Category.objects.get_or_create(name=cat_name)
            cat_objs[cat_name] = c
        self.stdout.write(self.style.SUCCESS(f'✅ Створено {len(cat_objs)} категорій'))

        # --- 2. СКЛАДИ ---
        warehouses_data = [
            {'name': 'Центральний Склад', 'addr': 'вул. Промислова, 1', 'main': True, 'budget': 500000},
            {'name': 'ЖК "Затишок" (Секція 1)', 'addr': 'вул. Шевченка, 10', 'main': False, 'budget': 1500000},
            {'name': 'Котедж в Лісниках', 'addr': 'с. Лісники, вул. Лісова', 'main': False, 'budget': 800000},
        ]
        
        warehouses = []
        for wd in warehouses_data:
            wh, _ = Warehouse.objects.get_or_create(
                name=wd['name'],
                defaults={
                    'address': wd['addr'],
                    'is_main_storage': wd['main'],
                    'budget_limit': wd['budget'],
                    'responsible': user
                }
            )
            warehouses.append(wh)

        # --- 3. МАТЕРІАЛИ (З КАТЕГОРІЯМИ) ---
        materials_data = [
            ('Цемент М-500', 'CEM-500', 'шт', 180.00, 'Загальнобудівельні'),
            ('Цегла рядова М-100', 'BRICK-100', 'шт', 8.50, 'Загальнобудівельні'),
            ('Газоблок 300мм', 'AEROC-300', 'м3', 2400.00, 'Загальнобудівельні'),
            ('Арматура 12мм', 'ARM-12', 'т', 28000.00, 'Металопрокат'),
            ('Пісок річковий', 'SAND-RIV', 'т', 450.00, 'Загальнобудівельні'),
            ('Ґрунтовка глибокого проникнення', 'CERESIT-CT17', 'л', 85.00, 'Оздоблення'),
            ('Фарба фасадна біла', 'COLOR-F-W', 'л', 220.00, 'Оздоблення'),
            ('Дюбель 6х40', 'DUB-640', 'пак', 120.00, 'Витратні матеріали'),
            ('Гіпсокартон стіновий', 'KNAUF-WALL', 'шт', 350.00, 'Оздоблення'),
            ('Профіль CD-60', 'PROF-CD60', 'шт', 110.00, 'Оздоблення'),
            ('Шпаклівка фінішна', 'FINISH-PL', 'шт', 420.00, 'Оздоблення'),
            ('Клей для плитки', 'CM-11', 'шт', 210.00, 'Оздоблення'),
            ('Рукавиці будівельні', 'GLOVES-X', 'пак', 250.00, 'Витратні матеріали'),
            ('Диск відрізний 125мм', 'DISK-125', 'шт', 45.00, 'Витратні матеріали'),
            ('Саморізи по дереву 35мм', 'SCREW-35', 'пак', 180.00, 'Витратні матеріали'),
        ]

        materials_objs = []
        for name, art, unit, price, cat_name in materials_data:
            mat, _ = Material.objects.get_or_create(
                article=art,
                defaults={
                    'name': name,
                    'unit': unit,
                    'category': cat_objs.get(cat_name), # ПРИВ'ЯЗУЄМО КАТЕГОРІЮ
                    'current_avg_price': price,
                    'market_price': price * 1.1, 
                    'min_limit': 10
                }
            )
            # Якщо матеріал вже був, оновимо категорію
            if not mat.category:
                mat.category = cat_objs.get(cat_name)
                mat.save()
                
            materials_objs.append(mat)
        self.stdout.write(self.style.SUCCESS(f'✅ Створено {len(materials_objs)} матеріалів'))

        # --- 4. ПОСТАЧАЛЬНИКИ ---
        suppliers_data = [
            'Епіцентр К', 'Леруа Мерлен', 'Метал-Холдінг', 'Бетон від Ковальської', 'ФОП "БудМайстер"'
        ]
        
        for sup_name in suppliers_data:
            sup, _ = Supplier.objects.get_or_create(name=sup_name)
            
            random_materials = random.sample(materials_objs, k=random.randint(3, 8))
            for mat in random_materials:
                sup.materials.add(mat)
                price = float(mat.current_avg_price) * random.uniform(0.9, 1.1)
                SupplierPrice.objects.update_or_create(
                    supplier=sup, material=mat,
                    defaults={'price': Decimal(price)}
                )

        # --- 5. ЗАЛИШКИ ---
        main_wh = warehouses[0]
        if not Transaction.objects.exists():
            for mat in materials_objs:
                qty = random.randint(50, 500)
                if mat.unit == 'т': qty = random.randint(5, 20)
                
                Transaction.objects.create(
                    transaction_type='IN',
                    warehouse=main_wh,
                    material=mat,
                    quantity=qty,
                    price=mat.current_avg_price,
                    description='Початковий залишок (Імпорт)',
                    created_by=user
                )
            self.stdout.write(self.style.SUCCESS(f'✅ Залишки нараховано'))
        
        self.stdout.write(self.style.SUCCESS('🎉 БАЗА ГОТОВА!'))