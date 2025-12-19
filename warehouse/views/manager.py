from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Case, When, F, DecimalField, Count
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from ..models import Order, OrderComment, Warehouse, Transaction, OrderItem, Supplier, SupplierPrice
from .utils import log_audit

@login_required
def manager_dashboard(request):
    if not request.user.is_staff: return redirect('index')
    
    orders = Order.objects.exclude(status='draft').select_related('warehouse', 'created_by').prefetch_related('items__material').order_by('-created_at')
    
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    wh_id = request.GET.get('warehouse')
    
    if status: orders = orders.filter(status=status)
    if priority: orders = orders.filter(priority=priority)
    if wh_id: orders = orders.filter(warehouse_id=wh_id)
    
    warehouses = Warehouse.objects.all()
    count_new = Order.objects.filter(status='new').count()
    count_rfq = Order.objects.filter(status='rfq').count()
    
    return render(request, 'warehouse/manager_dashboard.html', {
        'orders': orders, 'warehouses': warehouses,
        'current_status': status, 'count_new': count_new, 'count_rfq': count_rfq
    })

@login_required
def manager_order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related(
        'items__material', 
        'items__material__supplier_prices__supplier'
    ), pk=pk)
    
    if not request.user.is_staff: return redirect('index')
    
    order.manager_last_viewed_at = timezone.now()
    order.save(update_fields=['manager_last_viewed_at'])

    if request.method == 'POST' and 'comment_text' in request.POST:
        comment_text = request.POST.get('comment_text')
        if comment_text:
            OrderComment.objects.create(order=order, author=request.user, text=comment_text)
            return redirect('manager_order_detail', pk=pk)
    
    # --- ЛОГІКА ПІДБОРУ ПОСТАЧАЛЬНИКА ---
    suggested_suppliers = []
    items_list = list(order.items.all())
    
    if items_list:
        material_ids = [item.material.id for item in items_list]
        distinct_materials_count = len(set(material_ids))
        
        suggested_suppliers = Supplier.objects.filter(
            prices__material__id__in=material_ids
        ).annotate(
            covered_count=Count('prices__material', distinct=True)
        ).filter(
            covered_count=distinct_materials_count
        )

    # --- INTERNAL STOCK ---
    # Перевіряємо, чи є товари на інших складах
    internal_stock_suggestions = {}
    
    for item in items_list:
        stock_qs = Transaction.objects.filter(
            material=item.material
        ).exclude(
            warehouse=order.warehouse
        ).values('warehouse').annotate(
            total=Sum(Case(
                When(transaction_type='IN', then=F('quantity')),
                When(transaction_type__in=['OUT', 'TRANSFER', 'LOSS'], then=0-F('quantity')),
                default=0, output_field=DecimalField()
            ))
        ).filter(total__gt=0)
        
        suggestions = []
        for s in stock_qs:
            wh = Warehouse.objects.get(pk=s['warehouse'])
            suggestions.append({'wh': wh, 'qty': s['total']})
        
        if suggestions:
            internal_stock_suggestions[item.material.name] = suggestions

    comments = order.comments.all().select_related('author')
    
    return render(request, 'warehouse/manager_order_detail.html', {
        'order': order, 
        'internal_stock_suggestions': internal_stock_suggestions,
        'suggested_suppliers': suggested_suppliers,
        'comments': comments
    })

