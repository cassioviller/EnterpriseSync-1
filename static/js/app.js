// Main application JavaScript for SIGE - Estruturas do Vale

// Global variables
let currentUser = null;
let appSettings = {
    dateFormat: 'dd/mm/yyyy',
    timeFormat: '24h',
    language: 'pt-BR',
    theme: 'dark'
};

// Initialize app when DOM is ready
$(document).ready(function() {
    initializeApp();
    setupEventListeners();
    setupDataTables();
    setupFormValidation();
    setupTooltips();
    setupModals();
});

// Initialize application
function initializeApp() {
    console.log('Initializing SIGE application...');
    
    // Set up CSRF token for AJAX requests
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", getCookie('csrf_token'));
            }
        }
    });
    
    // Initialize clock if present
    if (document.getElementById('currentTime')) {
        updateClock();
        setInterval(updateClock, 1000);
    }
    
    // Initialize charts if Chart.js is available
    if (typeof Chart !== 'undefined' && typeof initializeDashboardCharts === 'function') {
        initializeDashboardCharts();
    }
    
    // Setup auto-save for forms
    setupAutoSave();
    
    console.log('SIGE application initialized successfully!');
}

// Setup global event listeners
function setupEventListeners() {
    // Handle form submissions
    $('form').on('submit', function(e) {
        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        
        // Prevent double submission
        if (submitBtn.hasClass('disabled')) {
            e.preventDefault();
            return false;
        }
        
        // Show loading state
        submitBtn.addClass('disabled');
        submitBtn.html('<i class="fas fa-spinner fa-spin"></i> Processando...');
        
        // Re-enable button after 3 seconds (fallback)
        setTimeout(() => {
            submitBtn.removeClass('disabled');
            submitBtn.html(submitBtn.data('original-text') || 'Salvar');
        }, 3000);
    });
    
    // Handle delete confirmations
    $(document).on('click', '.btn-delete', function(e) {
        e.preventDefault();
        const itemName = $(this).data('item-name') || 'este item';
        
        if (confirm(`Tem certeza que deseja excluir ${itemName}?`)) {
            const form = $(this).closest('form');
            if (form.length) {
                form.submit();
            } else {
                window.location.href = $(this).attr('href');
            }
        }
    });
    
    // Handle number formatting
    $(document).on('input', 'input[type="number"]', function() {
        formatCurrency(this);
    });
    
    // Handle date inputs
    $(document).on('change', 'input[type="date"]', function() {
        validateDateRange(this);
    });
    
    // Handle file uploads
    $(document).on('change', 'input[type="file"]', function() {
        handleFileUpload(this);
    });
    
    // Handle search functionality
    $(document).on('input', '.search-input', function() {
        const searchTerm = $(this).val().toLowerCase();
        const targetTable = $(this).data('target');
        
        if (targetTable) {
            filterTable(targetTable, searchTerm);
        }
    });
    
    // Handle modal events
    $('.modal').on('show.bs.modal', function() {
        const modal = $(this);
        modal.find('.modal-title span').text(modal.data('title') || 'Formulário');
        
        // Clear previous validation errors
        modal.find('.is-invalid').removeClass('is-invalid');
        modal.find('.invalid-feedback').hide();
    });
    
    $('.modal').on('hidden.bs.modal', function() {
        const modal = $(this);
        modal.find('form')[0]?.reset();
        modal.find('.btn-primary').removeClass('disabled');
    });
    
    // Handle keyboard shortcuts
    $(document).keydown(function(e) {
        // Ctrl + S to save
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            const activeForm = $('form:visible').first();
            if (activeForm.length) {
                activeForm.submit();
            }
        }
        
        // Esc to close modal
        if (e.key === 'Escape') {
            const visibleModal = $('.modal:visible').last();
            if (visibleModal.length) {
                visibleModal.modal('hide');
            }
        }
    });
}

// Setup DataTables
function setupDataTables() {
    if ($.fn.DataTable) {
        // Default DataTables configuration
        $.extend(true, $.fn.dataTable.defaults, {
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/pt-BR.json'
            },
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "Todos"]],
            order: [[0, 'asc']],
            columnDefs: [
                {
                    targets: 'no-sort',
                    orderable: false
                },
                {
                    targets: 'actions',
                    orderable: false,
                    searchable: false
                }
            ],
            drawCallback: function(settings) {
                // Re-initialize tooltips after table redraw
                $('[data-bs-toggle="tooltip"]').tooltip();
            }
        });
        
        // Initialize all tables with class 'datatable'
        $('.datatable').each(function() {
            if (!$.fn.DataTable.isDataTable(this)) {
                $(this).DataTable();
            }
        });
    }
}

