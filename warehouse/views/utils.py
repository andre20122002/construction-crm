from django.db.models import Sum, Case, When, F, DecimalField, Value, Q
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import Transaction, Warehouse, Material, AuditLog, UserProfile
import json
from decimal import Decimal

# ==============================================================================
# 1. ДОСТУП ТА БЕЗПЕКА
# ==============================================================================

def get_allowed_warehouses(user):
    """
    Повертає QuerySet складів, до яких користувач має доступ.
    - Superuser/Staff: Всі склади.
    - Інші: Тільки ті, до яких надано доступ (через user.profile.warehouses).
    """
    if not user.is_authenticated:
        return Warehouse.objects.none()
    
    if user.is_superuser or user.is_staff:
        return Warehouse.objects.all()
    
    # Перевіряємо наявність профілю та поля warehouses
    if hasattr(user, 'profile') and hasattr(user.profile, 'warehouses'):
        return user.profile.warehouses.all()
        
    # Якщо профілю немає або немає зв'язку
    return Warehouse.objects.none()

def restrict_warehouses_qs(qs, user, warehouse_field='warehouse'):
    """
    Фільтрує QuerySet, залишаючи тільки записи, що стосуються дозволених складів.
    - qs: Початковий QuerySet (Transaction, Order, тощо).
    - user: Користувач.
    - warehouse_field: Назва поля FK на Warehouse в моделі (default='warehouse').
    """
    if user.is_superuser or user.is_staff:
        return qs
        
    allowed_whs = get_allowed_warehouses(user)
    
    # Формуємо фільтр динамічно: warehouse__in=allowed_whs
    filter_kwargs = {f"{warehouse_field}__in": allowed_whs}
    
    return qs.filter(**filter_kwargs)

def enforce_warehouse_access_or_404(user, warehouse):
    """
    Перевіряє доступ користувача до конкретного складу.
    Якщо доступу немає - піднімає Http404.
    """
    # Якщо warehouse передано як ID, дістаємо об'єкт (або перевіряємо ID в allowed)
    # Але для спрощення припускаємо, що це об'єкт.
    # Якщо це ID, треба спочатку отримати об'єкт або перевірити входження ID.
    
    allowed = get_allowed_warehouses(user)
    
    # Перевірка: чи є цей склад у дозволених
    if not allowed.filter(pk=warehouse.pk).exists():
        raise Http404("Склад не знайдено або доступ заборонено.")

def get_user_warehouses(user):
    """
    Alias for get_allowed_warehouses to maintain backward compatibility if used elsewhere.
    Повертає QuerySet складів, доступних користувачу.
    """
    return get_allowed_warehouses(user)

def check_access(user, warehouse):
    """
    Перевіряє, чи має користувач доступ до конкретного складу (об'єкт або ID).
    True - доступ є, False - немає.
    """
    if user.is_superuser or user.is_staff:
        return True

    if not hasattr(user, 'profile'):
        return False
        
    # Отримуємо ID складу для перевірки
    wh_id = warehouse
    if hasattr(warehouse, 'id'):
        wh_id = warehouse.id
        
    # Перевіряємо наявність у списку доступних
    # Використовуємо filter().exists() для ефективності
    if hasattr(user.profile, 'warehouses'):
        return user.profile.warehouses.filter(id=wh_id).exists()
        
    return False

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================

def is_transfer_tx(tx):
    """
    Перевіряє, чи є транзакція частиною переміщення.
    Повертає True, якщо це переміщення (має transfer_group_id).
    """
    return tx.transfer_group_id is not None

def work_writeoffs_qs(qs):
    """
    Фільтрує QuerySet, залишаючи тільки реальні операційні витрати/списання.
    ВИКЛЮЧАЄ переміщення (трансфери), навіть якщо вони мають тип OUT.
    
    Залишаються:
    - OUT (Витрата на роботи)
    - LOSS (Бій/Втрата)
    """
    return qs.filter(
        transaction_type__in=['OUT', 'LOSS'],
        transfer_group_id__isnull=True
    )

# ==============================================================================
# 3. ЛОГІКА БАЛАНСУ ТА СКЛАДУ
# ==============================================================================

