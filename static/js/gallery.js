(() => {
  const grid = document.getElementById('gallery-grid');
  const empty = document.getElementById('gallery-empty');
  const pagination = document.getElementById('gallery-pagination');
  const searchInput = document.getElementById('gallery-search');
  const sortSelect = document.getElementById('gallery-sort');
  const perPageSelect = document.getElementById('gallery-per-page');
  const template = document.getElementById('gallery-card-template');

  if (!grid || !template) return;

  const state = {
    page: 1,
    perPage: Number(perPageSelect ? perPageSelect.value : 12),
    search: '',
    sort: sortSelect ? sortSelect.value : 'created_at_desc',
  };

  function renderCards(conversions) {
    grid.innerHTML = '';
    if (!conversions.length) {
      empty.classList.remove('d-none');
      return;
    }
    empty.classList.add('d-none');

    conversions.forEach((conversion) => {
      // 生成画像が複数ある場合は、それぞれカードを作成
      const generatedImages = conversion.generated_images || [];
      const displayTitle = conversion.preset_name || conversion.prompt || '（指示なし）';

      if (generatedImages.length === 0) {
        // 生成画像がない場合（処理中など）は元画像を表示
        const node = template.content.cloneNode(true);
        node.querySelector('.gallery-thumb').src = conversion.original_image_url;

        // 処理中の場合は状態を表示
        let titleText = displayTitle;
        if (conversion.status === 'processing') {
          titleText = '⏳ 処理中... - ' + titleText;
        } else if (conversion.status === 'pending') {
          titleText = '⏱️ 待機中... - ' + titleText;
        } else if (conversion.status === 'failed') {
          titleText = '❌ 失敗 - ' + titleText;
        }

        node.querySelector('.gallery-title').textContent = titleText;
        const createdAt = new Date(conversion.created_at);
        node.querySelector('.gallery-date').textContent = createdAt.toLocaleString('ja-JP');
        node.querySelector('.view-detail').dataset.conversionId = conversion.id;
        node.querySelector('.view-detail').dataset.imageId = '';

        // 処理中の場合は詳細ボタンを無効化
        if (conversion.status === 'processing' || conversion.status === 'pending') {
          const detailBtn = node.querySelector('.view-detail');
          detailBtn.disabled = true;
          detailBtn.textContent = '処理中...';
        }

        grid.appendChild(node);
      } else {
        // 生成画像ごとにカードを作成
        generatedImages.forEach((image, index) => {
          const node = template.content.cloneNode(true);
          node.querySelector('.gallery-thumb').src = image.image_url;
          const promptText = displayTitle;
          const suffix = generatedImages.length > 1 ? ` (${index + 1}/${generatedImages.length})` : '';
          node.querySelector('.gallery-title').textContent = promptText + suffix;
          const createdAt = new Date(image.created_at);
          node.querySelector('.gallery-date').textContent = createdAt.toLocaleString('ja-JP');
          node.querySelector('.view-detail').dataset.conversionId = conversion.id;
          node.querySelector('.view-detail').dataset.imageId = image.id;
          grid.appendChild(node);
        });
      }
    });
  }

  function renderPagination(meta) {
    pagination.innerHTML = '';
    if (meta.total_pages <= 1) return;

    for (let i = 1; i <= meta.total_pages; i += 1) {
      const item = document.createElement('li');
      item.className = `page-item ${i === meta.current_page ? 'active' : ''}`;
      const link = document.createElement('a');
      link.className = 'page-link';
      link.href = '#';
      link.dataset.page = i;
      link.textContent = i;
      item.appendChild(link);
      pagination.appendChild(item);
    }
  }

  let autoReloadTimer = null;

  async function loadGallery(checkProcessing = false) {
    try {
      const params = new URLSearchParams({
        page: state.page,
        per_page: state.perPage,
        sort: state.sort,
      });
      if (state.search) {
        params.append('search', state.search);
      }

      const data = await APIClient.get(`/api/v1/gallery/?${params.toString()}`);
      renderCards(data.conversions);
      renderPagination(data.pagination);

      // 処理中の変換があるかチェック
      if (checkProcessing) {
        const hasProcessing = data.conversions.some(c => c.status === 'processing' || c.status === 'pending');

        if (hasProcessing) {
          // 処理中の変換がある場合、5秒後に自動リロード
          if (autoReloadTimer) clearTimeout(autoReloadTimer);
          autoReloadTimer = setTimeout(() => loadGallery(true), 5000);
        } else {
          // 全て完了したらタイマーをクリア
          if (autoReloadTimer) {
            clearTimeout(autoReloadTimer);
            autoReloadTimer = null;
          }
        }
      }
    } catch (error) {
      notifyError('ギャラリーの読み込みに失敗しました');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    // 初回読み込み時は自動リロードを有効化（処理中の変換がある可能性があるため）
    loadGallery(true);

    if (searchInput) {
      searchInput.addEventListener('input', () => {
        state.search = searchInput.value.trim();
        state.page = 1;
        loadGallery();
      });
    }

    if (sortSelect) {
      sortSelect.addEventListener('change', () => {
        state.sort = sortSelect.value;
        state.page = 1;
        loadGallery();
      });
    }

    if (perPageSelect) {
      perPageSelect.addEventListener('change', () => {
        state.perPage = Number(perPageSelect.value);
        state.page = 1;
        loadGallery();
      });
    }

    pagination.addEventListener('click', (event) => {
      const link = event.target.closest('.page-link');
      if (!link) return;
      event.preventDefault();
      state.page = Number(link.dataset.page);
      loadGallery();
    });

    grid.addEventListener('click', (event) => {
      const button = event.target.closest('.view-detail');
      if (!button) return;
      const conversionId = button.dataset.conversionId;
      const imageId = button.dataset.imageId;
      if (window.ImageDetail) {
        window.ImageDetail.open(conversionId, imageId);
      }
    });
  });
})();
