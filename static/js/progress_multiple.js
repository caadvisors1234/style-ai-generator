/**
 * 複数画像変換進捗表示（WebSocket対応）
 * 複数の変換を同時にWebSocketでリアルタイム監視
 */
(() => {
  'use strict';

  if (!conversionIds || !conversionIds.length) {
    const errorMessage = '変換IDが指定されていません';
    console.error('[ProgressMultiple]', errorMessage);
    notifyError(errorMessage);
    setTimeout(() => (window.location.href = '/'), 2000);
    return;
  }

  const container = document.getElementById('conversion-items');
  const template = document.getElementById('conversion-item-template');
  const overallBar = document.getElementById('overall-progress-bar');
  const overallCounter = document.getElementById('overall-counter');
  const overallMessage = document.getElementById('overall-message');
  const overallStatusPhaseEl = document.getElementById('overall-status-phase');
  const cancelBtn = document.getElementById('cancel-all-conversions');
  const tipsTextEl = document.getElementById('tips-text');

  if (!container || !template || !overallBar || !overallCounter || !overallMessage) {
    const errorMessage = '必要な要素が見つかりません';
    console.error('[ProgressMultiple]', errorMessage);
    notifyError(errorMessage);
    return;
  }

  const conversions = {};
  let wsManager = null;
  let fallbackTimer = null;
  let tipsTimer = null;
  const ACTIVE_STATUSES = new Set(['pending', 'processing']);

  // 定数定義
  const PHASES = [
    { threshold: 0, text: '準備中...', sub: 'システムを初期化しています' },
    { threshold: 10, text: '並列処理中...', sub: '複数の画像を同時に処理しています' },
    { threshold: 30, text: 'AI生成進行中', sub: '最適なパラメータを計算中' },
    { threshold: 50, text: 'スタイル適用中...', sub: 'ディテールを描き込んでいます' },
    { threshold: 80, text: '仕上げ中...', sub: '最終調整を行っています' },
    { threshold: 100, text: '完了', sub: 'ギャラリーへ移動します' }
  ];

  const TIPS = [
    '複数の画像を一度に処理することで、時間を効率的に使えます。',
    '完了した画像から順次ギャラリーに保存されます。',
    'AIは各画像の特性に合わせて最適な変換を行います。',
    '大量の変換を行う場合は、少し時間がかかることがあります。',
    'ブラウザを閉じても、サーバー側で処理は継続されます。',
    '「キャンセル」を押すと、まだ開始していない処理は停止します。'
  ];

  function getPhaseInfo(progress) {
    for (let i = PHASES.length - 1; i >= 0; i--) {
      if (progress >= PHASES[i].threshold) {
        return PHASES[i];
      }
    }
    return PHASES[0];
  }

  function startTipsRotation() {
    if (tipsTimer) clearInterval(tipsTimer);
    
    if (tipsTextEl) {
      tipsTextEl.textContent = TIPS[Math.floor(Math.random() * TIPS.length)];
    }

    tipsTimer = setInterval(() => {
      if (!tipsTextEl) return;
      
      tipsTextEl.style.opacity = '0';
      tipsTextEl.style.transform = 'translateY(5px)';
      
      setTimeout(() => {
        const randomTip = TIPS[Math.floor(Math.random() * TIPS.length)];
        tipsTextEl.textContent = randomTip;
        tipsTextEl.style.opacity = '1';
        tipsTextEl.style.transform = 'translateY(0)';
      }, 300);
    }, 5000);
  }

  function hasActiveConversions() {
    return Object.values(conversions).some((conversion) => ACTIVE_STATUSES.has(conversion.status));
  }

  function setCancelButtonState(forceDisabled = false) {
    if (!cancelBtn) return;
    if (forceDisabled) {
      cancelBtn.disabled = true;
      return;
    }
    cancelBtn.disabled = !hasActiveConversions();
  }

  function initializeConversionCards() {
    container.innerHTML = '';
    conversionIds.forEach((id, index) => {
      const node = template.content.cloneNode(true);
      const card = node.querySelector('.conversion-card');
      card.dataset.conversionId = id;

      node.querySelector('.conversion-title').textContent = `変換 #${index + 1}`;
      node.querySelector('.conversion-prompt').textContent = '読み込み中...';
      
      // ステータス初期化
      const dot = node.querySelector('.conversion-status-dot');
      const text = node.querySelector('.conversion-status-text');
      dot.className = 'conversion-status-dot status-dot-pending';
      text.textContent = '待機中';
      
      node.querySelector('.conversion-counter').textContent = '0 / 0';

      container.appendChild(node);

      conversions[id] = {
        id,
        status: 'pending',
        progress: 0,
        current: 0,
        total: 0,
        prompt: '',
        error: null,
      };
    });

    setCancelButtonState();
  }

  function updateConversionCard(id, data) {
    const card = container.querySelector(`[data-conversion-id="${id}"]`);
    if (!card) return;

    const conversion = data.conversion;
    const total = conversion.generation_count || 0;
    const current = conversion.current_count || 0;

    let progress = 5;
    if (total > 0) {
      const ratio = Math.min(99, Math.round((current / total) * 100));
      progress = Math.max(progress, ratio);
    }
    if (conversion.status === 'completed' || conversion.status === 'failed') {
      progress = 100;
    } else if (conversion.status === 'cancelled') {
      progress = 0;
    }

    const progressBar = card.querySelector('.conversion-progress-bar');
    if (progressBar) {
      // アニメーションクラスはCSSで制御（色など）
      progressBar.style.width = `${progress}%`;
      progressBar.setAttribute('aria-valuenow', progress);
    }

    // ステータス表示更新
    const dot = card.querySelector('.conversion-status-dot');
    const statusText = card.querySelector('.conversion-status-text');
    
    // クラスリセット
    if (dot) dot.className = 'conversion-status-dot';
    
    const statusMap = {
      pending: { text: '待機中', class: 'status-dot-pending' },
      processing: { text: '処理中', class: 'status-dot-processing' },
      completed: { text: '完了', class: 'status-dot-completed' },
      failed: { text: '失敗', class: 'status-dot-failed' },
      cancelled: { text: 'キャンセル', class: 'status-dot-pending' },
    };

    const info = statusMap[conversion.status] || statusMap.pending;
    if (dot) dot.classList.add(info.class);
    if (statusText) statusText.textContent = info.text;

    const counter = card.querySelector('.conversion-counter');
    if (counter) {
      if (conversion.status === 'completed' && data.images) {
        counter.textContent = `${data.images.length} / ${total}`;
      } else if (conversion.status === 'processing' && total > 0) {
        counter.textContent = `${current} / ${total}`;
      } else if (conversion.status === 'cancelled') {
        counter.textContent = '- / -';
      } else {
        counter.textContent = conversion.status === 'processing' ? '...' : '0 / 0';
      }
    }

    const promptEl = card.querySelector('.conversion-prompt');
    if (promptEl && conversion.prompt && promptEl.textContent === '読み込み中...') {
      promptEl.textContent = conversion.prompt;
      promptEl.title = conversion.prompt; // ツールチップ
    }

    conversions[id] = {
      id,
      status: conversion.status,
      progress,
      current,
      total,
      prompt: conversion.prompt || '',
      error: conversion.error_message || null,
    };
  }

  function updateOverallProgress() {
    const total = conversionIds.length;
    const list = Object.values(conversions);
    const completed = list.filter((c) => c.status === 'completed').length;
    const failed = list.filter((c) => c.status === 'failed').length;
    const cancelled = list.filter((c) => c.status === 'cancelled').length;
    const processing = list.filter((c) => c.status === 'processing').length;
    const finished = completed + failed + cancelled;
    
    // 全体の進捗率計算
    // 各変換の進捗率の平均をとる
    const totalProgressSum = list.reduce((sum, c) => sum + c.progress, 0);
    const overallPercent = total > 0 ? Math.round(totalProgressSum / total) : 0;

    overallBar.style.width = `${overallPercent}%`;
    overallBar.setAttribute('aria-valuenow', overallPercent);

    // フェーズ更新
    const phase = getPhaseInfo(overallPercent);
    if (overallStatusPhaseEl) {
      if (finished === total) {
        if (completed === total) {
          overallStatusPhaseEl.textContent = '変換完了';
          overallStatusPhaseEl.style.color = 'var(--success-text)';
        } else if (failed === total) {
          overallStatusPhaseEl.textContent = '変換失敗';
          overallStatusPhaseEl.style.color = 'var(--danger-text)';
        } else if (cancelled === total) {
          overallStatusPhaseEl.textContent = 'キャンセル済み';
          overallStatusPhaseEl.style.color = 'var(--text-muted)';
        } else {
          // 混在（成功 + 失敗/キャンセル）
          overallStatusPhaseEl.textContent = '処理完了（要確認）';
          overallStatusPhaseEl.style.color = 'var(--accent-color)';
        }
      } else {
        overallStatusPhaseEl.textContent = phase.text;
        overallStatusPhaseEl.style.color = 'var(--text-primary)';
      }
    }

    let counterText = `${completed} / ${total} 件完了`;
    if (cancelled > 0) {
      counterText += ` ・ ${cancelled}件キャンセル`;
    }
    if (failed > 0) {
      counterText += ` ・ ${failed}件失敗`;
    }
    overallCounter.textContent = counterText;

    // メッセージ更新
    if (finished === total) {
      if (completed === total) {
        overallMessage.textContent = '全ての変換が完了しました！ギャラリーへ移動します...';
      } else if (completed > 0) {
        overallMessage.textContent = '一部の変換が完了しました。ギャラリーで確認できます。';
      } else if (cancelled === total) {
        overallMessage.textContent = '全ての変換をキャンセルしました。';
      } else if (failed === total) {
        overallMessage.textContent = '全ての変換が失敗しました。';
      } else {
        overallMessage.textContent = '一部の変換がキャンセルまたは失敗しました。';
      }
    } else if (processing > 0) {
      overallMessage.textContent = phase.sub; // フェーズのサブテキストを使用
    } else if (cancelled > 0) {
      overallMessage.textContent = `${cancelled}件の変換をキャンセルしました`;
    } else if (failed > 0) {
      overallMessage.textContent = `${failed}件の変換が失敗しました`;
    }

    setCancelButtonState();

    return { completed, failed, cancelled, total, finished };
  }

  async function cancelAllConversions() {
    if (!cancelBtn) return;

    const cancellableIds = conversionIds.filter((id) => {
      const status = conversions[id]?.status;
      return ACTIVE_STATUSES.has(status || 'pending');
    });

    if (!cancellableIds.length) {
      notifyWarning('キャンセル可能な変換はありません');
      setCancelButtonState(true);
      return;
    }

    cancelBtn.disabled = true;

    try {
      const results = await Promise.allSettled(
        cancellableIds.map((id) =>
          APIClient.post(`/api/v1/convert/${id}/cancel/`, {}).then(
            (data) => ({ id, data }),
            (error) => {
              throw { id, error };
            }
          )
        )
      );

      let cancelledCount = 0;
      let alreadyFinishedCount = 0;
      let alreadyCancelledCount = 0;
      const failed = [];

      results.forEach((result) => {
        if (result.status === 'fulfilled') {
          const { data } = result.value || {};
          if (data && data.result === 'already_finished') {
            alreadyFinishedCount += 1;
          } else if (data && data.result === 'already_cancelled') {
            alreadyCancelledCount += 1;
          } else {
            cancelledCount += 1;
          }
        } else {
          failed.push(result.reason);
        }
      });

      if (cancelledCount > 0) {
        notifySuccess(`${cancelledCount}件の変換をキャンセルしました`);
      }

      if (alreadyFinishedCount > 0) {
        notifyWarning(`${alreadyFinishedCount}件の変換は既に完了していました`);
      }

      if (alreadyCancelledCount > 0) {
        notifyWarning(`${alreadyCancelledCount}件の変換は既にキャンセル済みでした`);
      }

      if (failed.length > 0) {
        const errorMessage = `${failed.length}件のキャンセルに失敗しました`;
        console.error('[ProgressMultiple] Failed to cancel conversions:', failed.map((item) => item.reason));
        notifyError(errorMessage);
      }
    } finally {
      await fetchAllStatus();
      setCancelButtonState();
    }
  }

  /**
   * 初期状態を取得（WebSocket接続前に一度取得）
   */
  async function fetchInitialStatus() {
    try {
      const promises = conversionIds.map((id) =>
        APIClient.get(`/api/v1/convert/${id}/status/`).catch((error) => {
          console.error(`[ProgressMultiple] Failed to fetch status for conversion ${id}:`, error);
          return {
            error: true,
            conversion: { id, status: 'failed', error_message: 'ステータスの取得に失敗しました' },
          };
        })
      );

      const results = await Promise.all(promises);

      results.forEach((data) => {
        if (data.conversion) {
          updateConversionCard(data.conversion.id, data);
        }
      });

      updateOverallProgress();
    } catch (error) {
      const errorMessage = '進捗の取得に失敗しました';
      console.error('[ProgressMultiple] Failed to fetch initial status:', error);
      notifyError(errorMessage);
    }
  }

  /**
   * WebSocket接続を開始
   */
  function connectWebSocket() {
    if (!window.MultipleConversionWebSocket) {
      console.warn('[ProgressMultiple] MultipleConversionWebSocket not available, falling back to polling');
      startFallbackPolling();
      return;
    }

    wsManager = new window.MultipleConversionWebSocket(conversionIds, {
      reconnectInterval: 3000,
      maxReconnectAttempts: 5,
      enableFallback: true,
      fallbackPollInterval: 4000,
    });

    // 進捗更新イベント
    wsManager.on('progress', ({ conversionId, progress, status, message, current, currentCount, total, totalCount }) => {
      // 変換データを更新
      if (conversions[conversionId]) {
        conversions[conversionId].status = status;
        conversions[conversionId].progress = progress;
        // currentを更新（データに含まれている場合）
        if (current !== undefined) {
          conversions[conversionId].current = current;
        } else if (currentCount !== undefined) {
          conversions[conversionId].current = currentCount;
        }
        // totalを更新（データに含まれている場合）
        if (total !== undefined) {
          conversions[conversionId].total = total;
        } else if (totalCount !== undefined) {
          conversions[conversionId].total = totalCount;
        }
        
        // カード更新用のダミーデータ構造作成
        const dummyData = {
            conversion: {
                id: conversionId,
                status: status,
                prompt: conversions[conversionId].prompt,
                current_count: conversions[conversionId].current,
                generation_count: conversions[conversionId].total
            }
        };
        updateConversionCard(conversionId, dummyData);
      }
      
      updateOverallProgress();
    });

    // 完了イベント
    wsManager.on('completed', ({ conversionId, images }) => {
      // ステータスAPIを呼び出して最新情報を取得
      APIClient.get(`/api/v1/convert/${conversionId}/status/`)
        .then((data) => {
          updateConversionCard(conversionId, data);
          checkAllFinished();
        })
        .catch((error) => {
          console.error(`[ProgressMultiple] Failed to fetch completion status for conversion ${conversionId}:`, error);
          // エラー時もカードを更新して続行
          checkAllFinished();
        });
    });

    // 失敗イベント
    wsManager.on('failed', ({ conversionId, error }) => {
      // ステータスAPIを呼び出して最新情報を取得
      APIClient.get(`/api/v1/convert/${conversionId}/status/`)
        .then((data) => {
          updateConversionCard(conversionId, data);
          checkAllFinished();
        })
        .catch((err) => {
          console.error(`[ProgressMultiple] Failed to fetch failure status for conversion ${conversionId}:`, err);
          // エラー時もカードを更新して続行
          checkAllFinished();
        });
    });

    // キャンセルイベント
    wsManager.on('cancelled', ({ conversionId }) => {
      // ステータスAPIを呼び出して最新情報を取得
      APIClient.get(`/api/v1/convert/${conversionId}/status/`)
        .then((data) => {
          updateConversionCard(conversionId, data);
          checkAllFinished();
        })
        .catch((err) => {
          console.error(`[ProgressMultiple] Failed to fetch cancellation status for conversion ${conversionId}:`, err);
          // エラー時もカードを更新して続行
          checkAllFinished();
        });
    });

    wsManager.connect();
  }

  /**
   * フォールバック（ポーリング）を開始
   */
  function startFallbackPolling() {
    if (fallbackTimer) {
      return; // 既に開始されている
    }

    console.log('[ProgressMultiple] Starting fallback polling for multiple conversions');
    if (overallMessage) {
      overallMessage.textContent = 'ポーリングモードで進捗を監視中...';
    }

    fallbackTimer = setInterval(async () => {
      await fetchAllStatus();
    }, 4000);
  }

  /**
   * 全ての変換のステータスを取得（フォールバック用）
   */
  async function fetchAllStatus() {
    try {
      const promises = conversionIds.map((id) =>
        APIClient.get(`/api/v1/convert/${id}/status/`).catch((error) => {
          console.error(`[ProgressMultiple] Failed to fetch status for conversion ${id}:`, error);
          return {
            error: true,
            conversion: { id, status: 'failed', error_message: 'ステータスの取得に失敗しました' },
          };
        })
      );

      const results = await Promise.all(promises);

      results.forEach((data) => {
        if (data.conversion) {
          updateConversionCard(data.conversion.id, data);
        }
      });

      checkAllFinished();
    } catch (error) {
      const errorMessage = '進捗の取得に失敗しました';
      console.error('[ProgressMultiple] Failed to fetch conversion status:', error);
      notifyError(errorMessage);
      setCancelButtonState();
    }
  }

  /**
   * 全ての変換が完了したかチェック
   */
  function checkAllFinished() {
    const { completed, failed, cancelled, total, finished } = updateOverallProgress();

    if (finished === total) {
      if (wsManager) {
        wsManager.disconnect();
        wsManager = null;
      }
      if (fallbackTimer) {
        clearInterval(fallbackTimer);
        fallbackTimer = null;
      }
      if (tipsTimer) {
        clearInterval(tipsTimer);
      }

      setCancelButtonState(true);

      if (completed > 0) {
        const summary = [];
        if (cancelled > 0) summary.push(`${cancelled}件キャンセル`);
        if (failed > 0) summary.push(`${failed}件失敗`);

        if (summary.length) {
          notifyWarning(`${completed}件完了 (${summary.join('・')})`);
        } else {
          notifySuccess(`${completed}件の変換が完了しました`);
        }

        setTimeout(() => {
          window.location.href = '/gallery/';
        }, 2000);
      } else if (cancelled === total) {
        notifyWarning('全ての変換をキャンセルしました');
        setTimeout(() => {
          window.location.href = '/';
        }, 1500);
      } else if (failed === total) {
        notifyError('全ての変換が失敗しました');
        setTimeout(() => {
          window.location.href = '/';
        }, 3000);
      } else {
        notifyWarning(`キャンセル: ${cancelled}件 / 失敗: ${failed}件`);
        setTimeout(() => {
          window.location.href = '/';
        }, 2000);
      }
    }
  }

  /**
   * 初期化
   */
  document.addEventListener('DOMContentLoaded', async () => {
    initializeConversionCards();
    
    // Tipsローテーション開始
    startTipsRotation();
    
    // 初期状態を取得
    await fetchInitialStatus();

    // WebSocket接続を開始
    connectWebSocket();

    // キャンセルボタンのイベントリスナー
    if (cancelBtn) {
      cancelBtn.addEventListener('click', cancelAllConversions);
    }

    // ページ離脱時に接続を閉じる
    window.addEventListener('beforeunload', () => {
      if (wsManager) {
        wsManager.disconnect();
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
