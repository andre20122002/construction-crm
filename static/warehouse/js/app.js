"use strict";

/**
 * BudSklad ERP - Global JavaScript Helpers
 * * Цей файл містить спільні утиліти для роботи з даними,
 * які використовуються на різних сторінках проекту.
 */

window.App = {
    
    /**
     * Безпечно зчитує та парсить JSON дані з тегу <script id="...">
     * Використовується для отримання даних, переданих з Django view через json_script.
     * * @param {string} id - ID HTML елемента скрипта
     * @returns {any|null} - Розпарсений об'єкт або null, якщо елемент не знайдено або помилка парсингу
     */
    readJsonScript: function(id) {
        const element = document.getElementById(id);
        
        if (!element) {
            console.warn(`[App] JSON script element with id "${id}" not found.`);
            return null;
        }
        
        try {
            const content = element.textContent;
            if (!content || content.trim() === "") return null;
            return JSON.parse(content);
        } catch (error) {
            console.error(`[App] Failed to parse JSON from element "${id}":`, error);
            return null;
        }
    },

    /**
     * Форматує рядок кількості для відображення.
     * Важливо: НЕ перетворює в float, щоб зберегти точність Decimal з бекенду.
     * * @param {string|number} qtyStr - Значення кількості (зазвичай рядок з бекенду)
     * @returns {string} - Відформатований рядок
     */
    formatQty: function(qtyStr) {
        if (qtyStr === null || qtyStr === undefined || qtyStr === "") {
            return "0";
        }
        
        // Перетворюємо в рядок, якщо це число
        let value = String(qtyStr);
        
        // Нормалізація: замінюємо кому на крапку (якщо раптом прилетіло з локалізованого інпуту)
        value = value.replace(',', '.');
        
        // Видаляємо пробіли (якщо це форматований рядок "1 000")
        value = value.replace(/\s/g, '');
        
        return value;
    }

};