from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from decimal import Decimal

# --- 1. ДОВІДНИКИ ---

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Назва категорії")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії матеріалів"

class Supplier(models.Model):
    name = models.CharField(max_length=200, verbose_name="Компанія")
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="Контактна особа")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True)
    materials = models.ManyToManyField('Material', blank=True, related_name='suppliers', verbose_name="Постачає матеріали")
    rating = models.IntegerField(default=5, verbose_name="Рейтинг (1-5)")

    def __str__(self):
        return self.name

class Material(models.Model):
    UNIT_CHOICES = [
        ('шт', 'Штука'), ('кг', 'Кілограм'), ('т', 'Тонна'),
        ('м3', 'Метр кубічний'), ('м2', 'Метр квадратний'),
        ('м', 'Метр'), ('мп', 'Метр погонний'), ('л', 'Літр'),
        ('пак', 'Пакунок'), ('рул', 'Рулон'),
    ]
    
    # НОВЕ ПОЛЕ: Категорія
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категорія")
    
    name = models.CharField(max_length=200, verbose_name="Назва матеріалу")
    article = models.CharField(max_length=50, unique=True, verbose_name="Артикул")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, verbose_name="Од. виміру")
    barcode = models.CharField(max_length=100, blank=True, null=True, verbose_name="Штрихкод / QR")
    
    min_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, verbose_name="Мін. ліміт",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    current_avg_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, verbose_name="Сер. собівартість",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    market_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, verbose_name="Поточна ринкова ціна",
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    def __str__(self):
        return f"{self.name} ({self.article})"

    class Meta:
        verbose_name = "Матеріал"
        verbose_name_plural = "Матеріали (Довідник)"

class SupplierPrice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='prices')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='supplier_prices')
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Договірна ціна",
        validators=[MinValueValidator(Decimal('0.01'))] 
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        unique_together = ('supplier', 'material')
        verbose_name = "Договірна ціна"
        verbose_name_plural = "Прайс-лист постачальників"

    def __str__(self):
        return f"{self.supplier.name} - {self.material.name}: {self.price} грн"

