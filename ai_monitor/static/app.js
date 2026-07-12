const PAGE_META = {
  overview: { title: '舆情概览', desc: '社媒爬取 · AI 分析 · 规则告警 · 仓库监控' },
  jobs: { title: '监控任务', desc: '创建任务、手动执行检查、管理舆情与仓库监控' },
  alerts: { title: '告警中心', desc: '品牌舆情与规则触发记录' },
  analysis: { title: '分析结果', desc: 'AI 情感与话题提取' },
  rules: { title: '规则配置', desc: '关键词、情感、趋势与异常规则' },
  history: { title: '运行历史', desc: '仓库代码更新与任务执行记录' }, history: { title: '运行历史', desc: '仓库代码更新与任务执行记录' }, repos: { title: '仓库监控', desc: 'GitHub / Gitee 代码更新' },
  settings: { title: '系统设置', desc: '服务状态、通知渠道与运行环境' },
};

const PLATFORM_LABELS = {
  xhs: '小红书', dy: '抖音', ks: '快手', bili: 'B站',
  wb: '微博', tieba: '贴吧', zhihu: '知乎',
  github: 'GitHub', gitee: 'Gitee',
};

const REPO_TYPES = new Set(['github', 'gitee']);

let lastRefresh = null;
let allJobs = [];
let jobFilter = 'all';
let running = false;
let ruleSetOptions = [];
let editingJobId = null;

const api = async (path, opts = {}) => {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const err = await r.json();
      msg = err.detail || err.message || msg;
    } catch {
      msg = await r.text() || msg;
    }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return r.json();
};

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3200);
}

function parseUtc(iso) {
  if (!iso) return null;
  if (iso.includes('+') || iso.endsWith('Z')) return new Date(iso);
  return new Date(`${iso}Z`);
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = parseUtc(iso);
  if (!d || Number.isNaN(d.getTime())) return iso.replace('T', ' ').slice(0, 19);
  return d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function platLabel(p) {
  return PLATFORM_LABELS[p] || p;
}

function isRepoJob(j) {
  return REPO_TYPES.has(j.source_type) || REPO_TYPES.has(j.platform);
}

function switchPanel(id) {
  document.querySelectorAll('.nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.panel === id);
  });
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`panel-${id}`).classList.add('active');
  const meta = PAGE_META[id];
  document.getElementById('pageTitle').textContent = meta.title;
  document.getElementById('pageDesc').textContent = meta.desc;
}

function branchDisplay(branch) {
  const b = (branch || '').trim();
  return b || '默认分支';
}

function renderJobCard(j) {
  const typeCls = j.source_type === "social" ? "tag-social" : (j.platform === "gitee" ? "tag-gitee" : "tag-github");
  const repoKw = j.repo || j.keywords || "\u2014";
  const kw = isRepoJob(j) && j.branch
    ? "" + repoKw + ""
    : repoKw;
  const branch_label = (isRepoJob(j) && j.branch) ? "<span class=\"branch-label\">\u279e " + branchDisplay(j.branch) + "</span>" : "";
  const status_dot = j.status === "active" ? "\u25cf" : "\u25cb";
  const status_cls = j.status === "active" ? "status-active" : "status-paused";
  const runLabel = isRepoJob(j) ? "\u7acb\u5373\u68c0\u67e5" : "\u7acb\u5373\u6267\u884c";
  return "<article class=\"job-card mono-card\" data-job-id=\"" + j.job_id + "\">" +
    "<div class=\"mono-card-main\">" +
      "<div class=\"mono-card-name\">" +
        "<span class=\"tag " + typeCls + "\">" + platLabel(j.platform) + "</span>" +
        "<span class=\"mono-repo-name\">" + kw + "</span>" +
        branch_label +
      "</div>" +
      "<div class=\"mono-card-status\">" +
        "<span class=\"" + status_cls + "\">" + status_dot + " " + j.status + "</span>" +
      "</div>" +
    "</div>" +
    "<div class=\"mono-card-actions\">" +
      "<button class=\"btn-ghost btn-run-job\" data-job-id=\"" + j.job_id + "\">" + runLabel + "</button>" +
      "<button class=\"btn-ghost btn-edit-job\" data-job-id=\"" + j.job_id + "\">\u7f16\u8f91</button>" +
      "<button class=\"btn-ghost btn-del-job\" data-job-id=\"" + j.job_id + "\">\u5220\u9664</button>" +
    "</div>" +
  "</article>";
}function filterJobs(jobs) {
  if (jobFilter === 'all') return jobs;
  if (jobFilter === 'social') return jobs.filter(j => j.source_type === 'social');
  return jobs.filter(j => j.source_type === jobFilter || j.platform === jobFilter);
}

