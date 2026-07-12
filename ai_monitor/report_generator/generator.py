import os, base64, json, re, logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ai_monitor")
REPORTS_DIR = Path(__file__).resolve().parent.parent / "generated_reports"
GITHUB_API = "https://api.github.com"
GITEE_API = "https://gitee.com/api/v5"

def _parse_repo(repo):
    parts = repo.strip().strip("/").split("/")
    if len(parts) != 2: raise ValueError(f"Invalid repo: {repo}")
    return parts[0], parts[1]

async def collect_repo_data(platform, repo, token, max_commits=30):
    from ai_monitor.collectors.github_collector import GitHubCollector
    from ai_monitor.collectors.gitee_collector import GiteeCollector
    import httpx
    data = {"platform": platform, "repo": repo}
    
    if platform == "github":
        try:
            c = GitHubCollector(token)
            stats = await c.fetch_repo_stats(repo)
            for key in ['name','owner','description','language','stars','forks','open_issues','topics','default_branch','html_url']:
                data[key] = getattr(stats, key, "")
            data['created_at'] = str(stats.created_at)[:10] if stats.created_at else ""
            data['updated_at'] = str(stats.updated_at)[:10] if stats.updated_at else ""
            data['topics'] = stats.topics or []
        except: pass
        
        try: data['readme'] = (await c.fetch_readme(repo)) or ""
        except: data['readme'] = ""
        
        ow, nm = _parse_repo(repo)
        async with httpx.AsyncClient(timeout=10) as client:
            gh_headers = c._headers()
            
            try:
                r = await client.get(GITHUB_API + f"/repos/{ow}/{nm}/languages", headers=gh_headers)
                if r.status_code == 200: data['languages'] = r.json()
                else: data['languages'] = {}
            except: data['languages'] = {}
            
            data['files'] = []
            try:
                r = await client.get(GITHUB_API + f"/repos/{ow}/{nm}/contents", headers=gh_headers)
                if r.status_code == 200 and isinstance(r.json(), list):
                    data['files'] = [{"name":i['name'],'type':i['type'],'path':i['path']} for i in r.json()]
            except: pass
            
            data['config_files'] = {}
            for fname in ['requirements.txt','package.json','Dockerfile','docker-compose.yml','Makefile','go.mod','Cargo.toml','pyproject.toml','Pipfile']:
                try:
                    r = await client.get(GITHUB_API + f"/repos/{ow}/{nm}/contents/{fname}", headers={**gh_headers, 'Accept':'application/vnd.github.raw'})
                    if r.status_code == 200: data['config_files'][fname] = r.text
                except: pass
            
            data['releases'] = []
            try:
                r = await client.get(GITHUB_API + f"/repos/{ow}/{nm}/releases?per_page=5", headers=gh_headers)
                if r.status_code == 200:
                    data['releases'] = [{'tag_name':ri.get('tag_name',''),'name':ri.get('name',''),'published_at':str(ri.get('published_at',''))[:10]} for ri in r.json()]
            except: pass
            
            data['contributors'] = []
            try:
                r = await client.get(GITHUB_API + f"/repos/{ow}/{nm}/contributors?per_page=10", headers=gh_headers)
                if r.status_code == 200:
                    data['contributors'] = [{'login':ci.get('login',''),'contributions':ci.get('contributions',0)} for ci in r.json()]
            except: pass
        
        try:
            data['commits'] = await c.fetch_recent_commits(repo, count=max_commits)
        except:
            data['commits'] = []
    

    elif platform == "gitee":
        c = GiteeCollector(token)
        try:
            stats = c._parse_gitee_repo(repo)
            data['name'] = stats.name if hasattr(stats,'name') else repo.split('/')[1]
            data['description'] = ""
            data['language'] = ""
            data['stars'] = 0
            data['forks'] = 0
        except: pass
        try: data['readme'] = (await c.fetch_readme(repo)) or ""
        except: data['readme'] = ""
        data['languages'] = {}
        data['files'] = []
        data['config_files'] = {}
        data['releases'] = []
        data['contributors'] = []
        data['commits'] = []
    
    return data

