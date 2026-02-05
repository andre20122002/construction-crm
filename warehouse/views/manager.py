from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, F, Case, When, DecimalField
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.utils import timezone

# --- Models Import ---
from ..models import (
    Order, OrderItem, OrderComment, Material,
    Warehouse, Transaction, Supplier, Category, ConstructionStage, SupplierPrice
)
from .utils import (
    get_warehouse_balance, log_audit,
    get_allowed_warehouses, restrict_warehouses_qs, enforce_warehouse_access_or_404
)
from ..decorators import staff_required

# --- Forms Import ---
try:
    from ..forms import OrderForm, OrderItemForm, OrderCommentForm, OrderFnItemFormSet
except ImportError:
    # Fallback definition if forms.py is missing or incomplete
    from django import forms
    from django.forms import inlineformset_factory

    class OrderForm(forms.ModelForm):
        class Meta:
            model = Order
            fields = ['warehouse', 'priority', 'expected_date', 'note', 'request_photo']
    class OrderItemForm(forms.ModelForm):
        class Meta:
            model = OrderItem
            fields = ['material', 'quantity']
    class OrderCommentForm(forms.ModelForm):
        class Meta:
            model = OrderComment
            fields = ['text']
            widgets = {'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ваш коментар...'})}
    
    OrderFnItemFormSet = inlineformset_factory(Order, OrderItem, form=OrderItemForm, extra=1)


@staff_required
def dashboard(request):
    """
    Головна панель менеджера (Dashboard).
    Фільтрує дані за дозволеними складами.
    """
    # Отримуємо дозволені склади для користувача
    allowed_warehouses = get_allowed_warehouses(request.user)

    # Базовий QuerySet заявок з фільтрацією по дозволених складах
    base_orders = Order.objects.filter(warehouse__in=allowed_warehouses)

    # KPI Статистика (тільки для дозволених складів)
    orders_stat = {
        'new': base_orders.filter(status='new').count(),
        'approved': base_orders.filter(status='approved').count(),
        'purchasing': base_orders.filter(status='purchasing').count(),
        'transit': base_orders.filter(status='transit').count(),
        'active_total': base_orders.exclude(status__in=['completed', 'rejected', 'draft']).count()
    }

    # Фільтрація списку останніх заявок
    recent_orders = base_orders.select_related('warehouse', 'created_by').prefetch_related('items__material').order_by('-created_at')

    status = request.GET.get('status')
    if status:
        recent_orders = recent_orders.filter(status=status)

    # Ліміт 10 для дашборду
    recent_orders = recent_orders[:10]

    # Матеріали з низьким запасом (для дозволених складів)
    low_stock_materials = Material.objects.filter(min_limit__gt=0).order_by('-min_limit')[:5]

    context = {
        'stats': orders_stat,
        'recent_orders': recent_orders,
        'low_stock_materials': low_stock_materials,
        'page_title': 'Панель керування',
        'current_status': status
    }
    return render(request, 'warehouse/manager_dashboard.html', context)


@staff_required
def order_list(request):
    """
    Список заявок з розширеною фільтрацією та пошуком.
    Фільтрує за дозволеними складами.
    """
    # Фільтруємо заявки за дозволеними складами
    allowed_warehouses = get_allowed_warehouses(request.user)
    orders = Order.objects.filter(warehouse__in=allowed_warehouses)\
        .select_related('warehouse', 'created_by')\
        .prefetch_related('items__material')\
        .order_by('-created_at')

    status = request.GET.get('status')
    priority = request.GET.get('priority')
    warehouse_id = request.GET.get('warehouse')
    search_query = request.GET.get('q')

    if status:
        orders = orders.filter(status=status)
    if priority:
        orders = orders.filter(priority=priority)
    if warehouse_id:
        # Перевіряємо, що обраний склад є в дозволених
        if allowed_warehouses.filter(pk=warehouse_id).exists():
            orders = orders.filter(warehouse_id=warehouse_id)

    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(note__icontains=search_query) |
            Q(warehouse__name__icontains=search_query) |
            Q(items__material__name__icontains=search_query)
        ).distinct()

    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'orders': page_obj,
        'warehouses': allowed_warehouses,  # Тільки дозволені склади у фільтрі
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status,
        'page_title': 'Усі заявки'
    }
    return render(request, 'warehouse/order_list.html', context)


@staff_required
def order_detail(request, pk):
    """
    Детальний перегляд заявки: інформація, позиції, коментарі (чат).
    Перевіряє доступ до складу заявки.
    """
    order = get_object_or_404(Order, pk=pk)

    # Перевірка доступу до складу заявки
    enforce_warehouse_access_or_404(request.user, order.warehouse)

    if request.method == 'POST' and 'add_comment' in request.POST:
        form = OrderCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.order = order
            comment.author = request.user
            comment.save()
            messages.success(request, "Коментар додано!")
            return redirect('manager_order_detail', pk=pk) 
    else:
        comment_form = OrderCommentForm()

    context = {
        'order': order,
        # Використовуємо items.all() - канонічний спосіб
        'items': order.items.select_related('material').all(),
        'comments': order.comments.select_related('author').order_by('created_at'),
        'comment_form': comment_form,
        'page_title': f'Заявка #{order.id}'
    }
    return render(request, 'warehouse/order_detail.html', context)


