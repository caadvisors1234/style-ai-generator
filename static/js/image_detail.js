(() => {
  const modalElement = document.getElementById('imageDetailModal');
  if (!modalElement) return;

  const modal = new bootstrap.Modal(modalElement);
  const originalImg = document.getElementById('detail-original');
  const generatedImg = document.getElementById('detail-generated');
  const createdAtEl = document.getElementById('detail-created-at');
  const modelEl = document.getElementById('detail-model');
  const promptEl = document.getElementById('detail-prompt');
  const brightnessRange = document.getElementById('brightness-range');
  const brightnessValue = document.getElementById('brightness-value');
  const brightnessReset = document.getElementById('brightness-reset');
  const brightnessApply = document.getElementById('brightness-apply');
  const downloadLink = document.getElementById('detail-download');
  const deleteButton = document.getElementById('detail-delete');

  const state = {
    conversionId: null,
    imageId: null,
    savedBrightness: 0,
  };

  function updatePreview() {
    const adjustment = Number(brightnessRange.value || 0);
    const factor = 1 + (adjustment / 100);
    generatedImg.style.filter = `brightness(${factor})`;
    brightnessValue.textContent = String(adjustment);
  }

  async function loadDetail(imageId) {
    const data = await APIClient.get(`/api/v1/gallery/images/${imageId}/`);
    const image = data.image;
    state.conversionId = image.conversion.id;
    state.imageId = image.id;

    const bustCache = (url) => {
      const separator = url.includes('?') ? '&' : '?';
      return `${url}${separator}t=${Date.now()}`;
    };

    originalImg.src = bustCache(image.conversion.original_image_url);
    generatedImg.src = bustCache(image.image_url);
    createdAtEl.textContent = new Date(image.created_at).toLocaleString('ja-JP');
    modelEl.textContent = image.conversion.model_name || '—';
    promptEl.textContent = image.conversion.prompt || '（設定なし）';
    state.savedBrightness = image.brightness_adjustment ?? 0;
    brightnessRange.value = state.savedBrightness;
    generatedImg.style.filter = 'brightness(1)';
    brightnessValue.textContent = String(brightnessRange.value);
    downloadLink.href = `/api/v1/gallery/images/${image.id}/download/`;
  }

  async function applyBrightness() {
    if (!state.imageId) return;
    try {
      const adjustment = Number(brightnessRange.value);
      const data = await APIClient.patch(`/api/v1/gallery/images/${state.imageId}/brightness/`, { adjustment });
      const image = data.image;
      const imageUrl = image.image_url;
      const separator = imageUrl.includes('?') ? '&' : '?';
      generatedImg.src = `${imageUrl}${separator}t=${Date.now()}`;
      state.savedBrightness = image.brightness_adjustment ?? 0;
      brightnessRange.value = String(state.savedBrightness);
      generatedImg.style.filter = 'brightness(1)';
      brightnessValue.textContent = brightnessRange.value;
      notifySuccess(image.message || '輝度を調整しました');
    } catch (error) {
      notifyError('輝度調整に失敗しました');
    }
  }

  async function deleteImage() {
    if (!state.imageId) return;
    const confirmed = window.confirm('この生成画像を削除しますか？');
    if (!confirmed) return;

    try {
      await APIClient.delete(`/api/v1/gallery/images/${state.imageId}/delete/`, {});
      notifyWarning('画像を削除しました');
      modal.hide();
      if (typeof window.location.reload === 'function') {
        setTimeout(() => window.location.reload(), 800);
      }
    } catch (error) {
      notifyError('画像の削除に失敗しました');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    brightnessRange.addEventListener('input', () => {
      updatePreview();
    });
    brightnessReset.addEventListener('click', async () => {
      brightnessRange.value = 0;
      updatePreview();
      // リセット時は輝度0で適用
      await applyBrightness();
    });
    brightnessApply.addEventListener('click', applyBrightness);
    deleteButton.addEventListener('click', deleteImage);
  });

  window.ImageDetail = {
    open: async (conversionId, imageId) => {
      try {
        await loadDetail(imageId);
        modal.show();
      } catch (error) {
        notifyError('画像詳細の取得に失敗しました');
      }
    },
  };
})();
