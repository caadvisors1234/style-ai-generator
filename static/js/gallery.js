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
        const card = node.querySelector('.gallery-card');
        card.dataset.conversionId = conversion.id;
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
          const card = node.querySelector('.gallery-card');
          card.dataset.conversionId = conversion.id;
          card.dataset.imageId = image.id;
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

    const currentPage = meta.current_page;
    const totalPages = meta.total_pages;
    const delta = 2; // 現在のページの前後に表示するページ数

    // ページ番号の配列を生成
    const pages = [];
    
    // ページ数が少ない場合は全て表示
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // 常に最初のページを追加
      pages.push(1);
      
      // 現在のページ周辺のページを計算
      const startPage = Math.max(2, currentPage - delta);
      const endPage = Math.min(totalPages - 1, currentPage + delta);
      
      // 最初のページとstartPageの間にギャップがある場合は「...」を追加
      if (startPage > 2) {
        pages.push('ellipsis-start');
      }
      
      // 現在のページ周辺のページを追加（1とtotalPagesは除外）
      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }
      
      // endPageと最後のページの間にギャップがある場合は「...」を追加
      if (endPage < totalPages - 1) {
        pages.push('ellipsis-end');
      }
      
      // 常に最後のページを追加
      pages.push(totalPages);
    }
    
    // ページネーション要素を生成
    pages.forEach((page) => {
      if (page === 'ellipsis-start' || page === 'ellipsis-end') {
        // 省略記号を表示
        const item = document.createElement('li');
        item.className = 'page-item disabled';
        const span = document.createElement('span');
        span.className = 'page-link';
        span.textContent = '...';
        item.appendChild(span);
        pagination.appendChild(item);
      } else {
        // 通常のページ番号
        const item = document.createElement('li');
        item.className = `page-item ${page === currentPage ? 'active' : ''}`;
        const link = document.createElement('a');
        link.className = 'page-link';
        link.href = '#';
        link.dataset.page = page;
        link.textContent = page;
        item.appendChild(link);
        pagination.appendChild(item);
      }
    });
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

    window.addEventListener('imageDeleted', (event) => {
      const { imageId, conversionId } = event.detail || {};
      if (!imageId && !conversionId) return;
      const cards = grid.querySelectorAll('.gallery-card');
      cards.forEach((card) => {
        const cardImageId = card.dataset.imageId;
        const cardConversionId = card.dataset.conversionId;
        if ((imageId && cardImageId && String(cardImageId) === String(imageId)) ||
            (!imageId && conversionId && String(cardConversionId) === String(conversionId))) {
          card.classList.add('fade-out');
          setTimeout(() => {
            card.parentElement?.remove();
            const remaining = grid.querySelectorAll('.gallery-card').length;
            if (remaining === 0) {
              empty.classList.remove('d-none');
            }
          }, 250);
        }
      });
    });
  });
})();
