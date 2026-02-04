"use strict";

/**
 * suppliers_charts.js
 * Логіка для сторінки рейтингу постачальників.
 * Обробляє прогрес-бари та потенційні графіки в майбутньому.
 */

window.SuppliersCharts = {
    
    init: function() {
        this.initProgressBars();
    },

    /**
     * Ініціалізація прогрес-барів надійності.
     * Замінює кому на крапку для коректного CSS width.
     */
    initProgressBars: function() {
        document.querySelectorAll('.progress-bar[data-width]').forEach(bar => {
            let widthAttr = bar.getAttribute('data-width');
            if (widthAttr) {
                // Замінюємо кому на крапку (якщо локалізація вивела число з комою)
                let width = widthAttr.replace(',', '.');
                bar.style.width = width + '%';
            }
        });
    }
};