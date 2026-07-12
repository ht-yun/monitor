// ===== System Configuration Functions =====

CONFIG_GROUPS = [
  "notifications",
  "tokens",
  "ai",
  "platform_cookies"
];

GROUP_LABELS = {
  "notifications": "\u901a\u77e5\u6e20\u9053\u914d\u7f6e",
  "tokens": "Token / API \u5bc6\u94a5\u914d\u7f6e",
  "ai": "AI \u914d\u7f6e",
  "platform_cookies": "\u793e\u5a92\u5e73\u53f0 Cookie \u914d\u7f6e"
};

function initConfig() {
  try {
    var settingsNav = document.querySelector('.nav-item[data-panel="settings"]');
    if (settingsNav) {
      var handler = function() { setTimeout(function() {
        if (!document.getElementById("config-sections").hasChildNodes()) {
          renderConfigSections();
        }
        loadSysConfig();
      }, 200); };
      settingsNav.addEventListener("click", handler);
    }
  } catch(e) { console.error("initConfig error:", e); }
}

function renderConfigSections() {
  var container = document.getElementById("config-sections");
  if (!container) return;
  container.innerHTML = "";
  for (var g = 0; g < CONFIG_GROUPS.length; g++) {
    var group = CONFIG_GROUPS[g];
    var label = GROUP_LABELS[group] || group;
    var card = document.createElement("div");
    card.className = "form-card";
    card.id = "cfg-group-" + group;
    card.innerHTML = "<h3>" + label + "</h3><div id=\"cfg-items-" + group + "\"></div>" +
      '<div class="form-row" style="margin-top:12px"><button class="btn-primary" onclick="saveSysConfigGroup(\'' + group + '\')">\u4fdd\u5b58</button>' +
      '<span style="font-size:0.78rem;color:var(--ink-muted);margin-left:8px" id="cfg-msg-' + group + '"></span></div>';
    container.appendChild(card);
  }
}

async function loadSysConfig() {
  try {
    var config = await api("/api/system/config");
    for (var g = 0; g < CONFIG_GROUPS.length; g++) {
      var group = CONFIG_GROUPS[g];
      var data = config[group];
      if (!data) continue;
      var itemsDiv = document.getElementById("cfg-items-" + group);
      if (!itemsDiv) continue;
      var html = "";
      for (var i = 0; i < data.items.length; i++) {
        var item = data.items[i];
        var inputType = item.is_secret ? "password" : "text";
        var placeholder = "";
        if (item.is_secret && item.configured) {
          placeholder = "\u5f53\u524d: " + item.config_value;
        } else if (!item.configured) {
          placeholder = "\u8bf7\u8f93\u5165" + item.display_name;
        }
        var currentVal = (!item.is_secret && item.configured) ? item.config_value : "";
        var statusIcon = item.configured ? "\u2705" : "\u274c";
        var statusColor = item.configured ? "var(--info)" : "var(--warning)";
        html += '<div class="form-row" style="margin-bottom:8px">' +
          '<label style="min-width:140px;font-size:0.85rem;color:var(--ink-muted)">' + item.display_name + '</label>' +
          '<input type="' + inputType + '" id="cfg_' + item.config_key + '" value="' + currentVal + '" placeholder="' + placeholder + '" style="flex:1;min-width:200px" />' +
          '<span id="sts_' + item.config_key + '" style="font-size:0.78rem;color:' + statusColor + ';min-width:80px">' + statusIcon + ' ' + (item.configured ? "\u5df2\u914d\u7f6e" : "\u672a\u914d\u7f6e") + '</span>' +
          '</div>';
      }
      itemsDiv.innerHTML = html;
    }
  } catch(e) { console.error("loadSysConfig error:", e); }
}

async function exportCookiesToCrawler() {
  try {
    var result = await api("/api/system/config/export-cookies", { method: "POST" });
    if (result.count > 0) {
      toast("\u5df2\u5bfc\u51fa " + result.count + " \u4e2a\u5e73\u53f0\u7684 Cookie \u5230 MediaCrawler\u914d\u7f6e");
    } else {
      toast("\u6ca1\u6709\u5df2\u914d\u7f6e\u7684 Cookie \u53ef\u5bfc\u51fa");
    }
  } catch(e) { toast("\u5bfc\u51fa\u5931\u8d25: " + (e.message || "")); }
}

async function saveSysConfigGroup(group) {
  var inputs = document.querySelectorAll("#cfg-group-" + group + " input[id^=\"cfg_\"]");
  var values = [];
  for (var i = 0; i < inputs.length; i++) {
    var input = inputs[i];
    var key = input.id.replace("cfg_", "");
    var val = input.value.trim();
    if (val) {
      values.push({ config_group: group, config_key: key, config_value: val });
    }
  }
  if (!values.length) { toast("\u8bf7\u8f93\u5165\u8981\u4fdd\u5b58\u7684\u914d\u7f6e\u503c"); return; }
  try {
    await api("/api/system/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: values }),
    });
    toast(GROUP_LABELS[group] + " \u5df2\u4fdd\u5b58");
    var msg = document.getElementById("cfg-msg-" + group);
    if (msg) { msg.textContent = "\u2705 \u5df2\u4fdd\u5b58"; msg.style.color = "var(--info)"; }
    await loadSysConfig();
  } catch(e) { toast("\u4fdd\u5b58\u5931\u8d25: " + (e.message || "")); }
}
