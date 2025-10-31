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
      const node = template.content.cloneNode(true);
      node.querySelector('.gallery-thumb').src = conversion.generated_images[0]?.image_url || conversion.original_image_url;
      node.querySelector('.gallery-title').textContent = conversion.prompt || '（プロンプト未設定）';
      const createdAt = new Date(conversion.created_at);
      node.querySelector('.gallery-date').textContent = createdAt.toLocaleString('ja-JP');
      node.querySelector('.view-detail').dataset.conversionId = conversion.id;
      node.querySelector('.view-detail').dataset.imageId = conversion.generated_images[0]?.id || '';
      grid.appendChild(node);
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

  async function loadGallery() {
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
    } catch (error) {
      notifyError('ギャラリーの読み込みに失敗しました');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadGallery();

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
