/**
 * RetailPulse KB UI - vanilla JS, no framework
 * - Search via API Gateway
 * - Filter results
 * - Submit feedback ratings
 * - Toast notifications
 */

(function () {
  'use strict';

  const config = {
    apiUrl: window.RETAILPULSE_API_URL || 'https://api.example.com',
    region: 'ap-south-1',
    environment: 'dev',
  };

  if (window.location.hostname.includes('staging')) config.environment = 'staging';
  if (window.location.hostname.includes('prod')) config.environment = 'prod';
  document.getElementById('env-badge').textContent = config.environment;

  const state = {
    results: [],
    selected: new Set(),
    lastQuery: '',
    lastAgent: '',
    feedbackRating: 0,
  };

  const $ = (id) => document.getElementById(id);
  const showToast = (msg, type = 'success') => {
    const t = $('toast');
    t.textContent = msg;
    t.className = `toast show ${type}`;
    setTimeout(() => t.className = 'toast', 2500);
  };

  async function signAndFetch(method, path, body) {
    // In production, this uses AWS SigV4 with credentials from Cognito/SSO
    // For demo, we use the API key if available
    const url = `${config.apiUrl}${path}`;
    const headers = { 'Content-Type': 'application/json' };
    if (body) headers['Content-Type'] = 'application/json';
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const response = await fetch(url, opts);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'UNKNOWN' }));
      throw new Error(`${err.error || response.statusText}`);
    }
    return response.json();
  }

  async function performSearch() {
    const q = $('search-input').value.trim();
    if (!q) {
      showToast('Enter a search query', 'error');
      return;
    }
    const topK = parseInt($('top-k').value, 10) || 10;
    const params = new URLSearchParams({ q, top_k: topK });
    const source = $('filter-source').value;
    if (source) params.set('source', source);

    $('search-btn').disabled = true;
    $('search-btn').textContent = 'Searching...';
    try {
      const data = await signAndFetch('GET', `/v1/catalog/search?${params.toString()}`);
      state.results = data.results || [];
      state.lastQuery = q;
      renderResults(data);
    } catch (err) {
      showToast(`Search failed: ${err.message}`, 'error');
    } finally {
      $('search-btn').disabled = false;
      $('search-btn').textContent = 'Search';
    }
  }

  function renderResults(data) {
    const container = $('results');
    if (data.results.length === 0) {
      container.innerHTML = `<div class="empty-state"><h2>No results</h2><p>Try a different query or relax filters.</p></div>`;
      return;
    }
    container.innerHTML = data.results.map((r) => `
      <article class="result-card">
        <div class="result-header">
          <div class="result-meta">
            <span class="score-pill">${r.score.toFixed(3)}</span>
            <span class="tag">${r.format || 'text'}</span>
            ${r.category ? `<span class="tag">${r.category}</span>` : ''}
          </div>
        </div>
        <div class="result-text">${escapeHtml(r.text_preview || r.name || '(no preview)')}</div>
        <div class="result-source">${escapeHtml(r.source || '')} ${r.name ? '· ' + escapeHtml(r.name) : ''} ${r.price_inr ? '· ₹' + r.price_inr : ''}</div>
      </article>
    `).join('');
    $('stat-results').textContent = `${data.total_results || data.results.length} results`;
    $('stat-duration').textContent = `${data.query_duration_ms || 0}ms`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Feedback
  document.querySelectorAll('.rating span').forEach((star) => {
    star.addEventListener('click', () => {
      state.feedbackRating = parseInt(star.dataset.rating, 10);
      document.querySelectorAll('.rating span').forEach((s) => {
        s.classList.toggle('active', parseInt(s.dataset.rating, 10) <= state.feedbackRating);
      });
    });
  });

  $('feedback-btn')?.addEventListener('click', async () => {
    if (state.feedbackRating === 0) {
      showToast('Please select a rating', 'error');
      return;
    }
    try {
      await signAndFetch('POST', '/v1/feedback', {
        session_id: state.lastQuery || 'test',
        agent: 'search',
        rating: state.feedbackRating,
        comments: $('feedback-comments').value,
        resolved: true,
      });
      showToast('Feedback recorded');
      state.feedbackRating = 0;
      document.querySelectorAll('.rating span').forEach((s) => s.classList.remove('active'));
      $('feedback-comments').value = '';
    } catch (err) {
      showToast(`Feedback failed: ${err.message}`, 'error');
    }
  });

  // Wire up
  $('search-btn').addEventListener('click', performSearch);
  $('search-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performSearch();
  });
  $('min-score').addEventListener('input', (e) => {
    $('min-score-value').textContent = parseFloat(e.target.value).toFixed(2);
  });
  $('reset-filters').addEventListener('click', () => {
    $('filter-source').value = '';
    $('min-score').value = '0';
    $('min-score-value').textContent = '0.00';
  });
})();
