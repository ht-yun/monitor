// ===== PPT Generator Functions =====
var pptStyles = [];
var pptRepos = [];

function initPptEvents() {
  try {
    var genBtn = document.getElementById("btnOpenPptGenerator");
    if (genBtn) genBtn.addEventListener("click", openPptDialog);
    var batchBtn = document.getElementById("btnPptBatch");
    if (batchBtn) batchBtn.addEventListener("click", batchGeneratePpt);
    var cancelBtn = document.getElementById("btnPptCancel");
    if (cancelBtn) cancelBtn.addEventListener("click", function() {
      var d = document.getElementById("pptDialog");
      if (d) d.close();
    });
    var form = document.getElementById("pptForm");
    if (form) form.addEventListener("submit", generatePpt);
    var styleSelect = document.getElementById("pptStyleSelect");
    if (styleSelect) styleSelect.addEventListener("change", updateStylePreview);
    var repoSelect = document.getElementById("pptRepoSelect");
    if (repoSelect) repoSelect.addEventListener("change", onPptRepoChange);
  } catch(e) { console.error("initPptEvents error:", e); }
}

async function loadPptRepos() {
  try {
    var repos = await api("/api/ppt-generator/repositories");
    pptRepos = repos;
    var sel = document.getElementById("pptRepoSelect");
    if (!sel) return;
    var active = repos.filter(function(r) { return r.status === "active"; });
    sel.innerHTML = '' +
      active.map(function(r) {
        return '<option value="' + r.id + '">' + r.platform + '/' + r.repo + '</option>';
      }).join('');
    var genBtn = document.getElementById("btnPptGenerate");
    if (genBtn) genBtn.disabled = active.length === 0;
  } catch(e) { console.error("loadPptRepos error:", e); }
}

function onPptRepoChange() {
  var sel = document.getElementById("pptRepoSelect");
  var branchSel = document.getElementById("pptBranchSelect");
  if (!sel || !branchSel) return;
  var repoId = parseInt(sel.value);
  if (!repoId) {
    branchSel.innerHTML = '<option value="">—— 全部分支 ——</option>';
    return;
  }
  var repo = null;
  for (var i = 0; i < pptRepos.length; i++) {
    if (pptRepos[i].id === repoId) { repo = pptRepos[i]; break; }
  }
  if (!repo) {
    branchSel.innerHTML = '<option value="">—— 全部分支 ——</option>';
    return;
  }
  var branches = repo.branches || [];
  var activeBranches = branches.filter(function(b) { return b.status === "active"; });
  branchSel.innerHTML = '<option value="">—— 全部分支 ——</option>' +
    activeBranches.map(function(b) {
      var label = b.branch;
      if (b.is_default) label += " (default)";
      if (b.last_sha) label += " [" + b.last_sha.slice(0, 8) + "]";
      return '<option value="' + b.branch + '">' + label + '</option>';
    }).join('');
}

async function loadPptStyles() {
  try {
    var data = await api("/api/ppt-generator/styles");
    pptStyles = data.styles || [];
    var sel = document.getElementById("pptStyleSelect");
    if (!sel) return;
    sel.innerHTML = '' +
      pptStyles.map(function(s) {
        return '<option value="' + s.id + '">' + s.name + '</option>';
      }).join('');
  } catch(e) { console.error("loadPptStyles error:", e); }
}

function updateStylePreview() {
  try {
    var sel = document.getElementById("pptStyleSelect");
    var preview = document.getElementById("pptStylePreview");
    if (!sel || !preview) return;
    var styleId = parseInt(sel.value);
    if (!styleId) { preview.style.display = "none"; return; }
    var style = null;
    for (var i = 0; i < pptStyles.length; i++) {
      if (pptStyles[i].id === styleId) { style = pptStyles[i]; break; }
    }
    if (!style) { preview.style.display = "none"; return; }
    preview.style.display = "block";
    preview.style.border = "1px solid " + style.line;
    preview.style.background = style.bg;
    var accent = document.getElementById("styleAccentPreview");
    var bgPrev = document.getElementById("styleBgPreview");
    if (accent) { accent.style.background = style.accent; accent.textContent = '强调色 ' + style.accent; }
    if (bgPrev) { bgPrev.style.background = style.bg; bgPrev.style.color = style.title; bgPrev.textContent = '背景色 ' + style.bg; }
    var mood = document.getElementById("styleMoodPreview");
    var suit = document.getElementById("styleSuitablePreview");
    if (mood) mood.textContent = style.mood || "";
    if (suit) suit.textContent = '适用: ' + (style.suitable_for || "");
    var imgWrap = document.getElementById("pptStyleImageWrap");
    var img = document.getElementById("pptStyleImage");
    if (style.preview_url && img && imgWrap) {
      img.src = style.preview_url;
      img.alt = style.name;
      imgWrap.style.display = "block";
    } else if (imgWrap) {
      imgWrap.style.display = "none";
    }
  } catch(e) { console.error("updateStylePreview error:", e); }
}