class Warehouse(models.Model):
    name = models.CharField(max_length=200, verbose_name="Назва складу / Об'єкту")
    address = models.CharField(max_length=300, blank=True, verbose_name="Адреса")
    is_main_storage = models.BooleanField(default=False, verbose_name="Це центральний склад?")
    budget_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=100000.00, verbose_name="Бюджет проекту",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    responsible = models.ForeignKey(
       User, on_delete=models.SET_NULL, null=True, blank=True, 
       verbose_name="Матеріально відповідальний (МВО)", related_name='responsible_warehouses'
    )
    assigned_users = models.ManyToManyField(
        User, related_name='assigned_warehouses', blank=True, verbose_name="Інші користувачі з доступом"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Склад / Об'єкт"
        verbose_name_plural = "Склади"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    photo = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Фото профілю")
    position = models.CharField(max_length=100, blank=True, default="Співробітник", verbose_name="Посада")

    def __str__(self):
        return f"Профіль {self.user.username}"


# --- 2. ЗАЯВКИ (ПЛАН) ---

class Order(models.Model):
    STATUS_CHOICES = [
        ('draft', '📝 Чернетка'),
        ('new', '⏳ На погодженні'),
        ('rfq', '🔍 Тендер (RFQ)'),
        ('approved', '✅ Погоджено (PO)'),
        ('purchasing', '💸 У закупівлі'),
        ('in_transit', '🚚 У дорозі'),
        ('completed', '🏁 Виконано'),
        ('rejected', '🚫 Відхилено'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', '🟢 Не терміново'),
        ('normal', '🟡 Звичайно'),
        ('high', '🔴 Терміново!'),
    ]

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")
    
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Куди (Об'єкт)", related_name='destination_orders')
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Звідки (Джерело)", related_name='source_orders')
    
    # Видаляємо пряме посилання на material та quantity, оскільки це тепер в OrderItem
    # material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Що треба") 
    # quantity = models.DecimalField(...)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Статус")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal', verbose_name="Пріоритет")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор", related_name='created_orders', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name="Хто погодив", related_name='approved_orders', null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата погодження")
    
    audit_log = models.TextField(blank=True, default="", verbose_name="Історія змін (Log)")

    expected_date = models.DateField(null=True, blank=True, verbose_name="На коли треба?")
    note = models.TextField(blank=True, verbose_name="Причина / Коментар")
    
    request_photo = models.ImageField(upload_to='requests/', null=True, blank=True, verbose_name="Фото до заявки")
    proof_photo = models.ImageField(upload_to='proofs/', null=True, blank=True, verbose_name="Фото факту")
    
    selected_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Обраний постачальник")
    
    supplier_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Ціна закупівлі",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    supplier_info = models.CharField(max_length=200, blank=True, verbose_name="Постачальник (Текст)")

    manager_last_viewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Менеджер бачив")

    driver_name = models.CharField(max_length=100, blank=True, verbose_name="Водій ПІБ")
    driver_phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон водія")
    vehicle_number = models.CharField(max_length=20, blank=True, verbose_name="Номер авто")
    shipping_doc = models.ImageField(upload_to='shipping_docs/', null=True, blank=True, verbose_name="Скан ТТН (Відправка)")

    def log_change(self, user, message):
        timestamp = timezone.now().strftime("%d.%m.%Y %H:%M")
        user_name = user.get_full_name() or user.username
        entry = f"[{timestamp}] {user_name}: {message}\n"
        self.audit_log = entry + self.audit_log
        self.save(update_fields=['audit_log', 'updated_at'])
        
    def get_total_cost(self):
        """Рахує загальну вартість замовлення на основі товарів"""
        return sum(item.total_price() for item in self.items.all())

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ['-created_at']

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    quantity_fact = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def total_price(self):
        """Сума рядка: Ціна * Кількість"""
        price = self.supplier_price or self.material.current_avg_price
        qty = self.quantity_fact or self.quantity
        return round(qty * price, 2)

    def __str__(self):
        return f"{self.material.name} - {self.quantity}"

class OrderComment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(verbose_name="Повідомлення")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author}: {self.text[:20]}"
    
    class Meta:
        ordering = ['created_at']


# --- 3. РУХ ТОВАРІВ (ФАКТ) ---

class Transaction(models.Model):
    TYPE_CHOICES = [
        ('IN', 'Прихід (Закупівля)'),
        ('OUT', 'Витрата (Робота)'),
        ('TRANSFER', 'Переміщення'),
        ('LOSS', '⚠️ Списання (Бій / Псування)'),
    ]
    
    WORK_TYPES = [
        ('foundation', 'Фундамент'),
        ('walls', 'Стіни / Кладка'),
        ('roof', 'Покрівля / Дах'),
        ('facade', 'Фасад'),
        ('interior', 'Внутрішнє оздоблення'),
        ('plumbing', 'Сантехніка'),
        ('electric', 'Електрика'),
        ('other', 'Інше'),
    ]
    
    SHIFT_CHOICES = [
        ('1', '1-ша зміна'),
        ('2', '2-га зміна'),
        ('3', 'Нічна'),
    ]

    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Тип")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Склад")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Матеріал")
    
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Кількість",
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Ціна (за од.)",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    description = models.TextField(blank=True, verbose_name="Коментар")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата запису")
    
    date = models.DateField(default=timezone.now, verbose_name="Дата виконання")
    work_type = models.CharField(max_length=50, choices=WORK_TYPES, blank=True, verbose_name="Вид робіт")
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES, default='1', verbose_name="Зміна")

    photo = models.ImageField(upload_to='transactions/', null=True, blank=True, verbose_name="Фото-звіт")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пов'язана заявка")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Виконавець")

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.material.name}"

    class Meta:
        verbose_name = "Транзакція"
        verbose_name_plural = "Журнал руху"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({'quantity': "Кількість має бути строго більше нуля!"})
        if self.transaction_type == 'IN' and self.price <= 0:
            is_internal_transfer = self.order and self.order.source_warehouse
            if not is_internal_transfer:
                raise ValidationError({'price': "Ціна закупівлі не може бути 0.00! Це ламає облік собівартості."})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("⛔ Змінювати проведені транзакції заборонено! Видаліть запис і створіть новий, якщо допущено помилку.")
        self.full_clean()
        super().save(*args, **kwargs)


# === 4. АУДИТ ===

class AuditLog(models.Model):
    ACTION_TYPES = [
        ('LOGIN', 'Вхід в систему'),
        ('CREATE', 'Створення'),
        ('UPDATE', 'Зміна'),
        ('DELETE', 'Видалення'),
        ('APPROVE', 'Погодження'),
        ('REJECT', 'Відхилення'),
        ('CHANGE_PRICE', 'Зміна ціни'),
        ('WRITEOFF', 'Списання'),
        ('TRANSFER', 'Переміщення'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Користувач")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="Дія")
    
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveIntegerField(null=True)
    affected_object = GenericForeignKey('content_type', 'object_id')

    old_value = models.TextField(blank=True, null=True, verbose_name="Було")
    new_value = models.TextField(blank=True, null=True, verbose_name="Стало")
    
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Час")

    class Meta:
        verbose_name = "Запис аудиту"
        verbose_name_plural = "Журнал аудиту (Audit Log)"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.user}: {self.action_type}"


# --- СИГНАЛИ ---

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def update_material_avg_price(sender, instance, **kwargs):
    material = instance.material
    if instance.transaction_type == 'IN' and instance.price > 0:
        material.market_price = instance.price

    purchases = Transaction.objects.filter(material=material, transaction_type='IN', price__gt=0)
    
    if not purchases.exists():
        material.current_avg_price = 0
    else:
        total_data = purchases.aggregate(
            total_spent=Sum(F('quantity') * F('price')),
            total_qty=Sum('quantity')
        )
        if total_data['total_qty']:
            material.current_avg_price = total_data['total_spent'] / total_data['total_qty']
        else:
            material.current_avg_price = 0
    material.save()

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if not hasattr(instance, 'profile'):
            UserProfile.objects.create(user=instance)
    instance.profile.save()