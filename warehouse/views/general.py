from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from decimal import Decimal, ROUND_HALF_UP

from ..models import Order, UserProfile, Warehouse, ConstructionStage, Material, Transaction
from ..forms import UserUpdateForm, ProfileUpdateForm
from .utils import get_user_warehouses, get_warehouse_balance, check_access
from ..decorators import rate_limit

# ==============================================================================
# ГОЛОВНА СТОРІНКА
# ==============================================================================

@login_required
def index(request):
    """
    Точка входу в систему.
    Визначає роль користувача і відображає відповідний дашборд.
    """
    user_warehouses = get_user_warehouses(request.user)
    
    # Базовий контекст
    context = {
        'warehouses': user_warehouses,
        'now': timezone.now()
    }
    
    # --- ЛОГІКА ДЛЯ ПРОРАБА (Non-Staff) ---
    if not request.user.is_staff:
        context['role'] = 'foreman'
        
        # Перевіряємо, чи вибрано активний склад в сесії
        active_wh_id = request.session.get('active_warehouse_id')
        active_wh = None
        
        if active_wh_id:
            try:
                active_wh = user_warehouses.get(pk=active_wh_id)
            except Warehouse.DoesNotExist:
                pass
        
        # Якщо склад не вибрано або він недоступний, беремо перший доступний
        if not active_wh and user_warehouses.exists():
            active_wh = user_warehouses.first()
            request.session['active_warehouse_id'] = active_wh.id
            
        context['active_warehouse'] = active_wh
        
        # Розрахунок метрик для дашборда (items_count, total_value)
        # Логіка ідентична foreman_storage_view
        items_count = 0
        total_value = Decimal("0.00")
        
        if active_wh:
            # Отримуємо баланс: {Material: Decimal(qty)}
            balance_map = get_warehouse_balance(active_wh)
            
            for material, qty in balance_map.items():
                if qty > 0: # Враховуємо тільки позитивні залишки
                    items_count += 1
                    
                    # Ціна та сума
                    avg_price = material.current_avg_price or Decimal("0.00")
                    sum_val = (qty * avg_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    total_value += sum_val
        
        context['items_count'] = items_count
        context['total_value'] = total_value
        
        # Останні активні заявки для цього складу
        if active_wh:
            context['my_orders'] = Order.objects.filter(
                warehouse=active_wh
            ).exclude(status__in=['completed', 'rejected']).order_by('-updated_at')[:5]
            
        return render(request, 'warehouse/index.html', context)

    # --- ЛОГІКА ДЛЯ МЕНЕДЖЕРА/АДМІНА (Staff) ---
    else:
        context['role'] = 'manager'
        # Менеджери мають свій дашборд
        return redirect('manager_dashboard')


# ==============================================================================
# ПРОФІЛЬ КОРИСТУВАЧА
# ==============================================================================

@login_required
def profile_view(request):
    """
    Сторінка профілю користувача.
    """
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Ваш профіль успішно оновлено!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        # Переконаємось, що профіль існує (сигнали повинні були створити його, але для надійності)
        if not hasattr(request.user, 'profile'):
            UserProfile.objects.create(user=request.user)
            
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'warehouse/profile.html', context)


