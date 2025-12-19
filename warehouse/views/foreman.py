from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from ..models import Order, OrderComment, Transaction, Warehouse
from ..forms import OrderForm, OrderFnItemFormSet
from .utils import get_user_warehouses, check_access, get_warehouse_balance, get_stock_json, get_barcode_json, log_audit
import json

@login_required
def foreman_order_detail(request, pk):
    # Завантажуємо items
    order = get_object_or_404(Order.objects.prefetch_related('items__material'), pk=pk)
    if order.created_by != request.user and not check_access(request.user, order.warehouse):
        return HttpResponse("⛔ Немає доступу", 403)

    if request.method == 'POST' and 'comment_text' in request.POST:
        comment_text = request.POST.get('comment_text')
        if comment_text:
            OrderComment.objects.create(order=order, author=request.user, text=comment_text)
            return redirect('foreman_order_detail', pk=pk)

    comments = order.comments.all().select_related('author')
    return render(request, 'warehouse/foreman_order_detail.html', {
        'order': order, 'comments': comments
    })

@login_required
def foreman_edit_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.created_by != request.user: return HttpResponse("⛔ Тільки автор може редагувати", 403)
    
    if order.status not in ['new', 'draft']: 
        return HttpResponse("⛔ Заявка вже в роботі", 403)

    available_warehouses = get_user_warehouses(request.user)

    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES, instance=order)
        # FormSet для редагування списку товарів
        formset = OrderFnItemFormSet(request.POST, instance=order)
        form.fields['warehouse'].queryset = available_warehouses
        
        if form.is_valid() and formset.is_valid():
            action = request.POST.get('action', 'send')
            if action == 'draft':
                order.status = 'draft'
                log_msg = "Оновив чернетку"
            else:
                order.status = 'new'
                log_msg = "Відправив заявку (редаговано)"

            order.log_change(request.user, log_msg)
            form.save()
            formset.save() # Зберігаємо товари
            
            log_audit(request, 'UPDATE', order, new_val=f"Edited order #{order.id}")
            return redirect('foreman_order_detail', pk=pk)
    else:
        form = OrderForm(instance=order)
        formset = OrderFnItemFormSet(instance=order)
        form.fields['warehouse'].queryset = available_warehouses
    
    main_wh_ids = list(Warehouse.objects.filter(is_main_storage=True).values_list('id', flat=True))
    
    # Використовуємо той самий шаблон order_form.html, але передаємо formset
    return render(request, 'warehouse/order_form.html', {
        'form': form, 
        'formset': formset, # <-- ВАЖЛИВО
        'stock_json': get_stock_json(), 
        'main_wh_ids': json.dumps(main_wh_ids), 
        'barcode_json': get_barcode_json(),
        'edit_mode': True, 
        'order': order
    })

@login_required
def foreman_storage_view(request):
    user_warehouses = get_user_warehouses(request.user)
    active_wh_id = request.session.get('active_warehouse_id')
    my_warehouse = None
    
    if active_wh_id:
        my_warehouse = user_warehouses.filter(id=active_wh_id).first()
    if not my_warehouse:
        my_warehouse = user_warehouses.first()
        if my_warehouse: request.session['active_warehouse_id'] = my_warehouse.id

    stock = []
    total_items = 0
    if my_warehouse:
        stock = get_warehouse_balance(my_warehouse)
        total_items = len(stock)

    return render(request, 'warehouse/foreman_storage.html', {
        'stock': stock, 'warehouse': my_warehouse, 'total_items': total_items
    })

@login_required
def writeoff_history_view(request):
    user_warehouses = get_user_warehouses(request.user)
    writeoffs = Transaction.objects.filter(
        warehouse__in=user_warehouses, transaction_type__in=['OUT', 'LOSS']
    ).select_related('material', 'warehouse').order_by('-created_at')
    return render(request, 'warehouse/writeoff_history.html', {'writeoffs': writeoffs})

@login_required
def delivery_history_view(request):
    user_warehouses = get_user_warehouses(request.user)
    deliveries = Transaction.objects.filter(
        warehouse__in=user_warehouses, transaction_type='IN'
    ).select_related('material', 'warehouse', 'order').order_by('-created_at')
    return render(request, 'warehouse/delivery_history.html', {'deliveries': deliveries})