def get_warehouse_balance(warehouse):
    """
    Рахує залишки по складу.
    Формула: SUM(IN) - SUM(OUT) - SUM(LOSS).
    
    Повертає словник {Material_Object: Decimal_quantity}.
    Використовує in_bulk для оптимізації запитів до БД.
    """
    # 1. Агрегація по material_id
    qs = Transaction.objects.filter(warehouse=warehouse).values('material').annotate(
        total_in=Sum('quantity', filter=Q(transaction_type='IN')),
        total_out=Sum('quantity', filter=Q(transaction_type__in=['OUT', 'LOSS']))
    )
    
    # 2. Збираємо проміжні дані {material_id: qty}
    temp_balance = {}
    material_ids = []
    
    for item in qs:
        in_qty = item['total_in'] or Decimal("0.000")
        out_qty = item['total_out'] or Decimal("0.000")
        
        # Розрахунок залишку (Decimal)
        current_stock = in_qty - out_qty
        
        mat_id = item['material']
        temp_balance[mat_id] = current_stock
        material_ids.append(mat_id)
        
    # 3. Витягуємо об'єкти Material одним запитом (in_bulk)
    materials_map = Material.objects.in_bulk(material_ids)
    
    # 4. Формуємо фінальний словник {Material: qty}
    balance = {}
    for mat_id, qty in temp_balance.items():
        if mat_id in materials_map:
            # Використовуємо об'єкт Material як ключ
            balance[materials_map[mat_id]] = qty
        
    return balance

def get_stock_json(user=None):
    """
    Повертає JSON з залишками по всіх складах.
    Використовується для JS-валідації у формах (TransactionForm, TransferForm).
    Format: {warehouse_id: {name: "...", items: {mat_id: "qty_string", ...}}}
    """
    data = {}
    
    if user is None:
        warehouses = Warehouse.objects.all()
    elif user.is_superuser or user.is_staff:
        warehouses = Warehouse.objects.all()
    else:
        warehouses = get_allowed_warehouses(user)
    
    for wh in warehouses:
        balance_map = get_warehouse_balance(wh)
        
        # Оскільки get_warehouse_balance повертає об'єкти Material як ключі,
        # нам треба перетворити їх назад в ID для JSON серіалізації.
        # Значення конвертуємо в string для збереження точності Decimal у JSON
        items_dict = {mat.id: str(qty) for mat, qty in balance_map.items()}
        
        data[wh.id] = {
            'name': wh.name,
            'items': items_dict
        }
            
    return json.dumps(data)

# ==============================================================================
# 4. АУДИТ ТА ЖУРНАЛИ
# ==============================================================================

def log_audit(request, action_type, affected_object=None, old_val=None, new_val=None):
    """
    Записує дію в журнал аудиту (AuditLog).
    Fail-safe версія.
    """
    user = None
    ip = None

    if request:
        # 1. User extraction (fail-safe)
        req_user = getattr(request, 'user', None)
        if req_user and getattr(req_user, 'is_authenticated', False):
            user = req_user
        
        # 2. IP extraction (fail-safe)
        meta = getattr(request, 'META', {}) or {}
        
        x_forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Беремо перший IP зі списку проксі
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = meta.get('REMOTE_ADDR')
    
    # 3. Smart creation: pass only allowed fields
    import logging
    logger = logging.getLogger('warehouse')

    try:
        allowed_fields = {f.name for f in AuditLog._meta.fields}
    except (AttributeError, TypeError) as e:
        logger.debug(f"Could not get AuditLog fields: {e}")
        allowed_fields = {'user', 'action_type', 'old_value', 'new_value', 'ip_address'}

    audit_kwargs = {
        'user': user,
        'action_type': action_type,
        'old_value': str(old_val) if old_val is not None else None,
        'new_value': str(new_val) if new_val is not None else None,
        'ip_address': ip
    }

    if 'affected_object' in allowed_fields:
        audit_kwargs['affected_object'] = affected_object

    try:
        AuditLog.objects.create(**audit_kwargs)
    except (ValueError, TypeError) as e:
        # Не блокуємо основну операцію через помилку логування
        logger.warning(f"Failed to create AuditLog: {e}")