function renderJobsList(containerId, jobs, emptyMsg) {
  const container = document.getElementById(containerId);
  if (!jobs.length) {
    container.innerHTML = `<div class="empty-state">${emptyMsg}</div>`;
    return;
  }
  container.innerHTML = jobs.map(renderJobCard).join('');
}

async function checkHealth() {
  const dot = document.getElementById('healthDot');
  const label = document.getElementById('healthLabel');
  try {
    await api('/api/health');
    const st = await api('/api/system/status');
    dot.classList.remove('off');
    const bits = [];
    if (st.mediacrawler?.ok) bits.push('爬虫');
    if (st.openai_configured) bits.push('AI');
    if (st.github_token_configured) bits.push('GitHub');
    label.textContent = bits.length ? `正常 · ${bits.join(' · ')}` : '服务正常';
  } catch {
    dot.classList.add('off');
    label.textContent = '服务离线';
  }
}

async function loadSettings() {
  const st = await api('/api/system/status');
  const n = st.notifications || {};
  const rows = [
    ['MediaCrawler', st.mediacrawler?.ok ? '已就绪' : '路径无效'],
    ['OpenAI', st.openai_configured ? '已配置' : '未配置'],
    ['GitHub Token', st.github_token_configured ? '已配置' : '未配置'],
    ['钉钉', n.dingtalk ? '已配置' : '—'],
    ['飞书', n.feishu ? '已配置' : '—'],
    ['企微', n.wechat_work ? '已配置' : '—'],
    ['Slack', n.slack ? '已配置' : '—'],
    ['Discord', n.discord ? '已配置' : '—'],
    ['邮件', n.email ? '已配置' : '—'],
    ['短信', n.sms ? '已配置' : '—'],
  ];
  document.getElementById('systemStatusGrid').innerHTML = rows.map(([k, v]) =>
    `<div class="stat-card"><b>${v}</b><span>${k}</span></div>`
  ).join('');
}

async function loadRuleSetOptions() {
  try {
    const data = await api('/api/rules/sets');
    ruleSetOptions = data.rule_sets || [];
    const sel = document.getElementById('newRuleSets');
    if (sel && ruleSetOptions.length) {
      sel.innerHTML = ruleSetOptions.map(rs =>
        `<option value="${rs.id}"${rs.id === 'brand_monitoring' ? ' selected' : ''}>${rs.name}</option>`
      ).join('');
    }
  } catch (_) { /* keep defaults */ }
}

async function loadOverview() {
  const s = await api('/api/dashboard/stats');
  document.getElementById('statsGrid').innerHTML = `
    <div class="stat-card"><b>${s.active_jobs}</b><span>活跃任务</span></div>
    <div class="stat-card"><b>${s.total_alerts}</b><span>告警总数</span></div>
    <div class="stat-card"><b>${s.unack_alerts}</b><span>待确认</span></div>
    <div class="stat-card"><b>${s.analysis_today}</b><span>今日分析</span></div>
  `;
  document.getElementById('overviewPlatforms').textContent =
    (s.platforms || []).map(platLabel).join('、') || '暂无';

  const alerts = await api('/api/alerts?limit=5');
  const ob = document.getElementById('overviewAlertsBody');
  if (!alerts.length) {
    ob.innerHTML = '<tr><td colspan="5" class="empty-state">暂无告警</td></tr>';
  } else {
    ob.innerHTML = alerts.map(a => `
      <tr>
        <td>${fmtTime(a.created_at)}</td>
        <td class="sev-${a.severity}">${a.severity}</td>
        <td>${a.rule_name || '—'}</td>
        <td>${platLabel(a.platform) || '—'}</td>
        <td>${(a.summary || '').slice(0, 60)}</td>
      </tr>`).join('');
  }
}

async function loadJobs() {
  allJobs = await api('/api/jobs');
  renderJobsList('jobsList', filterJobs(allJobs), '暂无监控任务，请在上方创建');
}

