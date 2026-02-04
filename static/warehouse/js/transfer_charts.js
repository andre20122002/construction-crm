"use strict";

/**
 * transfer_charts.js
 * Логіка побудови графіків для аналітики переміщень (логістики).
 */

window.TransferCharts = {
    
    init: function() {
        this.renderMaterialChart();
        this.renderRouteChart();
    },

    /**
     * Helper для отримання даних.
     * Оскільки дані можуть приходити з view вже як JSON-рядок (json.dumps),
     * json_script може їх подвійно закодувати.
     * Цей метод розпаковує їх до масиву/об'єкта.
     */
    getData: function(id) {
        let data = window.App.readJsonScript(id);
        
        // Якщо отримали рядок, спробуємо його розпарсити ще раз
        if (typeof data === 'string') {
            try {
                data = JSON.parse(data);
            } catch (e) {
                console.warn(`[TransferCharts] Could not double-parse data for ${id}`, e);
            }
        }
        return data || [];
    },

    /**
     * Графік 1: Топ матеріалів (Pie)
     */
    renderMaterialChart: function() {
        const ctx = document.getElementById('matChart');
        if (!ctx) return;

        const labels = this.getData('mat-labels');
        const dataValues = this.getData('mat-data');

        if (!labels.length || !dataValues.length) return;

        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: dataValues,
                    backgroundColor: [
                        '#0d6efd', // Primary
                        '#20c997', // Teal
                        '#ffc107', // Warning
                        '#dc3545', // Danger
                        '#6f42c1', // Purple
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
                    }
                }
            }
        });
    },

    /**
     * Графік 2: Популярні маршрути (Horizontal Bar)
     */
    renderRouteChart: function() {
        const ctx = document.getElementById('routeChart');
        if (!ctx) return;

        const labels = this.getData('route-labels');
        const dataValues = this.getData('route-data');

        if (!labels.length || !dataValues.length) return;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Кількість рейсів',
                    data: dataValues,
                    backgroundColor: '#0dcaf0', // Info color
                    borderRadius: 4,
                    barThickness: 20
                }]
            },
            options: {
                indexAxis: 'y', // Горизонтальний графік
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { display: false }
                    },
                    y: {
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
};