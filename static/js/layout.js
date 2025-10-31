(() => {
  async function fetchUsage() {
    const usageElement = document.getElementById('usage-summary');
    if (!usageElement) {
      return;
    }

    try {
      const data = await APIClient.get('/api/v1/usage/');
      const summary = data.data;
      usageElement.textContent = `今月 ${summary.monthly_used} / ${summary.monthly_limit} 枚 （残り ${summary.remaining} 枚）`;
    } catch (error) {
      usageElement.textContent = '利用状況を取得できません';
    }
  }

  async function logout() {
    try {
      await APIClient.post('/api/v1/auth/logout/', {});
      window.location.href = '/login/';
    } catch (error) {
      notifyError('ログアウトに失敗しました');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
      logoutButton.addEventListener('click', logout);
      fetchUsage();
    }
  });
})();
