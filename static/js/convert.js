(() => {
  const startButton = document.getElementById('start-conversion');
  const generationSelect = document.getElementById('generation-count');
  const modelSelect = document.getElementById('model-variant');
  const aspectSelect = document.getElementById('aspect-ratio');

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
        if (modelSelect) {
          formData.append('model_variant', modelSelect.value);
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
    }
  });
})();