async function loadAlerts() {
  const alerts = await api('/api/alerts?limit=50');
  const tbody = document.getElementById('alertsBody');
  if (!alerts.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无告警</td></tr>';
    return;
  }
  tbody.innerHTML = alerts.map(a => `
    <tr>
      <td>${fmtTime(a.created_at)}</td>
      <td class="sev-${a.severity}">${a.severity}</td>
      <td>${a.rule_name || '—'}</td>
      <td>${platLabel(a.platform) || '—'}</td>
      <td>${(a.summary || '').slice(0, 72)}</td>
      <td>${a.acknowledged ? '✓' : `<button class="btn-ghost btn-ack" data-id="${a.id}">确认</button>`}</td>
    </tr>`).join('');
}

async function loadAnalysis() {
  const rows = await api('/api/analysis?limit=50');
  const tbody = document.getElementById('analysisBody');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无分析数据</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => {
    const sentCls = r.sentiment ? `sent-${r.sentiment}` : '';
    return `<tr>
      <td>${fmtTime(r.analyzed_at)}</td>
      <td>${platLabel(r.platform)}</td>
      <td class="${sentCls}">${r.sentiment || '—'}</td>
      <td>${r.sentiment_score != null ? r.sentiment_score.toFixed(2) : '—'}</td>
      <td>${(r.topics || []).slice(0, 3).join('、') || '—'}</td>
      <td>${(r.summary || r.content_id || '').slice(0, 48)}</td>
    </tr>`;
  }).join('');
}

async function loadRules() {
  const data = await api('/api/rules');
  const tbody = document.getElementById('rulesBody');
  const rules = data.rules || [];
  if (!rules.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">请点击上方按钮导入规则</td></tr>';
    return;
  }
  tbody.innerHTML = rules.map(r => `
    <tr>
      <td><code style="font-size:0.72rem">${r.rule_id}</code></td>
      <td>${r.name}</td>
      <td>${r.rule_type}</td>
      <td class="sev-${r.severity}">${r.severity}</td>
      <td>${(r.notification_channels || []).join('、') || '—'}</td>
    </tr>`).join('');
}



async function loadHistory() {   const eventsData = await api('/api/repo-watch/events?limit=50');   const events = eventsData.events || [];   const tbody = document.getElementById('historyEventsBody');   if (!events.length) {     tbody.innerHTML = '<tr><td colspan="7" class="empty-state">暂无运行记录</td></tr>';     return;   }   tbody.innerHTML = events.map(e => `     <tr>       <td>${fmtTime(e.detected_at)}</td>       <td>${e.repo}</td>       <td>${branchDisplay(e.branch)}</td>       <td>${e.commit_author}</td>       <td>${fmtTime(e.committed_at)}</td>       <td><code>${e.commit_sha.slice(0, 8)}</code></td>       <td>${(e.commit_message || '').slice(0, 40)}</td>     </tr>`).join(''); }

async function loadRepos() {
  const repoJobs = allJobs.length ? allJobs.filter(isRepoJob) : (await api('/api/jobs')).filter(isRepoJob);
  renderJobsList('reposJobsList', repoJobs, '暂无仓库任务，请在「监控任务」中创建');
}function selectedRuleSets() {
  const sel = document.getElementById('newRuleSets');
  return Array.from(sel.selectedOptions).map(o => o.value);
}

async function createSocialJob() {
  const platform = document.getElementById('newPlatform').value;
  const keywords = document.getElementById('newKeywords').value.trim();
  if (!keywords) { toast('请输入关键词'); return; }
  const rule_set_ids = selectedRuleSets();
  await api('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform, keywords, source_type: 'social', rule_set_ids }),
  });
  document.getElementById('newKeywords').value = '';
  toast('舆情任务已创建');
  await refresh();
}

async function createRepoJob() {
  const platform = document.getElementById('newRepoPlatform').value;
  const repo = document.getElementById('newRepo').value.trim();
  const branch = (document.getElementById('newRepoBranch')?.value || '').trim();
  const isUrl = repo.includes('github.com') || repo.includes('gitee.com') || repo.startsWith('http');
  if (!isUrl && !repo.includes('/')) {
    toast('请填写 owner/name 或完整 GitHub/Gitee 链接');
    return;
  }
  try {
    await api('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform,
        repo,
        branch,
        keywords: repo,
        source_type: platform,
      }),
    });
    document.getElementById('newRepo').value = '';
    if (document.getElementById('newRepoBranch')) {
      document.getElementById('newRepoBranch').value = '';
    }
    toast('仓库任务已创建');
    await refresh();
  } catch (e) {
    toast(e.message.includes('409') ? '该仓库任务已存在' : '创建失败');
  }
}