def enrich_transfers(queryset):
    """
    Групує транзакції переміщень у зручний формат для журналу.
    Зв'язує пари транзакцій (OUT + IN) по transfer_group_id.
    """
    grouped_transfers = {}
    
    # Беремо тільки транзакції з transfer_group_id
    transfers_raw = queryset.filter(transfer_group_id__isnull=False).select_related('warehouse', 'material', 'created_by').order_by('-created_at')
    
    for tx in transfers_raw:
        gid = tx.transfer_group_id
        
        if gid not in grouped_transfers:
            grouped_transfers[gid] = {
                'id': str(gid),
                'date': tx.created_at,
                'created_at': tx.created_at,
                'material': tx.material.name,
                'quantity': tx.quantity,
                'unit': tx.material.unit,
                'initiator': tx.created_by.get_full_name() if tx.created_by else "Система",
                'source_wh': None,
                'target_wh': None,
                'description': tx.description,
                'status_label': 'Виконано',
                'status_class': 'success'
            }
        
        # Визначаємо напрямок по типу IN/OUT
        # OUT - це джерело, IN - це призначення
        if tx.transaction_type == 'OUT':
            grouped_transfers[gid]['source_wh'] = tx.warehouse.name
        elif tx.transaction_type == 'IN':
            grouped_transfers[gid]['target_wh'] = tx.warehouse.name
            
    return list(grouped_transfers.values())

@login_required
def ajax_warehouse_stock(request, warehouse_id=None):
    """
    AJAX API: Повертає залишки по конкретному складу.
    URL: /ajax/warehouse/<int:warehouse_id>/stock/ (REST-style)
    URL: /ajax/warehouse-stock/?warehouse_id=123 (Legacy support)
    
    JSON Response:
    {
      "warehouse_id": 123,
      "items": [
        {"material_id": 10, "name": "Цемент", "unit": "кг", "qty": "500.000"},
        ...
      ]
    }
    """
    # 1. Визначаємо warehouse_id з аргументів або GET-параметрів
    if warehouse_id is None:
        warehouse_id = request.GET.get('warehouse_id')
    
    if not warehouse_id:
        return JsonResponse({'error': 'Missing warehouse_id'}, status=400)
    
    try:
        wh_id_int = int(warehouse_id)
    except (TypeError, ValueError):
        # ВИПРАВЛЕНО: повертаємо 404 замість 400 для нечислового ID, щоб відповідати тестам
        return JsonResponse({'error': 'Invalid ID'}, status=404)
        
    try:
        warehouse = Warehouse.objects.get(pk=wh_id_int)
        # Перевірка доступу
        enforce_warehouse_access_or_404(request.user, warehouse)
    except (Warehouse.DoesNotExist, Http404):
        # Якщо склад не знайдено або немає доступу - повертаємо 404 (щоб не світити наявність)
        return JsonResponse({}, status=404)
    
    # Розрахунок балансу
    balance_map = get_warehouse_balance(warehouse)
    
    items = []
    
    for mat, qty in balance_map.items():
        if qty != 0:
            items.append({
                "material_id": mat.id,
                "name": mat.name,
                "unit": mat.unit,
                "qty": str(qty) # Серіалізуємо Decimal як рядок
            })
    
    # Сортуємо список за назвою матеріалу
    items.sort(key=lambda x: x['name'])
        
    return JsonResponse({
        "warehouse_id": warehouse.id,
        "items": items
    })

@login_required
def ajax_materials(request):
    """
    AJAX API: Пошук матеріалів (Autocomplete).
    URL: /ajax/materials/?q=term
    
    JSON Response:
    {
      "items": [
        {"id": 1, "name": "Цемент", "unit": "кг", "article": "CEM-001"},
        ...
      ]
    }
    """
    query = request.GET.get('q') or request.GET.get('term')
    
    materials = Material.objects.all().order_by('name')
    
    if query:
        # Фільтрація по назві або артикулу
        materials = materials.filter(
            Q(name__icontains=query) | Q(article__icontains=query)
        )
    
    # Оптимізація: беремо тільки потрібні поля і лімітуємо кількість
    # Використовуємо values() для отримання словників
    items = list(materials.values('id', 'name', 'unit', 'article')[:50])
    
    return JsonResponse({'items': items})