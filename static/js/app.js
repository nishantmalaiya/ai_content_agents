/* ============================================
   AI Content Agent System — Client JS
   ============================================ */

const socket = io();
let activeTab = 'scraper';

// ────────── Socket Events ──────────
socket.on('connect', () => log('Connected to server', 'success'));

socket.on('agent_start', d => {
  log(`Agent [${d.agent}] started`, 'info');
  setStepState(d.agent, 'running');
});

socket.on('agent_progress', d => {
  log(`[${d.agent}] ${d.message}`, 'info');
  if (d.percent >= 0) updateProgress(d.agent, d.percent);
});

socket.on('agent_done', d => {
  log(`Agent [${d.agent}] done ✓`, 'success');
  setStepState(d.agent, 'done');
  if (d.agent === 'scraper') renderScraperResults(d);
  if (d.agent === 'validator') renderValidatorResults(d.data);
  if (d.agent === 'writer') renderScript(d.data);
  if (d.agent === 'hooks') renderHooks(d.data);
});

socket.on('agent_error', d => {
  log(`[${d.agent || 'system'}] Error: ${d.msg}`, 'error');
  if (d.agent) setStepState(d.agent, '');
  clearAgentOutput(d.agent);
  document.getElementById('btnRunAll').disabled = false;
});

socket.on('pipeline_start', () => {
  log('Full pipeline started ━━━━━━━━━━', 'info');
  document.getElementById('btnRunAll').disabled = true;
  document.getElementById('btnRunAll').innerHTML = '<span class="spinner"></span> Running…';
});

socket.on('pipeline_done', d => {
  log('Pipeline complete ━━━━━━━━━━', 'success');
  document.getElementById('btnRunAll').disabled = false;
  document.getElementById('btnRunAll').innerHTML = '▶ Run Full Pipeline';
  fetchResults();
});

socket.on('pipeline_error', d => {
  log(`Pipeline error: ${d.msg}`, 'error');
  clearAgentOutput('validator');
  clearAgentOutput('writer');
  clearAgentOutput('hooks');
  document.getElementById('btnRunAll').disabled = false;
  document.getElementById('btnRunAll').innerHTML = '▶ Run Full Pipeline';
});

function clearAgentOutput(agent) {
  if (agent === 'validator') {
    document.getElementById('validatorRec').innerHTML = '';
    document.getElementById('topTopics').innerHTML = '<div class="empty-state"><p>No live validation result.</p></div>';
    document.getElementById('topicClusters').innerHTML = '<div class="empty-state"><p>No live validation result.</p></div>';
    document.getElementById('topFormats').innerHTML = '<div class="empty-state"><p>No live validation result.</p></div>';
    document.getElementById('repeatSignals').innerHTML = '<div class="empty-state"><p>No live validation result.</p></div>';
  }
  if (agent === 'writer') {
    document.getElementById('scriptOutput').innerHTML = '<div class="empty-state"><p>No AI-generated script.</p></div>';
  }
  if (agent === 'hooks') {
    document.getElementById('hooksOutput').innerHTML = '<div class="empty-state"><p>No AI-generated hooks.</p></div>';
  }
}

// ────────── Tab Switching ──────────
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === `tab-${tab}`));
  document.querySelectorAll('.pipeline-step').forEach(s => s.classList.toggle('active', s.id === `step-${tab}`));
}

// ────────── Pipeline Step States ──────────
function setStepState(agent, state) {
  const step = document.getElementById(`step-${agent}`);
  const icon = document.getElementById(`icon-${agent}`);
  if (!step) return;
  step.classList.remove('running', 'done');
  if (state) step.classList.add(state);
  if (state === 'done') icon.textContent = '✓';
  if (state === 'running') icon.innerHTML = '<span class="spinner"></span>';
  if (!state) { const num = {scraper:'01',validator:'02',writer:'03',hooks:'04'}; icon.textContent = num[agent] || '?'; }
}

function updateProgress(agent, pct) {
  const el = document.getElementById(`progress-${agent}`);
  if (el) el.querySelector('.progress-fill').style.width = pct + '%';
}

// ────────── Actions ──────────
function runFullPipeline() {
  const topic = document.getElementById('topicInput').value.trim();
  const platforms = [];
  if (document.getElementById('platIG').checked) platforms.push('instagram');
  if (document.getElementById('platYT').checked) platforms.push('youtube');
  if (document.getElementById('platTW').checked) platforms.push('twitter');
  const keywords = document.getElementById('keywordsInput').value.split(',').map(s => s.trim()).filter(Boolean);
  const competitors = document.getElementById('competitorsInput').value.split(',').map(s => s.trim()).filter(Boolean);
  const ig_user = localStorage.getItem('ig_user');
  const ig_pass = localStorage.getItem('ig_pass');
  const apify_token = localStorage.getItem('apify_token');
  const openai_key = localStorage.getItem('openai_key');
  socket.emit('run_full_pipeline', { 
    topic, platforms, keywords: keywords.length ? keywords : undefined, 
    competitors, days_back: +document.getElementById('daysBack').value || 7,
    ig_user, ig_pass, apify_token, openai_key
  });
}