@login_required
def change_password_view(request):
    """
    Зміна пароля.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Щоб не розлогінило
            messages.success(request, 'Пароль успішно змінено!')
            return render(request, 'warehouse/password_change_done.html')
        else:
            messages.error(request, 'Виправте помилки нижче.')
    else:
        form = PasswordChangeForm(request.user)
        
    return render(request, 'warehouse/password_change_form.html', {'form': form})


# ==============================================================================
# УПРАВЛІННЯ СЕСІЄЮ
# ==============================================================================

@login_required
def switch_active_warehouse(request, pk):
    """
    Швидке перемикання активного складу.
    """
    if check_access(request.user, pk):
        warehouse = get_object_or_404(Warehouse, pk=pk)
        request.session['active_warehouse_id'] = pk
        messages.success(request, f"🏢 Активний об'єкт змінено на: {warehouse.name}")
    else:
        messages.error(request, "⛔ У вас немає доступу до цього складу.")
        
    return redirect(request.META.get('HTTP_REFERER', 'index'))


# ==============================================================================
# КАТАЛОГ МАТЕРІАЛІВ
# ==============================================================================

@login_required
def material_list(request):
    """
    Список матеріалів з пошуком та пагінацією.
    """
    query = request.GET.get('q', '')
    materials_list = Material.objects.all().select_related('category').order_by('name')
    
    if query:
        materials_list = materials_list.filter(
            Q(name__icontains=query) | 
            Q(article__icontains=query) |
            Q(characteristics__icontains=query)
        )
        
    paginator = Paginator(materials_list, 20) # 20 матеріалів на сторінку
    page_number = request.GET.get('page')
    materials = paginator.get_page(page_number)
    
    return render(request, 'warehouse/material_list.html', {
        'materials': materials,
        'page_title': 'Довідник матеріалів'
    })


@login_required
def material_detail(request, pk):
    """
    Детальна сторінка матеріалу.
    Показує загальні залишки по всіх складах та історію руху.
    """
    material = get_object_or_404(Material, pk=pk)
    
    # 1. Рахуємо залишки по складах (тільки доступні користувачу, або всі для менеджера)
    warehouses = get_user_warehouses(request.user)
    stock_distribution = []
    total_quantity = 0
    
    for wh in warehouses:
        # Рахуємо залишок конкретного матеріалу на складі
        # Формула: IN - OUT - LOSS (враховуючи переміщення, які є OUT/IN з group_id)
        
        # IN (Прихід + Вхідні переміщення)
        in_qty = Transaction.objects.filter(
            material=material, 
            warehouse=wh, 
            transaction_type='IN'
        ).aggregate(s=Sum('quantity'))['s'] or 0
        
        # OUT (Витрата + Вихідні переміщення) + LOSS
        out_loss_qty = Transaction.objects.filter(
            material=material, 
            warehouse=wh, 
            transaction_type__in=['OUT', 'LOSS']
        ).aggregate(s=Sum('quantity'))['s'] or 0
        
        qty = in_qty - out_loss_qty
        
        if qty != 0: # Показуємо тільки якщо є рух або залишок
            stock_distribution.append({
                'warehouse': wh.name,
                'quantity': round(qty, 2)
            })
            total_quantity += qty
            
    # 2. Оціночна вартість
    total_value = total_quantity * float(material.current_avg_price)
    
    # 3. Історія операцій (останні 50)
    # Фільтруємо транзакції тільки по доступних складах
    transactions = Transaction.objects.filter(
        material=material,
        warehouse__in=warehouses
    ).select_related('warehouse', 'created_by').order_by('-created_at')[:50]

    return render(request, 'warehouse/material_detail.html', {
        'material': material,
        'stock_distribution': stock_distribution,
        'total_quantity': round(total_quantity, 2),
        'total_value': round(total_value, 2),
        'transactions': transactions
    })


# ==============================================================================
# AJAX API
# ==============================================================================

@login_required
@require_GET
@rate_limit(requests_per_minute=60, key_prefix='ajax_stages')
def load_stages(request):
    """
    API: Повертає список етапів будівництва для вибраного складу.
    URL: /ajax/load-stages/?warehouse_id=123
    """
    warehouse_id = request.GET.get('warehouse_id')
    stages = []
    
    if warehouse_id:
        try:
            wh_id_int = int(warehouse_id)
            if check_access(request.user, wh_id_int):
                qs = ConstructionStage.objects.filter(warehouse_id=wh_id_int).order_by('name')
                stages = list(qs.values('id', 'name'))
        except (ValueError, TypeError):
            pass
            
    return JsonResponse(stages, safe=False)

@login_required
@require_GET
@rate_limit(requests_per_minute=120, key_prefix='ajax_mat_general')
def ajax_materials(request):
    """
    API: Пошук матеріалів для TomSelect (Autocomplete).
    URL: /ajax/materials/?q=query
    """
    query = request.GET.get('q', '')
    materials = Material.objects.all().order_by('name')
    
    if query:
        materials = materials.filter(name__icontains=query)
    
    # Повертаємо топ-50 результатів
    results = list(materials.values('id', 'name')[:50])
    return JsonResponse(results, safe=False)