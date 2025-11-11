(() => {
  const containerId = 'prompt-preset-container';
  const customPromptId = 'custom-prompt';
  const categoryTabsId = 'prompt-category-tabs';
  const searchInputId = 'prompt-search-input';
  const noResultsId = 'prompt-no-results';
  const multiSelectToggleId = 'toggle-multi-select';
  const multiSelectIndicatorId = 'multi-select-indicator';
  const selectedCountId = 'selected-count';

  let selectedText = '';
  let allPrompts = [];
  let allCategories = [];
  let favoritePrompts = [];
  let recentPrompts = [];
  let currentCategory = 'all';
  let searchQuery = '';
  let tooltipInstances = [];
  let isMultiSelectMode = false;
  let selectedPresets = new Set();
  let isShowingAllPrompts = false;

  const RECENT_PROMPTS_KEY = 'recentPrompts';
  const MAX_RECENT_PROMPTS = 10;

  /**
   * 使用履歴を取得
   */
  function getRecentPrompts() {
    try {
      const stored = sessionStorage.getItem(RECENT_PROMPTS_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  }

  /**
   * 使用履歴を保存
   */
  function saveRecentPrompt(preset) {
    try {
      let recents = getRecentPrompts();
      // 既存の同じIDを削除
      recents = recents.filter((p) => p.id !== preset.id);
      // 先頭に追加
      recents.unshift({
        id: preset.id,
        name: preset.name,
        prompt: preset.prompt,
        category: preset.category,
        description: preset.description,
        timestamp: Date.now(),
      });
      // 最大数を超えたら古いものを削除
      if (recents.length > MAX_RECENT_PROMPTS) {
        recents = recents.slice(0, MAX_RECENT_PROMPTS);
      }
      sessionStorage.setItem(RECENT_PROMPTS_KEY, JSON.stringify(recents));
      recentPrompts = recents;
    } catch (error) {
      console.error('Failed to save recent prompt:', error);
    }
  }

  /**
   * お気に入り追加
   */
  async function addToFavorites(presetId) {
    try {
      const data = await APIClient.post('/api/v1/prompts/favorites/add/', {
        preset_id: presetId,
      });

      if (data.status === 'success') {
        notifySuccess(data.message);
        // プリセット一覧を再読み込み
        await loadPrompts();
      }
    } catch (error) {
      console.error('Failed to add favorite:', error);
      notifyError('お気に入り追加に失敗しました');
    }
  }

  /**
   * お気に入り削除
   */
  async function removeFromFavorites(presetId) {
    try {
      const data = await APIClient.post(
        `/api/v1/prompts/favorites/${presetId}/remove/`,
        {}
      );

      if (data.status === 'success') {
        notifySuccess(data.message);
        // プリセット一覧を再読み込み
        await loadPrompts();
      }
    } catch (error) {
      console.error('Failed to remove favorite:', error);
      notifyError('お気に入り削除に失敗しました');
    }
  }

  /**
   * お気に入り一覧を取得
   */
  async function loadFavorites() {
    try {
      const data = await APIClient.get('/api/v1/prompts/favorites/');
      favoritePrompts = data.favorites || [];
    } catch (error) {
      console.error('Failed to load favorites:', error);
      favoritePrompts = [];
    }
  }

  /**
   * プリセットボタンを生成
   */
  function renderPresetButton(preset) {
    const wrapper = document.createElement('div');
    wrapper.className = 'position-relative d-inline-block';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'prompt-preset-btn preset-button btn btn-outline-primary btn-sm';
    button.dataset.presetId = preset.id;
    button.dataset.prompt = preset.prompt;
    button.dataset.category = preset.category;
    button.dataset.description = preset.description || '';

    // 複数選択モード時のスタイル
    if (isMultiSelectMode && selectedPresets.has(preset.id)) {
      button.classList.add('active');
    }

    button.textContent = preset.name;

    // ツールチップの設定
    if (preset.description) {
      button.setAttribute('data-bs-toggle', 'tooltip');
      button.setAttribute('data-bs-placement', 'top');
      button.setAttribute('title', preset.description);
    }

    // お気に入りボタン
    if (preset.is_favorite !== undefined) {
      const favBtn = document.createElement('button');
      favBtn.type = 'button';
      favBtn.className = 'btn btn-sm position-absolute top-0 end-0 p-0 border-0 bg-transparent prompt-favorite-btn';
      favBtn.style.cssText = 'margin-top: -6px; margin-right: -6px; z-index: 10; opacity: 0.5; transition: opacity 0.2s ease;';
      favBtn.innerHTML = preset.is_favorite
        ? '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="#FFB800" class="bi bi-star-fill" viewBox="0 0 16 16"><path d="M3.612 15.443c-.386.198-.824-.149-.746-.592l.83-4.73L.173 6.765c-.329-.314-.158-.888.283-.95l4.898-.696L7.538.792c.197-.39.73-.39.927 0l2.184 4.327 4.898.696c.441.062.612.636.282.95l-3.522 3.356.83 4.73c.078.443-.36.79-.746.592L8 13.187l-4.389 2.256z"/></svg>'
        : '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="#A3A3A3" class="bi bi-star" viewBox="0 0 16 16"><path d="M2.866 14.85c-.078.444.36.791.746.593l4.39-2.256 4.389 2.256c.386.198.824-.149.746-.592l-.83-4.73 3.522-3.356c.33-.314.16-.888-.282-.95l-4.898-.696L8.465.792a.513.513 0 0 0-.927 0L5.354 5.12l-4.898.696c-.441.062-.612.636-.283.95l3.523 3.356-.83 4.73zm4.905-2.767-3.686 1.894.694-3.957a.565.565 0 0 0-.163-.505L1.71 6.745l4.052-.576a.525.525 0 0 0 .393-.288L8 2.223l1.847 3.658a.525.525 0 0 0 .393.288l4.052.575-2.906 2.77a.565.565 0 0 0-.163.506l.694 3.957-3.686-1.894a.503.503 0 0 0-.461 0z"/></svg>';
      
      // ホバー時の透明度変更
      favBtn.addEventListener('mouseenter', () => {
        favBtn.style.opacity = '1';
      });
      favBtn.addEventListener('mouseleave', () => {
        favBtn.style.opacity = '0.5';
      });

      favBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (preset.is_favorite) {
          await removeFromFavorites(preset.id);
        } else {
          await addToFavorites(preset.id);
        }
      });

      wrapper.appendChild(favBtn);
    }

    wrapper.appendChild(button);
    return wrapper;
  }

  /**
   * カテゴリタブを生成
   */
  function renderCategoryTabs(categories) {
    const tabsContainer = document.getElementById(categoryTabsId);
    if (!tabsContainer) return;

    // 固定タブ（すべて、お気に入り、最近使用）を保持
    const fixedTabs = ['tab-all', 'tab-favorites', 'tab-recent'];
    const fixedElements = fixedTabs
      .map((id) => tabsContainer.querySelector(`#${id}`)?.parentElement)
      .filter(Boolean);

    tabsContainer.innerHTML = '';
    fixedElements.forEach((el) => tabsContainer.appendChild(el));

    // カテゴリタブを追加
    categories.forEach((category) => {
      const li = document.createElement('li');
      li.className = 'nav-item';
      li.setAttribute('role', 'presentation');

      const button = document.createElement('button');
      button.className = 'nav-link';
      button.id = `tab-${category.value}`;
      button.dataset.category = category.value;
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.textContent = `${category.label} (${category.count})`;

      li.appendChild(button);
      tabsContainer.appendChild(li);
    });
  }

  /**
   * カテゴリタブクリックハンドラ
   */
  function handleCategoryTabClick(event) {
    const target = event.target.closest('button[data-category]');
    if (!target) return;

    // アクティブタブの切り替え
    document.querySelectorAll('#prompt-category-tabs .nav-link').forEach((btn) => {
      btn.classList.remove('active');
    });
    target.classList.add('active');

    // カテゴリフィルタを更新
    currentCategory = target.dataset.category;
    isShowingAllPrompts = false; // カテゴリ変更時に表示状態をリセット
    filterAndRenderPrompts();
  }

  /**
   * プリセットクリックハンドラ
   */
  function handlePresetClick(event) {
    const target = event.target.closest('.preset-button');
    if (!target) return;

    const presetId = parseInt(target.dataset.presetId);
    const preset = allPrompts.find((p) => p.id === presetId);

    if (isMultiSelectMode) {
      // 複数選択モード
      if (selectedPresets.has(presetId)) {
        selectedPresets.delete(presetId);
        target.classList.remove('active');
      } else {
        selectedPresets.add(presetId);
        target.classList.add('active');
      }
      updateMultiSelectIndicator();
      updateCombinedPrompt();
    } else {
      // 単一選択モード
      selectedText = target.dataset.prompt;
      document.querySelectorAll('.preset-button').forEach((btn) => btn.classList.remove('active'));
      target.classList.add('active');

      const promptArea = document.getElementById(customPromptId);
      if (promptArea) {
        promptArea.value = selectedText;
      }

      // 使用履歴に追加
      if (preset) {
        saveRecentPrompt(preset);
      }
    }
  }

  /**
   * 複数選択モード切り替え
   */
  function toggleMultiSelectMode() {
    isMultiSelectMode = !isMultiSelectMode;
    selectedPresets.clear();

    const toggleBtn = document.getElementById(multiSelectToggleId);
    const indicator = document.getElementById(multiSelectIndicatorId);

    if (isMultiSelectMode) {
      toggleBtn.classList.add('active');
      indicator.style.display = 'inline';
    } else {
      toggleBtn.classList.remove('active');
      indicator.style.display = 'none';
    }

    updateMultiSelectIndicator();
    filterAndRenderPrompts();
  }

  /**
   * 複数選択インジケータ更新
   */
  function updateMultiSelectIndicator() {
    const countEl = document.getElementById(selectedCountId);
    if (countEl) {
      countEl.textContent = selectedPresets.size;
    }
  }

  /**
   * 複数選択したプロンプトを結合
   */
  function updateCombinedPrompt() {
    if (!isMultiSelectMode || selectedPresets.size === 0) return;

    const selectedPromptTexts = Array.from(selectedPresets)
      .map((id) => {
        const preset = allPrompts.find((p) => p.id === id);
        return preset ? preset.prompt : null;
      })
      .filter(Boolean);

    const combinedPrompt = selectedPromptTexts.join(' ');
    const promptArea = document.getElementById(customPromptId);
    if (promptArea) {
      promptArea.value = combinedPrompt;
    }
  }

  /**
   * 検索入力ハンドラ
   */
  function handleSearchInput(event) {
    searchQuery = event.target.value.trim().toLowerCase();
    // 検索時は全件表示
    isShowingAllPrompts = searchQuery.length > 0;
    filterAndRenderPrompts();
  }

  /**
   * 「もっと見る」ボタンを生成
   */
  function renderShowMoreButton() {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline-secondary btn-sm';
    button.textContent = 'もっと見る';
    button.id = 'show-more-prompts-btn';
    button.addEventListener('click', () => {
      isShowingAllPrompts = true;
      filterAndRenderPrompts();
    });
    return button;
  }

  /**
   * プリセットをフィルタリングして表示
   */
  function filterAndRenderPrompts() {
    const container = document.getElementById(containerId);
    const noResultsEl = document.getElementById(noResultsId);
    if (!container) return;

    // 既存のツールチップを破棄
    tooltipInstances.forEach((tooltip) => tooltip.dispose());
    tooltipInstances = [];

    // カテゴリが変更された場合は表示状態をリセット
    const previousCategory = container.dataset.currentCategory;
    if (previousCategory !== currentCategory) {
      isShowingAllPrompts = false;
    }
    container.dataset.currentCategory = currentCategory;

    // フィルタリング
    let filteredPrompts = [];

    if (currentCategory === 'favorites') {
      // お気に入りタブ
      filteredPrompts = allPrompts.filter((p) => p.is_favorite);
    } else if (currentCategory === 'recent') {
      // 最近使用タブ
      const recentIds = recentPrompts.map((r) => r.id);
      filteredPrompts = allPrompts.filter((p) => recentIds.includes(p.id));
      // 最近使用順にソート
      filteredPrompts.sort((a, b) => {
        return recentIds.indexOf(a.id) - recentIds.indexOf(b.id);
      });
    } else {
      // 通常のカテゴリフィルタ
      filteredPrompts = allPrompts;
      if (currentCategory !== 'all') {
        filteredPrompts = filteredPrompts.filter((p) => p.category === currentCategory);
      }
    }

    // 検索フィルタ
    if (searchQuery) {
      filteredPrompts = filteredPrompts.filter((p) => {
        const nameMatch = p.name.toLowerCase().includes(searchQuery);
        const descMatch = (p.description || '').toLowerCase().includes(searchQuery);
        return nameMatch || descMatch;
      });
      // 検索時は常に全件表示
      isShowingAllPrompts = true;
    }
    // 検索クエリが空の場合は、isShowingAllPromptsの状態を維持
    // （カテゴリ変更時は既にリセットされている）

    // 表示件数の制限（5件を超える場合、かつ全件表示フラグがfalseの場合）
    const MAX_INITIAL_DISPLAY = 5;
    const shouldLimitDisplay = !isShowingAllPrompts && filteredPrompts.length > MAX_INITIAL_DISPLAY;
    const displayPrompts = shouldLimitDisplay
      ? filteredPrompts.slice(0, MAX_INITIAL_DISPLAY)
      : filteredPrompts;

    // 表示
    container.innerHTML = '';
    if (filteredPrompts.length === 0) {
      noResultsEl.style.display = 'block';
    } else {
      noResultsEl.style.display = 'none';
      displayPrompts.forEach((preset) => {
        const wrapper = renderPresetButton(preset);
        container.appendChild(wrapper);

        // Bootstrap Tooltipを初期化
        const button = wrapper.querySelector('.preset-button');
        if (preset.description && typeof bootstrap !== 'undefined' && button) {
          const tooltip = new bootstrap.Tooltip(button);
          tooltipInstances.push(tooltip);
        }
      });

      // 「もっと見る」ボタンを追加
      if (shouldLimitDisplay) {
        const showMoreBtn = renderShowMoreButton();
        container.appendChild(showMoreBtn);
      }
    }
  }

  /**
   * カテゴリ一覧を取得
   */
  async function loadCategories() {
    try {
      const data = await APIClient.get('/api/v1/prompts/categories/');
      allCategories = data.categories || [];
      renderCategoryTabs(allCategories);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  }

  /**
   * プリセット一覧を取得
   */
  async function loadPrompts() {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
      const data = await APIClient.get('/api/v1/prompts/');
      allPrompts = data.prompts || [];
      filterAndRenderPrompts();
    } catch (error) {
      container.innerHTML = '<span class="text-danger small">プリセットの取得に失敗しました</span>';
    }
  }

  /**
   * 初期化
   */
  document.addEventListener('DOMContentLoaded', async () => {
    // 使用履歴を読み込み
    recentPrompts = getRecentPrompts();

    // カテゴリとプリセットを読み込み
    await loadCategories();
    await loadFavorites();
    await loadPrompts();

    // イベントリスナー設定
    const container = document.getElementById(containerId);
    if (container) {
      container.addEventListener('click', handlePresetClick);
    }

    const tabsContainer = document.getElementById(categoryTabsId);
    if (tabsContainer) {
      tabsContainer.addEventListener('click', handleCategoryTabClick);
    }

    const searchInput = document.getElementById(searchInputId);
    if (searchInput) {
      searchInput.addEventListener('input', handleSearchInput);
    }

    const multiSelectToggle = document.getElementById(multiSelectToggleId);
    if (multiSelectToggle) {
      multiSelectToggle.addEventListener('click', toggleMultiSelectMode);
    }

    // グローバルAPIを公開
    window.PromptManager = {
      getPrompt: () => {
        const custom = document.getElementById(customPromptId);
        const customText = custom ? custom.value.trim() : '';
        return customText || selectedText;
      },
      clearSelection: () => {
        selectedText = '';
        selectedPresets.clear();
        isMultiSelectMode = false;
        document.querySelectorAll('.preset-button').forEach((btn) => btn.classList.remove('active'));
        const custom = document.getElementById(customPromptId);
        if (custom) custom.value = '';
        const indicator = document.getElementById(multiSelectIndicatorId);
        if (indicator) indicator.style.display = 'none';
        const toggleBtn = document.getElementById(multiSelectToggleId);
        if (toggleBtn) toggleBtn.classList.remove('active');
      },
      refresh: async () => {
        await loadCategories();
        await loadFavorites();
        await loadPrompts();
      },
    };
  });
})();
