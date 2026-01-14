/**
 * プロンプト改善機能
 *
 * Gemini 2.5 FlashでユーザーのプロンプトをAI改善する
 */

(() => {
  const IMPROVE_API_URL = '/api/v1/prompts/improve/';
  const PROMPT_TEXTAREA_ID = 'custom-prompt';
  const IMPROVE_BTN_ID = 'improve-prompt-btn';

  /**
   * プロンプト改善ボタンの初期化
   */
  function initImproveButton() {
    const improveBtn = document.getElementById(IMPROVE_BTN_ID);
    const promptTextarea = document.getElementById(PROMPT_TEXTAREA_ID);

    if (!improveBtn || !promptTextarea) {
      console.error('Prompt improver: Required elements not found');
      return;
    }

    // ボタンクリックイベント
    improveBtn.addEventListener('click', async () => {
      const prompt = promptTextarea.value.trim();

      // プロンプトが空の場合
      if (!prompt) {
        showNotification('error', 'プロンプトを入力してください');
        return;
      }

      // ボタンを無効化してローディング状態に
      setButtonLoading(improveBtn, true);

      try {
        // API呼び出し
        const improvedPrompt = await improvePrompt(prompt);

        // テキストエリアに改善後のプロンプトをセット
        promptTextarea.value = improvedPrompt;

        // テキストエリアをハイライト（アニメーション）
        highlightTextarea(promptTextarea);

        // 成功通知（トースト）
        showNotification('success', 'AIがプロンプトを改善しました');

      } catch (error) {
        console.error('Prompt improvement error:', error);
        showNotification('error', error.message || 'プロンプトの改善に失敗しました');
      } finally {
        // ボタンを再度有効化
        setButtonLoading(improveBtn, false);
      }
    });
  }

  /**
   * CSRFトークンを取得
   */
  function getCsrfToken() {
    const cookies = document.cookie ? document.cookie.split('; ') : [];
    for (const cookie of cookies) {
      if (cookie.startsWith('csrftoken=')) {
        return decodeURIComponent(cookie.slice('csrftoken='.length));
      }
    }
    return null;
  }

  /**
   * API呼び出し: プロンプト改善（認証・CSRF保護付き）
   */
  async function improvePrompt(prompt) {
    const csrfToken = getCsrfToken();

    const response = await fetch(IMPROVE_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'include',
      body: JSON.stringify({ prompt }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== 'success') {
      // 特定のエラーコードに応じたメッセージ
      if (data.code === 'AUTHENTICATION_REQUIRED') {
        throw new Error('ログインが必要です。ページを再読み込みしてログインしてください。');
      } else {
        throw new Error(data.message || 'プロンプトの改善に失敗しました');
      }
    }

    return data.improved_prompt;
  }

  /**
   * ボタンのローディング状態を切り替え
   */
  function setButtonLoading(button, isLoading) {
    const textElement = button.querySelector('.improve-btn-text');
    const spinner = button.querySelector('.spinner-border');

    if (isLoading) {
      button.disabled = true;
      if (textElement) textElement.textContent = '改善中...';
      if (spinner) spinner.classList.remove('d-none');
    } else {
      button.disabled = false;
      if (textElement) textElement.textContent = 'AIで改善';
      if (spinner) spinner.classList.add('d-none');
    }
  }

  /**
   * テキストエリアをハイライト（アニメーション効果）
   */
  function highlightTextarea(textarea) {
    textarea.classList.add('highlight-animation');

    setTimeout(() => {
      textarea.classList.remove('highlight-animation');
    }, 2000);
  }

  /**
   * トースト通知を表示
   */
  function showNotification(type, message) {
    // 既存のトースト通知システムを使用
    if (type === 'success' && typeof window.notifySuccess === 'function') {
      window.notifySuccess(message);
    } else if (type === 'error' && typeof window.notifyError === 'function') {
      window.notifyError(message);
    } else {
      // フォールバック: コンソールログ
      console.log(`[${type}] ${message}`);
    }
  }

  /**
   * 初期化
   */
  document.addEventListener('DOMContentLoaded', () => {
    initImproveButton();
  });

  // CSSアニメーションを動的に追加
  const style = document.createElement('style');
  style.textContent = `
    .highlight-animation {
      animation: highlight-pulse 2s ease-in-out;
    }

    @keyframes highlight-pulse {
      0% {
        box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.4);
        border-color: #0d6efd;
      }
      50% {
        box-shadow: 0 0 20px 5px rgba(13, 110, 253, 0.2);
        border-color: #0d6efd;
      }
      100% {
        box-shadow: 0 0 0 0 rgba(13, 110, 253, 0);
        border-color: #dee2e6;
      }
    }

    #improve-prompt-btn {
      transition: all 0.3s ease;
    }

    #improve-prompt-btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
    }

    #improve-prompt-btn:active:not(:disabled) {
      transform: translateY(0);
    }

    #improve-prompt-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  `;
  document.head.appendChild(style);
})();
