from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Case, When, F, DecimalField
from django.contrib import messages
from django.db import transaction as db_transaction  # <--- Перейменовано для уникнення конфліктів
from ..models import Transaction, Order, Warehouse, Material
from ..forms import TransactionForm
from .utils import get_user_warehouses, check_access, get_stock_json, get_barcode_json, get_warehouse_balance, log_audit

@login_required
def add_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            if not check_access(request.user, obj.warehouse): return HttpResponse("⛔", 403)
            
            obj.created_by = request.user 
            
            if not request.user.is_staff and not obj.transaction_type:
                obj.transaction_type = 'OUT'
            
            if obj.transaction_type in ['OUT', 'LOSS'] and obj.price == 0:
                obj.price = obj.material.current_avg_price
            
            obj.save()
            
            action_name = "Списано на роботи" if obj.transaction_type == 'OUT' else "Зафіксовано втрату"
            messages.success(request, f"📉 {action_name}: {obj.material.name} (-{obj.quantity} {obj.material.unit})")
            
            audit_action = 'WRITEOFF' if obj.transaction_type == 'LOSS' else 'UPDATE'
            log_audit(
                request, 
                action_type=audit_action, 
                obj=obj, 
                new_val=f"{action_name}: {obj.quantity} {obj.material.unit}. Причина: {obj.description}"
            )
            
            return redirect('index')
    else:
        form = TransactionForm()
        form.fields['warehouse'].queryset = get_user_warehouses(request.user)
        
    return render(request, 'warehouse/transaction_form.html', {
        'form': form, 'stock_json': get_stock_json(), 'barcode_json': get_barcode_json()
    })

@login_required
def confirm_receipt(request, pk):
    # Завантажуємо заявку разом із товарами
    order = get_object_or_404(Order.objects.prefetch_related('items__material'), pk=pk)
    
    if not check_access(request.user, order.warehouse): 
        return HttpResponse("⛔ Немає доступу", 403)

    if request.method == 'POST':
        action = request.POST.get('action') 
        
        # --- ВІДХИЛЕННЯ ---
        if action == 'reject':
            reject_reason = request.POST.get('reject_reason', 'Відхилено прорабом')
            
            # Зберігаємо фото доказу, якщо модель це підтримує
            if 'proof_photo' in request.FILES and hasattr(order, 'proof_photo'):
                order.proof_photo = request.FILES['proof_photo']
            
            order.status = 'rejected'
            order.note = f"{order.note} | ВІДХИЛЕНО: {reject_reason}"
            order.log_change(request.user, f"Відхилив: {reject_reason}")
            order.save()
            
            log_audit(request, 'REJECT', order, new_val=f"Відхилено при прийомі. Причина: {reject_reason}")
            
            messages.warning(request, f"🚫 Поставку відхилено.")
            return redirect('index')

        # --- ПРИЙОМ (CONFIRM) ---
        with db_transaction.atomic():
            # Отримуємо фото з форми
            proof_photo = request.FILES.get('proof_photo')
            
            # Якщо в моделі є поле proof_photo, зберігаємо і туди
            if proof_photo and hasattr(order, 'proof_photo'):
                order.proof_photo = proof_photo
            
            # Проходимо по кожному товару в заявці
            for item in order.items.all():
                input_name = f"qty_{item.id}"
                raw_qty = request.POST.get(input_name, str(item.quantity))
                
                try:
                    # Замінюємо кому на крапку і конвертуємо
                    real_qty = float(raw_qty.replace(',', '.'))
                    if real_qty < 0: real_qty = 0
                except (ValueError, TypeError):
                    real_qty = float(item.quantity) # Якщо помилка, беремо план

                # Оновлюємо фактичну кількість
                item.quantity_fact = real_qty
                item.save()

                # Визначаємо ціну
                price = item.supplier_price or order.supplier_price or item.material.current_avg_price

                # Створюємо транзакцію приходу, використовуючи фото з змінної
                if real_qty > 0:
                    Transaction.objects.create(
                        transaction_type='IN', 
                        warehouse=order.warehouse, 
                        material=item.material,
                        quantity=real_qty, 
                        price=price, 
                        description=f"Прийом заявки #{order.id}", 
                        order=order, 
                        photo=proof_photo,  # <-- Використовуємо змінну proof_photo напряму
                        created_by=request.user
                    )
            
            order.status = 'completed'
            order.log_change(request.user, "Прийняв поставку")
            order.save()
            
            log_audit(request, 'UPDATE', order, new_val="Поставка прийнята (Completed)")

        messages.success(request, f"✅ Поставку успішно оприбутковано!")
        return redirect('index')

    return render(request, 'warehouse/confirm_receipt.html', {'order': order})

