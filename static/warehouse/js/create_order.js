"use strict";

/**
 * create_order.js
 * Логіка для сторінки створення/редагування заявки.
 * Включає:
 * 1. UX завантаження файлів (Drag & Drop, Preview, Validation).
 * 2. Роботу з FormSet (динамічне додавання/видалення рядків).
 */

window.CreateOrder = {
    _inited: false,

    init: function() {
        if (this._inited) return; // Захист від повторної ініціалізації
        
        this.initFileUpload();
        this.initFormset();
        
        this._inited = true;
    },

    /**
     * Ініціалізація блоку завантаження файлів
     */
    initFileUpload: function() {
        const uploadBox = document.getElementById('uploadBox');
        const fileInput = document.getElementById('id_request_photo');
        const dropzoneContent = document.getElementById('dropzoneContent');
        const previewContainer = document.getElementById('previewContainer');
        const imgPreview = document.getElementById('imgPreview');
        const fileNameEl = document.getElementById('fileName');
        const fileSizeEl = document.getElementById('fileSize');
        const removeBtn = document.getElementById('removeFileBtn');
        const errorEl = document.getElementById('uploadError');

        // Якщо елементів немає (наприклад, на іншій сторінці), виходимо
        if (!uploadBox || !fileInput) return;

        // Конфігурація
        const MAX_SIZE_MB = 10;
        const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

        // --- Допоміжні функції ---

        const formatBytes = (bytes, decimals = 2) => {
            if (!+bytes) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
        };

        const showError = (msg) => {
            if (errorEl) {
                errorEl.textContent = msg;
                errorEl.style.display = 'block';
            }
            uploadBox.classList.add('has-error');
        };

        const clearError = () => {
            if (errorEl) errorEl.style.display = 'none';
            uploadBox.classList.remove('has-error');
        };

        const resetUpload = () => {
            fileInput.value = ''; // Очищаємо інпут
            
            if (previewContainer) previewContainer.style.display = 'none';
            if (dropzoneContent) dropzoneContent.style.display = 'block';
            
            uploadBox.classList.remove('has-file');
            clearError();
        };

        const handleFile = (file) => {
            clearError();
            
            // Валідація: Тип
            if (!file.type.startsWith('image/')) {
                showError("Дозволено лише зображення (JPEG, PNG, WEBP)");
                fileInput.value = ''; 
                return;
            }

            // Валідація: Розмір
            if (file.size > MAX_SIZE_BYTES) {
                showError(`Файл занадто великий (${formatBytes(file.size)}). Макс. розмір: ${MAX_SIZE_MB}MB`);
                fileInput.value = '';
                return;
            }

            // Все ок: показуємо прев'ю
            const reader = new FileReader();
            reader.onload = function(e) {
                if (imgPreview) imgPreview.src = e.target.result;
                if (fileNameEl) fileNameEl.textContent = file.name;
                if (fileSizeEl) fileSizeEl.textContent = formatBytes(file.size);
                
                if (dropzoneContent) dropzoneContent.style.display = 'none';
                if (previewContainer) previewContainer.style.display = 'block';
                uploadBox.classList.add('has-file'); 
            };
            reader.readAsDataURL(file);
        };

        // --- Event Listeners ---

        // 1. Зміна інпуту (вибір файлу)
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                handleFile(this.files[0]);
            }
        });

        // 2. Drag & Drop
        const preventDefaults = (e) => {
            e.preventDefault();
            e.stopPropagation();
        };

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadBox.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadBox.addEventListener(eventName, () => uploadBox.classList.add('is-dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadBox.addEventListener(eventName, () => uploadBox.classList.remove('is-dragover'), false);
        });

        uploadBox.addEventListener('drop', function(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files && files[0]) {
                fileInput.files = files; // Присвоюємо файл в інпут
                handleFile(files[0]);
            }
        });

        // 3. Кнопка "Прибрати"
        if (removeBtn) {
            removeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation(); 
                resetUpload();
            });
        }
    },

    /**
     * Ініціалізація Django FormSet (динамічне додавання та видалення рядків)
     */
    initFormset: function() {
        const addBtn = document.getElementById('add-item-btn');
        const container = document.getElementById('formset-container');
        const emptyFormTemplate = document.getElementById('empty-form');
        const totalForms = document.getElementById('id_items-TOTAL_FORMS');

        // Логіка додавання рядка
        if (addBtn && container && emptyFormTemplate && totalForms) {
            addBtn.addEventListener('click', function() {
                const count = parseInt(totalForms.value);
                // Беремо HTML з шаблону і замінюємо __prefix__ на поточний індекс
                const newFormHtml = emptyFormTemplate.innerHTML.replace(/__prefix__/g, count);
                
                // Додаємо HTML в таблицю
                container.insertAdjacentHTML('beforeend', newFormHtml);
                
                // Оновлюємо лічильник форм
                totalForms.value = count + 1;
                
                // Знаходимо новостворений селект і ініціалізуємо TomSelect
                const newRow = container.lastElementChild;
                const newSelect = newRow.querySelector('select.tom-select'); 
                
                // Використовуємо глобальну функцію ініціалізації TomSelect, якщо вона доступна
                if (newSelect && window.initTomSelect) {
                    window.initTomSelect(newSelect);
                }
            });
        }

        // Логіка видалення рядка (через делегування подій)
        document.addEventListener('click', (e) => {
            // Перевіряємо, чи клік був по кнопці видалення (або її іконці)
            const btn = e.target.closest('[data-action="remove-row"]');
            if (btn) {
                this.handleRemoveRow(btn);
            }
        });
    },

    /**
     * Обробка видалення рядка
     * @param {HTMLElement} btn - Кнопка, яку натиснули
     */
    handleRemoveRow: function(btn) {
        const row = btn.closest('.item-row');
        if (!row) return;

        // Перевіряємо, чи це існуючий об'єкт (є приховане поле id з value)
        // Django formset зазвичай має поле id з іменем виду "items-0-id"
        const idInput = row.querySelector('input[type="hidden"][name$="-id"]');
        
        if (idInput && idInput.value) {
            // Це існуючий запис: ховаємо рядок і ставимо чекбокс DELETE = checked
            row.style.display = 'none';
            const deleteInput = row.querySelector('input[name$="-DELETE"]');
            if (deleteInput) deleteInput.checked = true;
        } else {
            // Це новий динамічний рядок: просто видаляємо з DOM
            row.remove();
            // Опціонально: можна оновити TOTAL_FORMS, але Django коректно обробляє "дірки" в індексах
        }
    }
};

// Ініціалізація при завантаженні DOM
document.addEventListener("DOMContentLoaded", function() {
    window.CreateOrder.init();
});