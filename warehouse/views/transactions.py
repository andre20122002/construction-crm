from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Case, When, F, DecimalField, Q
from django.utils import timezone
from django import forms
from decimal import Decimal, ROUND_HALF_UP

from ..models import Transaction, Order, Warehouse, Material, ConstructionStage 
from ..forms import TransactionForm
from .utils import (
    get_user_warehouses, 
    check_access, 
    get_warehouse_balance, 
    log_audit, 
    get_stock_json,
    enforce_warehouse_access_or_404,
    get_allowed_warehouses,
    restrict_warehouses_qs
)
from ..services import inventory
# Імпортуємо виняток для обробки помилок залишків
from ..services.inventory import InsufficientStockError

# ==============================================================================
# ДЕТАЛІ СКЛАДУ (WAREHOUSE DETAIL)
# ==============================================================================

@login_required
def warehouse_detail(request, pk):
    """
    Сторінка конкретного складу.
    Відображає:
    1. Поточний баланс (Залишки).
    2. Історію транзакцій з фільтрами.
    """
    wh = get_object_or_404(Warehouse, pk=pk)
    
    # Перевірка доступу (використовуємо нову функцію, яка підніме 404, якщо немає доступу)
    enforce_warehouse_access_or_404(request.user, wh)

    # 1. Отримуємо баланс (словник {Material: quantity})
    balance_map = get_warehouse_balance(wh)
    
    # Формуємо список для шаблону та рахуємо загальну вартість
    balance_list = []
    total_value = Decimal("0.00")
    
    for mat, qty in balance_map.items():
        # Пропускаємо нульові залишки, якщо це не критично
        if qty != 0:
            # Розрахунок вартості позиції (Decimal * Decimal)
            # qty вже Decimal завдяки оновленому get_warehouse_balance
            # mat.current_avg_price теж Decimal з моделі
            val = (qty * mat.current_avg_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_value += val
            
            # Визначення статусу (критичний залишок чи ні)
            status = 'ok'
            # Перевіряємо, чи є мін. ліміт і чи поточна кількість менша/рівна йому
            limit = getattr(mat, 'min_limit', None) or getattr(mat, 'min_stock', None)
            
            if limit and qty <= limit:
                status = 'critical'
            
            balance_list.append({
                'id': mat.id,
                'name': mat.name,
                'unit': mat.unit,
                'quantity': qty,
                'avg_price': mat.current_avg_price, # Додаємо про всяк випадок для відображення
                'total_sum': val,                   # Додаємо для відображення суми по рядку
                'status': status,
                # Зберігаємо посилання на об'єкт матеріалу для сумісності з шаблонами
                'material': mat 
            })
            
    # Сортуємо залишки по назві матеріалу
    balance_list.sort(key=lambda x: x['name'])

    # 2. Історія транзакцій
    transactions = Transaction.objects.filter(warehouse=wh).select_related('material', 'created_by', 'order').order_by('-date', '-created_at')
    
    # Оптимізація фільтра матеріалів: показуємо тільки ті матеріали, які фігурують у транзакціях цього складу
    material_ids = transactions.values_list('material_id', flat=True).distinct()
    available_materials = Material.objects.filter(id__in=material_ids).order_by('name')

    # Фільтрація
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    t_type = request.GET.get('type')
    material_id = request.GET.get('material')
    
    if date_from: transactions = transactions.filter(date__gte=date_from)
    if date_to: transactions = transactions.filter(date__lte=date_to)
    
    # Логіка фільтрації за типом
    if t_type:
        # Підтримка 'TRANSFER' для backward compatibility, але основний 'MOVE'
        if t_type == 'MOVE' or t_type == 'TRANSFER':
            # Якщо користувач хоче бачити переміщення - шукаємо записи з group_id
            transactions = transactions.filter(transfer_group_id__isnull=False)
        else:
            # Інакше фільтруємо за прямим типом (IN, OUT, LOSS)
            transactions = transactions.filter(transaction_type=t_type)
            
    if material_id: transactions = transactions.filter(material_id=material_id)

    return render(request, 'warehouse/warehouse_detail.html', {
        'warehouse': wh,
        'balance_list': balance_list, # Передаємо оновлений список
        'stock_list': balance_list,   # Alias для сумісності зі старими шаблонами
        'transactions': transactions[:100], # Ліміт 100 останніх
        'total_value': total_value,
        'materials': available_materials, # Оптимізований список матеріалів для фільтру
        'f_date_from': date_from,
        'f_date_to': date_to,
        'f_type': t_type,
        'f_material': int(material_id) if material_id else '',
        'page_title': f"{wh.name} - Деталі"
    })


# ==============================================================================
# ДЕТАЛІ ТРАНЗАКЦІЇ
# ==============================================================================

@login_required
def transaction_detail(request, pk):
    """
    Детальний перегляд однієї транзакції.
    """
    trans = get_object_or_404(Transaction, pk=pk)
    
    # Перевірка доступу до складу транзакції
    enforce_warehouse_access_or_404(request.user, trans.warehouse)
    
    # Розрахунок загальної суми транзакції (Decimal)
    price = trans.price or Decimal("0.00")
    total_sum = (trans.quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    # Прапорець, чи це переміщення
    is_transfer = bool(trans.transfer_group_id)
         
    return render(request, 'warehouse/transaction_detail.html', {
        'trans': trans,
        'total_sum': total_sum,
        'is_transfer': is_transfer
    })


# ==============================================================================
# ДОДАВАННЯ ТРАНЗАКЦІЇ (РУЧНЕ)
# ==============================================================================

@login_required
def add_transaction(request):
    """
    Ручне створення запису: Прихід, Списання (Роботи), Втрати.
    НЕ створює переміщення (для цього є окрема в'юха).
    """
    if request.method == 'POST':
        # Створюємо копію POST даних для модифікації
        post_data = request.POST.copy()
        
        # Fail-safe для дати: якщо не вказана або порожня, ставимо сьогоднішню
        if not post_data.get('date'):
            post_data['date'] = timezone.localdate().isoformat()
            
        # Fail-safe для ціни: якщо не вказана або порожня, ставимо 0.00
        if not post_data.get('price'):
            post_data['price'] = '0.00'
            
        form = TransactionForm(post_data, request.FILES)
        
        # Видалено обмеження queryset тут для POST, щоб form.is_valid() пройшов, 
        # навіть якщо користувач маніпулював ID або форма рендериться заново.
        # Перевірка доступу буде виконана нижче через enforce_warehouse_access_or_404.
        
        if form.is_valid():
            data = form.cleaned_data
            wh = data['warehouse']
            
            # Перевірка доступу до складу
            # Це викликає 404, якщо користувач не має прав на цей склад
            enforce_warehouse_access_or_404(request.user, wh)

            try:
                # Використовуємо inventory services замість ручного створення
                t_type = data['transaction_type']
                
                # Отримуємо дату та ціну з post_data (бо їх може не бути в form.cleaned_data, якщо полів немає у формі)
                tx_date = post_data.get('date')
                tx_price = post_data.get('price')
                
                if t_type == 'IN':
                    inventory.create_incoming(
                        material=data['material'],
                        warehouse=wh,
                        quantity=data['quantity'],
                        user=request.user,
                        price=tx_price,
                        description=data['description'],
                        date=tx_date,
                        photo=data.get('photo')
                    )
                    action_msg = "✅ Прихід успішно створено!"
                    
                elif t_type in ['OUT', 'LOSS']:
                    # Спроба створити списання з перевіркою залишків
                    inventory.create_writeoff(
                        transaction_type=t_type,
                        material=data['material'],
                        warehouse=wh,
                        quantity=data['quantity'],
                        user=request.user,
                        description=data['description'],
                        date=tx_date,
                        stage=data.get('stage'), # Тільки для OUT
                        photo=data.get('photo')
                    )
                    action_msg = f"✅ {'Списання' if t_type == 'OUT' else 'Втрати'} успішно проведено!"
                else:
                    # Якщо раптом прилетів TRANSFER або щось інше
                    raise ValidationError("Невірний тип транзакції для цієї форми.")
                
                log_audit(request, 'CREATE', new_val=f"{t_type}: {data['material'].name} x {data['quantity']} on {wh.name}")
                messages.success(request, action_msg)
                return redirect('warehouse_detail', pk=wh.id)
                
            except InsufficientStockError as e:
                # Обробка помилки нестачі товару
                messages.error(request, str(e))
                # Повертаємо користувача на форму з даними
                return render(request, 'warehouse/transaction_form.html', {'form': form})
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Помилка: {e}")
    else:
        # GET request
        form = TransactionForm()
        # Передзаповнення з URL параметрів (наприклад, з QR-коду)
        t_type = request.GET.get('type')
        
        if t_type: 
            form.fields['transaction_type'].initial = t_type
            
        # Фільтруємо склади у формі (ТІЛЬКИ ДОЗВОЛЕНІ) - тільки для GET, для відображення у dropdown
        form.fields['warehouse'].queryset = get_allowed_warehouses(request.user)
        
        # Активний склад з сесії
        active_wh_id = request.session.get('active_warehouse_id')
        if active_wh_id:
            # Перевіряємо, чи є доступ до активного складу
            if get_allowed_warehouses(request.user).filter(pk=active_wh_id).exists():
                form.fields['warehouse'].initial = active_wh_id

    return render(request, 'warehouse/transaction_form.html', {'form': form})


# ==============================================================================
# ПЕРЕМІЩЕННЯ (TRANSFER)
# ==============================================================================

class TransferForm(forms.Form):
    source_warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.none(), label="Зі складу")
    # ТІЛЬКИ ДОЗВОЛЕНІ СКЛАДИ ДЛЯ ПРИЗНАЧЕННЯ (по замовчуванню none, заповниться у view)
    target_warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.none(), label="На склад")
    material = forms.ModelChoiceField(queryset=Material.objects.all(), label="Матеріал")
    
    # DECIMAL UPDATE
    quantity = forms.DecimalField(
        min_value=Decimal("0.001"), 
        max_digits=14, 
        decimal_places=3, 
        label="Кількість",
        widget=forms.NumberInput(attrs={'step': '0.001'})
    )
    
    date = forms.DateField(initial=timezone.now().date, widget=forms.DateInput(attrs={'type': 'date'}), label="Дата")
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label="Коментар")

