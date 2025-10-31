(() => {
  const container = document.getElementById('conversion-progress');
  if (!container) return;

  const conversionId = container.dataset.conversionId;
  const messageEl = document.getElementById('progress-message');
  const counterEl = document.getElementById('progress-counter');
  const bar = document.getElementById('progress-bar');
  const cancelBtn = document.getElementById('cancel-conversion');

  let timer = null;

  function updateBar(progress, status, text) {
    if (bar) {
      bar.style.width = `${progress}%`;
      bar.setAttribute('aria-valuenow', progress);
      bar.textContent = `${progress}%`;
    }
    if (messageEl) {
      messageEl.textContent = text || status;
    }
  }

  async function fetchStatus() {
    try {
      const data = await APIClient.get(`/api/v1/convert/${conversionId}/status/`);
      const conversion = data.conversion;

      const total = conversion.generation_count || 0;
      const current = conversion.current_count || 0;

      let progress = 10;
      if (total > 0) {
        const ratio = Math.min(99, Math.round((current / total) * 100));
        progress = Math.max(progress, ratio);
      }
      if (conversion.status === 'completed' || conversion.status === 'failed') {
        progress = 100;
      }

      updateBar(progress, conversion.status, `ステータス: ${conversion.status}`);

      if (counterEl) {
        if (conversion.status === 'completed' && data.images) {
          counterEl.textContent = `${data.images.length} / ${total} 枚`;
        } else if (total > 0 && conversion.status === 'processing') {
          counterEl.textContent = `${current} / ${total} 枚`;
        } else {
          counterEl.textContent = conversion.status === 'processing' ? '処理中...' : '';
        }
      }

      if (conversion.status === 'completed') {
        notifySuccess('画像変換が完了しました');
        clearInterval(timer);
        setTimeout(() => window.location.href = '/gallery/', 1500);
      } else if (conversion.status === 'failed') {
        notifyError(conversion.error_message || '画像変換に失敗しました');
        clearInterval(timer);
      }
    } catch (error) {
      updateBar(100, 'failed', 'ステータスの取得に失敗しました');
      notifyError('進捗の取得に失敗しました');
      clearInterval(timer);
    }
  }

  async function cancelConversion() {
    cancelBtn.disabled = true;
    try {
      await APIClient.post(`/api/v1/convert/${conversionId}/cancel/`, {});
      notifyWarning('変換をキャンセルしました');
      clearInterval(timer);
      setTimeout(() => window.location.href = '/', 1500);
    } catch (error) {
      notifyError('キャンセル処理に失敗しました');
      cancelBtn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    timer = setInterval(fetchStatus, 4000);
    if (cancelBtn) {
      cancelBtn.addEventListener('click', cancelConversion);
    }
  });
})();
