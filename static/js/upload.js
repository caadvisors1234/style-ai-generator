(() => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileButton = document.getElementById('file-picker-button');
  const uploadedList = document.getElementById('uploaded-list');
  const errorBox = document.getElementById('upload-errors');
  const template = document.getElementById('uploaded-item-template');
  const hpbUrlInput = document.getElementById('hpb-url-input');
  const fetchHPBButton = document.getElementById('fetch-hpb-images-button');
  const fetchHPBSpinner = fetchHPBButton ? fetchHPBButton.querySelector('.spinner-border') : null;
  const fetchHPBButtonText = fetchHPBButton ? fetchHPBButton.querySelector('.button-text') : null;
  const startButton = document.getElementById('start-conversion');

  const state = {
    uploads: [],
  };

  function emitUploadsChanged() {
    try {
      window.dispatchEvent(new CustomEvent('uploadsChanged', {
        detail: { count: state.uploads.length },
      }));
    } catch (e) {
      // no-op
    }
  }

  function updateStartButton() {
    if (startButton) {
      startButton.disabled = state.uploads.length === 0;
    }
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove('d-none');
  }

  function clearError() {
    if (!errorBox) return;
    errorBox.classList.add('d-none');
  }

  function humanFileSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, index)).toFixed(1)} ${units[index]}`;
  }

  function renderUploads() {
    if (!uploadedList) return;
    uploadedList.innerHTML = '';

    state.uploads.forEach((item, idx) => {
      const clone = template.content.cloneNode(true);
      const img = clone.querySelector('.uploaded-thumb');
      img.src = item.preview_url;

      clone.querySelector('.uploaded-name').textContent = item.file_name;
      clone.querySelector('.uploaded-size').textContent = humanFileSize(item.file_size);

      const removeBtn = clone.querySelector('.remove-upload');
      removeBtn.dataset.index = idx;

      // Loading state
      if (item.isUploading) {
        const cardBody = clone.querySelector('.card-body');
        const spinner = document.createElement('div');
        spinner.className = 'spinner-border text-primary spinner-border-sm ms-2';
        spinner.setAttribute('role', 'status');
        clone.querySelector('.card-title').appendChild(spinner);

        img.style.opacity = '0.5';
        removeBtn.disabled = true;
      }

      uploadedList.appendChild(clone);
    });

    updateStartButton();
    emitUploadsChanged();
  }

  async function uploadFiles(files) {
    if (!files.length) return;

    const fileArray = Array.from(files);
    const formData = new FormData();
    fileArray.forEach((file) => formData.append('images', file));

    // Create temporary entries for instant preview
    const tempUploads = fileArray.map((file) => ({
      file_name: file.name,
      file_size: file.size,
      preview_url: URL.createObjectURL(file),
      originalFile: file,
      isUploading: true, // Flag to show loading state
    }));

    // Add to state immediately
    const startIdx = state.uploads.length;
    state.uploads.push(...tempUploads);
    renderUploads();

    try {
      clearError();
      const response = await APIClient.upload('/api/v1/upload/', formData);

      // Update the temporary entries with real data
      response.uploaded_files.forEach((info, i) => {
        const targetIdx = startIdx + i;
        if (state.uploads[targetIdx]) {
          state.uploads[targetIdx] = {
            ...info,
            originalFile: fileArray[i] || null,
            isUploading: false,
            // Keep the local preview URL until we are sure? 
            // Actually server returns preview_url, but local blob is faster.
            // Let's use server URL to ensure consistency, need to revoke blob later?
            // For now, let's keep it simple and just replace.
          };
          // Revoke temporary blob to free memory (optional but good practice)
          if (tempUploads[i] && tempUploads[i].preview_url) {
            URL.revokeObjectURL(tempUploads[i].preview_url);
          }
        }
      });

      renderUploads();
      notifySuccess(`${response.count}件の画像をアップロードしました`);
    } catch (error) {
      // Remove temporary uploads on failure
      state.uploads.splice(startIdx, tempUploads.length);
      renderUploads();

      const payload = error.payload || {};
      showError(payload.message || 'アップロードに失敗しました');
      if (payload.errors) {
        payload.errors.forEach((err) => notifyError(err.error, err.filename));
      }
    }
  }

  async function handleFetchHPBImages() {
    if (!hpbUrlInput || !fetchHPBButton) return;

    const targetUrl = hpbUrlInput.value.trim();
    if (!targetUrl) return;

    clearError();
    fetchHPBButton.disabled = true;
    if (fetchHPBSpinner) fetchHPBSpinner.classList.remove('d-none');
    if (fetchHPBButtonText) fetchHPBButtonText.textContent = '取得中...';

    try {
      const response = await APIClient.post('/api/v1/scrape/', { url: targetUrl });
      const files = Array.isArray(response.uploaded_files) ? response.uploaded_files : [];

      files.forEach((info) => {
        state.uploads.push({
          ...info,
          originalFile: null,
        });
      });

      renderUploads();
      notifySuccess(`${response.count}件の画像を取得しました`);
    } catch (error) {
      const payload = error?.payload || {};
      notifyError(payload.message || '画像の取得に失敗しました。');
    } finally {
      fetchHPBButton.disabled = false;
      if (fetchHPBSpinner) fetchHPBSpinner.classList.add('d-none');
      if (fetchHPBButtonText) fetchHPBButtonText.textContent = '取得';
    }
  }

  async function removeUpload(index) {
    const target = state.uploads[index];
    if (!target) return;

    try {
      await APIClient.delete('/api/v1/upload/delete/', { file_path: target.file_path });
      state.uploads.splice(index, 1);
      renderUploads();
      notifySuccess('画像を削除しました');
    } catch (error) {
      notifyError('画像の削除に失敗しました');
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    dropZone.classList.remove('drag-over');
    uploadFiles(event.dataTransfer.files);
  }

  function handleDragOver(event) {
    event.preventDefault();
    dropZone.classList.add('drag-over');
  }

  function handleDragLeave() {
    dropZone.classList.remove('drag-over');
  }

  function registerEvents() {
    if (dropZone) {
      dropZone.addEventListener('dragover', handleDragOver);
      dropZone.addEventListener('dragleave', handleDragLeave);
      dropZone.addEventListener('drop', handleDrop);
      dropZone.addEventListener('click', (event) => {
        // ボタン自体のクリックイベントと重複しないようにする
        if (event.target !== fileButton && !fileButton.contains(event.target)) {
          fileInput.click();
        }
      });
    }

    if (fileButton && fileInput) {
      fileButton.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (event) => {
        uploadFiles(event.target.files);
        fileInput.value = '';
      });
    }

    if (fetchHPBButton) {
      fetchHPBButton.addEventListener('click', handleFetchHPBImages);
    }

    if (uploadedList) {
      uploadedList.addEventListener('click', (event) => {
        const button = event.target.closest('.remove-upload');
        if (button) {
          removeUpload(Number(button.dataset.index));
        }
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    registerEvents();
    updateStartButton();
    window.UploadManager = {
      getFiles: () => state.uploads.slice(),
      clear: () => {
        state.uploads = [];
        renderUploads();
      },
    };
  });
})();
