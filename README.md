# BudSklad ERP

**Система управління закупівлями та складським обліком для будівельних компаній**

BudSklad — це ERP-система, розроблена для автоматизації процесів закупівель, складського обліку та контролю витрат матеріалів на будівельних об'єктах. Система забезпечує повний цикл від створення заявки на матеріали до їх списання на конкретні етапи будівництва.

---

## Ключові можливості

### Управління заявками
- Створення заявок на закупівлю матеріалів
- Багаторівневе погодження (прораб → менеджер)
- Розділення заявок по постачальниках
- Відстеження статусів: нова → погоджена → в закупівлі → в дорозі → прийнята
- Прикріплення фото та документів до заявок

### Складський облік
- Облік залишків по кожному складу/об'єкту
- Прихід матеріалів (закупівля, коригування)
- Списання на роботи (витрата, втрати)
- Переміщення між складами
- Автоматичний розрахунок середньозваженої ціни

### Логістика
- Моніторинг вантажів в реальному часі
- Дані водія та транспорту
- Друк ТТН (товарно-транспортних накладних)
- Підтвердження прийому з фото

### Аналітика та звіти
- Залишки по складах
- Оборотна відомість
- Звіт по списаннях та втратах
- Рейтинг постачальників
- Аналітика витрат по етапах будівництва
- Фінансові звіти
- Експорт в Excel

### Безпека
- Розмежування доступу по ролях
- Контроль доступу до складів
- Аудит всіх операцій (хто, коли, що змінив)
- Rate limiting для захисту від атак

---

## Ролі користувачів

### Менеджер (is_staff=True)
- Доступ до всіх складів та заявок
- Погодження/відхилення заявок
- Управління довідниками (матеріали, постачальники)
- Перегляд всіх звітів та аналітики
- Контроль бюджетів об'єктів

### Прораб (звичайний користувач)
- Доступ тільки до призначених об'єктів
- Створення заявок на матеріали
- Підтвердження прийому товарів
- Списання матеріалів на роботи
- Мобільний інтерфейс

---

## Технічний стек

| Компонент | Технологія |
|-----------|------------|
| Backend | Django 5.0, Python 3.11+ |
| Database | PostgreSQL |
| Frontend | Bootstrap 5, JavaScript |
| Static Files | WhiteNoise |
| WSGI Server | Gunicorn |
| Authentication | Django Auth + Custom Decorators |

---

## Архітектура

```
construction_crm/          # Django project configuration
├── settings.py            # Environment-aware settings
├── urls.py                # Root URL routing + health check
└── wsgi.py                # WSGI application

warehouse/                 # Main application
├── models.py              # Data models (Order, Material, Transaction, etc.)
├── forms.py               # Form classes with validation
├── decorators.py          # @staff_required, @rate_limit
├── services/
│   └── inventory.py       # Business logic (create_incoming, create_writeoff, etc.)
├── views/
│   ├── general.py         # Dashboard, profile, common views
│   ├── manager.py         # Manager-specific views
│   ├── orders.py          # Order CRUD operations
│   ├── transactions.py    # Inventory transactions
│   ├── reports.py         # Reports and analytics
│   └── utils.py           # Helper functions, AJAX endpoints
└── templates/             # HTML templates (44 files)
```

---

## Моделі даних

```
Warehouse (Склад/Об'єкт)
    ├── Materials (через Transaction)
    ├── Orders (Заявки)
    ├── ConstructionStages (Етапи будівництва)
    └── Users (через UserProfile.warehouses)

Order (Заявка)
    ├── OrderItems (Позиції заявки)
    ├── OrderComments (Коментарі/чат)
    └── Transactions (Створені при прийомі)

Material (Матеріал)
    ├── Category (Категорія)
    ├── SupplierPrices (Ціни постачальників)
    └── Transactions (Історія руху)

Transaction (Транзакція)
    ├── Types: IN, OUT, LOSS
    ├── transfer_group_id (для переміщень)
    └── AuditLog (Автоматичний аудит)
```

---

## Швидкий старт

```bash
# 1. Клонування
git clone https://github.com/andre20122002/construction-crm.git
cd construction-crm

# 2. Віртуальне оточення
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Залежності
pip install -r requirements.txt

# 4. Конфігурація
cp .env.example .env
# Відредагуйте .env: DB_PASSWORD, DJANGO_SECRET_KEY

# 5. База даних
python manage.py migrate
python manage.py seed_data  # Демо-дані (опційно)

# 6. Запуск
python manage.py runserver
```

Відкрийте http://127.0.0.1:8000

---

## Production Deployment

### Вимоги
- Python 3.11+
- PostgreSQL 14+
- Redis (для кешування, опційно)

### Налаштування .env
```bash
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generate-strong-key>
DJANGO_ALLOWED_HOSTS=yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com

DB_PASSWORD=<strong-password>

# Email (опційно)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=app-password
```

### Запуск
```bash
python manage.py collectstatic --noinput
gunicorn construction_crm.wsgi:application --bind 0.0.0.0:8000
```

### Health Check
```bash
curl http://localhost:8000/health/
# {"status": "healthy", "database": "ok"}
```

---

## API Endpoints

| Endpoint | Метод | Опис |
|----------|-------|------|
| `/health/` | GET | Health check для load balancers |
| `/ajax/materials/` | GET | Пошук матеріалів (autocomplete) |
| `/ajax/warehouse/<id>/stock/` | GET | Залишки по складу |
| `/ajax/load-stages/` | GET | Етапи будівництва |

---

## Тестування

```bash
# Всі тести
python manage.py test

# Конкретний клас
python manage.py test warehouse.tests.InventoryServiceTests
```

Покриття: 26 тестів (inventory, transfers, access control, AJAX)

---

## Безпека

- **Authentication**: Django session-based
- **Authorization**: Role-based (is_staff) + warehouse-level access
- **CSRF**: Enabled with trusted origins
- **XSS**: Django template auto-escaping
- **SQL Injection**: ORM-only, no raw queries
- **Rate Limiting**: 30-120 req/min on AJAX endpoints
- **File Upload**: 10MB limit, extension whitelist
- **Audit Trail**: Full logging with IP tracking

---

## Ліцензія

Proprietary. All rights reserved.

---

## Контакти

- **Author**: Andrey
- **Repository**: https://github.com/andre20122002/construction-crm
