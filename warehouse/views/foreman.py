from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db import transaction
from django.contrib import messages
from decimal import Decimal, ROUND_HALF_UP

from ..models import Order, OrderComment, Transaction, Warehouse
# Імпортуємо форми. OrderFnItemFormSet тепер існує в forms.py (як аліас)
from ..forms import OrderForm, OrderFnItemFormSet
from .utils import get_user_warehouses, check_access, get_warehouse_balance, log_audit

# ==============================================================================
# ДЕТАЛІ ЗАЯВКИ (FOREMAN)
# ==============================================================================

@login_required
def foreman_order_detail(request, pk):
    """
    Перегляд деталей заявки для прораба (чат, статус).
    """
    # Завантажуємо items разом з матеріалами для оптимізації
    order = get_object_or_404(Order.objects.prefetch_related('items__material'), pk=pk)
    
    # Перевірка прав (автор або доступ до складу)
    if order.created_by != request.user and not check_access(request.user, order.warehouse):
        return HttpResponse("⛔ Немає доступу", status=403)

    # Додавання коментаря (чат)
    if request.method == 'POST' and 'comment_text' in request.POST:
        comment_text = request.POST.get('comment_text')
        if comment_text:
            OrderComment.objects.create(
                order=order,
                author=request.user,
                text=comment_text
            )
            return redirect('foreman_order_detail', pk=pk)

    comments = order.comments.select_related('author').all()

    return render(request, 'warehouse/foreman_order_detail.html', {
        'order': order,
        'comments': comments
    })


# ==============================================================================
# СКЛАД ПРОРАБА (MY STORAGE)
# ==============================================================================

@login_required
def foreman_storage_view(request):
    """
    Сторінка "Мій склад" для прораба.
    Показує залишки на активному (або першому доступному) складі.
    """
    user_warehouses = get_user_warehouses(request.user)
    
    # Визначаємо активний склад
    active_wh_id = request.session.get('active_warehouse_id')
    my_warehouse = None
    
    if active_wh_id:
        try:
            my_warehouse = user_warehouses.get(pk=active_wh_id)
        except Warehouse.DoesNotExist:
            pass
            
    if not my_warehouse and user_warehouses.exists():
        my_warehouse = user_warehouses.first()
        request.session['active_warehouse_id'] = my_warehouse.id
        
    stock_items = []
    total_items = 0
    total_value = Decimal("0.00")
    
    if my_warehouse:
        # get_warehouse_balance повертає словник {Material (об'єкт): Quantity (Decimal)}
        balance_map = get_warehouse_balance(my_warehouse)
        
        for material, qty in balance_map.items():
            if qty == 0:
                continue

            # Безпечне отримання ціни та ліміту
            avg_price = material.current_avg_price or Decimal("0.00")
            # Підтримка різних назв поля ліміту (min_limit або min_stock)
            min_limit = getattr(material, "min_limit", 0) or getattr(material, "min_stock", 0)
            
            # Розрахунок суми
            total_sum = (qty * avg_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # Визначаємо статус "закінчується" тут
            is_low_stock = min_limit > 0 and qty <= min_limit

            stock_items.append({
                "id": material.id,
                "name": material.name,
                "quantity": qty,
                "unit": material.unit,
                "min_limit": min_limit,
                "avg_price": avg_price,
                "total_sum": total_sum,
                "is_low_stock": is_low_stock, # Передаємо в шаблон
            })
            
        # Сортування по назві
        stock_items.sort(key=lambda x: (x["name"] or "").lower())
        
        total_items = len(stock_items)
        total_value = sum((i["total_sum"] for i in stock_items), Decimal("0.00"))

    return render(request, 'warehouse/foreman_storage.html', {
        'stock': stock_items, 
        'warehouse': my_warehouse, 
        'total_items': total_items,
        'total_value': total_value
    })


# ==============================================================================
# ІСТОРІЯ ОПЕРАЦІЙ (HISTORY)
# ==============================================================================

@login_required
def writeoff_history_view(request):
    """
    Історія списань (OUT/LOSS) по складах користувача.
    """
    user_warehouses = get_user_warehouses(request.user)
    
    writeoffs = Transaction.objects.filter(
        warehouse__in=user_warehouses, 
        transaction_type__in=['OUT', 'LOSS']
    ).select_related('material', 'warehouse', 'created_by').order_by('-created_at')
    
    return render(request, 'warehouse/writeoff_history.html', {'writeoffs': writeoffs})


@login_required
def delivery_history_view(request):
    """
    Історія приходів (IN) по складах користувача.
    """
    user_warehouses = get_user_warehouses(request.user)
    
    deliveries = Transaction.objects.filter(
        warehouse__in=user_warehouses, 
        transaction_type='IN'
    ).select_related('material', 'warehouse', 'created_by', 'order').order_by('-created_at')
    
    return render(request, 'warehouse/delivery_history.html', {'deliveries': deliveries})

# Alias for compatibility with old urls (if any)
foreman_storage = foreman_storage_view