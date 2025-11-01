(() => {
  // URLパラメータから取得した変換IDは既にグローバル変数として定義済み
  if (!conversionIds || !conversionIds.length) {
    notifyError('変換IDが指定されていません');
    setTimeout(() => window.location.href = '/', 2000);
    return;
  }

  const container = document.getElementById('conversion-items');
  const template = document.getElementById('conversion-item-template');
  const overallBar = document.getElementById('overall-progress-bar');
  const overallCounter = document.getElementById('overall-counter');
  const overallMessage = document.getElementById('overall-message');

  if (!container || !template || !overallBar || !overallCounter) {
    console.error('Required elements not found');
    return;
  }

  // 各変換の状態を保持
  const conversions = {};
  let timer = null;

  // 変換カードの初期化
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
  }

  // 個別カードの更新
  function updateConversionCard(id, data) {
    const card = container.querySelector(`[data-conversion-id="${id}"]`);
    if (!card) return;

    const conversion = data.conversion;
    const total = conversion.generation_count || 0;
    const current = conversion.current_count || 0;

    // 進捗率の計算
    let progress = 10;
    if (total > 0) {
      const ratio = Math.min(99, Math.round((current / total) * 100));
      progress = Math.max(progress, ratio);
    }
    if (conversion.status === 'completed' || conversion.status === 'failed') {
      progress = 100;
    }

    // プログレスバーの更新
    const progressBar = card.querySelector('.conversion-progress-bar');
    progressBar.classList.remove('bg-success', 'bg-danger');
    progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute('aria-valuenow', progress);
    progressBar.textContent = `${progress}%`;

    // ステータスバッジの更新
    const statusBadge = card.querySelector('.conversion-status-badge');
    const statusMap = {
      pending: { text: '待機中', class: 'bg-secondary' },
      processing: { text: '処理中', class: 'bg-primary' },
      completed: { text: '完了', class: 'bg-success' },
      failed: { text: '失敗', class: 'bg-danger' },
    };
    const statusInfo = statusMap[conversion.status] || statusMap.pending;
    statusBadge.textContent = statusInfo.text;
    statusBadge.className = `badge ${statusInfo.class} conversion-status-badge`;

    // 進捗バーの色を単一画像の進捗バーと統一するため、状態による色変更は行わない

    // カウンターの更新
    const counter = card.querySelector('.conversion-counter');
    if (conversion.status === 'completed' && data.images) {
      counter.textContent = `${data.images.length} / ${total} 枚`;
    } else if (total > 0 && conversion.status === 'processing') {
      counter.textContent = `${current} / ${total} 枚`;
    } else {
      counter.textContent = conversion.status === 'processing' ? '処理中...' : '';
    }

    // プロンプトの更新（初回のみ）
    const promptEl = card.querySelector('.conversion-prompt');
    if (conversion.prompt && promptEl.textContent === '読み込み中...') {
      promptEl.textContent = conversion.prompt;
    }

    // 状態を保存
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

  // 全体の進捗を更新
  function updateOverallProgress() {
    const total = conversionIds.length;
    const completed = Object.values(conversions).filter((c) => c.status === 'completed').length;
    const failed = Object.values(conversions).filter((c) => c.status === 'failed').length;
    const processing = Object.values(conversions).filter((c) => c.status === 'processing').length;

    // 全体の進捗率
    const overallPercent = Math.round((completed / total) * 100);

    // プログレスバーの更新
    overallBar.classList.remove('bg-success', 'bg-danger');
    overallBar.classList.add('progress-bar-striped', 'progress-bar-animated');
    overallBar.style.width = `${overallPercent}%`;
    overallBar.setAttribute('aria-valuenow', overallPercent);
    overallBar.textContent = `${overallPercent}%`;

    // カウンターの更新
    overallCounter.textContent = `${completed} / ${total} 件完了`;

    // メッセージの更新
    if (completed === total) {
      overallMessage.textContent = '全ての変換が完了しました！ギャラリーへ移動します...';
    } else if (failed > 0 && completed + failed === total) {
      overallMessage.textContent = `${failed}件の変換が失敗しました`;
    } else if (processing > 0) {
      overallMessage.textContent = `${processing}件の変換を処理中...`;
    }

    return { completed, failed, total };
  }

  // 全ての変換のステータスを取得
  async function fetchAllStatus() {
    try {
      const promises = conversionIds.map((id) =>
        APIClient.get(`/api/v1/convert/${id}/status/`).catch((error) => ({
          error: true,
          conversion: { id, status: 'failed', error_message: 'ステータスの取得に失敗' },
        }))
      );

      const results = await Promise.all(promises);

      // 各カードを更新
      results.forEach((data) => {
        if (data.conversion) {
          updateConversionCard(data.conversion.id, data);
        }
      });

      // 全体の進捗を更新
      const { completed, failed, total } = updateOverallProgress();

      // 全て完了または失敗したらタイマーを停止してギャラリーへ遷移
      if (completed + failed === total) {
        clearInterval(timer);

        if (completed > 0) {
          notifySuccess(`${completed}件の変換が完了しました`);
          setTimeout(() => {
            window.location.href = '/gallery/';
          }, 2000);
        } else {
          notifyError('全ての変換が失敗しました');
          setTimeout(() => {
            window.location.href = '/';
          }, 3000);
        }
      }
    } catch (error) {
      console.error('Failed to fetch conversion status:', error);
      notifyError('進捗の取得に失敗しました');
    }
  }

  // 初期化処理
  document.addEventListener('DOMContentLoaded', () => {
    initializeConversionCards();
    fetchAllStatus();
    timer = setInterval(fetchAllStatus, 4000);
  });
})();