function runScraper() {
  const platforms = [];
  if (document.getElementById('platIG').checked) platforms.push('instagram');
  if (document.getElementById('platYT').checked) platforms.push('youtube');
  if (document.getElementById('platTW').checked) platforms.push('twitter');
  const keywords = document.getElementById('keywordsInput').value.split(',').map(s => s.trim()).filter(Boolean);
  const competitors = document.getElementById('competitorsInput').value.split(',').map(s => s.trim()).filter(Boolean);
  const apify_token = localStorage.getItem('apify_token');
  const ig_user = localStorage.getItem('ig_user');
  const ig_pass = localStorage.getItem('ig_pass');
  socket.emit('run_scraper', { platforms, keywords: keywords.length ? keywords : undefined, competitors, days_back: +document.getElementById('daysBack').value || 7, apify_token, ig_user, ig_pass });
}

function runValidator() { socket.emit('run_validator', {}); }

function runWriter() {
  const topic = document.getElementById('scriptTopic').value.trim() || document.getElementById('topicInput').value.trim() || 'AI automation with Claude Code';
  socket.emit('run_writer', { topic, openai_key: localStorage.getItem('openai_key') });
}

function runHooks() {
  const topic = document.getElementById('hookTopic').value.trim() || document.getElementById('topicInput').value.trim() || 'AI automation';
  socket.emit('run_hooks', { topic, openai_key: localStorage.getItem('openai_key') });
}

// ────────── Renderers ──────────
function renderScraperResults(d) {
  const count = d.count || 0;
  document.getElementById('statPosts').textContent = count;
  document.getElementById('postCount').textContent = count + ' posts';
  document.getElementById('scraperStatus').innerHTML = `
    <div style="text-align:center;padding:20px;">
      <div style="font-size:36px;font-weight:800;color:var(--accent-green);">${count}</div>
      <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;">posts scraped successfully</div>
    </div>`;
  fetchResults();
}

function renderPostsTable(posts) {
  renderTableInto('scraperTable', posts, 'No live posts returned.');
}

function renderPlatformTables(platformResults) {
  renderTableInto('youtubeTable', platformResults?.youtube || [], 'No live YouTube rows returned.');
  renderTableInto('instagramTable', platformResults?.instagram || [], 'No live Instagram rows returned.');
}

