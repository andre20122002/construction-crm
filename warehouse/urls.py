from django.urls import path

# 🔥 Модульні імпорти views
from .views import general, orders, reports, transactions, manager, foreman
from .views.project_dashboard import project_dashboard
from .views.concrete_analytics import concrete_analytics
from .views.rebar_analytics import rebar_analytics
from .views.mechanisms_analytics import mechanisms_analytics
from .views.utils import ajax_warehouse_stock, ajax_materials
# Імпортуємо нову view home (диспетчер)
from .views.home import home as home_view

urlpatterns = [
    # ==============================================================================
    # ГОЛОВНА СТОРІНКА (HOME / DISPATCHER)
    # ==============================================================================
    # Головний URL '/' тепер веде на home_view, який перенаправляє за роллю
    path('', home_view, name='home'),

    # Старий index перенесено на /dashboard/ (але name='index' збережено для шаблонів)
    path('dashboard/', general.index, name='index'),
    
    # ==============================================================================
    # AJAX API (ДЛЯ JS)
    # ==============================================================================
    path('ajax/check_duplicates/', orders.check_order_duplicates, name='check_order_duplicates'),
    path('ajax/load-stages/', general.load_stages, name='ajax_load_stages'),
    
    # (A) Ajax Warehouse Stock: Legacy path з новим іменем
    path('ajax/warehouse-stock/', ajax_warehouse_stock, name='ajax_warehouse_stock_legacy'),
    # (A) Ajax Warehouse Stock: Canonical path
    path('ajax/warehouse/<int:warehouse_id>/stock/', ajax_warehouse_stock, name='ajax_warehouse_stock'),
    # Allow reversing 'ajax_warehouse_stock' without arguments (aliases to legacy) for templates using query params
    path('ajax/warehouse/stock/', ajax_warehouse_stock, name='ajax_warehouse_stock'),

    # AJAX API для матеріалів
    path('ajax/materials/', ajax_materials, name='ajax_materials'),

    # ==============================================================================
    # РОБОЧИЙ СТІЛ МЕНЕДЖЕРА (MANAGER)
    # ==============================================================================
    path('manager/dashboard/', manager.manager_dashboard, name='manager_dashboard'),
    # Список заявок (Order List)
    path('manager/orders/', orders.order_list, name='order_list'),
    path('manager/order/<int:pk>/', manager.manager_order_detail, name='manager_order_detail'),
    
    # Канонічні дії менеджера для створення/редагування заявок (Order + Items)
    path('order/create/', orders.create_order, name='create_order'),
    # (B) Відновлено маршрут edit_order
    path('order/<int:pk>/edit/', orders.edit_order, name='edit_order'),
    path('order/<int:pk>/delete/', orders.delete_order, name='delete_order'),
    
    # Обробка заявки (погодження/відхилення)
    path('manager/order/<int:pk>/process/', manager.manager_process_order, name='manager_process_order'),
    
    # Split Order (Розділення заявки)
    path('manager/order/<int:pk>/split/', manager.split_order, name='split_order'),

    # ==============================================================================
    # ЛОГІСТИКА
    # ==============================================================================
    # (C) Логістика: Канонічний маршрут
    path('logistics/', orders.logistics_monitor, name='logistics_monitor'),
    # (C) Логістика: Alias з іншим URL для усунення помилки NoReverseMatch та дублювання URL
    path('logistics/dashboard/', orders.logistics_monitor, name='logistics_dashboard'),
    
    path('order/<int:pk>/mark_shipped/', orders.mark_order_shipped, name='mark_order_shipped'),
    path('order/<int:pk>/confirm_receipt/', orders.confirm_receipt, name='confirm_receipt'),

    # ==============================================================================
    # СКЛАД (TRANSACTIONS)
    # ==============================================================================
    path('warehouse/<int:pk>/', transactions.warehouse_detail, name='warehouse_detail'),
    path('transaction/<int:pk>/', transactions.transaction_detail, name='transaction_detail'),
    path('transaction/add/', transactions.add_transaction, name='add_transaction'),
    
    # Переміщення (Transfers)
    path('transfer/create/', transactions.create_transfer_view, name='create_transfer'), # Використовує alias у transactions.py
    # Alias для сумісності з шаблонами/тестами (add_transfer)
    path('transfer/add/', transactions.create_transfer_view, name='add_transfer'),

    # ==============================================================================
    # ПРОРАБ (FOREMAN)
    # ==============================================================================
    path('foreman/storage/', foreman.foreman_storage_view, name='foreman_storage'),
    path('foreman/order/<int:pk>/', foreman.foreman_order_detail, name='foreman_order_detail'),
    path('foreman/history/writeoffs/', foreman.writeoff_history_view, name='writeoff_history'),
    path('foreman/history/deliveries/', foreman.delivery_history_view, name='delivery_history'),

    # ==============================================================================
    # МАТЕРІАЛИ (CATALOG)
    # ==============================================================================
    path('materials/', general.material_list, name='material_list'),
    path('materials/<int:pk>/', general.material_detail, name='material_detail'),

    # ==============================================================================
    # ЗВІТИ (REPORTS)
    # ==============================================================================
    path('reports/', reports.reports_dashboard, name='reports_dashboard'),
    path('reports/stock/balance/', reports.stock_balance_view, name='stock_balance_report'), # Alias
    path('reports/stock/excel/', reports.export_stock_report, name='export_stock_report'), # Alias
    
    path('reports/period/', reports.period_report, name='period_report'),
    path('reports/writeoffs/', reports.writeoff_report, name='writeoff_report'),
    
    # Фінанси та Планування
    path('reports/planning/', reports.planning_report, name='planning_report'),
    path('reports/suppliers/', reports.suppliers_rating, name='suppliers_rating'),
    path('reports/financial/', reports.savings_report, name='financial_report'), # Alias
    path('reports/problems/', reports.problem_areas, name='problem_areas'),
    path('reports/comparison/', reports.objects_comparison, name='objects_comparison'),
    
    # Логістика та Історія
    path('reports/transfers/', reports.transfer_journal, name='transfer_journal'),
    path('reports/transfers/analytics/', reports.transfer_analytics, name='transfer_analytics'),
    path('reports/movement/', reports.movement_history, name='movement_history'),
    path('reports/procurement/', reports.procurement_journal, name='procurement_journal'),
    path('reports/audit/', reports.global_audit_log, name='global_audit_log'),
    
    # SAP Analytics
    path('reports/rebar/', rebar_analytics, name='rebar_analytics'),
    path('reports/concrete/', concrete_analytics, name='concrete_analytics'),
    path('reports/mechanisms/', mechanisms_analytics, name='mechanisms_analytics'),
    path('dashboard/project/', project_dashboard, name='project_dashboard'),
    
    # ==============================================================================
    # ПРОФІЛЬ
    # ==============================================================================
    path('profile/', general.profile_view, name='profile'),
    path('profile/switch-wh/<int:pk>/', general.switch_active_warehouse, name='switch_active_warehouse'),
    path('profile/change-password/', general.change_password_view, name='change_password'),
    
    # Друк
    path('order/<int:pk>/print/', orders.print_order_pdf, name='print_order_pdf'),
]