"use strict";

/**
 * financial_charts.js
 * Логіка побудови графіків для фінансового звіту.
 */

window.FinancialCharts = {
    
    init: function() {
        this.renderSupplierChart();
        this.renderTrendChart();
    },

    /**
     * Helper для отримання даних.
     * Використовує window.App.readJsonScript, якщо він доступний.
     */
    getData: function(id) {
        if (window.App && window.App.readJsonScript) {
            return window.App.readJsonScript(id) || [];
        }
        // Fallback, якщо App.js не підключено
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : [];
    },

    /**
     * Графік 1: Топ постачальників (Doughnut)
     */
    renderSupplierChart: function() {
        const ctx = document.getElementById('suppliersChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="sup"]');

        const labels = this.getData('sup-labels');
        const dataStr = this.getData('sup-data');

        // Перевірка наявності даних
        const hasData = labels && labels.length > 0 && dataStr && dataStr.length > 0 && dataStr.some(val => Number(val) > 0);

        if (!hasData) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // Конвертуємо дані в числа
        const dataNumbers = dataStr.map(val => Number(val));

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: dataNumbers,
                    backgroundColor: [
                        '#0d6efd', // Primary
                        '#ffc107', // Warning
                        '#20c997', // Teal
                        '#6f42c1', // Purple
                        '#fd7e14', // Orange
                        '#adb5bd'  // Gray
                    ],
                    borderWidth: 1,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { boxWidth: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                const value = context.parsed;
                                label += value.toLocaleString('uk-UA', { minimumFractionDigits: 2 }) + ' ₴';
                                return label;
                            }
                        }
                    }
                }
            }
        });
    },

    /**
     * Графік 2: Динаміка витрат (Line)
     */
    renderTrendChart: function() {
        const ctx = document.getElementById('trendChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="trend"]');

        const labels = this.getData('date-labels');
        const dataStr = this.getData('date-values');

        // Перевірка наявності даних
        const hasData = labels && labels.length > 0 && dataStr && dataStr.length > 0 && dataStr.some(val => Number(val) > 0);

        if (!hasData) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // Конвертуємо дані в числа
        const dataNumbers = dataStr.map(val => Number(val));

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Витрати (грн)',
                    data: dataNumbers,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            borderDash: [2, 4],
                            color: '#e9ecef'
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString('uk-UA') + ' ₴';
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y.toLocaleString('uk-UA', { minimumFractionDigits: 2 }) + ' ₴';
                            }
                        }
                    }
                }
            }
        });
    }
};