async def ai_analyze(data, openai_api_key, openai_base="https://api.openai.com/v1", model="gpt-4o-mini"):
    if not openai_api_key or not data.get('readme'):
        return {'summary':'','highlights':[],'features':[],'use_case':''}
    import httpx
    prompt = f"""Analyze this project and return JSON with: summary, highlights (3-5 items), features (3-5 items), use_case.
Project: {data.get('name','')}
Description: {data.get('description','')}
Language: {data.get('language','')}
Stars: {data.get('stars',0)}
README: {(data.get('readme','') or '')[:4000]}
Output JSON only."""
    try:
        r = await httpx.AsyncClient(timeout=15).post(
            openai_base + '/chat/completions',
            headers={'Authorization':f'Bearer {openai_api_key}','Content-Type':'application/json'},
            json={'model':model,'messages':[{'role':'user','content':prompt}],'temperature':0.3,'max_tokens':800})
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            content = re.sub(r'^`(?:json)?\s*|`$','',content.strip())
            return json.loads(content)
    except: pass
    return {'summary':'','highlights':[],'features':[],'use_case':''}

def render_html(data, ai_result):
    langs = data.get('languages', {})
    lang_total = sum(langs.values()) or 1
    lang_items = sorted(langs.items(), key=lambda x: -x[1])[:8]
    lang_html = ''
    for lk, lv in lang_items:
        pct = lv / lang_total * 100
        lang_html += '<div style="display:flex;align-items:center;margin:4px 0"><span style="width:100px;font-size:0.85rem;color:#555">' + str(lk) + '</span><div style="flex:1;height:16px;background:#e8e0d0;border-radius:4px;overflow:hidden"><div style="width:' + format(pct, '.1f') + '%;height:100%;background:#5a8f6e;border-radius:4px"></div></div><span style="width:60px;text-align:right;font-size:0.8rem;color:#777">' + format(pct, '.1f') + '%</span></div>'
    
    files = data.get('files', [])
    dirs = [f for f in files if f['type'] == 'dir']
    only_files = [f for f in files if f['type'] == 'file']
    struct = '<div style="font-family:monospace;font-size:0.85rem;color:#3d4a3d">'
    for d in dirs[:10]: struct += '<div style="color:#5a8f6e">&#128193; ' + d['name'] + '/</div>'
    for f in only_files[:15]: struct += '<div>&#128196; ' + f['name'] + '</div>'
    if len(dirs) > 10: struct += '<div style="color:#999">... +' + str(len(dirs)-10) + ' more dirs</div>'
    if len(only_files) > 15: struct += '<div style="color:#999">... +' + str(len(only_files)-15) + ' more files</div>'
    struct += '</div>'
    
    cf = data.get('config_files', {})
    cfg_html = ''
    for fname, content in cf.items():
        cfg_html += '<h4 style="margin:10px 0 4px;font-size:0.9rem;color:#3d4a3d">' + fname + '</h4>'
        lines = content.split('\n')[:15]
        cfg_html += '<pre style="background:#f4f1ea;padding:8px;border-radius:6px;font-size:0.78rem;overflow-x:auto;white-space:pre-wrap;max-height:200px;overflow-y:auto">'
        for l in lines:
            if l.strip(): cfg_html += '<span style="color:#6b7a6b">' + l + '</span>\n'
        if len(content.split('\n')) > 15: cfg_html += '<span style="color:#999">... truncated</span>'
        cfg_html += '</pre>'
    
    summary = ai_result.get('summary','') or ''
    highlights = ai_result.get('highlights',[]) or []
    features = ai_result.get('features',[]) or []
    use_case = ai_result.get('use_case','') or ''
    
    releases = data.get('releases',[])
    rel_html = ''
    for r in releases[:5]:
        rel_html += '<div style="padding:6px 0;border-bottom:1px solid #e8e0d0"><strong>' + r.get('tag_name','') + '</strong> <span style="color:#777;font-size:0.8rem">' + r.get('published_at','') + '</span></div>'
    if not rel_html: rel_html = '<div style="color:#999">No releases</div>'
    
    contribs = data.get('contributors',[])
    contrib_html = '<div style="display:flex;flex-wrap:wrap;gap:12px">'
    for c in contribs[:10]:
        contrib_html += '<div style="background:#f4f1ea;padding:6px 12px;border-radius:6px;font-size:0.85rem"><strong>' + c['login'] + '</strong> <span style="color:#777">(' + str(c['contributions']) + ' commits)</span></div>'
    contrib_html += '</div>'
    if not contribs: contrib_html = '<div style="color:#999">No data</div>'
    
    topics = data.get('topics',[])
    topics_html = ''
    for t in topics:
        topics_html += '<span style="display:inline-block;background:#e8f0e8;color:#5a8f6e;padding:2px 8px;border-radius:12px;font-size:0.78rem;margin:2px">' + t + '</span>'
    if not topics: topics_html = '<span style="color:#999">No topics</span>'
    
    h = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>Report - ' + data.get('name',data.get('repo','')) + '</title>'
    h += '<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:#f7f4ed;color:#3d4a3d;padding:30px}.report{max-width:800px;margin:0 auto;background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(61,74,61,0.1)}.header{background:linear-gradient(135deg,#b8cbb8,#8fa88f);padding:30px 36px;color:#fff}.header h1{font-size:1.6rem;font-weight:600;margin-bottom:6px}.header .meta{display:flex;gap:16px;flex-wrap:wrap;font-size:0.85rem;margin-top:12px}.header .meta span{background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:6px}.body{padding:30px 36px}.section{margin-bottom:28px}.section h2{font-size:1.1rem;font-weight:600;color:#3d4a3d;padding-bottom:8px;border-bottom:2px solid #b8cbb8;margin-bottom:14px}.tag{display:inline-block;background:#e8f0e8;color:#5a8f6e;padding:2px 8px;border-radius:4px;font-size:0.78rem}.ai-box{background:#f0f6f0;border:1px solid #b8cbb8;border-radius:10px;padding:16px;margin-bottom:14px}.footer{text-align:center;padding:16px;font-size:0.78rem;color:#999;border-top:1px solid #e8e0d0}</style></head><body><div class="report">'
    h += '<div class="header"><h1>' + data.get('name',data.get('repo','')) + '</h1><p>' + data.get('description','') + '</p><div class="meta"><span>&#11088; ' + str(data.get('stars',0)) + '</span><span>&#128200; ' + str(data.get('forks',0)) + '</span><span>' + str(data.get('language','')) + '</span><span>' + str(data.get('default_branch','')) + '</span></div><div style="margin-top:10px">' + topics_html + '</div></div>'
    h += '<div class="body">'
    
    if summary:
        h += '<div class="section"><h2>AI &#20998;&#26512;</h2><div class="ai-box"><p>' + summary + '</p></div>'
        if highlights: h += '<div class="ai-box"><h3>&#39033;&#30446;&#20142;&#28857;</h3><ul>' + ''.join('<li>' + str(x) + '</li>' for x in highlights) + '</ul></div>'
        if features: h += '<div class="ai-box"><h3>&#21151;&#33021;&#29305;&#24615;</h3><ul>' + ''.join('<li>' + str(x) + '</li>' for x in features) + '</ul></div>'
        if use_case: h += '<div class="ai-box"><h3>&#36866;&#29992;&#22330;&#26223;</h3><p>' + use_case + '</p></div>'
        h += '</div>'
    
    h += '<div class="section"><h2>&#25216;&#26415;&#26632;</h2><p>Main: <span class="tag">' + str(data.get('language','N/A')) + '</span></p><div style="max-width:400px">' + lang_html + '</div></div>'
    h += '<div class="section"><h2>&#24037;&#31243;&#37197;&#32622;</h2>' + (cfg_html if cfg_html else '<p style="color:#999">No config files found</p>') + '</div>'
    h += '<div class="section"><h2>&#30446;&#24405;&#32467;&#26500;</h2>' + struct + '</div>'
    h += '<div class="section"><h2>&#24320;&#21457;&#27963;&#36291;&#24230;</h2><div style="margin-bottom:12px">' + str(len(data.get('commits',[]))) + ' recent commits</div>'
    h += '<h3 style="font-size:0.9rem;color:#555;margin:14px 0 8px">Releases</h3>' + rel_html
    h += '<h3 style="font-size:0.9rem;color:#555;margin:14px 0 8px">Contributors</h3>' + contrib_html + '</div>'
    h += '<div class="section"><h2>Report Info</h2><p>Generated: ' + datetime.now().strftime('%Y-%m-%d %H:%M') + '</p><p>Platform: ' + str(data.get('platform','')) + ' | Repo: ' + str(data.get('repo','')) + '</p></div>'
    h += '<div class="footer">AI Monitor - Project Report</div></div></div></body></html>'
    return h

async def generate_report(platform, repo, token, openai_api_key=None, openai_base=None, openai_model=None):
    from ai_monitor.config.settings import get_settings
    settings = get_settings()
    data = await collect_repo_data(platform, repo, token)
    ai_result = await ai_analyze(data, openai_api_key or settings.OPENAI_API_KEY, openai_base or settings.OPENAI_API_BASE, openai_model or settings.OPENAI_MODEL)
    html = render_html(data, ai_result)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe = repo.replace('/', '_').replace(':', '_')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{safe}_{ts}.html"
    open(REPORTS_DIR / filename, 'w', encoding='utf-8').write(html)
    return {'filename': filename, 'file_path': str(REPORTS_DIR / filename), 'html_content': html, 'repo': f"{platform}/{repo}", 'generated_at': datetime.now().isoformat(), 'has_ai': bool(ai_result.get('summary')), 'lang_count': len(data.get('languages',{}))}
