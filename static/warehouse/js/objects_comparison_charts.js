"use strict";

/**
 * objects_comparison_charts.js
 * Візуалізація порівняння бюджетів та витрат по об'єктах.
 */

window.ObjectsComparisonCharts = {
    
    init: function() {
        this.renderChart();
    },

    getData: function(id) {
        return window.App.readJsonScript(id) || [];
    },

    renderChart: function() {
        const ctx = document.getElementById('comparisonChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="comparison"]');
        const rawData = this.getData('comparison-data');

        // Перевірка наявності даних
        if (!rawData || rawData.length === 0) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // Підготовка даних для Chart.js
        const labels = rawData.map(item => item.name);
        const budgetData = rawData.map(item => Number(item.budget));
        const spentData = rawData.map(item => Number(item.spent));

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Фактичні витрати',
                        data: spentData,
                        backgroundColor: '#dc3545', // Червоний (Danger)
                        borderColor: '#b02a37',
                        borderWidth: 1,
                        borderRadius: 4,
                        order: 1 // Малюється поверх бюджету
                    },
                    {
                        label: 'Бюджетний ліміт',
                        data: budgetData,
                        // Напівпрозорий зелений, щоб було видно накладання
                        backgroundColor: 'rgba(25, 135, 84, 0.2)', 
                        borderColor: '#198754',
                        borderWidth: 2,
                        borderRadius: 4,
                        barPercentage: 1.1, // Трохи ширший за стовпчик витрат
                        order: 2 // Малюється позаду
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { 
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString('uk-UA') + ' ₴';
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toLocaleString('uk-UA') + ' ₴';
                                }
                                return label;
                            },
                            afterBody: function(context) {
                                // Додаткова інформація про залишок
                                const idx = context[0].dataIndex;
                                const b = budgetData[idx];
                                const s = spentData[idx];
                                const diff = b - s;
                                return `----------------\nЗалишок: ${diff.toLocaleString('uk-UA')} ₴`;
                            }
                        }
                    }
                }
            }
        });
    }
};