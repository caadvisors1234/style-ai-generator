(() => {
  const startButton = document.getElementById('start-conversion');
  const generationSelect = document.getElementById('generation-count');

  async function startConversion() {
    if (!startButton) return;

    const files = (window.UploadManager && window.UploadManager.getFiles()) || [];
    if (!files.length) {
      notifyWarning('先に画像をアップロードしてください');
      return;
    }

    const prompt = window.PromptManager ? window.PromptManager.getPrompt() : '';
    if (!prompt) {
      notifyWarning('プロンプトを入力するかプリセットを選択してください');
      return;
    }

    const formData = new FormData();
    const first = files[0];

    if (!first.originalFile) {
      notifyError('アップロードした画像データを取得できませんでした');
      return;
    }

    formData.append('image', first.originalFile, first.originalFile.name);
    formData.append('prompt', prompt);
    formData.append('generation_count', generationSelect.value);

    startButton.disabled = true;

    try {
      const data = await APIClient.upload('/api/v1/convert/', formData);
      notifySuccess('変換を開始しました');
      if (window.UploadManager) {
        const previousFiles = window.UploadManager.getFiles();
        await Promise.allSettled(previousFiles.map((file) => APIClient.delete('/api/v1/upload/delete/', { file_path: file.file_path })));
        window.UploadManager.clear();
      }
      window.location.href = `/processing/${data.conversion_id}/`;
    } catch (error) {
      const payload = error.payload || {};
      notifyError(payload.message || '変換の開始に失敗しました');
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
