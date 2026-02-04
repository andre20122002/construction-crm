import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from ..models import Transaction, Material, Warehouse, ConstructionStage

class InsufficientStockError(Exception):
    """
    Помилка: недостатньо товару на складі для виконання операції.
    """
    def __init__(self, warehouse, material, requested_qty, available_qty):
        self.warehouse = warehouse
        self.material = material
        self.requested_qty = requested_qty
        self.available_qty = available_qty
        self.message = (
            f"Insufficient stock: requested {requested_qty:.3f}, available {available_qty:.3f} "
            f"for material '{material.name}' on warehouse '{warehouse.name}'"
        )
        super().__init__(self.message)

def assert_stock_available(warehouse, material, requested_qty, *, allow_zero=True):
    """
    Перевіряє, чи достатньо товару на складі.
    Піднімає InsufficientStockError, якщо requested_qty > available_qty.
    """
    if requested_qty <= 0:
        if allow_zero:
            return
        # Якщо логіка забороняє нульові/від'ємні списання, можна додати валідацію тут
        pass

    # Розрахунок поточного залишку (IN - OUT - LOSS)
    # Фільтруємо транзакції, що відносяться до переміщень, через їх типи
    aggregates = Transaction.objects.filter(warehouse=warehouse, material=material).aggregate(
        total_in=Sum('quantity', filter=Q(transaction_type='IN')),
        total_out=Sum('quantity', filter=Q(transaction_type__in=['OUT', 'LOSS']))
    )
    
    total_in = aggregates['total_in'] or Decimal("0.000")
    total_out = aggregates['total_out'] or Decimal("0.000")
    
    available_qty = total_in - total_out
    
    if requested_qty > available_qty:
        raise InsufficientStockError(warehouse, material, requested_qty, available_qty)

