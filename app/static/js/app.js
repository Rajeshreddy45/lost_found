'use strict';
// Simple, local UI behavior: file previews and explicit destructive-action confirmations.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('input[type="file"][data-preview]').forEach(input => {
    input.addEventListener('change', () => {
      const img = document.getElementById(input.dataset.preview);
      if (!img) return;
      if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
      const file = input.files && input.files[0];
      if (!file) { img.classList.add('d-none'); img.removeAttribute('src'); return; }
      if (!file.type.startsWith('image/')) { img.classList.add('d-none'); return; }
      const objectUrl = URL.createObjectURL(file);
      img.dataset.objectUrl = objectUrl;
      img.src = objectUrl;
      img.classList.remove('d-none');
    });
  });
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll('form[data-confirm-action]').forEach(form => {
    form.addEventListener('submit', event => {
      const submitter = event.submitter;
      if (submitter && submitter.value === 'approve' && !window.confirm('Verify the evidence before approving. This will mark the item Returned. Continue?')) {
        event.preventDefault();
      }
    });
  });
});
