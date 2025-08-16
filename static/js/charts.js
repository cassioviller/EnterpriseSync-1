// Chart.js configuration and utilities for SIGE

// Chart.js default configuration
Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.color = '#dee2e6';
Chart.defaults.borderColor = '#495057';
Chart.defaults.backgroundColor = 'rgba(13, 110, 253, 0.1)';

// Color palette for charts
const chartColors = {
    primary: '#0d6efd',
    secondary: '#6c757d',
    success: '#198754',
    danger: '#dc3545',
    warning: '#ffc107',
    info: '#0dcaf0',
    light: '#f8f9fa',
    dark: '#212529'
};

// Chart utilities
const ChartUtils = {
    // Generate color palette
    generateColors: function(count) {
        const colors = Object.values(chartColors);
        const result = [];
        
        for (let i = 0; i < count; i++) {
            result.push(colors[i % colors.length]);
        }
        
        return result;
    },
    
    // Generate transparent colors
    generateTransparentColors: function(count, opacity = 0.2) {
        const colors = this.generateColors(count);
        return colors.map(color => {
            // Convert hex to rgba
            const r = parseInt(color.slice(1, 3), 16);
            const g = parseInt(color.slice(3, 5), 16);
            const b = parseInt(color.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${opacity})`;
        });
    },
    
    // Format currency for chart labels
    formatCurrency: function(value) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(value);
    },
    
    // Format numbers with thousands separator
    formatNumber: function(value) {
        return new Intl.NumberFormat('pt-BR').format(value);
    },
    
    // Get responsive chart options
    getResponsiveOptions: function(aspectRatio = 2) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: aspectRatio,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                }
            }
        };
    }
};

// Chart configurations
const ChartConfigs = {
    // Dashboard funcionários por departamento
    funcionariosPorDepartamento: function(labels, data) {
        return {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: ChartUtils.generateColors(labels.length),
                    borderWidth: 2,
                    borderColor: '#212529'
                }]
            },
            options: {
                ...ChartUtils.getResponsiveOptions(2),
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map(function(label, i) {
                                        const meta = chart.getDatasetMeta(0);
                                        const style = meta.controller.getStyle(i);
                                        return {
                                            text: label + ' (' + data.datasets[0].data[i] + ')',
                                            fillStyle: style.backgroundColor,
                                            strokeStyle: style.borderColor,
                                            lineWidth: style.borderWidth,
                                            pointStyle: 'circle',
                                            hidden: isNaN(data.datasets[0].data[i]) || meta.data[i].hidden,
                                            index: i
                                        };
                                    });
                                }
                                return [];
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((sum, val) => sum + val, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} funcionários (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '50%'
            }
        };
    },
    
    // Dashboard custos por obra
    custosPorObra: function(labels, data) {
        return {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Custos (R$)',
                    data: data,
                    backgroundColor: ChartUtils.generateTransparentColors(labels.length, 0.8),
                    borderColor: ChartUtils.generateColors(labels.length),
                    borderWidth: 1
                }]
            },
            options: {
                ...ChartUtils.getResponsiveOptions(),
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return ChartUtils.formatCurrency(value);
                            }
                        }
                    }
                }
            }
        };
    },
    
    // Evolução temporal de custos
    evolucaoCustos: function(labels, datasets) {
        return {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets.map((dataset, index) => ({
                    ...dataset,
                    borderColor: ChartUtils.generateColors(datasets.length)[index],
                    backgroundColor: ChartUtils.generateTransparentColors(1, 0.1)[0],
                    fill: true,
                    tension: 0.4
                }))
            },
            options: {
                ...ChartUtils.getResponsiveOptions(),
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return ChartUtils.formatCurrency(value);
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        };
    },
    
    // Horas trabalhadas vs extras
    horasTrabalhadas: function(labels, normalHours, extraHours) {
        return {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Horas Normais',
                    data: normalHours,
                    backgroundColor: chartColors.primary,
                    stack: 'horas'
                }, {
                    label: 'Horas Extras',
                    data: extraHours,
                    backgroundColor: chartColors.warning,
                    stack: 'horas'
                }]
            },
            options: {
                ...ChartUtils.getResponsiveOptions(),
                scales: {
                    x: {
                        stacked: true
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value + 'h';
                            }
                        }
                    }
                }
            }
        };
    },
    
    // Distribuição de custos por tipo
    distribuicaoCustos: function(labels, data) {
        return {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: ChartUtils.generateColors(labels.length),
                    borderWidth: 2,
                    borderColor: '#212529'
                }]
            },
            options: {
                ...ChartUtils.getResponsiveOptions(1),
                plugins: {
                    ...ChartUtils.getResponsiveOptions().plugins,
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${ChartUtils.formatCurrency(context.parsed)} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        };
    },
    
    // Gauge/Medidor para KPIs
    gaugeChart: function(value, max, label) {
        const percentage = (value / max) * 100;
        
        return {
            type: 'doughnut',
            data: {
                labels: [label, ''],
                datasets: [{
                    data: [value, max - value],
                    backgroundColor: [
                        percentage >= 80 ? chartColors.success : 
                        percentage >= 60 ? chartColors.warning : 
                        chartColors.danger,
                        '#2d3748'
                    ],
                    borderWidth: 0,
                    cutout: '70%'
                }]
            },
            options: {
                ...ChartUtils.getResponsiveOptions(1),
                plugins: {
                    legend: {
                        display: false
                    }
                },
                elements: {
                    arc: {
                        borderWidth: 0
                    }
                }
            }
        };
    },
    
    // Scatter plot para análise de correlação
    scatterPlot: function(data, xLabel, yLabel) {
        return {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Dados',
                    data: data,
                    backgroundColor: ChartUtils.generateTransparentColors(1, 0.6)[0],
                    borderColor: chartColors.primary,
                    borderWidth: 1
                }]
            },
            options: {
                ...ChartUtils.getResponsiveOptions(),
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: xLabel
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: yLabel
                        }
                    }
                }
            }
        };
    }
};

// Chart manager for handling multiple charts
class ChartManager {
    constructor() {
        this.charts = new Map();
    }
    
    // Create or update chart
    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`Canvas with id ${canvasId} not found`);
            return null;
        }
        
        // Destroy existing chart if exists
        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
        }
        
        const ctx = canvas.getContext('2d');
        const chart = new Chart(ctx, config);
        this.charts.set(canvasId, chart);
        
        return chart;
    }
    
    // Update chart data
    updateChart(canvasId, newData) {
        const chart = this.charts.get(canvasId);
        if (!chart) {
            console.error(`Chart with id ${canvasId} not found`);
            return;
        }
        
        chart.data = newData;
        chart.update();
    }
    
    // Destroy chart
    destroyChart(canvasId) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.destroy();
            this.charts.delete(canvasId);
        }
    }
    
    // Destroy all charts
    destroyAll() {
        this.charts.forEach(chart => chart.destroy());
        this.charts.clear();
    }
    
    // Get chart instance
    getChart(canvasId) {
        return this.charts.get(canvasId);
    }
    
    // Resize all charts
    resizeAll() {
        this.charts.forEach(chart => chart.resize());
    }
}

// Global chart manager instance
const chartManager = new ChartManager();

// Initialize charts on window resize
window.addEventListener('resize', () => {
    chartManager.resizeAll();
});

// Export for global use
window.ChartUtils = ChartUtils;
window.ChartConfigs = ChartConfigs;
window.chartManager = chartManager;

// Common chart initialization functions
function initializeDashboardCharts() {
    // This function will be called from dashboard.html
    // Charts will be initialized with actual data from the backend
}

function initializeReportCharts() {
    // This function will be called from relatorios.html
    // Charts will be initialized based on report filters
}

// Utility function to load chart data from API
async function loadChartData(endpoint, params = {}) {
    try {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key]) {
                url.searchParams.append(key, params[key]);
            }
        });
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error loading chart data:', error);
        return null;
    }
}

// Animation utilities
const ChartAnimations = {
    // Smooth entry animation
    smoothEntry: {
        duration: 2000,
        easing: 'easeInOutQuart'
    },
    
    // Fast update animation
    fastUpdate: {
        duration: 500,
        easing: 'easeOutQuart'
    },
    
    // No animation
    none: {
        duration: 0
    }
};

// Export animations
window.ChartAnimations = ChartAnimations;
