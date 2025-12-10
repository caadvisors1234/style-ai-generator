(() => {
  async function fetchUsage() {
    const usageElement = document.getElementById('usage-summary');
    const badge = document.getElementById('usage-badge');
    const progressBar = document.getElementById('usage-progress-bar');
    const remainingLabel = document.getElementById('usage-remaining-label');
    if (!usageElement || !badge || !progressBar || !remainingLabel) {
      return;
    }

    try {
      const data = await APIClient.get('/api/v1/usage/');
      const summary = data.data;
      const used = Number(summary.monthly_used) || 0;
      const limit = Number(summary.monthly_limit) || 1;
      const remaining = Math.max(0, Number(summary.remaining) || 0);
      const ratio = Math.min(100, Math.max(0, Math.round((used / limit) * 100)));

      badge.textContent = `今月 ${used} / ${limit} クレジット`;
      progressBar.style.width = `${ratio}%`;
      progressBar.setAttribute('aria-valuenow', ratio);
      remainingLabel.textContent = `残り ${remaining} クレジット`;

      // カラーをシンプルに段階分け
      progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
      if (ratio < 60) {
        progressBar.classList.add('bg-success');
      } else if (ratio < 85) {
        progressBar.classList.add('bg-warning');
      } else {
        progressBar.classList.add('bg-danger');
      }
    } catch (error) {
      badge.textContent = '利用状況を取得できません';
      progressBar.style.width = '0%';
      remainingLabel.textContent = '';
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
