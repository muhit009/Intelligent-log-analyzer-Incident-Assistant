/* ===== API Client Module ===== */
const API = (() => {
  const BASE = '';  // same origin

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  async function request(method, path, { body, params } = {}) {
    let url = `${BASE}${path}`;
    if (params) {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== '' && v !== null && v !== undefined) qs.append(k, v);
      });
      const str = qs.toString();
      if (str) url += `?${str}`;
    }

    const opts = {
      method,
      headers: { ...authHeaders() },
    };

    if (body instanceof FormData) {
      opts.body = body;
    } else if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }

    const res = await fetch(url, opts);

    if (res.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.hash = '#/login';
      throw new Error('Session expired');
    }

    if (res.status === 204) return null;

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Request failed (${res.status})`);
    }
    return data;
  }

  return {
    get:    (path, params) => request('GET', path, { params }),
    post:   (path, body)   => request('POST', path, { body }),
    del:    (path)         => request('DELETE', path),
    upload: (path, file)   => {
      const fd = new FormData();
      fd.append('file', file);
      return request('POST', path, { body: fd });
    },
  };
})();