@staff_required
def order_create(request):
    """
    Створення нової заявки менеджером (Order + Items через FormSet).
    Обмежує вибір складів до дозволених.
    """
    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES)
        formset = OrderFnItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            # Перевіряємо, що обраний склад є в дозволених
            warehouse = form.cleaned_data.get('warehouse')
            if warehouse:
                enforce_warehouse_access_or_404(request.user, warehouse)

            with transaction.atomic():
                order = form.save(commit=False)
                order.created_by = request.user
                order.status = 'new'
                order.save()

                # Зберігаємо позиції
                formset.instance = order
                formset.save()

                log_audit(request, 'CREATE', order, new_val=f"Order #{order.id} created by manager")
                messages.success(request, f"Заявку #{order.id} створено успішно.")
                return redirect('manager_order_detail', pk=order.id)
    else:
        form = OrderForm()
        formset = OrderFnItemFormSet()

    # Обмежуємо вибір складів
    form.fields['warehouse'].queryset = get_allowed_warehouses(request.user)

    context = {
        'form': form,
        'formset': formset,
        'page_title': 'Створити заявку'
    }
    return render(request, 'warehouse/order_form.html', context)


@staff_required
def order_edit(request, pk):
    """
    Редагування заявки та її позицій (Items через FormSet).
    """
    order = get_object_or_404(Order, pk=pk)

    # Перевірка доступу до складу заявки
    enforce_warehouse_access_or_404(request.user, order.warehouse)

    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES, instance=order)
        formset = OrderFnItemFormSet(request.POST, instance=order)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()

                log_audit(request, 'UPDATE', order, new_val="Edited by manager")
                messages.success(request, "Заявку оновлено.")
                return redirect('manager_order_detail', pk=pk)
    else:
        form = OrderForm(instance=order)
        formset = OrderFnItemFormSet(instance=order)

    # Обмежуємо вибір складів
    form.fields['warehouse'].queryset = get_allowed_warehouses(request.user)

    context = {
        'form': form,
        'formset': formset,
        'order': order,
        'page_title': f'Редагування заявки #{order.id}'
    }
    return render(request, 'warehouse/order_form.html', context)


@staff_required
def order_approve(request, pk):
    """
    Погодження заявки.
    """
    order = get_object_or_404(Order, pk=pk)
    enforce_warehouse_access_or_404(request.user, order.warehouse)

    if request.method == 'POST':
        order.status = 'approved'
        order.save()
        
        OrderComment.objects.create(
            order=order,
            author=request.user,
            text="✅ Заявку погоджено. Передано в закупівлю."
        )
        
        messages.success(request, f"Заявку #{order.id} погоджено!")
        return redirect('manager_order_detail', pk=pk)
    
    return render(request, 'warehouse/order_confirm_action.html', {
        'order': order, 
        'action': 'approve',
        'title': 'Погодити заявку?'
    })


@staff_required
def order_reject(request, pk):
    """
    Відхилення заявки.
    """
    order = get_object_or_404(Order, pk=pk)
    enforce_warehouse_access_or_404(request.user, order.warehouse)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Без пояснення')
        order.status = 'rejected'
        order.save()
        
        OrderComment.objects.create(
            order=order,
            author=request.user,
            text=f"🚫 Заявку відхилено. Причина: {reason}"
        )
        
        messages.warning(request, f"Заявку #{order.id} відхилено.")
        return redirect('manager_order_detail', pk=pk)

    return render(request, 'warehouse/order_confirm_action.html', {
        'order': order, 
        'action': 'reject',
        'title': 'Відхилити заявку?'
    })


@staff_required
def material_list(request):
    """
    Довідник матеріалів.
    """
    materials = Material.objects.all().order_by('name')
    
    search = request.GET.get('q')
    if search:
        materials = materials.filter(
            Q(name__icontains=search) | 
            Q(article__icontains=search)
        )
        
    paginator = Paginator(materials, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'materials': page_obj,
        'page_title': 'Матеріали'
    }
    return render(request, 'warehouse/material_list.html', context)