@login_required
def add_transfer(request):
    """
    Створення переміщення між складами.
    Використовує inventory.create_transfer (створює OUT + IN).
    """
    allowed_whs = get_allowed_warehouses(request.user)
    
    if request.method == 'POST':
        form = TransferForm(request.POST)
        # Підставляємо дозволені склади для валідації
        form.fields['source_warehouse'].queryset = allowed_whs
        # Для цільового складу логіка може відрізнятись:
        # Можна дозволити відправляти на будь-який склад (Warehouse.objects.all()) або тільки на свої.
        # Зазвичай відправляти можна куди завгодно, але бачити залишки - тільки свої.
        # Проте за завданням "звичайний користувач не повинен бачити чужі склади в dropdown".
        # Тому обмежуємо і цільовий склад.
        form.fields['target_warehouse'].queryset = allowed_whs
        
        if form.is_valid():
            data = form.cleaned_data
            source = data['source_warehouse']
            target = data['target_warehouse']
            
            # Додаткова перевірка доступу до джерела (хоча queryset вже фільтрує)
            enforce_warehouse_access_or_404(request.user, source)
            
            if source == target:
                messages.error(request, "Склад-джерело і призначення не можуть співпадати.")
            else:
                try:
                    inventory.create_transfer(
                        user=request.user,
                        material=data['material'],
                        source_warehouse=source,
                        target_warehouse=target,
                        quantity=data['quantity'], # Вже Decimal
                        description=data['description'],
                        date=data['date']
                    )
                    
                    log_audit(request, 'CREATE', new_val=f"Transfer: {data['material']} {source}->{target}")
                    messages.success(request, "✅ Переміщення успішно виконано!")
                    return redirect('transfer_journal')
                
                except InsufficientStockError as e:
                    # Обробка помилки нестачі товару при переміщенні
                    messages.error(request, str(e))
                    # Повертаємось на сторінку (не редірект), щоб зберегти введені дані (на жаль, для Form дані не зберігаються автоматично при render, але повідомлення буде видно)
                    # Щоб зберегти дані, треба передати form у render
                    # form вже містить POST дані
                    
                    # Також треба не забути про stock_json для JS
                    stock_json = get_stock_json(request.user)
                    return render(request, 'warehouse/transfer_form.html', {
                        'form': form,
                        'stock_json': stock_json,
                        'page_title': 'Переміщення матеріалів'
                    })
                    
                except ValidationError as e:
                    messages.error(request, str(e))
                except Exception as e:
                    messages.error(request, f"Помилка: {e}")
    else:
        form = TransferForm()
        # Фільтруємо склади (ТІЛЬКИ ДОЗВОЛЕНІ)
        form.fields['source_warehouse'].queryset = allowed_whs
        form.fields['target_warehouse'].queryset = allowed_whs
        
    # Словник залишків для JS (щоб показувати на льоту доступність)
    # get_stock_json вже user-aware завдяки змінам в utils.py
    stock_json = get_stock_json(request.user)

    return render(request, 'warehouse/transfer_form.html', {
        'form': form,
        'stock_json': stock_json,
        'page_title': 'Переміщення матеріалів'
    })

# Alias for compatibility with warehouse/urls.py
create_transfer_view = add_transfer