from django.contrib import admin
from django.contrib.admin import TabularInline
from django.db.models import Sum, Q
from .models import (
    Material, Warehouse, Transaction, Order, OrderItem, 
    Supplier, SupplierPrice, AuditLog, Category, 
    ConstructionStage, StageLimit, UserProfile
)

# --- INLINES (Вкладені таблиці) ---

class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 1
    raw_id_fields = ['material'] 

class SupplierPriceInline(TabularInline):
    model = SupplierPrice
    extra = 1
    
class StageLimitInline(TabularInline):
    model = StageLimit
    extra = 1
    raw_id_fields = ['material'] 

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
    list_display = ('name', 'article', 'characteristics', 'category', 'unit', 'current_avg_price', 'min_limit')
    list_filter = ('category',)
    search_fields = ('name', 'article')
    # ВИПРАВЛЕНО: замінено 'market_price' на 'current_avg_price'
    readonly_fields = ('current_avg_price',)

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'budget_limit', 'responsible_user')
    search_fields = ('name',)

@admin.register(ConstructionStage)
class ConstructionStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'warehouse', 'start_date', 'end_date', 'completed')
    list_filter = ('warehouse', 'completed')
    search_fields = ('name',)
    inlines = [StageLimitInline]

@admin.register(StageLimit)
class StageLimitAdmin(admin.ModelAdmin):
    # ВИПРАВЛЕНО: видалено неіснуюче поле 'construct_type', додано коректні поля
    list_display = ('stage', 'material', 'planned_quantity')
    # ВИПРАВЛЕНО: фільтр по стадії та складу
    list_filter = ('stage', 'stage__warehouse')
    search_fields = ('stage__name', 'material__name')
    raw_id_fields = ('material',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'transaction_type', 'warehouse', 'material', 'quantity', 'price', 'created_by')
    list_filter = ('transaction_type', 'warehouse', 'date')
    search_fields = ('material__name', 'description')
    date_hierarchy = 'date'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'warehouse', 'status', 'priority', 'created_by', 'created_at')
    list_filter = ('status', 'priority', 'warehouse')
    search_fields = ('id', 'warehouse__name', 'note')
    inlines = [OrderItemInline]

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action_type', 'affected_object', 'ip_address')
    list_filter = ('action_type', 'timestamp', 'user')
    search_fields = ('old_value', 'new_value', 'user__username')
    readonly_fields = ('user', 'action_type', 'content_type', 'object_id', 'ip_address', 'timestamp', 'old_value', 'new_value', 'affected_object')

    @admin.display(description="Об'єкт")
    def affected_object(self, obj):
        if obj.content_type:
             return obj.content_object
        return "-"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'position', 'phone')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'position')
    filter_horizontal = ('warehouses',)