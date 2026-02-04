"use strict";

/**
 * rebar_charts.js
 * Логіка побудови графіків для звіту по арматурі.
 */

window.RebarCharts = {
    
    init: function() {
        this.renderChart();
    },

    getData: function(id) {
        return window.App.readJsonScript(id) || [];
    },

    renderChart: function() {
        const ctx = document.getElementById('rebarChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="rebar"]');
        
        const labels = this.getData('chart-labels');
        const planDataRaw = this.getData('chart-plan');
        const factDataRaw = this.getData('chart-fact');

        // Перевірка наявності даних (якщо лейблів немає або план пустий)
        const hasData = labels.length > 0 && planDataRaw.some(val => Number(val) > 0);

        if (!hasData) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // 🔥 FIX: Конвертуємо Decimal-рядки в числа
        const planData = planDataRaw.map(val => Number(val));
        const factData = factDataRaw.map(val => Number(val));

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'План (т)',
                        data: planData,
                        backgroundColor: '#e9ecef',
                        borderColor: '#ced4da',
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.6,
                        categoryPercentage: 0.8
                    },
                    {
                        label: 'Факт (т)',
                        data: factData,
                        backgroundColor: '#6c757d', // Сірий для металу
                        borderColor: '#343a40',
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.6,
                        categoryPercentage: 0.8
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { 
                        beginAtZero: true,
                        grid: { color: '#f8f9fa' }
                    },
                    x: {
                        grid: { display: false }
                    }
                },
                plugins: { 
                    tooltip: { 
                        mode: 'index', 
                        intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 10,
                        cornerRadius: 4
                    },
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: { usePointStyle: true, boxWidth: 8 }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }
};