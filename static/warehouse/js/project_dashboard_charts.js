"use strict";

/**
 * project_dashboard_charts.js
 * Візуалізація прогресу по етапах (бетонування) на головному дашборді.
 */

window.ProjectDashboardCharts = {
    
    init: function() {
        this.renderConcreteProgressChart();
    },

    getData: function(id) {
        return window.App.readJsonScript(id) || [];
    },

    renderConcreteProgressChart: function() {
        const ctx = document.getElementById('concreteProgressChart');
        if (!ctx) return;

        const fallback = document.querySelector('[data-empty-msg="concrete"]');
        const stagesData = this.getData('concrete-stages-data');

        // Перевірка: чи є дані і чи хоча б в одному етапі план > 0
        const hasData = stagesData && stagesData.length > 0 && stagesData.some(item => Number(item.plan) > 0);

        if (!hasData) {
            ctx.style.display = 'none';
            if (fallback) fallback.classList.remove('d-none');
            return;
        }

        const labels = stagesData.map(item => item.name);
        // 🔥 FIX: Конвертуємо Decimal-рядки/Int в Number явно
        const planData = stagesData.map(item => Number(item.plan));
        const factData = stagesData.map(item => Number(item.fact));

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
                        order: 1
                    },
                    {
                        label: 'Факт (м³)',
                        data: factData,
                        backgroundColor: 'rgba(13, 110, 253, 0.8)',
                        borderColor: '#0d6efd',
                        borderWidth: 1,
                        borderRadius: 4,
                        order: 0
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
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: { boxWidth: 10, usePointStyle: true }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                }
            }
        });
    }
};