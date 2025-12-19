from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory # <--- ВАЖЛИВО
from django.db.models import Sum, Case, When, F, DecimalField
from .models import Transaction, Order, OrderItem, Warehouse, OrderComment, UserProfile

# --- ФОРМИ ЗАЯВКИ (MASTER-DETAIL) ---

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        # Тільки загальні поля
        fields = ['warehouse', 'priority', 'expected_date', 'note', 'request_photo']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'expected_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Коментар до всієї заявки (напр. доставка маніпулятором)'}),
        }

class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['material', 'quantity']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select item-material'}), # Клас для JS
            'quantity': forms.NumberInput(attrs={'class': 'form-control item-qty', 'min': '0.01', 'step': '0.01'}),
        }

# Factory для створення набору форм
OrderFnItemFormSet = inlineformset_factory(
    Order, OrderItem,
    form=OrderItemForm,
    extra=1, # Кількість пустих рядків при створенні
    can_delete=True
)

# --- ІНШІ ФОРМИ (Без змін) ---

class OrderCommentForm(forms.ModelForm):
    class Meta:
        model = OrderComment
        fields = ['text']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Написати повідомлення...'})
        }

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'photo', 'position']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+380...'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
        }

class TransactionForm(forms.ModelForm):
    TYPE_CHOICES = [
        ('OUT', '🛠️ Витрата на роботи'),
        ('LOSS', '🗑️ Бій / Псування / Втрата'),
    ]
    transaction_type = forms.ChoiceField(
        choices=TYPE_CHOICES, 
        label="Що сталося?",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'type-select'})
    )
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'date', 'warehouse', 'material', 'quantity', 'work_type', 'shift', 'description', 'photo']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'material': forms.Select(attrs={'class': 'form-select'}),
            'work_type': forms.Select(attrs={'class': 'form-select'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        warehouse = cleaned_data.get('warehouse')
        material = cleaned_data.get('material')
        quantity = cleaned_data.get('quantity')
        trans_type = cleaned_data.get('transaction_type')

        if trans_type in ['OUT', 'LOSS'] and warehouse and material and quantity:
            current_stock = Transaction.objects.filter(
                warehouse=warehouse, 
                material=material
            ).aggregate(
                total=Sum(Case(
                    When(transaction_type='IN', then=F('quantity')),
                    When(transaction_type__in=['OUT', 'TRANSFER', 'LOSS'], then=0 - F('quantity')),
                    default=0, output_field=DecimalField()
                ))
            )['total'] or 0

            if quantity > current_stock:
                raise ValidationError(f"⛔ Недостатньо товару! Доступно: {current_stock}")
        return cleaned_data

class PeriodReportForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))