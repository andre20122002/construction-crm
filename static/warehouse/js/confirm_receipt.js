"use strict";

/**
 * confirm_receipt.js
 * Логіка для сторінки прийому товару.
 * Відповідає за:
 * 1. Відображення прев'ю фотографії накладної/товару.
 * 2. Перемикання інтерфейсу між режимами "Оприбуткувати" та "Повернути постачальнику".
 */

window.ConfirmReceipt = {
    
    init: function() {
        this.initPhotoPreview();
        this.initRejectToggle();
    },

    /**
     * Налаштування прев'ю фото з input[type=file] (камери)
     */
    initPhotoPreview: function() {
        const fileInput = document.getElementById('cameraInput');
        const previewImg = document.getElementById('previewImg');
        const previewContainer = document.getElementById('previewContainer');
        const cameraLabel = document.getElementById('cameraLabel');
        const cameraText = document.getElementById('cameraText');

        // Якщо елементів немає на сторінці - виходимо
        if (!fileInput) return;

        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                const reader = new FileReader();

                reader.onload = function(e) {
                    // Показуємо картинку
                    if (previewImg) previewImg.src = e.target.result;
                    if (previewContainer) previewContainer.style.display = 'block';
                    
                    // Оновлюємо стиль кнопки
                    if (cameraLabel) cameraLabel.classList.add('active');
                    if (cameraText) cameraText.innerText = "Перезняти фото";
                };

                reader.readAsDataURL(file);
            }
        });
    },

    /**
     * Логіка перемикача "Це повернення / відмова?"
     */
    initRejectToggle: function() {
        const actReject = document.getElementById('actReject');
        const submitBtn = document.getElementById('mainSubmitBtn');
        const rejectBlock = document.getElementById('block-reject');

        if (!actReject || !submitBtn || !rejectBlock) return;

        const updateState = () => {
            if (actReject.checked) {
                // РЕЖИМ: ПОВЕРНЕННЯ
                rejectBlock.style.display = 'block';
                
                // Змінюємо стиль кнопки на червоний
                submitBtn.classList.remove('btn-success');
                submitBtn.classList.add('btn-danger');
                submitBtn.innerHTML = '<i class="bi bi-x-circle me-2"></i> ПОВЕРНУТИ ПОСТАЧАЛЬНИКУ';
            } else {
                // РЕЖИМ: ОПРИБУТКУВАННЯ (за замовчуванням)
                rejectBlock.style.display = 'none';
                
                // Змінюємо стиль кнопки на зелений
                submitBtn.classList.remove('btn-danger');
                submitBtn.classList.add('btn-success');
                submitBtn.innerHTML = '<i class="bi bi-box-seam me-2"></i> ОПРИБУТКУВАТИ';
            }
        };

        // Слухаємо зміни чекбокса
        actReject.addEventListener('change', updateState);

        // Встановлюємо початковий стан (на випадок, якщо браузер запам'ятав стан чекбокса при перезавантаженні)
        updateState();
    }
};

// Ініціалізація (якщо скрипт підключено без defer, але зазвичай викликається з шаблону)
// document.addEventListener('DOMContentLoaded', function() {
//     if (window.ConfirmReceipt) window.ConfirmReceipt.init();
// });