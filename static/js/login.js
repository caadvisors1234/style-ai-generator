(() => {
  async function fetchCsrfToken() {
    await fetch('/api/v1/auth/csrf/', {
      method: 'GET',
      credentials: 'include',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
  }

  function getRedirectPath() {
    const params = new URLSearchParams(window.location.search);
    const nextParam = params.get('next');
    if (nextParam && nextParam.startsWith('/')) {
      return nextParam;
    }
    return '/';
  }

  async function login(event) {
    event.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const errorBox = document.getElementById('login-error');
    const submit = document.getElementById('login-submit');

    if (!username || !password) {
      errorBox.textContent = 'ユーザー名とパスワードを入力してください。';
      errorBox.classList.remove('d-none');
      return;
    }

    submit.disabled = true;
    errorBox.classList.add('d-none');

    try {
      await APIClient.post('/api/v1/auth/login/', { username, password });
      window.location.href = getRedirectPath();
    } catch (error) {
      const payload = error.payload || {};
      errorBox.textContent = payload.message || 'ログインに失敗しました。';
      errorBox.classList.remove('d-none');
    } finally {
      submit.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await fetchCsrfToken();
    document.getElementById('login-form').addEventListener('submit', login);
  });
})();