@login_required
def warehouse_detail(request, pk):
    wh = get_object_or_404(Warehouse, pk=pk)
    if not check_access(request.user, wh): return HttpResponse("⛔", 403)
    
    balance = get_warehouse_balance(wh)
    total_val = sum(item['total_sum'] for item in balance)

    transactions = Transaction.objects.filter(warehouse=wh).select_related('material', 'order').order_by('-created_at')
    
    f_type = request.GET.get('type')
    f_material = request.GET.get('material')
    f_date_from = request.GET.get('date_from')
    f_date_to = request.GET.get('date_to')

    if f_type: transactions = transactions.filter(transaction_type=f_type)
    if f_material: transactions = transactions.filter(material_id=f_material)
    if f_date_from: transactions = transactions.filter(created_at__date__gte=f_date_from)
    if f_date_to: transactions = transactions.filter(created_at__date__lte=f_date_to)

    if not any([f_type, f_material, f_date_from, f_date_to]): transactions = transactions[:50]
    all_materials = Material.objects.all().order_by('name')

    return render(request, 'warehouse/warehouse_detail.html', {
        'warehouse': wh, 'balance_list': balance, 'transactions': transactions, 
        'total_value': round(total_val, 2), 'all_materials': all_materials, 
        'filter_type': f_type, 'filter_material': int(f_material) if f_material else None,
        'filter_date_from': f_date_from, 'filter_date_to': f_date_to,
    })

@login_required
def material_list(request):
    materials = Material.objects.all().order_by('name')
    for mat in materials:
        mat.total_stock = Transaction.objects.filter(material=mat).aggregate(
            total=Sum(Case(
                When(transaction_type='IN', then=F('quantity')),
                When(transaction_type__in=['OUT', 'TRANSFER', 'LOSS'], then=0 - F('quantity')),
                default=0, output_field=DecimalField()
            ))
        )['total'] or 0
        mat.current_avg_price = round(mat.current_avg_price, 2)
    return render(request, 'warehouse/material_list.html', {'materials': materials})

@login_required
def material_detail(request, pk):
    mat = get_object_or_404(Material, pk=pk)
    trans = Transaction.objects.filter(material=mat).order_by('-created_at')[:50]
    warehouses_stock = []
    total_qty = 0
    for wh in Warehouse.objects.all():
        bal = get_warehouse_balance(wh, mat.id)
        if bal:
            qty = bal[0]['quantity']; warehouses_stock.append({'warehouse': wh, 'quantity': qty}); total_qty += qty
    return render(request, 'warehouse/material_detail.html', {
        'material': mat, 'transactions': trans, 'warehouses_stock': warehouses_stock,
        'total_quantity': total_qty, 'total_value': round(total_qty * mat.current_avg_price, 2)
    })

@login_required
def transaction_detail(request, pk):
    trans = get_object_or_404(Transaction, pk=pk)
    if not check_access(request.user, trans.warehouse): return HttpResponse("⛔", 403)
    total_sum = round(trans.quantity * trans.price, 2)
    return render(request, 'warehouse/transaction_detail.html', {'trans': trans, 'total_sum': total_sum})