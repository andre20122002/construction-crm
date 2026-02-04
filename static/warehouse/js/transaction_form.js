"use strict";

/**
 * transaction_form.js
 * Логіка для форми створення транзакції.
 * Відповідає за:
 * 1. Відображення/приховування блоку етапів будівництва залежно від типу операції.
 * 2. AJAX-завантаження списку етапів при зміні складу.
 */

window.TransactionForm = {
    _inited: false,

    init: function() {
        if (this._inited) return; // Захист від повторної ініціалізації
        
        this.initStageToggle();
        this.initStageLoading();
        
        this._inited = true;
    },

    /**
     * Керує видимістю блоку #construction-details.
     * Блок показується тільки якщо вибрано тип 'OUT' (Списання на роботи).
     */
    initStageToggle: function() {
        const typeRadios = document.querySelectorAll('input[name="transaction_type"]');
        const constructionBlock = document.getElementById('construction-details');

        // Якщо елементів немає на сторінці - виходимо
        if (!constructionBlock) return;

        const toggle = () => {
            const selectedRadio = document.querySelector('input[name="transaction_type"]:checked');
            if (selectedRadio) {
                if (selectedRadio.value === 'OUT') {
                    constructionBlock.style.display = 'block';
                } else {
                    constructionBlock.style.display = 'none';
                }
            }
        };

        // Підписуємось на зміни радіокнопок
        typeRadios.forEach(radio => {
            radio.addEventListener('change', toggle);
        });
        
        // Встановлюємо початковий стан
        toggle();
    },

    /**
     * Завантажує етапи будівництва (Stages) через AJAX при зміні складу.
     * URL для запиту має бути в атрибуті data-stages-url форми.
     */
    initStageLoading: function() {
        const warehouseSelect = document.getElementById('id_warehouse');
        const stageSelect = document.getElementById('id_stage');
        const form = document.getElementById('transactionForm');
        
        // Отримуємо URL з data-атрибуту форми (має бути доданий у шаблоні)
        const stagesUrl = form ? form.getAttribute('data-stages-url') : null;

        // Перевірка на наявність всіх необхідних елементів
        if (!warehouseSelect || !stageSelect || !stagesUrl) return;

        const loadStages = (warehouseId) => {
            // Очищаємо поточний список, залишаючи дефолтну опцію
            stageSelect.innerHTML = '<option value="">---------</option>';

            if (!warehouseId) return;

            fetch(`${stagesUrl}?warehouse_id=${warehouseId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    data.forEach(item => {
                        const option = document.createElement('option');
                        option.value = item.id;
                        option.textContent = item.name;
                        stageSelect.appendChild(option);
                    });
                })
                .catch(err => console.error('Error loading stages:', err));
        };

        // Слухаємо подію зміни складу
        warehouseSelect.addEventListener('change', function() {
            loadStages(this.value);
        });

        // Якщо склад вже вибрано при завантаженні (наприклад, при помилці форми або редагуванні)
        // завантажуємо етапи одразу
        if (warehouseSelect.value) {
            loadStages(warehouseSelect.value);
        }
    }
};

// Ініціалізація модуля при завантаженні DOM
document.addEventListener('DOMContentLoaded', function() {
    if (window.TransactionForm) {
        window.TransactionForm.init();
    }
});