// Setup form validation
function setupFormValidation() {
    // Custom validation rules
    $.validator?.addMethod('cpf', function(value, element) {
        return this.optional(element) || isValidCPF(value);
    }, 'CPF inválido');
    
    $.validator?.addMethod('cnpj', function(value, element) {
        return this.optional(element) || isValidCNPJ(value);
    }, 'CNPJ inválido');
    
    $.validator?.addMethod('phone', function(value, element) {
        return this.optional(element) || isValidPhone(value);
    }, 'Telefone inválido');
    
    // Initialize form validation
    $('form').each(function() {
        if ($(this).hasClass('needs-validation')) {
            $(this).validate({
                errorClass: 'is-invalid',
                validClass: 'is-valid',
                errorElement: 'div',
                errorPlacement: function(error, element) {
                    error.addClass('invalid-feedback');
                    element.closest('.form-group, .mb-3').append(error);
                },
                highlight: function(element) {
                    $(element).addClass('is-invalid').removeClass('is-valid');
                },
                unhighlight: function(element) {
                    $(element).removeClass('is-invalid').addClass('is-valid');
                }
            });
        }
    });
}

// Setup tooltips
function setupTooltips() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Setup modals
function setupModals() {
    // Auto-focus first input in modals
    $('.modal').on('shown.bs.modal', function() {
        $(this).find('input:visible:first').focus();
    });
    
    // Handle modal form submissions
    $('.modal form').on('submit', function(e) {
        const form = $(this);
        const modal = form.closest('.modal');
        
        // Validate form before submission
        if (form.hasClass('needs-validation') && !form.valid()) {
            e.preventDefault();
            return false;
        }
        
        // Show loading state
        const submitBtn = form.find('button[type="submit"]');
        submitBtn.addClass('disabled');
        submitBtn.html('<i class="fas fa-spinner fa-spin"></i> Salvando...');
    });
}

// Setup auto-save functionality
function setupAutoSave() {
    let autoSaveTimeout;
    
    $('form[data-auto-save="true"]').on('input change', function() {
        const form = $(this);
        
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(() => {
            saveFormData(form);
        }, 2000);
    });
}

// Update clock display
function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('pt-BR');
    const dateString = now.toLocaleDateString('pt-BR', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
    
    const timeElement = document.getElementById('currentTime');
    const dateElement = document.getElementById('currentDate');
    
    if (timeElement) timeElement.textContent = timeString;
    if (dateElement) dateElement.textContent = dateString;
}

// Format currency input
function formatCurrency(input) {
    const value = parseFloat(input.value);
    if (!isNaN(value) && input.dataset.currency === 'true') {
        input.value = value.toFixed(2);
    }
}

// Validate date range
function validateDateRange(input) {
    const startDate = document.querySelector('input[name="data_inicio"]');
    const endDate = document.querySelector('input[name="data_fim"]');
    
    if (startDate && endDate && startDate.value && endDate.value) {
        if (new Date(startDate.value) > new Date(endDate.value)) {
            showAlert('A data de início não pode ser maior que a data de fim', 'warning');
            input.value = '';
        }
    }
}

// Handle file upload
function handleFileUpload(input) {
    const file = input.files[0];
    const maxSize = 5 * 1024 * 1024; // 5MB
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'];
    
    if (file) {
        if (file.size > maxSize) {
            showAlert('Arquivo muito grande. Tamanho máximo: 5MB', 'danger');
            input.value = '';
            return;
        }
        
        if (!allowedTypes.includes(file.type)) {
            showAlert('Tipo de arquivo não permitido', 'danger');
            input.value = '';
            return;
        }
        
        // Show file preview if it's an image
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const preview = input.parentElement.querySelector('.image-preview');
                if (preview) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                }
            };
            reader.readAsDataURL(file);
        }
    }
}

// Filter table
function filterTable(tableId, searchTerm) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const cells = row.getElementsByTagName('td');
        let found = false;
        
        for (let j = 0; j < cells.length; j++) {
            const cellText = cells[j].textContent.toLowerCase();
            if (cellText.includes(searchTerm)) {
                found = true;
                break;
            }
        }
        
        row.style.display = found ? '' : 'none';
    }
}

// Save form data to localStorage
function saveFormData(form) {
    const formData = {};
    const formKey = form.attr('id') || 'default-form';
    
    form.find('input, select, textarea').each(function() {
        const input = $(this);
        const name = input.attr('name');
        const value = input.val();
        
        if (name && value) {
            formData[name] = value;
        }
    });
    
    localStorage.setItem(`autosave_${formKey}`, JSON.stringify(formData));
    
    // Show auto-save indicator
    showToast('Dados salvos automaticamente', 'success', 2000);
}

