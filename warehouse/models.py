import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Warehouse(models.Model):
    name = models.CharField("Назва складу / Об'єкту", max_length=100)
    address = models.CharField("Адреса", max_length=255, blank=True)
    
    # DECIMAL UPDATE: Гроші (2 знаки)
    budget_limit = models.DecimalField(
        "Бюджетний ліміт (грн)", 
        max_digits=14, 
        decimal_places=2, 
        default=Decimal("0.00")
    )
    
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_warehouses', 
        verbose_name='Відповідальний'
    )

    class Meta:
        verbose_name = "Склад / Об'єкт"
        verbose_name_plural = "Склади та Об'єкти"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("Назва категорії", max_length=100)

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField("Назва постачальника", max_length=100)
    contact_person = models.CharField("Контактна особа", max_length=100, blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True)
    address = models.TextField("Адреса", blank=True)
    rating = models.IntegerField("Рейтинг надійності (0-100)", default=100, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "Постачальник"
        verbose_name_plural = "Постачальники"

    def __str__(self):
        return self.name


class Material(models.Model):
    name = models.CharField("Назва матеріалу", max_length=200)
    article = models.CharField("Артикул / Код", max_length=50, unique=True, blank=True, null=True)
    characteristics = models.TextField("Характеристики", blank=True)
    unit = models.CharField("Од. виміру", max_length=20, default='шт')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категорія")
    
    # DECIMAL UPDATE: Ціна (2 знаки), Кількість (3 знаки)
    current_avg_price = models.DecimalField(
        "Середня ціна", 
        max_digits=14, 
        decimal_places=2, 
        default=Decimal("0.00")
    )
    min_limit = models.DecimalField(
        "Мін. залишок (ліміт)", 
        max_digits=14, 
        decimal_places=3, 
        default=Decimal("0.000")
    )

    class Meta:
        verbose_name = "Матеріал"
        verbose_name_plural = "Матеріали"

    def __str__(self):
        return f"{self.name} ({self.unit})"

    def update_material_avg_price(self):
        """
        Перераховує середньозважену ціну на основі всіх приходів (IN).
        Використовує тільки Decimal для точності.
        Використовує select_for_update для запобігання race conditions.
        """
        from django.db import transaction

        with transaction.atomic():
            # Блокуємо рядок матеріалу для оновлення
            locked_material = Material.objects.select_for_update().get(pk=self.pk)

            # Беремо всі приходи (IN)
            in_txs = locked_material.transactions.filter(transaction_type='IN')

            # Агрегуємо: sum(qty * price), sum(qty)
            aggregates = in_txs.aggregate(
                total_value=Sum(F('quantity') * F('price'), output_field=DecimalField(max_digits=20, decimal_places=2)),
                total_qty=Sum('quantity', output_field=DecimalField(max_digits=20, decimal_places=3))
            )

            total_val = aggregates['total_value'] or Decimal("0.00")
            total_qty = aggregates['total_qty'] or Decimal("0.000")

            if total_qty > 0:
                new_price = (total_val / total_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                # Оновлюємо через UPDATE запит для атомарності
                Material.objects.filter(pk=self.pk).update(current_avg_price=new_price)
                # Оновлюємо локальний об'єкт
                self.current_avg_price = new_price


class ConstructionStage(models.Model):
    name = models.CharField("Етап будівництва", max_length=100)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stages', verbose_name="Об'єкт")
    start_date = models.DateField("Початок", null=True, blank=True)
    end_date = models.DateField("Кінець", null=True, blank=True)
    completed = models.BooleanField("Завершено", default=False)

    class Meta:
        verbose_name = "Етап будівництва"
        verbose_name_plural = "Етапи будівництва"

    def __str__(self):
        return f"{self.name} ({self.warehouse.name})"


class StageLimit(models.Model):
    """
    Ліміти матеріалів на етап (Кошторис).
    """
    stage = models.ForeignKey(ConstructionStage, on_delete=models.CASCADE, related_name='limits')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    
    # DECIMAL UPDATE: Кількість (3 знаки)
    planned_quantity = models.DecimalField(
        "План. кількість", 
        max_digits=14, 
        decimal_places=3, 
        default=Decimal("0.000")
    )

    class Meta:
        verbose_name = "Ліміт матеріалу"
        verbose_name_plural = "Ліміти матеріалів (Кошторис)"


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Нова'),
        ('rfq', 'Запит ціни (RFQ)'),
        ('approved', 'Погоджено'),
        ('purchasing', 'У закупівлі'),
        ('transit', 'В дорозі'),
        ('completed', 'Виконано / На складі'),
        ('rejected', 'Відхилено'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Низький'),
        ('medium', 'Середній'),
        ('high', 'Високий'),
        ('critical', 'Критичний 🔥'),
    ]

    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name="Куди (Склад)")
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField("Пріоритет", max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Автор")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expected_date = models.DateField("Очікувана дата", null=True, blank=True)
    
    note = models.TextField("Примітка", blank=True)
    request_photo = models.ImageField(upload_to='orders/requests/', null=True, blank=True, verbose_name="Фото заявки")
    
    # Для логістики (якщо це переміщення з іншого складу)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name='outgoing_orders', verbose_name="Звідки (якщо переміщення)")
    
    # Підтвердження отримання
    proof_photo = models.ImageField(upload_to='orders/proofs/', null=True, blank=True, verbose_name="Фото ТТН/Факт")

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    
    # DECIMAL UPDATE: Кількість (3 знаки)
    quantity = models.DecimalField(
        "Кількість (План)", 
        max_digits=14, 
        decimal_places=3, 
        default=Decimal("0.000")
    )
    quantity_fact = models.DecimalField(
        "Кількість (Факт)", 
        max_digits=14, 
        decimal_places=3, 
        default=Decimal("0.000"), 
        blank=True
    )
    
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Постачальник")
    
    # DECIMAL UPDATE: Ціна (2 знаки)
    supplier_price = models.DecimalField(
        "Ціна закупки", 
        max_digits=14, 
        decimal_places=2, 
        null=True, 
        blank=True
    )

    def __str__(self):
        return f"{self.material.name} - {self.quantity}"


class OrderComment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField("Коментар")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('IN', 'Прихід'),
        ('OUT', 'Списання'),
        ('LOSS', 'Втрати / Бій'),
        # 'TRANSFER' використовується тільки для відображення груп транзакцій, 
        # у базі зберігаються як OUT + IN з transfer_group_id
    ]

    transaction_type = models.CharField("Тип", max_length=10, choices=TYPE_CHOICES)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='transactions')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='transactions')
    
    # DECIMAL UPDATE: Кількість (3 знаки), Ціна (2 знаки)
    quantity = models.DecimalField("Кількість", max_digits=14, decimal_places=3)
    price = models.DecimalField("Ціна (на момент)", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    
    date = models.DateField("Дата операції", default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    description = models.CharField("Коментар", max_length=255, blank=True)
    
    # Зв'язки
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    stage = models.ForeignKey(ConstructionStage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Етап робіт")
    
    # Для переміщень (групує OUT та IN)
    transfer_group_id = models.UUIDField(null=True, blank=True, db_index=True)
    
    photo = models.ImageField(upload_to='transactions/', null=True, blank=True, verbose_name="Фото підтвердження")

    class Meta:
        verbose_name = "Транзакція"
        verbose_name_plural = "Транзакції"
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['warehouse', 'material']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.material.name} ({self.quantity})"


class SupplierPrice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='prices')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='supplier_prices')
    
    # DECIMAL UPDATE: Ціна (2 знаки)
    price = models.DecimalField("Ціна (грн)", max_digits=14, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('supplier', 'material')


# --- AUDIT LOG ---

class AuditLog(models.Model):
    ACTION_TYPES = [
        ('LOGIN', 'Вхід в систему'),
        ('LOGOUT', 'Вихід'),
        ('CREATE', 'Створення'),
        ('UPDATE', 'Зміна'),
        ('DELETE', 'Видалення'),
        ('ORDER_STATUS', 'Зміна статусу заявки'),
        ('ORDER_RECEIVED', 'Прийом заявки'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Запис аудиту'
        verbose_name_plural = 'Журнал аудиту (Audit Log)'
        ordering = ['-timestamp']


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='avatars/', null=True, blank=True)
    position = models.CharField("Посада", max_length=100, blank=True)
    warehouses = models.ManyToManyField(Warehouse, blank=True, verbose_name='Доступні склади')

    def __str__(self):
        return self.user.username


# --- SIGNALS ---

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()