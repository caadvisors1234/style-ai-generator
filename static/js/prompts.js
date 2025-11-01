(() => {
  const containerId = 'prompt-preset-container';
  const customPromptId = 'custom-prompt';
  let selectedText = '';

  function renderPresetButton(preset) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'prompt-preset-btn preset-button';
    button.dataset.prompt = preset.prompt;
    button.textContent = preset.name;
    return button;
  }

  function handlePresetClick(event) {
    const target = event.target.closest('.preset-button');
    if (!target) return;

    selectedText = target.dataset.prompt;
    document.querySelectorAll('.preset-button').forEach((btn) => btn.classList.remove('active'));
    target.classList.add('active');

    const promptArea = document.getElementById(customPromptId);
    if (promptArea) {
      promptArea.value = selectedText;
    }
  }

  async function loadPrompts() {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
      const data = await APIClient.get('/api/v1/prompts/');
      container.innerHTML = '';
      data.prompts.forEach((preset) => container.appendChild(renderPresetButton(preset)));
    } catch (error) {
      container.innerHTML = '<span class="text-danger small">プリセットの取得に失敗しました</span>';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadPrompts();
    const container = document.getElementById(containerId);
    if (container) {
      container.addEventListener('click', handlePresetClick);
    }
    window.PromptManager = {
      getPrompt: () => {
        const custom = document.getElementById(customPromptId);
        const customText = custom ? custom.value.trim() : '';
        return customText || selectedText;
      },
      clearSelection: () => {
        selectedText = '';
        document.querySelectorAll('.preset-button').forEach((btn) => btn.classList.remove('active'));
        const custom = document.getElementById(customPromptId);
        if (custom) custom.value = '';
      },
    };
  });
})();