@staff_required
def material_detail(request, pk):
    """
    Детальна сторінка матеріалу: загальний залишок, розподіл по складах, історія руху.
    """
    material = get_object_or_404(Material, pk=pk)
    
    # 1. Залишки по складах
    warehouses_stock = []
    total_quantity = 0
    
    warehouses = Warehouse.objects.all()
    for wh in warehouses:
        # Рахуємо залишок для конкретного складу
        txs = Transaction.objects.filter(warehouse=wh, material=material)
        in_qty = txs.filter(transaction_type='IN').aggregate(s=Sum('quantity'))['s'] or 0
        out_qty = txs.filter(transaction_type__in=['OUT', 'LOSS', 'TRANSFER']).aggregate(s=Sum('quantity'))['s'] or 0
        balance = in_qty - out_qty
        
        if balance > 0:
            warehouses_stock.append({
                'warehouse': wh,
                'quantity': round(balance, 2)
            })
            total_quantity += balance
            
    # 2. Оціночна вартість
    avg_price = float(material.current_avg_price) if material.current_avg_price else 0.0
    total_value = round(float(total_quantity) * avg_price, 2)
    
    # 3. Останні транзакції
    transactions = Transaction.objects.filter(material=material).select_related('warehouse', 'created_by').order_by('-created_at')[:20]

    context = {
        'material': material,
        'warehouses_stock': warehouses_stock,
        'total_quantity': round(total_quantity, 2),
        'total_value': total_value,
        'transactions': transactions,
        'page_title': material.name
    }
    return render(request, 'warehouse/material_detail.html', context)


# ==============================================================================
# SPLIT ORDER (РОЗДІЛЕННЯ ЗАЯВКИ)
# ==============================================================================

@staff_required
def split_order(request, pk):
    """
    Розділення заявки на декілька частин (наприклад, різні постачальники).
    Працює з items, а не з legacy material field.
    """
    original_order = get_object_or_404(Order, pk=pk)
    enforce_warehouse_access_or_404(request.user, original_order.warehouse)
    items = original_order.items.select_related('material').all()
    
    # Групуємо постачальників для форми
    suppliers = Supplier.objects.all()
    suppliers_map = {s.id: s for s in suppliers}
    
    if request.method == 'POST':
        with transaction.atomic():
            new_orders_map = {}
            moved_count = 0
            
            for item in items:
                group_key = request.POST.get(f'item_{item.id}')
                
                # Якщо група не 'default'/'original' (залишити в старій), переносимо
                if group_key and group_key != 'original':
                    if group_key not in new_orders_map:
                        supplier_id = None
                        supplier = None
                        
                        if group_key.startswith('sup_'):
                            try:
                                supplier_id = int(group_key.split('_')[1])
                                supplier = Supplier.objects.get(pk=supplier_id)
                            except (ValueError, Supplier.DoesNotExist):
                                pass
                        
                        new_order = Order.objects.create(
                            warehouse=original_order.warehouse,
                            created_by=original_order.created_by,
                            status='new',
                            priority=original_order.priority,
                            expected_date=original_order.expected_date,
                            supplier=supplier,
                            note=f"Розділено із заявки #{original_order.id}"
                        )
                        new_orders_map[group_key] = new_order
                    
                    target_order = new_orders_map[group_key]
                    item.order = target_order
                    
                    # Підтягуємо ціну постачальника
                    if target_order.supplier:
                        price_obj = SupplierPrice.objects.filter(
                            supplier=target_order.supplier, 
                            material=item.material
                        ).first()
                        if price_obj:
                            item.supplier_price = price_obj.price
                            
                    item.save()
                    moved_count += 1

            if new_orders_map:
                original_order.note = f"{original_order.note} | Частково розділена."
                original_order.save()
                
                if original_order.items.count() == 0:
                    original_order.status = 'rejected'
                    original_order.note += " (Всі товари перенесено)"
                    original_order.save()

                log_audit(request, 'UPDATE', original_order, new_val=f"Split into {len(new_orders_map)} new orders")
                messages.success(request, f"Успішно розділено на {len(new_orders_map)} нових заявок! Перенесено {moved_count} товарів.")
                
            return redirect('manager_dashboard')

    return render(request, 'warehouse/split_order.html', {
        'order': original_order, 
        'items': items, 
        'suppliers': suppliers,
        'suppliers_map': suppliers_map
    })


# ==============================================================================
# COMPATIBILITY LAYER (ALIASES & STUBS)
# ==============================================================================

# Aliases
manager_dashboard = dashboard
manager_order_detail = order_detail

@staff_required
def manager_process_order(request, pk):
    """
    Редирект на деталі заявки, оскільки процес погодження змінено.
    Відображає шаблон-повідомлення.
    """
    order = get_object_or_404(Order, pk=pk)
    enforce_warehouse_access_or_404(request.user, order.warehouse)
    return render(request, 'warehouse/manager_process_order.html', {'order': order})


# Stubs
@staff_required
def create_po(request, pk):
    """
    Формування PO (Purchase Order).
    """
    order = get_object_or_404(Order, pk=pk)
    enforce_warehouse_access_or_404(request.user, order.warehouse)
    return redirect('print_order_pdf', pk=pk)