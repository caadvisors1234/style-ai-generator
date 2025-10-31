(() => {
  const containerId = 'toast-container';

  function createToast(message, title, variant) {
    const container = document.getElementById(containerId);
    if (!container) {
      return;
    }

    const wrapper = document.createElement('div');
    wrapper.className = `toast align-items-center text-bg-${variant} border-0`;
    wrapper.role = 'alert';
    wrapper.ariaLive = 'assertive';
    wrapper.ariaAtomic = 'true';

    wrapper.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          ${title ? `<strong class="d-block mb-1">${title}</strong>` : ''}
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    container.appendChild(wrapper);
    const toast = bootstrap.Toast.getOrCreateInstance(wrapper, { delay: 4000 });
    toast.show();
    wrapper.addEventListener('hidden.bs.toast', () => wrapper.remove());
  }

  window.notifySuccess = (message, title = '') => createToast(message, title, 'success');
  window.notifyError = (message, title = '') => createToast(message, title, 'danger');
  window.notifyWarning = (message, title = '') => createToast(message, title, 'warning');
})(); 