function formatRunResult(r) {
  const st = r.source_type || '';
  if (st === 'github' || st === 'gitee' || REPO_TYPES.has(st)) {
    if (r.repo_updated) {
      return `发现新提交 · ${r.commit_author || ''} · ${fmtTime(r.commit_at)}`;
    }
    return `无新提交 · 当前 ${(r.commit_sha || '').slice(0, 8)}`;
  }
  return `爬取 ${r.items_crawled || 0} 条 · 分析 ${r.items_analyzed || 0} 条 · 告警 ${r.alerts_triggered || 0} 条`;
}

async function runJob(id) {
  if (running) return;
  running = true;
  setButtonsDisabled(true);
  toast('执行中，请稍候…');
  try {
    const r = await api(`/api/jobs/${encodeURIComponent(id)}/run`, { method: 'POST' });
    toast(formatRunResult(r));
  } catch (e) {
    toast(`执行失败：${(e.message || '').slice(0, 80)}`);
  } finally {
    running = false;
    setButtonsDisabled(false);
    await refresh();
  }
}

async function runBatch(sourceType) {
  if (running) return;
  const labels = { all: '全部', social: '舆情', repo: '全部仓库', github: 'GitHub', gitee: 'Gitee' };
  if (!confirm(`确定立即执行「${labels[sourceType] || sourceType}」任务？`)) return;
  running = true;
  setButtonsDisabled(true);
  toast('批量执行中…');
  try {
    const data = await api(`/api/jobs/run-batch?source_type=${sourceType}`, { method: 'POST' });
    const updated = data.results.filter(x => x.repo_updated).length;
    const failed = data.results.filter(x => x.status === 'failed').length;
    toast(`完成 ${data.ran} 个任务 · 新提交 ${updated} · 失败 ${failed}`);
  } catch (e) {
    toast('批量执行失败');
  } finally {
    running = false;
    setButtonsDisabled(false);
    await refresh();
  }
}

async function runFilteredJobs() {
  const jobs = filterJobs(allJobs);
  if (!jobs.length) { toast('当前列表无任务'); return; }
  if (!confirm(`执行当前列表 ${jobs.length} 个任务？`)) return;
  running = true;
  setButtonsDisabled(true);
  let ok = 0;
  for (const j of jobs) {
    try {
      await api(`/api/jobs/${encodeURIComponent(j.job_id)}/run`, { method: 'POST' });
      ok += 1;
    } catch (_) { /* continue */ }
  }
  running = false;
  setButtonsDisabled(false);
  toast(`已执行 ${ok}/${jobs.length} 个任务`);
  await refresh();
}

