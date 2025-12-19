from django.contrib.admin import TabularInline
from django.contrib import admin
from .models import Material, Warehouse, Transaction, Order, OrderItem, Supplier, SupplierPrice, AuditLog, Category

# --- INLINES (Вкладені таблиці) ---

class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ['material']

class SupplierPriceInline(TabularInline):
    model = SupplierPrice
    extra = 1
    autocomplete_fields = ['material']

# --- ADMIN MODELS ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'rating')
    search_fields = ('name',)
    inlines = [SupplierPriceInline]

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'article', 'unit', 'current_avg_price') # Додано category
    list_filter = ('category', 'unit') # Додано фільтр по категорії
    search_fields = ('name', 'article')

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'budget_limit', 'responsible')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'transaction_type', 'material', 'quantity', 'warehouse', 'created_by')
    list_filter = ('transaction_type', 'warehouse', 'date')
    date_hierarchy = 'created_at'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'warehouse', 'status', 'priority', 'created_by', 'created_at')
    list_filter = ('status', 'priority', 'warehouse')
    search_fields = ('id', 'warehouse__name')
    inlines = [OrderItemInline]

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action_type', 'affected_object', 'old_value', 'new_value', 'ip_address')
    list_filter = ('action_type', 'user', 'timestamp')
    search_fields = ('old_value', 'new_value', 'user__username')
    readonly_fields = ('user', 'action_type', 'content_type', 'object_id', 'old_value', 'new_value', 'ip_address', 'timestamp')
    
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False