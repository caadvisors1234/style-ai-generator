/**
 * 画像変換進捗表示（WebSocket対応）
 * WebSocketでリアルタイム進捗を受信し、接続失敗時はポーリングにフォールバック
 */
(() => {
  'use strict';

  const container = document.getElementById('conversion-progress');
  if (!container) return;

  const conversionId = container.dataset.conversionId;
  if (!conversionId) {
    const errorMessage = '変換IDが見つかりません';
    console.error('[Progress]', errorMessage);
    notifyError(errorMessage);
    return;
  }

  const messageEl = document.getElementById('progress-message');
  const counterEl = document.getElementById('progress-counter');
  const bar = document.getElementById('progress-bar');
  const cancelBtn = document.getElementById('cancel-conversion');

  let ws = null;
  let fallbackTimer = null;
  let totalCount = 0;
  let currentCount = 0;

  /**
   * 進捗バーを更新
   */
  function updateBar(progress, status, text) {
    if (bar) {
      bar.style.width = `${progress}%`;
      bar.setAttribute('aria-valuenow', progress);
      bar.textContent = `${progress}%`;

      // アニメーションの制御
      if (status === 'processing') {
        bar.classList.add('progress-bar-striped', 'progress-bar-animated');
      } else {
        bar.classList.remove('progress-bar-striped', 'progress-bar-animated');
      }
    }
    if (messageEl) {
      messageEl.textContent = text || status;
    }
  }

  /**
   * カウンターを更新
   */
  function updateCounter(status, images = null) {
    if (!counterEl) return;

    if (status === 'completed' && images) {
      counterEl.textContent = `${images.length} / ${totalCount} 枚`;
    } else if (status === 'processing' && totalCount > 0) {
      counterEl.textContent = `${currentCount} / ${totalCount} 枚`;
    } else if (status === 'cancelled') {
      counterEl.textContent = 'キャンセル済み';
    } else {
      counterEl.textContent = status === 'processing' ? '処理中...' : '';
    }
  }

  /**
   * 初期状態を取得（WebSocket接続前に一度取得）
   */
  async function fetchInitialStatus() {
    try {
      const data = await APIClient.get(`/api/v1/convert/${conversionId}/status/`);
      const conversion = data.conversion;

      totalCount = conversion.generation_count || 0;
      currentCount = conversion.current_count || 0;

      // 既に完了している場合は処理を終了
      if (conversion.status === 'completed') {
        handleCompleted(data.images || []);
        return false; // WebSocket接続不要
      } else if (conversion.status === 'failed') {
        handleFailed(conversion.error_message || '画像変換に失敗しました');
        return false;
      } else if (conversion.status === 'cancelled') {
        handleCancelled();
        return false;
      }

      // 進捗を初期表示
      let progress = 10;
      if (totalCount > 0) {
        const ratio = Math.min(99, Math.round((currentCount / totalCount) * 100));
        progress = Math.max(progress, ratio);
      }
      updateBar(progress, conversion.status, '接続中...');
      updateCounter(conversion.status);

      return true; // WebSocket接続を続行
    } catch (error) {
      const errorMessage = 'ステータスの取得に失敗しました';
      console.error('[Progress] Failed to fetch initial status:', error);
      updateBar(10, 'error', errorMessage);
      // エラーでもWebSocket接続を試みる（フォールバックが動作する）
      return true;
    }
  }

  /**
   * WebSocket接続を開始
   */
  function connectWebSocket() {
    if (!window.ConversionWebSocket) {
      console.warn('[Progress] ConversionWebSocket not available, falling back to polling');
      startFallbackPolling();
      return;
    }

    ws = new window.ConversionWebSocket(conversionId, {
      reconnectInterval: 3000,
      maxReconnectAttempts: 5,
      enableFallback: true,
      fallbackPollInterval: 4000,
    });

    // 進捗更新イベント
    ws.on('progress', (data) => {
      // currentCountを更新（データに含まれている場合）
      if (data.current !== undefined) {
        currentCount = data.current;
      } else if (data.currentCount !== undefined) {
        currentCount = data.currentCount;
      }
      // totalCountを更新（データに含まれている場合）
      if (data.total !== undefined) {
        totalCount = data.total;
      } else if (data.totalCount !== undefined) {
        totalCount = data.totalCount;
      }
      updateBar(data.progress, data.status, data.message);
      updateCounter(data.status);
    });

    // 完了イベント
    ws.on('completed', (data) => {
      handleCompleted(data.images || []);
    });

    // 失敗イベント
    ws.on('failed', (data) => {
      handleFailed(data.error || data.message || '画像変換に失敗しました');
    });

    // キャンセルイベント
    ws.on('cancelled', (data) => {
      handleCancelled();
    });

    // エラーイベント
    ws.on('error', (error) => {
      console.error('[Progress] WebSocket error:', error);
      // WebSocketエラーは内部で処理されるため、ユーザー通知は不要
    });

    // 接続イベント
    ws.on('connect', () => {
      console.log('[Progress] WebSocket connected');
      if (messageEl) {
        messageEl.textContent = 'リアルタイムで進捗を監視中...';
      }
    });

    // 切断イベント
    ws.on('disconnect', () => {
      console.log('[Progress] WebSocket disconnected');
    });

    ws.connect();
  }

  /**
   * フォールバック（ポーリング）を開始
   */
  function startFallbackPolling() {
    if (fallbackTimer) {
      return; // 既に開始されている
    }

    console.log('[Progress] Starting fallback polling');
    if (messageEl) {
      messageEl.textContent = 'ポーリングモードで進捗を監視中...';
    }

    fallbackTimer = setInterval(async () => {
      try {
        const data = await APIClient.get(`/api/v1/convert/${conversionId}/status/`);
        const conversion = data.conversion;

        totalCount = conversion.generation_count || 0;
        currentCount = conversion.current_count || 0;

        let progress = 10;
        if (totalCount > 0) {
          const ratio = Math.min(99, Math.round((currentCount / totalCount) * 100));
          progress = Math.max(progress, ratio);
        }
        if (conversion.status === 'completed' || conversion.status === 'failed') {
          progress = 100;
        }

        updateBar(progress, conversion.status, `ステータス: ${conversion.status}`);
        updateCounter(conversion.status, data.images);

        if (conversion.status === 'completed') {
          handleCompleted(data.images || []);
        } else if (conversion.status === 'failed') {
          handleFailed(conversion.error_message || '画像変換に失敗しました');
        } else if (conversion.status === 'cancelled') {
          handleCancelled();
        }
      } catch (error) {
        // ポーリングエラーは静かに処理（連続エラーの場合は別途対応）
        console.error('[Progress] Polling error:', error);
      }
    }, 4000);
  }

  /**
   * 完了処理
   */
  function handleCompleted(images) {
    if (ws) {
      ws.disconnect();
      ws = null;
    }
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }

    notifySuccess('画像変換が完了しました');
    updateBar(100, 'completed', '完了しました！ギャラリーへ移動します...');
    updateCounter('completed', images);

    if (cancelBtn) {
      cancelBtn.disabled = true;
    }

    setTimeout(() => {
      window.location.href = '/gallery/';
    }, 2000);
  }

  /**
   * 失敗処理
   */
  function handleFailed(errorMessage) {
    if (ws) {
      ws.disconnect();
      ws = null;
    }
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }

    notifyError(errorMessage);
    updateBar(100, 'failed', '変換に失敗しました');

    if (cancelBtn) {
      cancelBtn.disabled = true;
    }
  }

  /**
   * キャンセル処理
   */
  function handleCancelled() {
    if (ws) {
      ws.disconnect();
      ws = null;
    }
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }

    notifyWarning('変換をキャンセルしました');
    updateBar(0, 'cancelled', 'キャンセルしました');
    updateCounter('cancelled');

    if (cancelBtn) {
      cancelBtn.disabled = true;
    }

    setTimeout(() => {
      window.location.href = '/';
    }, 1500);
  }

  /**
   * 変換をキャンセル
   */
  async function cancelConversion() {
    if (cancelBtn) {
      cancelBtn.disabled = true;
    }

    try {
      await APIClient.post(`/api/v1/convert/${conversionId}/cancel/`, {});
      notifyWarning('変換をキャンセルしました');
      
      if (ws) {
        ws.disconnect();
        ws = null;
      }
      if (fallbackTimer) {
        clearInterval(fallbackTimer);
        fallbackTimer = null;
      }

      setTimeout(() => {
        window.location.href = '/';
      }, 1500);
    } catch (error) {
      const errorMessage = 'キャンセル処理に失敗しました';
      console.error('[Progress] Failed to cancel conversion:', error);
      notifyError(errorMessage);
      if (cancelBtn) {
        cancelBtn.disabled = false;
      }
    }
  }

  /**
   * 初期化
   */
  document.addEventListener('DOMContentLoaded', async () => {
    // 初期状態を取得
    const shouldConnect = await fetchInitialStatus();

    if (shouldConnect) {
      // WebSocket接続を開始
      connectWebSocket();
    }

    // キャンセルボタンのイベントリスナー
    if (cancelBtn) {
      cancelBtn.addEventListener('click', cancelConversion);
    }

    // ページ離脱時に接続を閉じる
    window.addEventListener('beforeunload', () => {
      if (ws) {
        ws.disconnect();
      }
      if (fallbackTimer) {
        clearInterval(fallbackTimer);
      }
    });
  });
})();
