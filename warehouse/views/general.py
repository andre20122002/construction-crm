from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta
from ..models import Order, UserProfile, Warehouse, Transaction # Додано Transaction
from ..forms import UserUpdateForm, ProfileUpdateForm
from .utils import get_user_warehouses, get_warehouse_balance, get_stock_json, check_access
import json

@login_required
def index(request):
    user_warehouses = get_user_warehouses(request.user)
    
    # --- СЦЕНАРІЙ ПРОРАБА ---
    if not request.user.is_staff:
        # 1. Визначаємо активний склад (щоб показувати аналітику саме по ньому)
        active_wh_id = request.session.get('active_warehouse_id')
        my_warehouse = None
        if active_wh_id:
            my_warehouse = user_warehouses.filter(id=active_wh_id).first()
        if not my_warehouse:
            my_warehouse = user_warehouses.first()
            if my_warehouse: request.session['active_warehouse_id'] = my_warehouse.id

        # ВИПРАВЛЕНО: prefetch_related('items__material') замість material
        active_orders = Order.objects.filter(
            Q(created_by=request.user) | Q(warehouse__in=user_warehouses)
        ).exclude(status__in=['completed', 'rejected', 'draft']).prefetch_related('items__material').order_by('-updated_at')
        
        drafts_count = Order.objects.filter(created_by=request.user, status='draft').count()
        incoming_count = active_orders.filter(status__in=['purchasing', 'in_transit']).count()
        
        # --- МІКРО-АНАЛІТИКА ---
        stats = {
            'spent_7_days': 0,
            'recent_actions': [],
            'top_materials': [],
            'low_stock_count': 0
        }

        if my_warehouse:
            seven_days_ago = timezone.now() - timedelta(days=7)
            
            # 1. Витрачено за 7 днів (кількість операцій списання)
            stats['spent_7_days'] = Transaction.objects.filter(
                warehouse=my_warehouse,
                transaction_type__in=['OUT', 'LOSS'],
                created_at__gte=seven_days_ago
            ).count()

            # 2. Хто списав? (Останні 5 дій на цьому складі)
            stats['recent_actions'] = Transaction.objects.filter(
                warehouse=my_warehouse,
                transaction_type__in=['OUT', 'LOSS']
            ).select_related('created_by', 'material').order_by('-created_at')[:5]

            # 3. Популярні матеріали (Топ-3 за кількістю списань за весь час)
            # Можна обмежити останнім місяцем, якщо даних багато
            stats['top_materials'] = Transaction.objects.filter(
                warehouse=my_warehouse,
                transaction_type='OUT'
            ).values('material__name', 'material__unit').annotate(
                total_qty=Sum('quantity')
            ).order_by('-total_qty')[:3]

            # 4. Прогноз (Критичні залишки)
            balance = get_warehouse_balance(my_warehouse)
            stats['low_stock_count'] = sum(1 for i in balance if i['min_limit'] > 0 and i['quantity'] <= i['min_limit'])
        
        return render(request, 'warehouse/index.html', {
            'role': 'foreman',
            'active_orders': active_orders,
            'drafts_count': drafts_count,
            'incoming_count': incoming_count,
            'my_warehouse': my_warehouse,
            'stock_json': get_stock_json(),
            'stats': stats # Передаємо статистику
        })

    # --- СЦЕНАРІЙ МЕНЕДЖЕРА ---
    alerts = []
    labels = []
    data = []
    new_orders_count = Order.objects.filter(status='new').count()
    transit_orders_count = Order.objects.filter(status='in_transit').count()

    for wh in user_warehouses:
        balance = get_warehouse_balance(wh)
        total_val = sum(item['total_sum'] for item in balance)
        wh.total_value = round(total_val, 2)
        
        if total_val > 0:
            labels.append(wh.name)
            data.append(float(total_val))
            
        for item in balance:
            if item['min_limit'] > 0 and item['quantity'] <= item['min_limit']:
                alerts.append(f"⚠️ {wh.name}: {item['name']} закінчується")

    return render(request, 'warehouse/index.html', {
        'role': 'manager',
        'warehouses': user_warehouses, 
        'chart_labels': json.dumps(labels), 
        'chart_data': json.dumps(data), 
        'alerts': alerts,
        'new_orders_count': new_orders_count,
        'transit_orders_count': transit_orders_count
    })

@login_required
def profile_view(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Ваш профіль оновлено!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=user_profile)

    assigned_warehouses = get_user_warehouses(request.user)
    active_wh_id = request.session.get('active_warehouse_id')

    return render(request, 'warehouse/profile.html', {
        'u_form': u_form,
        'p_form': p_form,
        'assigned_warehouses': assigned_warehouses,
        'active_wh_id': active_wh_id,
    })

@login_required
def switch_active_warehouse(request, pk):
    wh = get_object_or_404(Warehouse, pk=pk)
    if check_access(request.user, wh):
        request.session['active_warehouse_id'] = wh.id
        messages.success(request, f"Ви переключилися на об'єкт: {wh.name}")
    else:
        messages.error(request, "Немає доступу до цього об'єкту")
    return redirect('profile')