function updateStylePreview_old() {
  try {
    var sel = document.getElementById("pptStyleSelect");
    var preview = document.getElementById("pptStylePreview");
    if (!sel || !preview) return;
    var styleId = parseInt(sel.value);
    if (!styleId) { preview.style.display = "none"; return; }
    var style = null;
    for (var i = 0; i < pptStyles.length; i++) {
      if (pptStyles[i].id === styleId) { style = pptStyles[i]; break; }
    }
    if (!style) { preview.style.display = "none"; return; }
    preview.style.display = "block";
    preview.style.border = "1px solid " + style.line;
    preview.style.background = style.bg;
    var accent = document.getElementById("styleAccentPreview");
    var bgPrev = document.getElementById("styleBgPreview");
    if (accent) { accent.style.background = style.accent; }
    if (bgPrev) { bgPrev.style.background = style.bg; bgPrev.style.color = style.title; }
  } catch(e) { console.error("updateStylePreview error:", e); }
}

function openPptDialog() {
  var dialog = document.getElementById("pptDialog");
  if (!dialog) return;
  var statusEl = document.getElementById("pptStatus");
  var resultEl = document.getElementById("pptResult");
  var preview = document.getElementById("pptStylePreview");
  if (statusEl) statusEl.style.display = "none";
  if (resultEl) resultEl.style.display = "none";
  if (preview) preview.style.display = "none";
  loadPptRepos();
  loadPptStyles();
  try { dialog.showModal(); } catch(e) { console.error(e); }
}

async function generatePpt(e) {
  e.preventDefault();
  var repoId = document.getElementById("pptRepoSelect").value;
  if (!repoId) { toast("\u8bf7\u9009\u62e9\u4ed3\u5e93"); return; }
  var styleId = parseInt(document.getElementById("pptStyleSelect").value) || 4;
  var commitCount = parseInt(document.getElementById("pptCommitCount").value) || 20;
  var statusEl = document.getElementById("pptStatus");
  var resultEl = document.getElementById("pptResult");
  if (!statusEl || !resultEl) return;
  statusEl.style.display = "block";
  statusEl.textContent = "\u6b63\u5728\u62c9\u53d6\u4ed3\u5e93\u4fe1\u606f...";
  resultEl.style.display = "none";
  document.getElementById("btnPptGenerate").disabled = true;
  try {
    var params = new URLSearchParams({ repository_id: repoId, commit_count: commitCount, style_id: styleId });
    var branch = document.getElementById("pptBranchSelect").value;
    if (branch) params.set("branch", branch);
    statusEl.textContent = "\u6b63\u5728\u751f\u6210 PPT \u63d0\u793a\u8bcd...";
    var result = await api("/api/ppt-generator/generate?" + params.toString(), { method: "POST" });
    statusEl.style.display = "none";
    resultEl.style.display = "block";
    resultEl.innerHTML = "<strong>\u751f\u6210\u6210\u529f\uff01</strong><br>" +
      "\u4ed3\u5e93: " + result.repo + "<br>" +
      "\u98ce\u683c: " + (result.style || "") + "<br>" +
      "\u6587\u4ef6: " + result.filename + "<br><br>" +
      "<a href=\"/api/ppt-generator/download/" + encodeURIComponent(result.filename) +
      "\" class=\"btn-primary\" style=\"display:inline-block;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:0.85rem\" download>\u4e0b\u8f7d\u6587\u4ef6</a>";
    toast("PPT \u63d0\u793a\u8bcd\u5df2\u751f\u6210");
  } catch(e) {
    statusEl.style.display = "none";
    resultEl.style.display = "block";
    resultEl.style.color = "var(--critical)";
    resultEl.innerHTML = "\u751f\u6210\u5931\u8d25: " + (e.message || "\u8bf7\u6c42\u9519\u8bef");
  } finally {
    document.getElementById("btnPptGenerate").disabled = false;
  }
}

async function batchGeneratePpt() {
  if (!confirm("\u786e\u5b9a\u4e3a\u6240\u6709\u6d3b\u8dc3\u4ed3\u5e93\u751f\u6210 PPT \u63d0\u793a\u8bcd\uff1f")) return;
  var btn = document.getElementById("btnPptBatch");
  if (btn) { btn.disabled = true; btn.textContent = "\u751f\u6210\u4e2d..."; }
  toast("\u6b63\u5728\u6279\u91cf\u751f\u6210...");
  try {
    var result = await api("/api/ppt-generator/generate-all?style_id=4&commit_count=10", { method: "POST" });
    toast("\u6279\u91cf\u5b8c\u6210: " + result.succeeded + "/" + result.total + " \u6210\u529f");
    if (result.failed > 0) {
      result.results.filter(function(r) { return r.status === "error"; }).forEach(function(r) {
        console.error("Batch error:", r.repo, r.error);
      });
    }
  } catch(e) { toast("\u6279\u91cf\u5931\u8d25: " + (e.message || "")); }
  finally { if (btn) { btn.disabled = false; btn.textContent = "\u6279\u91cf\u751f\u6210"; } }
}