async function deleteJob(id) {
  if (!confirm('确定删除此任务？')) return;
  await api(`/api/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' });
  toast('已删除');
  await refresh();
}

function openEditJob(jobId) {
  const job = allJobs.find(j => j.job_id === jobId);
  if (!job) return;
  editingJobId = jobId;
  const isRepo = isRepoJob(job);
  document.getElementById('editJobIdLabel').textContent = jobId;
  document.getElementById('editKeywords').value = job.keywords || job.repo || '';
  document.getElementById('editStatus').value = job.status || 'active';
  document.getElementById('editRuleSets').value = (job.rule_set_ids || []).join(',');
  const branchWrap = document.getElementById('editBranchWrap');
  const ruleLabel = document.getElementById('editRuleSets')?.closest('label');
  if (branchWrap) {
    branchWrap.classList.toggle('hidden', !isRepo);
    document.getElementById('editBranch').value = job.branch || '';
  }
  if (ruleLabel) ruleLabel.classList.toggle('hidden', isRepo);
  document.getElementById('editJobDialog').showModal();
}

async function saveEditJob(e) {
  e.preventDefault();
  if (!editingJobId) return;
  const job = allJobs.find(j => j.job_id === editingJobId);
  const isRepo = job && isRepoJob(job);
  const payload = {
    keywords: document.getElementById('editKeywords').value.trim(),
    status: document.getElementById('editStatus').value,
  };
  if (isRepo) {
    payload.branch = document.getElementById('editBranch').value.trim();
  } else {
    payload.rule_set_ids = document.getElementById('editRuleSets').value
      .split(',').map(s => s.trim()).filter(Boolean);
  }
  await api(`/api/jobs/${encodeURIComponent(editingJobId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  document.getElementById('editJobDialog').close();
  editingJobId = null;
  toast('任务已更新');
  await refresh();
}

async function importRules(kind) {
  const path = kind === 'joyoung' ? '/api/rules/import-joyoung' : '/api/rules/import-default';
  const data = await api(path, { method: 'POST' });
  toast(`已导入 ${data.imported} 条规则`);
  await loadRules();
}

function setButtonsDisabled(disabled) {
  document.querySelectorAll('.btn-run-job, .btn-primary, .btn-ghost').forEach(btn => {
    if (btn.id !== 'btnRefreshAll' && !btn.id.match(/^(btnSaveFeishuBot|btnTestFeishuBot|btnSyncFeishuDoc|btnPushFeishu|btnOpenPptGenerator|btnPptGenerate|btnPptCancel|btnGenerateReport|btnPptBatch)$/)) btn.disabled = disabled;
  });
}

async function refresh() {
  try {
    await loadJobs();
    await Promise.all([
      loadOverview(),
      loadAlerts(),
      loadAnalysis(),
      loadRules(),
      loadRepos(),
      loadHistory(),
      loadSettings(),
      checkHealth(),
    ]);
    lastRefresh = new Date();
    document.getElementById('lastSync').textContent =
      `同步于 ${lastRefresh.toLocaleTimeString('zh-CN')}`;
    document.getElementById('saveStatus').innerHTML =
      '<span class="save-status ok">✓ 数据已同步</span>';
  } catch (e) {
    document.getElementById('saveStatus').innerHTML =
      '<span class="save-status">同步失败</span>';
    console.error(e);
  }
}

function initNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => switchPanel(btn.dataset.panel));
  });

  document.querySelectorAll('.form-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.form-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.form-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.form === 'repo' ? 'formRepo' : 'formSocial').classList.add('active');
    });
  });

  document.getElementById('btnCreateSocial').addEventListener('click', createSocialJob);
  document.getElementById('btnCreateRepo').addEventListener('click', createRepoJob);
  document.getElementById('btnRefreshAll').addEventListener('click', refresh);
  document.getElementById('btnRunAllRepo').addEventListener('click', () => runBatch('repo'));
  document.getElementById('btnRunAllRepo2').addEventListener('click', () => runBatch('repo'));
  document.getElementById('btnRunAllSocial').addEventListener('click', () => runBatch('social'));
  document.getElementById('btnRunFiltered').addEventListener('click', runFilteredJobs);
  document.getElementById('btnImportDefaultRules').addEventListener('click', () => importRules('default'));
  document.getElementById('btnImportJoyoungRules').addEventListener('click', () => importRules('joyoung'));
  document.getElementById('btnSyncNotifications')?.addEventListener('click', async () => {
    const r = await api('/api/system/sync-notifications', { method: 'POST' });
    toast(`已同步 ${r.synced} 个通知渠道`);
    await loadSettings();
  });
  document.getElementById('btnReloadRuleSets')?.addEventListener('click', loadRuleSetOptions);
  document.getElementById('editJobForm')?.addEventListener('submit', saveEditJob);
  document.getElementById('btnEditCancel')?.addEventListener('click', () => {
    document.getElementById('editJobDialog').close();
    editingJobId = null;
  });

  document.querySelectorAll('#jobFilters .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#jobFilters .chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      jobFilter = chip.dataset.filter;
      renderJobsList('jobsList', filterJobs(allJobs), '暂无监控任务');
    });
  });

  document.body.addEventListener('click', e => {
    const runBtn = e.target.closest('.btn-run-job');
    if (runBtn) { runJob(runBtn.dataset.jobId); return; }
    const editBtn = e.target.closest('.btn-edit-job');
    if (editBtn) { openEditJob(editBtn.dataset.jobId); return; }
    const delBtn = e.target.closest('.btn-del-job');
    if (delBtn) { deleteJob(delBtn.dataset.jobId); return; }
    const ackBtn = e.target.closest('.btn-ack');
    if (ackBtn) {
      api(`/api/alerts/${ackBtn.dataset.id}/acknowledge`, { method: 'POST' }).then(refresh);
    }
  });

}

initNav();
loadRuleSetOptions();
refresh();
setInterval(refresh, 60000);
