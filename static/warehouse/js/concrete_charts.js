"use strict";

/**
 * concrete_charts.js
 * Логіка побудови графіків для звіту по бетону.
 */

window.ConcreteCharts = {
    
    init: function() {
        this.renderConcreteChart();
    },

    /**
     * Helper для отримання даних з json_script
     */
    getData: function(id) {
        return window.App.readJsonScript(id) || [];
    },

    /**
     * Графік: План vs Факт (Bar Chart)
     */
    renderConcreteChart: function() {
        const ctx = document.getElementById('concreteChart');
        if (!ctx) return;

        const labels = this.getData('chart-labels');
        const planData = this.getData('chart-plan');
        const factData = this.getData('chart-fact');

        if (!labels.length) return;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'План (м³)',
                        data: planData,
                        backgroundColor: '#e9ecef',
                        borderColor: '#ced4da',
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.6,
                        categoryPercentage: 0.8
                    },
                    {
                        label: 'Факт (м³)',
                        data: factData,
                        backgroundColor: '#0d6efd', // Синій для бетону
                        borderColor: '#0a58ca',
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
                        grid: {
                            color: '#f8f9fa'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
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
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8
                        }
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