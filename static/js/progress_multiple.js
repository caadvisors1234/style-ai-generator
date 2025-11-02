(() => {
  if (!conversionIds || !conversionIds.length) {
    notifyError('変換IDが指定されていません');
    setTimeout(() => (window.location.href = '/'), 2000);
    return;
  }

  const container = document.getElementById('conversion-items');
  const template = document.getElementById('conversion-item-template');
  const overallBar = document.getElementById('overall-progress-bar');
  const overallCounter = document.getElementById('overall-counter');
  const overallMessage = document.getElementById('overall-message');
  const cancelBtn = document.getElementById('cancel-all-conversions');

  if (!container || !template || !overallBar || !overallCounter || !overallMessage) {
    console.error('Required elements not found');
    return;
  }

  const conversions = {};
  let timer = null;
  const ACTIVE_STATUSES = new Set(['pending', 'processing']);

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
      node.querySelector('.conversion-status-badge').textContent = '待機中';
      node.querySelector('.conversion-counter').textContent = '0 / 0 枚';

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

    let progress = 10;
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
    if (conversion.status === 'processing') {
      progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
    } else {
      progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
    }
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute('aria-valuenow', progress);
    progressBar.textContent = conversion.status === 'cancelled' ? 'キャンセル' : `${progress}%`;

    const statusBadge = card.querySelector('.conversion-status-badge');
    const statusMap = {
      pending: { text: '待機中', class: 'bg-secondary' },
      processing: { text: '処理中', class: 'bg-primary' },
      completed: { text: '完了', class: 'bg-success' },
      failed: { text: '失敗', class: 'bg-danger' },
      cancelled: { text: 'キャンセル済み', class: 'bg-secondary' },
    };
    const statusInfo = statusMap[conversion.status] || statusMap.pending;
    statusBadge.textContent = statusInfo.text;
    statusBadge.className = `badge ${statusInfo.class} conversion-status-badge`;

    const counter = card.querySelector('.conversion-counter');
    if (conversion.status === 'completed' && data.images) {
      counter.textContent = `${data.images.length} / ${total} 枚`;
    } else if (conversion.status === 'processing' && total > 0) {
      counter.textContent = `${current} / ${total} 枚`;
    } else if (conversion.status === 'cancelled') {
      counter.textContent = 'キャンセル済み';
    } else {
      counter.textContent = conversion.status === 'processing' ? '処理中...' : '';
    }

    const promptEl = card.querySelector('.conversion-prompt');
    if (conversion.prompt && promptEl.textContent === '読み込み中...') {
      promptEl.textContent = conversion.prompt;
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
    const overallPercent = total > 0 ? Math.round((finished / total) * 100) : 0;

    if (finished < total) {
      overallBar.classList.add('progress-bar-striped', 'progress-bar-animated');
    } else {
      overallBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
    }
    overallBar.style.width = `${overallPercent}%`;
    overallBar.setAttribute('aria-valuenow', overallPercent);
    overallBar.textContent = `${overallPercent}%`;

    let counterText = `${completed} / ${total} 件完了`;
    if (cancelled > 0) {
      counterText += ` ・ ${cancelled}件キャンセル`;
    }
    if (failed > 0) {
      counterText += ` ・ ${failed}件失敗`;
    }
    overallCounter.textContent = counterText;

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
      overallMessage.textContent = `${processing}件の変換を処理中...`;
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
        notifyError(`${failed.length}件のキャンセルに失敗しました`);
        console.error('Failed to cancel conversions:', failed.map((item) => item.reason));
      }
    } finally {
      await fetchAllStatus();
      setCancelButtonState();
    }
  }

  async function fetchAllStatus() {
    try {
      const promises = conversionIds.map((id) =>
        APIClient.get(`/api/v1/convert/${id}/status/`).catch(() => ({
          error: true,
          conversion: { id, status: 'failed', error_message: 'ステータスの取得に失敗' },
        }))
      );

      const results = await Promise.all(promises);

      results.forEach((data) => {
        if (data.conversion) {
          updateConversionCard(data.conversion.id, data);
        }
      });

      const { completed, failed, cancelled, total, finished } = updateOverallProgress();

      if (finished === total) {
        clearInterval(timer);
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
    } catch (error) {
      console.error('Failed to fetch conversion status:', error);
      notifyError('進捗の取得に失敗しました');
      setCancelButtonState();
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initializeConversionCards();
    fetchAllStatus();
    timer = setInterval(fetchAllStatus, 4000);

    if (cancelBtn) {
      cancelBtn.addEventListener('click', cancelAllConversions);
    }
  });
})();
