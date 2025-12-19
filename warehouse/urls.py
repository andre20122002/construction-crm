from django.urls import path
from . import views

urlpatterns = [
    # --- ГОЛОВНА ---
    path('', views.index, name='index'),
    
    # --- AJAX (API) ---
    path('ajax/check_duplicates/', views.check_order_duplicates, name='check_order_duplicates'),

    # --- РОБОЧИЙ СТІЛ МЕНЕДЖЕРА ---
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/order/<int:pk>/', views.manager_order_detail, name='manager_order_detail'),
    path('manager/order/<int:pk>/po/', views.create_po, name='create_po'),
    path('manager/order/<int:pk>/transfer/', views.transfer_from_stock, name='transfer_from_stock'),

    # --- КАБІНЕТ ПРОРАБА ---
    path('my/order/<int:pk>/', views.foreman_order_detail, name='foreman_order_detail'),
    path('my/order/<int:pk>/edit/', views.foreman_edit_order, name='foreman_edit_order'),
    path('my/deliveries/', views.delivery_history_view, name='delivery_history'),
    path('my/writeoffs/', views.writeoff_history_view, name='writeoff_history'),
    path('my/storage/', views.foreman_storage_view, name='foreman_storage'),

    # --- СКЛАДИ ТА МАТЕРІАЛИ ---
    path('warehouse/<int:pk>/', views.warehouse_detail, name='warehouse_detail'),
    path('materials/', views.material_list, name='material_list'),
    path('material/<int:pk>/', views.material_detail, name='material_detail'),
    
    # --- МОДУЛІ ---
    path('logistics/', views.logistics_dashboard, name='logistics_dashboard'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('report/period/', views.period_report, name='period_report'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/switch/<int:pk>/', views.switch_active_warehouse, name='switch_active_warehouse'),

    # --- ОПЕРАЦІЇ ---
    path('order/create/', views.create_order, name='create_order'),
    path('order/receipt/<int:pk>/', views.confirm_receipt, name='confirm_receipt'),
    path('transaction/add/', views.add_transaction, name='add_transaction'),
    path('transaction/<int:pk>/', views.transaction_detail, name='transaction_detail'),

    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:pk>/approve/', views.approve_order, name='approve_order'),
    path('orders/<int:pk>/reject/', views.reject_order, name='reject_order'),
    path('orders/<int:pk>/confirm/', views.confirm_draft, name='confirm_draft'),
    path('orders/<int:pk>/delete/', views.delete_order, name='delete_order'),
    
    # --- ЗВІТИ ТА ДРУК ---
    path('export/excel/', views.export_stock_report, name='export_stock_report'),
    path('orders/<int:pk>/pdf/', views.print_order_pdf, name='print_order_pdf'),
    path('reports/procurement/', views.procurement_journal, name='procurement_journal'),
    path('reports/financial/', views.financial_report, name='financial_report'),
    path('reports/planning/', views.planning_report, name='planning_report'),
    path('reports/stock/', views.stock_balance_report, name='stock_balance_report'),
    path('reports/movement/', views.movement_history, name='movement_history'), 
    path('reports/writeoff/', views.writeoff_report, name='writeoff_report'),
    path('reports/transfers/', views.transfer_journal, name='transfer_journal'),
    path('reports/transfers/analytics/', views.transfer_analytics, name='transfer_analytics'),
    path('reports/comparison/', views.objects_comparison, name='objects_comparison'),
    path('reports/suppliers/', views.suppliers_rating, name='suppliers_rating'),
    path('reports/savings/', views.savings_report, name='savings_report'),
    path('reports/problems/', views.problem_areas, name='problem_areas'),
    
    # 👇 НОВИЙ МАРШРУТ 👇
    path('reports/audit/', views.global_audit_log, name='global_audit_log'),
    
    path('orders/<int:pk>/mark_shipped/', views.mark_shipped, name='mark_shipped'),
    path('manager/order/<int:pk>/split/', views.split_order_view, name='split_order'),
]