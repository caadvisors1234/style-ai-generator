(() => {
  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split('; ') : [];
    for (const cookie of cookies) {
      if (cookie.startsWith(`${name}=`)) {
        return decodeURIComponent(cookie.slice(name.length + 1));
      }
    }
    return null;
  }

  async function request(url, options = {}) {
    const defaultHeaders = {
      'X-Requested-With': 'XMLHttpRequest',
    };

    const opts = {
      credentials: 'include',
      ...options,
    };

    opts.headers = {
      ...defaultHeaders,
      ...(opts.headers || {}),
    };

    if (opts.method && opts.method.toUpperCase() !== 'GET') {
      if (!(opts.body instanceof FormData)) {
        opts.headers['Content-Type'] = 'application/json';
      }
      opts.headers['X-CSRFToken'] = getCookie('csrftoken');
    }

    const response = await fetch(url, opts);
    const contentType = response.headers.get('Content-Type') || '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();

    if (!response.ok) {
      const error = new Error(data.message || 'API request failed');
      error.status = response.status;
      error.payload = data;
      throw error;
    }

    return data;
  }

  window.APIClient = {
    get: (url) => request(url, { method: 'GET' }),
    post: (url, body) => request(url, { method: 'POST', body: JSON.stringify(body) }),
    delete: (url, body) => request(url, { method: 'DELETE', body: JSON.stringify(body) }),
    patch: (url, body) => request(url, { method: 'PATCH', body: JSON.stringify(body) }),
    upload: (url, formData) => request(url, { method: 'POST', body: formData }),
  };
})(); 