function renderTableInto(elementId, posts, emptyMessage) {
  const target = document.getElementById(elementId);
  if (!target) return;
  if (!posts || !posts.length) {
    target.innerHTML = `<div class="empty-state"><div class="icon">📭</div><p>${esc(emptyMessage)}</p></div>`;
    return;
  }
  let html = '<table><thead><tr><th>Platform</th><th>Hook</th><th>Views</th><th>Likes</th><th>Comments</th><th>Eng %</th><th>Date</th><th>Status</th></tr></thead><tbody>';
  posts.forEach(p => {
    const viral = p.viral ? '<span class="viral-tag">🔥 VIRAL</span>' : '';
    html += `<tr>
      <td><span class="card-badge badge-${p.platform==='Instagram'?'pink':p.platform==='YouTube'?'red':'blue'}">${p.platform}</span></td>
      <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(p.hook)}">${esc(p.hook)}</td>
      <td style="font-weight:600;">${fmt(p.views)}</td>
      <td>${fmt(p.likes)}</td>
      <td>${fmt(p.comments)}</td>
      <td style="font-weight:600;color:${p.engagement_rate>=5?'var(--accent-green)':p.engagement_rate>=3?'var(--accent-orange)':'var(--text-secondary)'};">${p.engagement_rate}%</td>
      <td style="font-size:12px;color:var(--text-muted);">${p.post_date}</td>
      <td>${viral}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  target.innerHTML = html;
}

function renderValidatorResults(data) {
  if (!data) return;
  document.getElementById('statFiltered').textContent = data.posts_after_filter || 0;
  document.getElementById('statTopics').textContent = Object.keys(data.clusters || {}).length;
  document.getElementById('statViral').textContent = (data.repeat_viral_signals || []).length;

  // Recommendation
  document.getElementById('validatorRec').innerHTML = data.recommendation
    ? `<div class="recommendation">${data.recommendation.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</div>` : '';

  // Top Topics
  if (data.top_topics && data.top_topics.length) {
    let html = '<table><thead><tr><th>#</th><th>Topic</th><th>Posts</th><th>Avg Views</th><th>Eng %</th><th>Score</th></tr></thead><tbody>';
    data.top_topics.forEach((t, i) => {
      html += `<tr><td style="font-weight:700;color:var(--accent-purple);">${i+1}</td><td style="font-weight:600;">${esc(t.topic)}</td><td>${t.count}</td><td style="font-weight:600;">${fmt(t.avg_views)}</td><td>${t.avg_engagement}%</td><td>${t.avg_score}</td></tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('topTopics').innerHTML = html;
  }

  // Clusters
  if (data.clusters) {
    let html = '';
    Object.entries(data.clusters).forEach(([topic, info]) => {
      html += `<div class="cluster-tag"><strong>${esc(topic)}</strong> — ${info.count} posts, avg ${fmt(info.avg_views)} views</div>`;
    });
    document.getElementById('topicClusters').innerHTML = html;
  }

  // Formats
  if (data.top_formats && data.top_formats.length) {
    let html = '<table><thead><tr><th>Format</th><th>Count</th><th>Avg Views</th><th>Avg Shares</th><th>Eng %</th></tr></thead><tbody>';
    data.top_formats.forEach(f => {
      html += `<tr><td style="font-weight:600;">${esc(f.format)}</td><td>${f.count}</td><td>${fmt(f.avg_views)}</td><td>${fmt(f.avg_shares)}</td><td>${f.avg_engagement}%</td></tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('topFormats').innerHTML = html;
  }

  // Repeat signals
  if (data.repeat_viral_signals && data.repeat_viral_signals.length) {
    let html = '';
    data.repeat_viral_signals.forEach(s => {
      html += `<div class="cluster-tag" style="border-color:var(--accent-orange);">🔁 <strong>${esc(s.topic)}</strong> — ${s.occurrences}x</div>`;
    });
    if (data.sustained_trends && data.sustained_trends.length) {
      data.sustained_trends.forEach(s => {
        html += `<div class="cluster-tag" style="border-color:var(--accent-green);"><strong>${esc(s.format)}</strong> — ${esc(s.signal)}</div>`;
      });
    }
    document.getElementById('repeatSignals').innerHTML = html;
  } else if (data.sustained_trends && data.sustained_trends.length) {
    let html = '';
    data.sustained_trends.forEach(s => {
      html += `<div class="cluster-tag" style="border-color:var(--accent-green);"><strong>${esc(s.format)}</strong> — ${esc(s.signal)}</div>`;
    });
    document.getElementById('repeatSignals').innerHTML = html;
  }
}

function renderScript(data) {
  if (!data) return;
  const script = data.full_script || '';
  let html = `<div class="script-box">${esc(script).replace(/\[BEAT (\d)\]/g, '</div><div class="beat-label">BEAT $1</div><div class="script-box">').replace(/\[CTA\]/g, '</div><div class="beat-label">CTA</div><div class="script-box">')}</div>`;
  html += `<div style="margin-top:12px;font-size:12px;color:var(--text-muted);">Source: AI-generated | Topic: ${esc(data.topic)}</div>`;
  document.getElementById('scriptOutput').innerHTML = html;
}

function renderHooks(data) {
  if (!data || !data.hooks) return;
  let html = '';
  if (data.recommendation_reason) {
    html += `<div class="recommendation" style="margin-bottom:18px;">💡 <strong>Recommended:</strong> ${esc(data.recommendation_reason)}</div>`;
  }
  data.hooks.forEach((h, i) => {
    const isRec = h.recommended;
    const conf = h.confidence || 0;
    const confColor = conf >= 8 ? 'var(--accent-green)' : conf >= 6 ? 'var(--accent-orange)' : 'var(--accent-red)';
    html += `<div class="hook-card${isRec ? ' recommended' : ''}">
      <div style="display:flex;justify-content:space-between;align-items:start;">
        <div class="hook-text">${isRec ? '⭐ ' : ''}Hook ${i+1}: "${esc(h.hook)}"</div>
        ${isRec ? '<span class="card-badge badge-green">Recommended</span>' : ''}
      </div>
      <div class="hook-meta">
        <span>Pattern: <strong>${esc(h.pattern)}</strong></span>
        ${h.matched_post ? `<span>Match: <strong>${esc(h.matched_post)}</strong> (${fmt(h.matched_views)} views)</span>` : ''}
        <span>Confidence: <strong style="color:${confColor}">${conf}/10</strong>
          <span class="confidence-bar"><span class="confidence-fill" style="width:${conf*10}%;background:${confColor};"></span></span>
        </span>
      </div>
      ${h.reasoning ? `<div style="margin-top:8px;font-size:12px;color:var(--text-secondary);">${esc(h.reasoning)}</div>` : ''}
    </div>`;
  });
  document.getElementById('hooksOutput').innerHTML = html;
}

// ────────── Console ──────────
function log(msg, type = '') {
  const el = document.getElementById('consoleLog');
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  el.innerHTML += `<div class="log-line ${type}"><span class="log-time">[${time}]</span> ${esc(msg)}</div>`;
  el.scrollTop = el.scrollHeight;
}

function clearConsole() {
  document.getElementById('consoleLog').innerHTML = '<div class="log-line info"><span class="log-time">[system]</span> Console cleared.</div>';
}

// ────────── Settings / Voice Modals ──────────
function openSettings() { document.getElementById('settingsModal').classList.add('show'); }
function openVoiceModal() { document.getElementById('voiceModal').classList.add('show'); }
function closeModal(id) { document.getElementById(id).classList.remove('show'); }

function saveSettings() {
  localStorage.setItem('apify_token', document.getElementById('settApify').value);
  localStorage.setItem('openai_key', document.getElementById('settOpenAI').value);
  localStorage.setItem('ig_user', document.getElementById('settIGUser').value);
  localStorage.setItem('ig_pass', document.getElementById('settIGPass').value);
  closeModal('settingsModal'); 
  log('Settings saved locally', 'success'); 
}

function analyzeVoice() {
  const raw = document.getElementById('pastScripts').value.trim();
  if (!raw) return;
  const scripts = raw.split(/\n\s*\n/).filter(Boolean);
  fetch('/api/voice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scripts, openai_key: localStorage.getItem('openai_key') }) })
    .then(async r => {
      const profile = await r.json();
      if (!r.ok) throw new Error(profile.error || 'Voice analysis failed');
      return profile;
    }).then(profile => {
      log(`Voice profile analyzed from ${scripts.length} scripts`, 'success');
      renderVoiceProfile(profile);
      closeModal('voiceModal');
    }).catch(e => log('Voice analysis error: ' + e, 'error'));
}

function renderVoiceProfile(p) {
  const el = document.getElementById('voiceProfile');
  el.innerHTML = `<div style="margin-top:8px;">
    <div><strong>Vocabulary:</strong> ${Array.isArray(p.vocabulary) ? p.vocabulary.join(', ') : p.vocabulary || '—'}</div>
    <div><strong>Sentence Style:</strong> ${p.sentence_style || '—'}</div>
    <div><strong>Structure:</strong> ${p.structure || '—'}</div>
    <div><strong>CTA Style:</strong> ${p.cta_style || '—'}</div>
    <div><strong>Energy:</strong> ${p.energy || '—'}</div>
    <div><strong>Hinglish:</strong> ${p.hinglish ? 'Yes' : 'No'}</div>
  </div>`;
}

// ────────── Fetch Full Results ──────────
function fetchResults() {
  fetch('/api/results').then(r => r.json()).then(data => {
    renderPlatformTables(data.platform_results || {});
    if (data.scraper_results) renderPostsTable(data.scraper_results);
    if (data.validator_results && data.validator_results.recommendation) renderValidatorResults(data.validator_results);
    if (data.script_result && data.script_result.full_script) renderScript(data.script_result);
    if (data.hook_result && data.hook_result.hooks) renderHooks(data.hook_result);
  });
}

// ────────── Helpers ──────────
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function fmt(n) { return (n || 0).toLocaleString(); }

// ────────── Init ──────────
window.addEventListener('DOMContentLoaded', () => {
  fetchResults();
  fetch('/api/voice').then(r => r.json()).then(renderVoiceProfile).catch(() => {});
  fetch('/api/config').then(r => r.json()).then(cfg => {
    if (cfg.keywords) document.getElementById('keywordsInput').value = cfg.keywords.join(', ');
    if (cfg.competitors) document.getElementById('competitorsInput').value = cfg.competitors.join(', ');
    if (cfg.days_back) document.getElementById('daysBack').value = cfg.days_back;
    
    // Load saved settings
    document.getElementById('settApify').value = localStorage.getItem('apify_token') || '';
    document.getElementById('settOpenAI').value = localStorage.getItem('openai_key') || '';
    document.getElementById('settIGUser').value = localStorage.getItem('ig_user') || '';
    document.getElementById('settIGPass').value = localStorage.getItem('ig_pass') || '';
  }).catch(() => {});
});

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(m => {
  m.addEventListener('click', e => { if (e.target === m) m.classList.remove('show'); });
});
