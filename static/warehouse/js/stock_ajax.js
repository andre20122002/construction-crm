/**
 * stock_ajax.js
 * Скрипт для динамічної перевірки залишків на складі.
 *
 * Використання:
 * Додайте атрибут data-stock-validate до тегу <form>.
 * Налаштуйте селектори через data-атрибути (опціонально):
 * - data-warehouse-select="#id_warehouse"
 * - data-material-select="#id_material"
 * - data-qty-input="#id_quantity"
 * - data-hint-target="#stock-hint"
 */

(function() {
    'use strict';

    /**
     * Парсить рядок з десятковим числом в ціле число (помножене на scale).
     * Це дозволяє порівнювати кількості без float-артефактів.
     * Приклад (scale=1000): "1.5" -> 1500, "10.000" -> 10000
     *
     * @param {string} valueStr - Рядок з числом
     * @param {number} scale - Множник (1000 для 3 знаків)
     * @returns {number} - Ціле число
     */
    function parseDecimalToInt(valueStr, scale = 1000) {
        if (!valueStr) return 0;
        
        // Нормалізація: прибираємо пробіли, замінюємо кому на крапку
        let s = String(valueStr).replace(/\s/g, '').replace(',', '.');
        
        // Перевірка на валідність (хоча б цифри)
        if (!s || isNaN(Number(s))) return 0;

        const parts = s.split('.');
        const whole = parseInt(parts[0] || '0', 10);
        let fraction = parts[1] || '';

        // Визначаємо кількість нулів у scale (напр. 1000 -> 3)
        // Для спрощення припускаємо scale як ступінь 10 (10, 100, 1000)
        const precision = Math.log10(scale);

        // Обрізаємо або доповнюємо дробову частину нулями
        if (fraction.length > precision) {
            fraction = fraction.substring(0, precision);
        } else {
            while (fraction.length < precision) {
                fraction += '0';
            }
        }

        // Об'єднуємо і парсимо як ціле (еквівалент множення, але без мат. операцій float)
        // Враховуємо знак мінус
        const isNegative = s.startsWith('-');
        const result = parseInt((isNegative ? '-' : '') + Math.abs(whole) + fraction, 10);
        
        return result;
    }

    class StockValidator {
        constructor(form) {
            this.form = form;
            this.cache = {}; // Кеш для зберігання даних: { warehouseId: responseData }

            // 1. Зчитуємо налаштування з data-атрибутів або беремо дефолтні (Django IDs)
            this.config = {
                warehouseSelector: form.getAttribute('data-warehouse-select') || '#id_warehouse',
                materialSelector: form.getAttribute('data-material-select') || '#id_material',
                qtySelector: form.getAttribute('data-qty-input') || '#id_quantity',
                submitSelector: form.getAttribute('data-submit-button') || 'button[type="submit"]',
                hintSelector: form.getAttribute('data-hint-target') || '#stockHint' // Елемент для виводу тексту
            };

            // 2. Знаходимо елементи
            this.elWarehouse = form.querySelector(this.config.warehouseSelector);
            this.elMaterial = form.querySelector(this.config.materialSelector);
            this.elQty = form.querySelector(this.config.qtySelector);
            this.elSubmit = form.querySelector(this.config.submitSelector);
            this.elHint = form.querySelector(this.config.hintSelector);

            // Якщо немає селектора складу — скрипт не може працювати
            if (!this.elWarehouse) return;

            // 3. Підписуємось на події
            this.bindEvents();

            // 4. Ініціалізація (якщо форма відкрилась з вибраними значеннями)
            if (this.elWarehouse.value) {
                this.fetchStock(this.elWarehouse.value);
            }
        }

        bindEvents() {
            // Зміна складу -> завантажити нові дані
            this.elWarehouse.addEventListener('change', (e) => {
                this.fetchStock(e.target.value);
            });

            // Зміна матеріалу -> перевірити залишок
            if (this.elMaterial) {
                this.elMaterial.addEventListener('change', () => this.validate());
            }

            // Ввід кількості -> перевірити залишок
            if (this.elQty) {
                this.elQty.addEventListener('input', () => this.validate());
            }
        }

        fetchStock(warehouseId) {
            if (!warehouseId) {
                this.currentData = null;
                this.updateUI(null);
                return;
            }

            // Перевірка кешу
            if (this.cache[warehouseId]) {
                this.currentData = this.cache[warehouseId];
                this.validate();
                return;
            }

            // Індикація завантаження
            if (this.elHint) {
                this.elHint.style.display = 'block';
                this.elHint.textContent = 'Завантаження залишків...';
                this.elHint.className = 'form-text text-muted';
            }
            if (this.elSubmit) this.elSubmit.disabled = true;

            // AJAX запит на canonical endpoint
            fetch(`/ajax/warehouse/${warehouseId}/stock/`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    // Зберігаємо в кеш
                    this.cache[warehouseId] = data;
                    this.currentData = data;
                    this.validate();
                })
                .catch(error => {
                    console.error('Error fetching stock:', error);
                    if (this.elHint) {
                        this.elHint.textContent = 'Помилка отримання даних';
                        this.elHint.className = 'form-text text-danger';
                    }
                    // ЗАХИСТ: Розблокуємо кнопку, щоб не блокувати роботу при збої API
                    if (this.elSubmit) this.elSubmit.disabled = false;
                });
        }

        validate() {
            // Скидаємо стан кнопки (розблоковуємо за замовчуванням)
            if (this.elSubmit) this.elSubmit.disabled = false;

            if (!this.currentData || !this.elMaterial) {
                this.updateUI(null);
                return;
            }

            const matId = this.elMaterial.value;
            if (!matId) {
                this.updateUI(null);
                return;
            }

            // Отримуємо дані про матеріал
            const stockMap = this.currentData.stock || {};
            const unitsMap = this.currentData.units || {};

            // 1. Отримуємо доступну кількість (РЯДОК)
            let availableStr = '0';
            let unit = '';
            
            if (Object.prototype.hasOwnProperty.call(stockMap, matId)) {
                availableStr = String(stockMap[matId]); // Це Decimal-рядок з бекенду
                unit = unitsMap[matId] || '';
            }

            // 2. Отримуємо введену кількість (РЯДОК)
            let requestedStr = '0';
            if (this.elQty && this.elQty.value) {
                requestedStr = this.elQty.value;
            }

            // 3. Парсимо в цілі числа для порівняння (scale=1000)
            const availableInt = parseDecimalToInt(availableStr, 1000);
            const requestedInt = parseDecimalToInt(requestedStr, 1000);

            // Оновлюємо UI та валідуємо, передаючи рядки для відображення та інти для логіки
            this.updateUI(availableStr, unit, availableInt, requestedInt);
        }

        updateUI(availableStr, unit = '', availableInt = 0, requestedInt = 0) {
            if (!this.elHint) return;

            if (availableStr === null) {
                this.elHint.style.display = 'none';
                this.elHint.textContent = '';
                return;
            }

            this.elHint.style.display = 'block';

            if (availableInt > 0) {
                // Товар є на складі
                // Виводимо рядок як є, не перетворюючи у float
                let message = `На складі: ${availableStr} ${unit}`;
                let cssClass = 'form-text text-success fw-bold';

                // Перевірка на перевищення ліміту (порівняння цілих чисел)
                if (requestedInt > availableInt) {
                    message += ` (Недостатньо!)`;
                    cssClass = 'form-text text-danger fw-bold';
                    
                    // Блокуємо кнопку
                    if (this.elSubmit) this.elSubmit.disabled = true;
                }

                this.elHint.textContent = message;
                this.elHint.className = cssClass;
            } else {
                // Товару немає (availableInt <= 0)
                this.elHint.textContent = 'Немає на складі';
                this.elHint.className = 'form-text text-danger fw-bold';
                
                // Якщо намагаються списати (requestedInt > 0) те, чого немає - блокуємо
                if (requestedInt > 0 && this.elSubmit) {
                    this.elSubmit.disabled = true;
                }
            }
        }
    }

    // Автоматична ініціалізація для форм з атрибутом data-stock-validate
    document.addEventListener('DOMContentLoaded', () => {
        const forms = document.querySelectorAll('form[data-stock-validate]');
        forms.forEach(form => new StockValidator(form));
    });

})();