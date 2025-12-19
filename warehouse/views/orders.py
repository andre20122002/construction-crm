from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from ..models import Order, Warehouse, Material, OrderItem
from ..forms import OrderForm, OrderFnItemFormSet
from .utils import get_user_warehouses, check_access, get_stock_json, get_barcode_json, log_audit
import json
import openpyxl

@login_required
def check_order_duplicates(request):
    wh_id = request.GET.get('warehouse')
    if not wh_id: return JsonResponse({'exists': False})

    # Перевіряємо, чи є будь-які активні заявки на цей склад
    recent_orders = Order.objects.filter(
        warehouse_id=wh_id
    ).exclude(status__in=['completed', 'rejected', 'draft']).order_by('-created_at')[:3]
    
    if recent_orders.exists():
        data = []
        for o in recent_orders:
            # Беремо перші 2 матеріали для прев'ю
            items_str = ", ".join([i.material.name for i in o.items.all()[:2]])
            data.append({
                'id': o.id,
                'date': o.created_at.strftime('%d.%m'),
                'preview': items_str
            })
        return JsonResponse({'exists': True, 'orders': data})
    
    return JsonResponse({'exists': False})

@login_required
def create_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES)
        formset = OrderFnItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                if not check_access(request.user, order.warehouse): 
                    return HttpResponse("⛔ Немає доступу до складу", status=403)
                
                order.created_by = request.user
                
                action = request.POST.get('action', 'send')
                if action == 'draft':
                    order.status = 'draft'
                    log_msg = "Збережено як чернетку"
                else:
                    order.status = 'new'
                    log_msg = "Створив заявку"

                timestamp = timezone.now().strftime("%d.%m.%Y %H:%M")
                user_name = request.user.get_full_name() or request.user.username
                order.audit_log = f"[{timestamp}] {user_name}: {log_msg}\n"
                
                order.save()
                
                # Зберігаємо товари
                formset.instance = order
                formset.save()
                
                if order.status == 'new':
                    log_audit(request, 'CREATE', order, new_val=f"Заявка на {order.items.count()} позицій")

            return redirect('index')
    else:
        form = OrderForm()
        formset = OrderFnItemFormSet()
        whs = get_user_warehouses(request.user)
        form.fields['warehouse'].queryset = whs
        if whs.count() == 1:
            form.fields['warehouse'].initial = whs.first()

    return render(request, 'warehouse/order_form.html', {
        'form': form,
        'formset': formset,
        'stock_json': get_stock_json(), 
        'barcode_json': get_barcode_json()
    })

@login_required
def order_list(request):
    # ВИПРАВЛЕНО: prefetch_related('items__material')
    orders = Order.objects.all().select_related('warehouse', 'created_by').prefetch_related('items__material').order_by('-created_at')
    
    if not request.user.is_staff:
        whs = get_user_warehouses(request.user)
        orders = orders.filter(Q(created_by=request.user) | Q(warehouse__in=whs))

    f_status = request.GET.get('status')
    f_date_from = request.GET.get('date_from')
    f_date_to = request.GET.get('date_to')

    if f_status: orders = orders.filter(status=f_status)
    if f_date_from: orders = orders.filter(created_at__date__gte=f_date_from)
    if f_date_to: orders = orders.filter(created_at__date__lte=f_date_to)

    if request.GET.get('export') == 'excel':
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Заявки"
        ws.append(['ID', 'Дата', 'Статус', 'Об\'єкт', 'Автор', 'Матеріали'])
        
        for o in orders:
            items_str = ", ".join([f"{i.material.name} ({i.quantity})" for i in o.items.all()])
            ws.append([
                o.id,
                o.created_at.strftime('%d.%m.%Y'),
                o.get_status_display(),
                o.warehouse.name,
                o.created_by.get_full_name() if o.created_by else "-",
                items_str
            ])
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=orders.xlsx'
        wb.save(response)
        return response

    return render(request, 'warehouse/order_list.html', {
        'orders': orders, 
        'f_status': f_status, 'f_date_from': f_date_from, 'f_date_to': f_date_to,
    })

@login_required
def confirm_draft(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.created_by == request.user and order.status == 'draft':
        order.status = 'new'
        order.log_change(request.user, "Відправив чернетку в роботу")
        order.save()
        log_audit(request, 'UPDATE', order, new_val="Status: draft -> new")
    return redirect('order_list')

@login_required
def delete_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.created_by == request.user:
        log_audit(request, 'DELETE', order, old_val=f"Deleted order #{order.id}")
        order.delete()
    return redirect('index')

@login_required
def print_order_pdf(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'warehouse/pdf_invoice.html', {'order': order})

@login_required
def logistics_dashboard(request):
    if not request.user.is_staff: return redirect('index')
    # ВИПРАВЛЕНО: prefetch_related
    transit_orders = Order.objects.filter(status='in_transit').prefetch_related('items__material').order_by('-updated_at')
    purchasing_orders = Order.objects.filter(status='purchasing').prefetch_related('items__material').order_by('-updated_at')
    return render(request, 'warehouse/logistics.html', {
        'transit_orders': transit_orders, 'purchasing_orders': purchasing_orders
    })

@login_required
def mark_shipped(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not request.user.is_staff: return redirect('index') 

    if request.method == 'POST':
        order.driver_name = request.POST.get('driver_name', '')
        order.driver_phone = request.POST.get('driver_phone', '')
        order.vehicle_number = request.POST.get('vehicle_number', '')
        
        if 'shipping_doc' in request.FILES:
            order.shipping_doc = request.FILES['shipping_doc']

        order.status = 'in_transit'
        order.log_change(request.user, f"🚛 Відправив машину: {order.vehicle_number} ({order.driver_name})")
        order.save()
        
        log_audit(request, 'UPDATE', order, new_val="Shipped (in_transit)")
        
        return redirect('logistics_dashboard')
    
    return redirect('logistics_dashboard')