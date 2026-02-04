"use strict";

/**
 * mechanisms_charts.js
 * Логіка побудови графіків для звіту по механізмах.
 */

window.MechanismsCharts = {
    
    init: function() {
        this.renderChart();
    },

    getData: function(id) {
        return window.App.readJsonScript(id) || [];
    },

    /**
     * Графік: План vs Факт (Bar Chart)
     */
    renderChart: function() {
        const ctx = document.getElementById('mechanismsChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="mechanisms"]');
        
        const labels = this.getData('chart-labels');
        const planDataRaw = this.getData('chart-plan');
        const factDataRaw = this.getData('chart-fact');

        // Перевірка наявності даних
        const hasData = labels.length > 0 && planDataRaw.some(val => Number(val) > 0);

        if (!hasData) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        // Конвертуємо дані в числа
        const planData = planDataRaw.map(val => Number(val));
        const factData = factDataRaw.map(val => Number(val));

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'План (год)',
                        data: planData,
                        backgroundColor: '#e9ecef',
                        borderColor: '#ced4da',
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.6,
                        categoryPercentage: 0.8
                    },
                    {
                        label: 'Факт (год)',
                        data: factData,
                        backgroundColor: '#ffc107', // Жовтий для техніки
                        borderColor: '#d35400',
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