// Load form data from localStorage
function loadFormData(form) {
    const formKey = form.attr('id') || 'default-form';
    const savedData = localStorage.getItem(`autosave_${formKey}`);
    
    if (savedData) {
        const formData = JSON.parse(savedData);
        
        Object.keys(formData).forEach(name => {
            const input = form.find(`[name="${name}"]`);
            if (input.length) {
                input.val(formData[name]);
            }
        });
    }
}

// Clear saved form data
function clearFormData(form) {
    const formKey = form.attr('id') || 'default-form';
    localStorage.removeItem(`autosave_${formKey}`);
}

// Show alert message
function showAlert(message, type = 'info', duration = 5000) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const alertContainer = document.querySelector('.alert-container') || document.body;
    alertContainer.insertAdjacentHTML('afterbegin', alertHtml);
    
    // Auto-dismiss after duration
    setTimeout(() => {
        const alert = alertContainer.querySelector('.alert');
        if (alert) {
            alert.remove();
        }
    }, duration);
}

// Show toast notification
function showToast(message, type = 'info', duration = 3000) {
    const toastHtml = `
        <div class="toast align-items-center text-bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = toastContainer.lastElementChild;
    const toast = new bootstrap.Toast(toastElement, { delay: duration });
    toast.show();
    
    // Remove toast element after hide
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// Utility functions
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function isValidCPF(cpf) {
    cpf = cpf.replace(/[^\d]+/g, '');
    if (cpf.length !== 11 || /^(\d)\1+$/.test(cpf)) return false;
    
    let sum = 0;
    for (let i = 0; i < 9; i++) {
        sum += parseInt(cpf.charAt(i)) * (10 - i);
    }
    
    let remainder = 11 - (sum % 11);
    if (remainder === 10 || remainder === 11) remainder = 0;
    if (remainder !== parseInt(cpf.charAt(9))) return false;
    
    sum = 0;
    for (let i = 0; i < 10; i++) {
        sum += parseInt(cpf.charAt(i)) * (11 - i);
    }
    
    remainder = 11 - (sum % 11);
    if (remainder === 10 || remainder === 11) remainder = 0;
    
    return remainder === parseInt(cpf.charAt(10));
}

function isValidCNPJ(cnpj) {
    cnpj = cnpj.replace(/[^\d]+/g, '');
    if (cnpj.length !== 14 || /^(\d)\1+$/.test(cnpj)) return false;
    
    let size = cnpj.length - 2;
    let numbers = cnpj.substring(0, size);
    let digits = cnpj.substring(size);
    let sum = 0;
    let pos = size - 7;
    
    for (let i = size; i >= 1; i--) {
        sum += numbers.charAt(size - i) * pos--;
        if (pos < 2) pos = 9;
    }
    
    let result = sum % 11 < 2 ? 0 : 11 - (sum % 11);
    if (result !== parseInt(digits.charAt(0))) return false;
    
    size = size + 1;
    numbers = cnpj.substring(0, size);
    sum = 0;
    pos = size - 7;
    
    for (let i = size; i >= 1; i--) {
        sum += numbers.charAt(size - i) * pos--;
        if (pos < 2) pos = 9;
    }
    
    result = sum % 11 < 2 ? 0 : 11 - (sum % 11);
    return result === parseInt(digits.charAt(1));
}

function isValidPhone(phone) {
    phone = phone.replace(/[^\d]+/g, '');
    return phone.length >= 10 && phone.length <= 11;
}

function formatPhone(phone) {
    phone = phone.replace(/[^\d]+/g, '');
    if (phone.length === 11) {
        return phone.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    } else if (phone.length === 10) {
        return phone.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
    }
    return phone;
}

function formatCPF(cpf) {
    cpf = cpf.replace(/[^\d]+/g, '');
    if (cpf.length === 11) {
        return cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    }
    return cpf;
}

function formatCNPJ(cnpj) {
    cnpj = cnpj.replace(/[^\d]+/g, '');
    if (cnpj.length === 14) {
        return cnpj.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
    }
    return cnpj;
}

function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

function formatDate(date) {
    return new Intl.DateTimeFormat('pt-BR').format(new Date(date));
}

function formatDateTime(date) {
    return new Intl.DateTimeFormat('pt-BR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(date));
}

// Export functions for use in other modules
window.SIGE = {
    showAlert,
    showToast,
    formatCurrency,
    formatDate,
    formatDateTime,
    formatPhone,
    formatCPF,
    formatCNPJ,
    isValidCPF,
    isValidCNPJ,
    isValidPhone,
    saveFormData,
    loadFormData,
    clearFormData
};
