"use strict";

/**
 * reports_charts.js
 * Логіка побудови графіків для фінансового звіту.
 * Використовує Chart.js та дані, передані через json_script.
 */

window.ReportsCharts = {
    
    init: function() {
        this.renderWarehouseChart();
        this.renderTrendChart();
    },

    /**
     * Графік 1: Витрати по об'єктах (Doughnut)
     */
    renderWarehouseChart: function() {
        const ctx = document.getElementById('whChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="wh"]');
        
        // Отримуємо дані через глобальний хелпер
        const labels = window.App.readJsonScript('wh-labels');
        const dataStr = window.App.readJsonScript('wh-data');

        // Перевірка наявності даних
        // Вважаємо, що даних немає, якщо масив порожній або сума нульова
        // Використовуємо Number() замість parseFloat() для уніфікації стилю
        const hasData = dataStr && dataStr.length > 0 && dataStr.some(val => Number(val) > 0);

        if (!hasData) {
            // Ховаємо canvas і показуємо повідомлення
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // Конвертуємо рядки (Decimal) в числа для Chart.js
        const dataNumbers = dataStr.map(val => Number(val));

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: dataNumbers,
                    // Спокійні кольори з палітри Bootstrap 5
                    backgroundColor: [
                        '#0d6efd', // Primary
                        '#198754', // Success
                        '#ffc107', // Warning
                        '#0dcaf0', // Info
                        '#dc3545', // Danger
                        '#6610f2', // Indigo
                        '#d63384', // Pink
                        '#fd7e14', // Orange
                        '#adb5bd'  // Gray
                    ],
                    borderWidth: 1
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
     * Графік 2: Динаміка витрат по місяцях (Line)
     */
    renderTrendChart: function() {
        const ctx = document.getElementById('trendChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="trend"]');

        const labels = window.App.readJsonScript('month-labels');
        const dataStr = window.App.readJsonScript('month-data');

        // Використовуємо Number() замість parseFloat()
        const hasData = dataStr && dataStr.length > 0 && dataStr.some(val => Number(val) > 0);

        if (!hasData) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // Конвертуємо рядки в числа
        const dataNumbers = dataStr.map(val => Number(val));

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Витрати',
                    data: dataNumbers,
                    borderColor: '#198754', // Зелений графік
                    backgroundColor: 'rgba(25, 135, 84, 0.1)', // Прозора заливка
                    borderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3, // Плавні лінії
                    fill: true
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
                        display: false // Ховаємо легенду, бо лінія одна
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