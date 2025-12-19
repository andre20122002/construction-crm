from django.test import TestCase
from django.contrib.auth.models import User
from warehouse.models import Warehouse, Material, Category, Order, OrderItem

class WarehouseTests(TestCase):
    def setUp(self):
        """Підготовка даних перед кожним тестом"""
        # 1. Створюємо юзера
        self.user = User.objects.create_user(username='testuser', password='password')
        
        # 2. Створюємо категорію
        self.category = Category.objects.create(name="Будматеріали")
        
        # 3. Створюємо матеріал
        self.material = Material.objects.create(
            name="Цемент М-500", 
            article="CM-500", 
            unit="шт", 
            current_avg_price=150.00,
            category=self.category
        )
        
        # 4. Створюємо склад
        self.warehouse = Warehouse.objects.create(
            name="Головний Склад", 
            budget_limit=50000, 
            responsible=self.user
        )

    def test_material_category_link(self):
        """Тест: Матеріал прив'язаний до правильної категорії"""
        self.assertEqual(self.material.category.name, "Будматеріали")
        # print("✅ Тест категорії пройдено") # Можна розкоментувати для налагодження

    def test_warehouse_creation(self):
        """Тест: Склад створено з правильним лімітом"""
        self.assertEqual(self.warehouse.budget_limit, 50000)
        self.assertEqual(self.warehouse.responsible.username, 'testuser')

    def test_order_lifecycle(self):
        """Тест: Створення заявки та додавання товару (Master-Detail)"""
        # Створюємо шапку заявки
        order = Order.objects.create(
            warehouse=self.warehouse,
            created_by=self.user,
            status='new',
            priority='normal',
            # Оскільки ми змінили модель, material і quantity в Order більше немає (якщо ви їх видалили)
            # Якщо вони є (як legacy), то можна залишити, але краще не заповнювати
        )
        
        # Додаємо товар у заявку
        OrderItem.objects.create(
            order=order,
            material=self.material,
            quantity=100
        )
        
        # Перевірки
        self.assertEqual(order.status, 'new')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().material.name, "Цемент М-500")
        
        # Перевірка методу підрахунку вартості
        # 100 шт * 150 грн = 15000
        self.assertEqual(order.get_total_cost(), 15000.00)