@login_required
def create_po(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not request.user.is_staff: return HttpResponse("⛔", 403)

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id') 
        manual_supplier = request.POST.get('manual_supplier') 
        
        if supplier_id:
            try:
                sup = Supplier.objects.get(id=supplier_id)
                order.selected_supplier = sup
                order.supplier_info = sup.name
                for item in order.items.all():
                    price_obj = SupplierPrice.objects.filter(supplier=sup, material=item.material).first()
                    if price_obj:
                        item.supplier_price = price_obj.price
                        item.save()
            except Supplier.DoesNotExist: pass
        elif manual_supplier:
            order.selected_supplier = None
            order.supplier_info = manual_supplier 
        
        order.approved_by = request.user
        order.approved_at = timezone.now()
        order.status = 'purchasing'
        order.log_change(request.user, f"Затвердив закупівлю. Постачальник: {order.supplier_info}")
        log_audit(request, 'APPROVE', obj=order, new_val=f"Purchasing from: {order.supplier_info}")
        order.save()
        return redirect('logistics_dashboard') 
    
    return redirect('manager_order_detail', pk=pk)

@login_required
def transfer_from_stock(request, pk):
    """
    Переміщення товарів із запасів іншого складу.
    Виконує сувору перевірку залишків перед проведенням.
    """
    order = get_object_or_404(Order, pk=pk)
    if not request.user.is_staff: return HttpResponse("⛔", 403)

    source_id = request.POST.get('source_id')
    if source_id:
        source = get_object_or_404(Warehouse, pk=source_id)
        
        # 1. ПЕРЕВІРКА: Чи вистачає ВСІХ товарів на складі-донорі?
        missing_items = []
        
        for item in order.items.all():
            # Рахуємо реальний залишок конкретного матеріалу на складі-джерелі
            stock_on_source = Transaction.objects.filter(
                warehouse=source, 
                material=item.material
            ).aggregate(
                total=Sum(Case(
                    When(transaction_type='IN', then=F('quantity')),
                    When(transaction_type__in=['OUT', 'TRANSFER', 'LOSS'], then=0-F('quantity')),
                    default=0, output_field=DecimalField()
                ))
            )['total'] or 0
            
            # Якщо залишку менше, ніж треба в заявці
            if stock_on_source < item.quantity:
                diff = item.quantity - stock_on_source
                missing_items.append(f"{item.material.name} (Треба: {item.quantity}, Є: {stock_on_source})")
        
        # Якщо знайшли нестачу - скасовуємо операцію і показуємо помилку
        if missing_items:
            error_msg = f"⛔ Помилка переміщення! На складі '{source.name}' недостатньо товарів: {', '.join(missing_items)}."
            messages.error(request, error_msg)
            return redirect('manager_order_detail', pk=pk)

        # 2. ЯКЩО ВСЕ ОК - ПРОВОДИМО ТРАНЗАКЦІЇ
        with transaction.atomic():
            for item in order.items.all():
                Transaction.objects.create(
                    transaction_type='TRANSFER', 
                    warehouse=source, 
                    material=item.material,
                    quantity=item.quantity, 
                    price=item.material.current_avg_price,
                    description=f"Трансфер на {order.warehouse.name} (Заявка #{order.id})", 
                    order=order, 
                    created_by=request.user
                )
            
            order.source_warehouse = source
            order.status = 'in_transit'
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.log_change(request.user, f"Погодив трансфер з {source.name}")
            order.save()
            
            log_audit(request, 'TRANSFER', obj=order, new_val=f"From {source.name}")
            messages.success(request, f"✅ Успішно оформлено переміщення з {source.name}")

    return redirect('manager_dashboard')

@login_required
def approve_order(request, pk): return redirect('manager_order_detail', pk=pk)

@login_required
def reject_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.user.is_staff:
        order.status = 'rejected'
        if not "ВІДХИЛЕНО" in order.note:
            order.note = (order.note + " | " if order.note else "") + "ВІДХИЛЕНО: Розділіть замовлення."
        log_audit(request, 'REJECT', obj=order, new_val="Rejected")
        order.save()
    return redirect('index')

# Додаємо нову view для розділення, якщо вона ще не була додана
@login_required
def split_order_view(request, pk):
    """
    Майстер розділення заявки на кілька частин за постачальниками.
    """
    original_order = get_object_or_404(Order, pk=pk)
    if not request.user.is_staff: return HttpResponse("⛔ Немає доступу", 403)
    
    if original_order.status != 'new':
        return HttpResponse("⛔ Можна розділяти тільки нові заявки!", 400)

    items = original_order.items.all().select_related('material')
    
    groups = {}
    suppliers_map = {} 
    
    for item in items:
        best_price = SupplierPrice.objects.filter(material=item.material).order_by('price').first()
        if best_price:
            sup = best_price.supplier
            suppliers_map[sup.id] = sup
            if sup.id not in groups: groups[sup.id] = []
            groups[sup.id].append(item)
        else:
            if 'unknown' not in groups: groups['unknown'] = []
            groups['unknown'].append(item)

    if request.method == 'POST':
        with transaction.atomic():
            new_orders_map = {}
            for item in items:
                group_key = request.POST.get(f'item_{item.id}')
                if group_key == 'original': continue
                
                if group_key not in new_orders_map:
                    new_supplier = None
                    sup_name = ""
                    if group_key.startswith('sup_'):
                        sup_id = int(group_key.replace('sup_', ''))
                        new_supplier = Supplier.objects.get(id=sup_id)
                        sup_name = new_supplier.name
                    else:
                        sup_name = "Розділена заявка"

                    new_order = Order.objects.create(
                        warehouse=original_order.warehouse,
                        status='new',
                        priority=original_order.priority,
                        created_by=request.user,
                        expected_date=original_order.expected_date,
                        note=f"{original_order.note} (Частина #2)",
                        selected_supplier=new_supplier,
                        supplier_info=sup_name
                    )
                    new_orders_map[group_key] = new_order

                target_order = new_orders_map[group_key]
                item.order = target_order
                if target_order.selected_supplier:
                    price_obj = SupplierPrice.objects.filter(supplier=target_order.selected_supplier, material=item.material).first()
                    if price_obj: item.supplier_price = price_obj.price
                item.save()

            if new_orders_map:
                original_order.note += " | Заявка була розділена."
                original_order.save()
                log_audit(request, 'UPDATE', original_order, new_val=f"Split into {len(new_orders_map)+1} orders")
                
            return redirect('manager_dashboard')

    return render(request, 'warehouse/split_order.html', {
        'order': original_order, 'items': items, 'groups': groups, 'suppliers_map': suppliers_map
    })