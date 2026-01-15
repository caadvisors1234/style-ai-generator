(() => {
  const startButton = document.getElementById('start-conversion');
  const generationSelect = document.getElementById('generation-count');
  const modelRadios = document.querySelectorAll('input[name="model_variant"]');
  const aspectSelect = document.getElementById('aspect-ratio');
  const estimatedEl = document.getElementById('estimated-credit');

  const MODEL_MULTIPLIERS = {
    'gemini-2.5-flash-image': 1,
    'gemini-3-pro-image-preview': 5,
  };

  function getSelectedModel() {
    const checked = document.querySelector('input[name="model_variant"]:checked');
    return checked ? checked.value : null;
  }

  function getUploadCount() {
    if (window.UploadManager && typeof window.UploadManager.getFiles === 'function') {
      return window.UploadManager.getFiles().length || 0;
    }
    return 0;
  }

  function updateEstimatedCredit() {
    if (!estimatedEl) return;
    const files = getUploadCount();
    const generation = Number(generationSelect?.value || 1);
    const model = getSelectedModel() || 'gemini-2.5-flash-image';
    const multiplier = MODEL_MULTIPLIERS[model] || 1;
    const total = files * generation * multiplier;
    estimatedEl.textContent = `この条件で合計 ${total} クレジット`;
  }

  function updateStartButtonState() {
    if (!startButton) return;

    const files = getUploadCount();
    const promptMeta = window.PromptManager && window.PromptManager.getSelectionMeta
      ? window.PromptManager.getSelectionMeta()
      : { prompt: window.PromptManager ? window.PromptManager.getPrompt() : '' };
    const hasPrompt = !!(promptMeta.prompt && promptMeta.prompt.trim());

    const isValid = files > 0 && hasPrompt;
    startButton.disabled = !isValid;

    if (!files) {
      startButton.title = '画像をアップロードしてください';
    } else if (!hasPrompt) {
      startButton.title = 'プロンプトを入力または選択してください';
    } else {
      startButton.title = '';
    }
  }

  async function ensureFileData(file, index) {
    if (file.originalFile) {
      return file.originalFile;
    }

    if (!file.preview_url) {
      throw new Error('preload-missing');
    }

    const response = await fetch(file.preview_url, { credentials: 'include' });
    if (!response.ok) {
      throw new Error('fetch-failed');
    }

    const blob = await response.blob();
    const filename = file.file_name || `image_${index + 1}`;
    const retrievedFile = new File([blob], filename, { type: blob.type || 'image/jpeg' });
    file.originalFile = retrievedFile;
    return retrievedFile;
  }

  async function startConversion() {
    if (!startButton) return;

    const files = (window.UploadManager && window.UploadManager.getFiles()) || [];
    if (!files.length) {
      notifyWarning('先に画像をアップロードしてください');
      return;
    }

    const promptMeta = window.PromptManager && window.PromptManager.getSelectionMeta
      ? window.PromptManager.getSelectionMeta()
      : { prompt: window.PromptManager ? window.PromptManager.getPrompt() : '' };

    const promptText = promptMeta.prompt || '';

    if (!promptText) {
      notifyWarning('指示文を入力するか、おすすめフレーズを選択してください');
      return;
    }

    startButton.disabled = true;

    try {
      // 複数画像を順番に変換処理
      const conversionIds = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];

        let sourceFile;
        try {
          sourceFile = await ensureFileData(file, i);
        } catch (error) {
          notifyError(`画像 ${i + 1} のデータを取得できませんでした`);
          continue;
        }

        const formData = new FormData();
        formData.append('image', sourceFile, sourceFile.name);
        formData.append('prompt', promptText);
        if (promptMeta && promptMeta.presetId !== null && promptMeta.presetId !== undefined) {
          formData.append('preset_id', promptMeta.presetId);
        }
        if (promptMeta && promptMeta.presetName) {
          formData.append('preset_name', promptMeta.presetName);
        }
        formData.append('generation_count', generationSelect.value);
        const selectedModel = getSelectedModel();
        if (selectedModel) {
          formData.append('model_variant', selectedModel);
        }
        if (aspectSelect) {
          formData.append('aspect_ratio', aspectSelect.value);
        }

        try {
          const data = await APIClient.upload('/api/v1/convert/', formData);
          conversionIds.push(data.conversion_id);
          notifySuccess(`画像 ${i + 1}/${files.length} の変換を開始しました`);
        } catch (error) {
          const payload = error.payload || {};
          notifyError(`画像 ${i + 1} の変換開始に失敗: ${payload.message || '不明なエラー'}`);
        }
      }

      // アップロード済みファイルを削除
      if (window.UploadManager) {
        const previousFiles = window.UploadManager.getFiles();
        await Promise.allSettled(previousFiles.map((file) => APIClient.delete('/api/v1/upload/delete/', { file_path: file.file_path })));
        window.UploadManager.clear();
      }

      // 変換処理画面へ遷移
      if (conversionIds.length > 0) {
        if (conversionIds.length === 1) {
          // 単一変換の場合は通常の処理画面
          window.location.href = `/processing/${conversionIds[0]}/`;
        } else {
          // 複数変換の場合は複数変換処理画面
          const idsParam = conversionIds.join(',');
          window.location.href = `/processing/multiple/?ids=${idsParam}`;
        }
      }
    } catch (error) {
      notifyError('変換処理中にエラーが発生しました');
    } finally {
      startButton.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (startButton) {
      startButton.addEventListener('click', startConversion);
      // 初期状態チェック
      updateStartButtonState();
    }
    if (generationSelect) {
      generationSelect.addEventListener('change', updateEstimatedCredit);
    }
    if (modelRadios && modelRadios.length) {
      modelRadios.forEach((radio) => {
        radio.addEventListener('change', updateEstimatedCredit);
      });
    }
    window.addEventListener('uploadsChanged', () => {
      updateEstimatedCredit();
      updateStartButtonState();
    });
    window.addEventListener('imageDeleted', () => {
      updateEstimatedCredit();
      updateStartButtonState();
    });
    window.addEventListener('promptChanged', updateStartButtonState);

    updateEstimatedCredit();
    // PromptManagerの準備ができたら初期状態を更新するために少し待つか、
    // PromptManager側で初期化完了イベントがあればそれを使うのがベストだが、
    // 簡易的にDOMContentLoadedの最後に一度呼ぶ
    setTimeout(updateStartButtonState, 100);


  });
})();
