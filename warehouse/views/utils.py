from django.db.models import Sum, Case, When, F, DecimalField, Q
from ..models import Transaction, Warehouse, Material, AuditLog
import json

# === ФУНКЦІЇ АУДИТУ ===

def get_client_ip(request):
    """Отримує реальну IP-адресу користувача"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_audit(request, action_type, obj=None, old_val=None, new_val=None):
    """
    Записує дію в AuditLog.
    :param request: об'єкт запиту (для user та IP)
    :param action_type: тип дії (код зі списку ACTION_TYPES)
    :param obj: об'єкт, над яким здійснено дію (Order, Transaction і т.д.)
    :param old_val: попереднє значення (рядок або JSON)
    :param new_val: нове значення
    """
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action_type=action_type,
            affected_object=obj,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
            ip_address=get_client_ip(request)
        )

# === ІСНУЮЧІ ФУНКЦІЇ ===

def get_warehouse_balance(warehouse, material_id=None):
    query = Transaction.objects.filter(warehouse=warehouse)
    if material_id:
        query = query.filter(material_id=material_id)
        
    data = query.values(
        'material__id', 'material__name', 'material__unit', 
        'material__current_avg_price', 'material__min_limit'
    ).annotate(
        total_qty=Sum(Case(
            When(transaction_type='IN', then=F('quantity')),
            When(transaction_type__in=['OUT', 'TRANSFER', 'LOSS'], then=0 - F('quantity')),
            default=0, output_field=DecimalField()
        ))
    ).filter(total_qty__gt=0)
    
    results = []
    for item in data:
        qty = item['total_qty']
        price = item['material__current_avg_price']
        
        results.append({
            'id': item['material__id'],
            'name': item['material__name'],       
            'unit': item['material__unit'],
            'quantity': qty,
            'price': price,
            'min_limit': item['material__min_limit'],
            'total_sum': round(qty * price, 2)
        })
    return results

def get_stock_json():
    data = Transaction.objects.values('warehouse_id', 'material_id').annotate(
        total=Sum(Case(
            When(transaction_type='IN', then=F('quantity')),
            When(transaction_type__in=['OUT', 'TRANSFER', 'LOSS'], then=0 - F('quantity')),
            default=0, output_field=DecimalField()
        ))
    ).filter(total__gt=0)
    
    stock_map = {}
    for item in data:
        w_id = item['warehouse_id']
        m_id = item['material_id']
        if w_id not in stock_map:
            stock_map[w_id] = {}
        stock_map[w_id][m_id] = float(item['total'])
    return json.dumps(stock_map)

def get_barcode_json():
    materials = Material.objects.exclude(barcode__isnull=True).exclude(barcode__exact='')
    barcode_map = {}
    for m in materials:
        code = m.barcode.strip()
        barcode_map[code] = {
            'id': m.id,
            'name': m.name,
            'unit': m.unit
        }
    return json.dumps(barcode_map)

def get_user_warehouses(user):
    if user.is_staff:
        return Warehouse.objects.all()
    return Warehouse.objects.filter(Q(assigned_users=user) | Q(responsible=user)).distinct()

def check_access(user, warehouse):
    if user.is_staff:
        return True
    return (user == warehouse.responsible) or (user in warehouse.assigned_users.all())