def to_decimal(value, places=3):
    """
    Безпечно конвертує значення в Decimal.
    places: кількість знаків після коми для округлення (3 для кількості, 2 для ціни).
    """
    if value is None:
        return Decimal("0")
    
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0")
    
    quantizer = Decimal("1").scaleb(-places)
    try:
        return d.quantize(quantizer, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return Decimal("0")

def create_incoming(material, warehouse, quantity, user, price=None, description="", date=None, photo=None):
    """
    Реєструє прихід матеріалу на склад (Закупівля / Введення залишків).
    Тип транзакції: IN.
    """
    if date is None:
        date = timezone.now().date()
        
    qty_dec = to_decimal(quantity, places=3)
    
    if price is None:
        price_dec = Decimal("0.00")
    else:
        price_dec = to_decimal(price, places=2)
    
    # IN не вимагає перевірки залишків
    txn = Transaction.objects.create(
        transaction_type='IN',
        material=material,
        warehouse=warehouse,
        quantity=qty_dec,
        price=price_dec,
        created_by=user,
        description=description,
        date=date,
        photo=photo
    )
    
    if price_dec > 0:
        material.update_material_avg_price()
        
    return txn

def create_writeoff(material, warehouse, quantity, user, transaction_type='OUT', description="", date=None, stage=None, photo=None, reason=None):
    """
    Реєструє списання матеріалу (Витрата на роботи або Втрати).
    Тип транзакції: OUT або LOSS.
    """
    if date is None:
        date = timezone.now().date()
        
    if reason:
        transaction_type = reason
        
    qty_dec = to_decimal(quantity, places=3)
    
    # Валідація залишків (Atomic block recommended at view level, but good to have check here)
    # Якщо викликається з view, який вже має atomic, це ок.
    # Додамо atomic локально, щоб гарантувати цілісність перевірки і запису.
    with transaction.atomic():
        assert_stock_available(warehouse, material, qty_dec)
        
        price_dec = material.current_avg_price
        
        txn = Transaction.objects.create(
            transaction_type=transaction_type, # 'OUT' або 'LOSS'
            material=material,
            warehouse=warehouse,
            quantity=qty_dec,
            price=price_dec,
            created_by=user,
            description=description,
            date=date,
            stage=stage,
            photo=photo
        )
    
    return txn

@transaction.atomic
def create_transfer(user, material, source_warehouse, target_warehouse, quantity, description="", date=None):
    """
    Переміщення між складами.
    Створює дві транзакції (OUT + IN) пов'язані одним transfer_group_id.
    Повертає group_id (UUID).
    """
    if date is None:
        date = timezone.now().date()
        
    group_id = uuid.uuid4()
    qty_dec = to_decimal(quantity, places=3)
    
    # Валідація залишків на джерелі
    assert_stock_available(source_warehouse, material, qty_dec)
    
    price_dec = material.current_avg_price
    
    # 1. Списання з джерела (OUT)
    Transaction.objects.create(
        transaction_type='OUT',
        warehouse=source_warehouse,
        material=material,
        quantity=qty_dec,
        price=price_dec,
        created_by=user,
        date=date,
        description=f"Переміщення на {target_warehouse.name}. {description}",
        transfer_group_id=group_id
    )
    
    # 2. Прихід на призначення (IN)
    Transaction.objects.create(
        transaction_type='IN',
        warehouse=target_warehouse,
        material=material,
        quantity=qty_dec,
        price=price_dec,
        created_by=user,
        date=date,
        description=f"Отримано з {source_warehouse.name}. {description}",
        transfer_group_id=group_id
    )
    
    return group_id

@transaction.atomic
def process_order_receipt(order, items_data, user, proof_photo=None, comment=""):
    """
    Прийом товарів по заявці.
    items_data: dict {item_id: quantity_fact}
    """
    transfer_group_id = None
    
    if order.source_warehouse:
        transfer_group_id = uuid.uuid4()

    created_transactions = []

    for item in order.items.all():
        qty_raw = items_data.get(item.id) or items_data.get(str(item.id))
            
        if qty_raw is None:
            continue
            
        qty_dec = to_decimal(qty_raw, places=3)
        if qty_dec <= 0:
            continue

        # Якщо це переміщення (логістика), перевіряємо чи є товар на складі-джерелі
        if order.source_warehouse:
             assert_stock_available(order.source_warehouse, item.material, qty_dec)

        # Оновлюємо факт в позиції заявки
        item.quantity_fact = qty_dec
        item.save()
        
        # Визначаємо ціну
        price_dec = Decimal("0.00")
        if order.source_warehouse:
            price_dec = item.material.current_avg_price
        else:
            if item.supplier_price is not None:
                price_dec = item.supplier_price
        
        # 1. Створюємо прихід (IN) на цільовий склад
        in_txn = Transaction.objects.create(
            transaction_type='IN',
            warehouse=order.warehouse,
            material=item.material,
            quantity=qty_dec,
            price=price_dec,
            created_by=user,
            order=order,
            date=timezone.now().date(),
            transfer_group_id=transfer_group_id,
            photo=proof_photo,
            description=comment or f"Прийом по заявці #{order.id}"
        )
        created_transactions.append(in_txn)
        
        # 2. Якщо це внутрішнє переміщення, створюємо списання (OUT) з джерела
        if order.source_warehouse and transfer_group_id:
            Transaction.objects.create(
                transaction_type='OUT',
                warehouse=order.source_warehouse,
                material=item.material,
                quantity=qty_dec,
                price=price_dec, 
                created_by=user,
                order=order,
                date=timezone.now().date(),
                transfer_group_id=transfer_group_id,
                description=f"Переміщення по заявці #{order.id} на {order.warehouse.name}"
            )
            
        if not order.source_warehouse and price_dec > 0:
            item.material.update_material_avg_price()

    order.status = 'completed'
    
    if proof_photo and hasattr(order, 'proof_photo'):
        try:
            order.proof_photo = proof_photo
            order.save()
        except Exception:
            order.save(update_fields=['status'])
    else:
        order.save(update_fields=['status'])

    return created_transactions