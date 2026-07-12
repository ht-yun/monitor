// ===== Feishu Bot Functions =====

function initFeishuBot() {
  try {
    // 显式启用并绑定飞书按钮
    var saveBtn = document.getElementById('btnSaveFeishuBot');
    if (saveBtn) { saveBtn.disabled = false; saveBtn.addEventListener('click', saveFeishuBotConfig); console.log('[Feishu] saveBtn bound'); }
    var testBtn = document.getElementById('btnTestFeishuBot');
    if (testBtn) { testBtn.disabled = false; testBtn.addEventListener('click', testFeishuBot); console.log('[Feishu] testBtn bound'); }
    var syncBtn = document.getElementById('btnSyncFeishuDoc');
    if (syncBtn) { syncBtn.disabled = false; syncBtn.addEventListener('click', syncFeishuDoc); console.log('[Feishu] syncBtn bound'); }
    
    // 每次系统设置面板切换时重新启用按钮 + 加载配置
    var settingsNav = document.querySelector('.nav-item[data-panel="settings"]');
    if (settingsNav) {
      settingsNav.addEventListener('click', function() {
        setTimeout(function(){
          var btns = document.querySelectorAll('#panel-settings .btn-primary, #panel-settings .btn-ghost');
          btns.forEach(function(b){ b.disabled = false; });
          loadFeishuBotConfig();
        }, 100);
      });
    }
    // 仓库监控面板切换时启用推送按钮
    var reposNav = document.querySelector('.nav-item[data-panel="repos"]');
    if (reposNav) {
      reposNav.addEventListener('click', function() {
        setTimeout(initPushFeishuBtn, 100);
      });
    }
    var syncBtn2 = document.getElementById('btnSyncBranches'); if (syncBtn2 && !syncBtn2._listenerAttached) { syncBtn2.addEventListener('click', reconcileRepositories); syncBtn2._listenerAttached = true; console.log('[Feishu] syncBranches bound'); } console.log('[Feishu] initFeishuBot complete');
  } catch(e) { console.error('initFeishuBot error:', e); }
}

async function loadFeishuBotConfig() {
  try {
    var cfg = await api('/api/notifications/feishu-bot');
    var inp = document.getElementById('feishuBotWebhook');
    var chk = document.getElementById('feishuBotEnabled');
    if (chk) chk.checked = cfg.enabled;
    var status = document.getElementById('feishuBotStatus');
    if (status) {
      if (cfg.configured) {
        status.innerHTML = '✅ 飞书机器人已配置（来源: ' + cfg.source + '）';
        status.style.color = 'var(--info)';
      } else {
        status.innerHTML = '❌ 未配置飞书机器人';
        status.style.color = 'var(--warning)';
      }
    }
    if (cfg.masked_webhook_url && inp) inp.placeholder = '当前: ' + cfg.masked_webhook_url;
  } catch(e) { console.error('loadFeishuBotConfig error:', e); }
}

async function saveFeishuBotConfig() {
  var webhook_url = (document.getElementById('feishuBotWebhook')?.value || '').trim();
  var enabled = document.getElementById('feishuBotEnabled')?.checked || false;
  if (!webhook_url) { toast('请输入飞书机器人 Webhook 地址'); return; }
  try {
    await api('/api/notifications/feishu-bot', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ webhook_url: webhook_url, enabled: enabled }),
    });
    toast('飞书机器人配置已保存');
    await loadFeishuBotConfig();
  } catch(e) { toast('保存失败: ' + (e.message || '')); }
}

async function testFeishuBot() {
  var status = document.getElementById('feishuBotStatus');
  try {
    if (status) { status.innerHTML = '正在发送测试消息...'; status.style.color = 'var(--ink-muted)'; }
    await api('/api/notifications/feishu-bot/test', { method: 'POST' });
    toast('测试消息已发送到飞书');
    if (status) { status.innerHTML = '✅ 测试消息发送成功！'; status.style.color = 'var(--info)'; }
  } catch(e) {
    toast('测试发送失败: ' + (e.message || ''));
    if (status) { status.innerHTML = '❌ 测试发送失败: ' + (e.message || ''); status.style.color = 'var(--critical)'; }
  }
}

async function syncFeishuDoc() {
  try {
    toast('正在同步飞书仓库文档...');
    var result = await api('/api/feishu/sync?reconcile=true', { method: 'POST' });
    toast('同步完成: ' + (result.message || ''));
  } catch(e) { toast('同步失败: ' + (e.message || '')); }
}

async function reconcileRepositories() {
  var btn = document.getElementById('btnSyncBranches');
  if (btn) { btn.disabled = true; btn.textContent = '同步中...'; }
  try {
    var result = await api('/api/repositories/reconcile', { method: 'POST' });
    toast('分支同步完成: ' + (result.branches_created || 0) + ' 个新分支, ' + (result.branches_deleted || 0) + ' 个已移除');
  } catch(e) { toast('分支同步失败: ' + (e.message || '')); }
  finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '同步分支';
    }
  }
}

async function pushFeishuRepoReport() {
  var btn = document.getElementById('btnPushFeishu');
  if (btn) { btn.disabled = true; btn.textContent = '推送中...'; }
  try {
    var repoJobs = allJobs.length ? allJobs.filter(isRepoJob) : (await api('/api/jobs')).filter(isRepoJob);
    var active = repoJobs.filter(function(j) { return j.status === 'active'; });
    if (!active.length) { toast('没有活跃的仓库任务可推送'); return; }

    var lines = ['【仓库监控报告】', '时间: ' + new Date().toLocaleString('zh-CN'), ''];
    for (var i = 0; i < active.length; i++) {
      var j = active[i];
      var repo = j.repo || j.keywords || '';
      var branch = j.branch || '';
      var sha = (j.last_sha || '').slice(0, 8);
      var author = j.last_commit_author || '';
      var time = j.latest_update_at ? j.latest_update_at.slice(0, 10) : '';
      lines.push(repo + (branch ? ' [' + branch + ']' : ''));
      lines.push('  最新提交: ' + sha + (author ? ' by ' + author : '') + (time ? ' at ' + time : ''));
    }
    await api('/api/notifications/feishu-bot/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '仓库监控报告', body: lines.join('\n') }),
    });
    toast('仓库报告已推送到飞书');
  } catch(e) { toast('推送失败: ' + (e.message || '')); }
  finally { if (btn) { btn.disabled = false; btn.textContent = '推送飞书'; } }
}

function initPushFeishuBtn() {
  var btn = document.getElementById('btnPushFeishu');
  if (btn && !btn._listenerAttached) {
    btn.addEventListener('click', pushFeishuRepoReport);
    btn._listenerAttached = true;
  }
}
