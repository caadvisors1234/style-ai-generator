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

  const statusPhaseEl = document.getElementById('status-phase');
  const messageEl = document.getElementById('progress-message');
  const counterEl = document.getElementById('progress-counter');
  const bar = document.getElementById('progress-bar');
  const cancelBtn = document.getElementById('cancel-conversion');
  const tipsTextEl = document.getElementById('tips-text');

  let ws = null;
  let fallbackTimer = null;
  let tipsTimer = null;
  let totalCount = 0;
  let currentCount = 0;
  let fallbackNotified = false;

  // 定数定義
  const PHASES = [
    { threshold: 0, text: '準備中...', sub: 'システムを初期化しています' },
    { threshold: 10, text: '画像解析中...', sub: 'アップロードされた画像を分析しています' },
    { threshold: 30, text: 'AI生成開始', sub: '最適なパラメータを計算中' },
    { threshold: 50, text: 'スタイル適用中...', sub: 'ディテールを描き込んでいます' },
    { threshold: 80, text: '仕上げ中...', sub: '高画質化処理を行っています' },
    { threshold: 100, text: '完了', sub: 'ギャラリーへ移動します' }
  ];

  const TIPS = [
    'AIは画像構図を維持しながらスタイルを適用します。',
    '「上位モデル」を使用すると、より高精細な結果が得られます。',
    '気に入った結果はギャラリーからダウンロードできます。',
    'プロンプトに具体的な指示を含めると、意図が伝わりやすくなります。',
    '変換時間は画像の複雑さやモデルによって異なります。',
    '複数の画像を一度にアップロードして一括変換も可能です。',
    '生成された画像の明るさやコントラストは後から調整できます。'
  ];

  /**
   * 進捗状況に応じたフェーズテキストを取得
   */
  function getPhaseInfo(progress) {
    for (let i = PHASES.length - 1; i >= 0; i--) {
      if (progress >= PHASES[i].threshold) {
        return PHASES[i];
      }
    }
    return PHASES[0];
  }

  /**
   * Tipsをローテーション表示
   */
  function startTipsRotation() {
    if (tipsTimer) clearInterval(tipsTimer);

    // 初回ランダム
    if (tipsTextEl) {
      tipsTextEl.textContent = TIPS[Math.floor(Math.random() * TIPS.length)];
    }

    tipsTimer = setInterval(() => {
      if (!tipsTextEl) return;

      // フェードアウト
      tipsTextEl.style.opacity = '0';
      tipsTextEl.style.transform = 'translateY(5px)';

      setTimeout(() => {
        // テキスト変更
        const randomTip = TIPS[Math.floor(Math.random() * TIPS.length)];
        tipsTextEl.textContent = randomTip;

        // フェードイン
        tipsTextEl.style.opacity = '1';
        tipsTextEl.style.transform = 'translateY(0)';
      }, 300); // CSS transitionと合わせる
    }, 5000);
  }

  /**
   * 進捗バーとステータスを更新
   */
  function updateBar(progress, status, text) {
    if (bar) {
      bar.style.width = `${progress}%`;
      // bar.textContentは削除（デザイン変更のため）
    }

    // フェーズ情報の更新
    const phase = getPhaseInfo(progress);

    if (statusPhaseEl) {
      if (status === 'completed') {
        statusPhaseEl.textContent = '変換完了';
        statusPhaseEl.style.color = 'var(--success-text)';
      } else if (status === 'failed') {
        statusPhaseEl.textContent = '変換失敗';
        statusPhaseEl.style.color = 'var(--danger-text)';
      } else if (status === 'cancelled') {
        statusPhaseEl.textContent = 'キャンセル済み';
        statusPhaseEl.style.color = 'var(--text-muted)';
      } else {
        statusPhaseEl.textContent = phase.text;
        statusPhaseEl.style.color = 'var(--text-primary)';
      }
    }

    if (messageEl) {
      if (text) {
        messageEl.textContent = text;
      } else {
        // テキスト未指定時はフェーズのサブテキストを優先
        messageEl.textContent = phase.sub || status;
      }
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
      let progress = 5; // 初期値少し上げる
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
      updateBar(5, 'error', errorMessage);
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

      if (data.fallback && !fallbackNotified) {
        const requested = data.requested_model || '指定モデル';
        const used = data.used_model || '利用モデル';
        const refund = data.refund ?? null;
        const refundText = refund && refund > 0 ? `（返金 ${refund} クレジット）` : '';
        notifyWarning(`${requested} が利用できなかったため ${used} にフォールバックしました。消費クレジットを再計算しました${refundText}`);
        fallbackNotified = true;
      }

      updateBar(data.progress, data.status, data.message);
      updateCounter(data.status);
    });

    // 完了イベント
    ws.on('completed', (data) => {
      handleCompleted(data.images || [], data.success_count, data.requested_count);
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
      // メッセージはupdateBarで管理するためここでは更新しない
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

        if (conversion.fallback && !fallbackNotified) {
          const requested = conversion.fallback.requested_model || '指定モデル';
          const used = conversion.fallback.used_model || conversion.fallback.model_used || '利用モデル';
          const refund = conversion.fallback.refund ?? null;
          const refundText = refund && refund > 0 ? `（返金 ${refund} クレジット）` : '';
          notifyWarning(`${requested} が利用できなかったため ${used} にフォールバックしました。消費クレジットを再計算しました${refundText}`);
          fallbackNotified = true;
        }

        let progress = 5;
        if (totalCount > 0) {
          const ratio = Math.min(99, Math.round((currentCount / totalCount) * 100));
          progress = Math.max(progress, ratio);
        }
        if (conversion.status === 'completed' || conversion.status === 'failed') {
          progress = 100;
        }

        updateBar(progress, conversion.status, null); // メッセージは自動フェーズ判定
        updateCounter(conversion.status, data.images);

        if (conversion.status === 'completed') {
          handleCompleted(data.images || []);
        } else if (conversion.status === 'failed') {
          handleFailed(conversion.error_message || '画像変換に失敗しました');
        } else if (conversion.status === 'cancelled') {
          handleCancelled();
        }
      } catch (error) {
        // ポーリングエラーは静かに処理
        console.error('[Progress] Polling error:', error);
      }
    }, 4000);
  }

  /**
   * 完了処理
   */

  function handleCompleted(images, successCount = null, requestedCount = null) {
    if (ws) {
      ws.disconnect();
      ws = null;
    }
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }
    if (tipsTimer) {
      clearInterval(tipsTimer);
    }

    // 部分的成功のチェック (images.length vs requestedCount)
    // imagesが渡されない場合もあるため、その場合はimages.lengthを使用
    const actualSuccess = successCount !== null ? successCount : (images ? images.length : 0);
    // requestedCountは引数で来ない場合、グローバルのtotalCountを使用
    const targetCount = requestedCount !== null ? requestedCount : totalCount;

    // 全て失敗した場合（0枚成功）
    if (targetCount > 0 && actualSuccess === 0) {
      notifyError(`画像生成に失敗しました（${targetCount}枚すべて失敗）`);
      updateBar(100, 'failed', '画像が生成されませんでした');
      if (cancelBtn) {
        cancelBtn.disabled = true;
      }
      return; // リダイレクトせずに終了
    }

    // 部分的成功の場合
    if (targetCount > 0 && actualSuccess < targetCount) {
      notifyWarning(`完了しましたが、${targetCount}枚中${actualSuccess}枚のみ生成されました。`);
    } else {
      notifySuccess('画像変換が完了しました');
    }

    updateBar(100, 'completed', '完了しました！ギャラリーへ移動します...');
    updateCounter('completed', images);

    if (cancelBtn) {
      cancelBtn.disabled = true;
    }

    // 即時リダイレクトせず、少し待機して余韻を残す
    setTimeout(() => {
      window.location.href = '/gallery/';
    }, 1500); // 1.5秒待機
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
    if (tipsTimer) {
      clearInterval(tipsTimer);
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
    if (tipsTimer) {
      clearInterval(tipsTimer);
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
      if (tipsTimer) {
        clearInterval(tipsTimer);
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
    // Tipsローテーション開始
    startTipsRotation();

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
      if (tipsTimer) {
        clearInterval(tipsTimer);
      }
    });
  });
})();
