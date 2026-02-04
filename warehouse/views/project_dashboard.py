from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from datetime import timedelta
from ..models import Transaction, Order, StageLimit, Material
# Імпортуємо правильні функції з utils
from .utils import get_user_warehouses, get_warehouse_balance

@login_required
def project_dashboard(request):
    """
    Головна панель управління проектом (Інвестор/Власник).
    """
    # FIX: PostgreSQL потребує ExpressionWrapper для множення Float * Decimal
    # Визначаємо вираз один раз, щоб використовувати його повторно
    spent_expr = ExpressionWrapper(
        F('quantity') * F('price'),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )
    
    # 1. Гроші (Витрати)
    # Виключаємо трансфери, якщо вони не мають бути у витратах (зазвичай OUT без group_id + LOSS)
    # Але тут для спрощення беремо загальні OUT/LOSS
    total_spent = Transaction.objects.filter(transaction_type__in=['OUT', 'LOSS']).aggregate(
        s=Sum(spent_expr)
    )['s'] or 0
    
    # 2. Витрати за місяць
    start_month = timezone.now().replace(day=1)
    spent_this_month = Transaction.objects.filter(
        transaction_type__in=['OUT', 'LOSS'], 
        date__gte=start_month
    ).aggregate(s=Sum(spent_expr))['s'] or 0
    
    # 3. Критичні залишки
    critical_items = []
    warehouses = get_user_warehouses(request.user)
    
    for wh in warehouses:
        # get_warehouse_balance тепер повертає словник {MaterialObj: quantity}
        balance = get_warehouse_balance(wh)
        
        for material, qty in balance.items():
            # 🔥 ВИПРАВЛЕНО: material - це об'єкт моделі, використовуємо getattr замість .get()
            # Також підтримуємо обидва варіанти назви поля (min_limit або min_stock)
            min_limit = getattr(material, 'min_limit', 0) or getattr(material, 'min_stock', 0)
            
            if min_limit > 0 and qty <= min_limit:
                critical_items.append({
                    'warehouse': wh.name,
                    'material': material.name,
                    'quantity': qty,
                    'unit': material.unit,
                    'min_limit': min_limit
                })

    # 4. Бетонування (KPI) - Приклад
    concrete_stages = []
    # Беремо ліміти для етапів
    limits = StageLimit.objects.select_related('stage', 'material').all().order_by('stage__id')[:6]
    
    for l in limits:
        fact = Transaction.objects.filter(
            stage=l.stage, 
            material=l.material, 
            transaction_type='OUT'
        ).aggregate(s=Sum('quantity'))['s'] or 0
        
        percent = (fact / l.planned_quantity * 100) if l.planned_quantity > 0 else 0
        
        concrete_stages.append({
            'name': l.stage.name,
            'plan': int(l.planned_quantity),
            'fact': int(fact),
            'percent': int(percent)
        })

    # 5. Останні події
    recent_logs = []
    last_txs = Transaction.objects.select_related('created_by', 'material').order_by('-created_at')[:5]
    for tx in last_txs:
        t_type = "Переміщення" if tx.transfer_group_id else tx.get_transaction_type_display()
        
        recent_logs.append({
            'title': f"{t_type}: {tx.material.name}",
            'desc': f"{tx.quantity} {tx.material.unit} — {tx.created_by.get_full_name() if tx.created_by else 'Система'}",
            'time': tx.created_at
        })

    return render(request, 'warehouse/project_dashboard.html', {
        'total_spent': total_spent,
        'spent_this_month': spent_this_month,
        'critical_items': critical_items,
        'concrete_stages': concrete_stages,
        'recent_logs': recent_logs
    })