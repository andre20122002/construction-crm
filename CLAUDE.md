# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BudSklad is a Django-based ERP system for construction companies focused on procurement, warehouse management, and inventory control. The codebase uses mixed Ukrainian/English naming conventions.

## Development Commands

```bash
# Setup virtual environment and install dependencies
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# Database setup
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data  # Populate demo data

# Run development server
python manage.py runserver

# Run tests
python manage.py test
python manage.py test warehouse.tests.TestClassName  # Single test class

# Production deployment
python manage.py collectstatic --noinput
gunicorn construction_crm.wsgi:application --bind 0.0.0.0:8000
```

## Architecture

### Project Structure
- `construction_crm/` - Django project configuration (settings, root URLs, WSGI)
- `warehouse/` - Main Django app containing all business logic
- `static/` - CSS/JS frontend assets
- `media/` - User-uploaded files

### Warehouse App Organization
The `warehouse/` app uses modular views split by feature area:

- `views/general.py` - Core dashboard, material management, user profiles
- `views/manager.py` - Manager dashboard, order processing, split orders
- `views/orders.py` - Order creation, logistics monitoring, shipping
- `views/transactions.py` - Warehouse transactions, transfers, writeoffs
- `views/reports.py` - Comprehensive reporting (20+ report types)
- `views/foreman.py` - Foreman/site worker interface
- `views/concrete_analytics.py`, `rebar_analytics.py`, `mechanisms_analytics.py` - Material-specific analytics
- `views/utils.py` - Helper functions and utilities
- `services/inventory.py` - Core inventory management business logic

### Key Models (`warehouse/models.py`)
- `Warehouse` - Construction sites with budget limits
- `Material` / `Category` - Materials with pricing and inventory limits
- `Supplier` / `SupplierPrice` - Supplier management with price tracking
- `Transaction` - Inventory movements (IN/OUT/LOSS transaction types)
- `Order` / `OrderItem` - Purchase orders with approval workflow
- `ConstructionStage` / `StageLimit` - Project phases with budget limits
- `AuditLog` - Change tracking for compliance

### User Roles
1. **Manager** (`is_staff=True`) - Creates/approves orders, manages budgets, views reports
2. **Foreman** (regular user) - Views assigned orders, confirms receipts, records usage

## Critical Implementation Details

### Decimal Precision
All financial and quantity calculations use precise decimals:
- Quantities: 3 decimal places
- Prices: 2 decimal places
Always use `Decimal` type, never floats, for inventory and financial calculations.

### URL Routes
135+ routes defined in `warehouse/urls.py`, organized by:
- Manager routes: `/manager/...`
- Logistics routes: `/logistics/...`
- Foreman routes: `/foreman/...`
- Report routes: `/reports/...`
- AJAX endpoints for dynamic content

### Environment Configuration
The `.env` file controls database connection (PostgreSQL), debug mode, allowed hosts, and security settings. See `construction_crm/settings.py` for environment-aware configuration.

## Testing

Tests are in `warehouse/tests.py` using Django's TestCase framework. The test suite covers inventory operations, transfers, and order workflows with attention to decimal precision.
