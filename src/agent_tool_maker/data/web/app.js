'use strict';
// All dynamic content is textContent/DOM nodes, never provider-controlled HTML.
const $ = (q, root = document) => root.querySelector(q);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs)) {
    if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (k === 'class') n.className = v;
    else if (k in n) n[k] = v;
    else n.setAttribute(k,v);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined) n.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return n;
};
// The bearer lives in this tab's sessionStorage (exact origin, this tab only); never localStorage or cookies.
const TOKEN_KEY = 'atm-console-token';
const tabToken = {
  get() { try { return sessionStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } },
  set(value) { try { sessionStorage.setItem(TOKEN_KEY, value); } catch {} },
  clear() { try { sessionStorage.removeItem(TOKEN_KEY); } catch {} }
};
let token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
if (token) tabToken.set(token); else token = tabToken.get();
if (location.hash) history.replaceState(null, '', location.pathname);
const forgetToken = () => { token = ''; tabToken.clear(); };
let data = null, active = 'overview', noticeTimer;
const toolFilters={q:'',mode:'',status:''};
const labels = {
  configured_not_verified:'已配置 · 未验证', not_registered:'未注册', registered_not_host_verified:'已注册 · 待宿主验收',
  registration_changed:'注册文件已变化', cli_not_configured:'CLI 未绑定', missing_credential:'未连接', needs_unlock:'需要解锁',
  unlock_not_checked:'未检查解锁', unlocked_in_this_process:'本次请求已解锁', not_initialized:'尚未初始化',
  keyring_unavailable:'系统凭证库不可用', executable_changed:'程序已变化', executable_missing:'程序缺失',
  credential_expired:'凭证已过期', browser_login_unknown:'交给浏览器', host_desktop_required:'交给桌面工具',
  host_human_required:'等待人工', mcp_not_configured:'MCP 未绑定', workflow_dependencies_not_verified:'待检查依赖',
  sync_conflict:'凭证冲突 · 已暂停', disabled:'已停用', missing_origin:'未设服务地址', probe_passed:'账户探针通过', completed:'完成',
  queued:'已排队', running:'运行中', submitting:'提交中', submission_unknown:'提交状态待核对', failed:'失败',
  requires_browser:'等待浏览器', requires_desktop:'等待桌面', requires_human:'等待人工', planned:'待确认',
  applied:'配置已应用', needs_dependencies:'仍有依赖待安装', already_configured:'已有连接，已保留', saved:'已加密保存'
};
const display = value => labels[value] || value || '未知';
const badge = (value, kind='') => el('span',{class:'badge '+kind},display(value));
const code = value => el('pre',{class:'codebox'},typeof value === 'string' ? value : JSON.stringify(value,null,2));
function brandMark(brand,compact=false) {
  const mark=el('span',{class:'provider-mark'+(compact?' compact':''),ariaHidden:'true','data-brand':brand.key});
  const fallback=()=>{mark.classList.add('initials');mark.replaceChildren(document.createTextNode(brand.initials));};
  if (brand.src) mark.append(el('img',{src:brand.src,alt:'',width:28,height:28,decoding:'async',onerror:()=>{
    fallback();console.warn('ATM brand image failed to render:',brand.key);
  }}));
  else fallback();
  return mark;
}
function brandIdentity(provider,content,toolId='',compact=false) {
  return el('div',{class:'provider-identity'},brandMark(window.ATM_BRANDS.get(provider,toolId),compact),el('div',{class:'provider-copy'},...content));
}
function toolCollection() {
  const groups=new Map();
  for (const tool of data.tools) {
    const brand=window.ATM_BRANDS.get(tool.provider,tool.id);
    if(!groups.has(brand.key))groups.set(brand.key,{brand,provider:tool.provider,count:0});
    groups.get(brand.key).count++;
  }
  const priority=['tripo','higgsfield','fal','xyq','comfyui','meshy','runway','elevenlabs','suno','ffmpeg','blender','github'];
  const rank=key=>priority.includes(key)?priority.indexOf(key):priority.length;
  const selected=[...groups.values()].sort((a,b)=>rank(a.brand.key)-rank(b.brand.key)||a.brand.name.localeCompare(b.brand.name)).slice(0,12);
  const browse=query=>{toolFilters.q=query;toolFilters.mode='';toolFilters.status='';active='tools';render();};
  return el('section',{class:'tool-collection'},
    el('div',{class:'section-head'},el('div',{},el('h2',{},'你的工具箱'),el('small',{},groups.size+' 个提供方 · 图标用于识别，登录与可用性请查看状态')),btn('查看全部工具 →',()=>browse(''),'plain')),
    el('div',{class:'brand-grid'},...selected.map(({brand,provider,count})=>el('button',{class:'brand-tile',onclick:()=>browse(brand.key==='tripo'?'tripo.':provider)},
      brandMark(brand),el('span',{class:'brand-name'},brand.name),el('small',{},count+' 个动作'),el('span',{class:'brand-arrow',ariaHidden:'true'},'↗')))));
}
const toast = (message, error=false) => {
  const n=$('#toast'); n.textContent=message; n.className=error?'error':''; n.hidden=false;
  clearTimeout(noticeTimer); noticeTimer=setTimeout(()=>n.hidden=true,7500);
};
const action = fn => async event => {
  const b=event?.currentTarget; if (b?.tagName==='BUTTON') b.disabled=true;
  try { await fn(event); } catch(e) { toast(e.message || '操作失败，请检查本地状态。',true); }
  finally { if (b?.isConnected) b.disabled=false; }
};
async function api(path, body) {
  const opts={headers:{Authorization:'Bearer '+token},cache:'no-store'};
  if (body !== undefined) {opts.method='POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
  const r=await fetch(path,opts); const value=await r.json();
  if (!r.ok) {
    if(r.status===401) {forgetToken(); $('#gate').hidden=false;}
    throw new Error((value.error?.code || 'request_failed')+': '+(value.error?.message || '请求未完成'));
  }
  return value;
}
async function refresh() {
  const [overview,tools,connections,jobs,clis,sync,access,extensions,session,passkeys]=await Promise.all(['/api/overview','/api/tools','/api/connections','/api/jobs','/api/clis','/api/sync','/api/access','/api/extensions','/api/session','/api/passkeys'].map(p=>api(p)));
  data={overview,tools:tools.tools,connections,jobs:jobs.jobs,clis:clis.clis,sync,access,extensions,session,passkeys,sessionFetchedAt:Date.now()};
  $('#version').textContent='ATM v'+overview.version;
  $('#origin').textContent=location.host;
  $('#gate').hidden=true;
  render();
}
const btn=(text,fn,type='secondary')=>el('button',{class:type,onclick:action(fn)},text);
function heading(title,subtitle,button) {
  return el('section',{class:'page-title'},el('div',{},el('p',{class:'eyebrow'},'AGENT TOOL MAKER / YOUR LOCAL WORKSHOP'),el('h1',{},title),el('p',{},subtitle)),button);
}
function section(title,meta='') {return el('div',{class:'section-head'},el('h2',{},title),el('small',{},meta));}
function openModal(title,...content) {$('#modal-title').textContent=title;$('#modal-body').replaceChildren(...content.flat().filter(c=>c!==null&&c!==undefined));if(!$('#modal').open)$('#modal').showModal();}
function closeModal() {$('#modal').close();$('#modal-body').replaceChildren();}
function agentCard(a) {
  const registered=a.state==='registered_not_host_verified';
  return el('article',{class:'card'},
    el('div',{class:'card-head'},brandIdentity(a.agent,[el('h3',{},a.label),el('small',{},'默认支持 · 用户级 Skill')]),badge(registered?'已注册':'待配置',registered?'good':'warn')),
    el('p',{},a.detected_executable?'检测到本地客户端入口。客户端加载及登录尚未验证。':'未在 PATH 检测到客户端 CLI。可预先注册 Skill；不会自动安装客户端。'),
    el('code',{class:'path'},a.skill_path || a.default_skill_path),
    el('div',{class:'card-actions'},btn(registered?'检查 / 更新注册':'配置此客户端',()=>setupDialog([a.agent])),registered?btn('移除入口',async()=>{
      if(!confirm('移除 '+a.label+' 的 ATM Skill？保留备份，不删除任何凭证或工具。'))return;
      await api('/api/agents/unregister',{agent:a.agent,confirm:a.agent}); await refresh(); toast('入口已移除；凭证与工具未改变。');
    },'plain danger'):null));
}
function render() {
  if(!data)return;
  document.querySelectorAll('[data-nav]').forEach(n=>n.classList.toggle('active',n.dataset.nav===active));
  const main=$('#main'); main.replaceChildren();
  if(active==='overview') {
    main.append(heading('连接一次，持续使用。','Claude Code 与 Codex，共用一套工具、凭证和执行记录。',btn('配置默认客户端 →',()=>setupDialog(), 'primary')));
    main.append(sessionPanel());
    const c=data.overview.counts;
    main.append(el('div',{class:'stats'},...[[c.tools,'工具动作','API · CLI · MCP · 外部交接'],[c.enabled,'启用的动作','同一开关作用于所有本地 Agent'],[c.connections,'已保存连接','已配置不等于上游已验证'],[c.recent_jobs,'最近任务','最多统计最近 50 条']].map(([n,t,h])=>el('div',{class:'stat'},el('small',{},t),el('strong',{},n),el('span',{},h)))));
    main.append(section('默认客户端','共用 ATM · 不复制密钥'),el('div',{class:'grid2'},...data.overview.agents.map(agentCard)));
    main.append(el('div',{class:'notice'},'本页只检查本地配置，不执行生成、发帖或部署。网页修改与 CLI 即时共用；新会话复用同一持久状态目录。'));
    main.append(toolCollection());
    main.append(section('从配置到交付','YOUR CONTROL LOOP'),el('div',{class:'panel workflow'},
      ...[['01 / CONNECT','准备工具入口','注册客户端、绑定已安装的 CLI。只为缺少的连接提供凭证。'],['02 / INSPECT','按任务检查状态','查看参数、权限与连接状态。把“已保存”与“可用”分开判断。'],['03 / EXECUTE','由 Agent 完成任务','主 Agent 通过 ATM CLI 执行；在这里查看脱敏的任务摘要。']].map(([i,t,p])=>el('div',{class:'step'},el('b',{},i),el('h3',{},t),el('p',{},p)))));
    main.append(el('p',{class:'quiet'},'持久状态目录：'+data.overview.home));
  } else if(active==='agents') {
    main.append(heading('Agent 客户端','默认支持 Claude Code、Codex；所有客户端调用同一个 ATM 执行器。',btn('预览默认注册',()=>setupDialog(),'primary')));
    main.append(el('div',{class:'grid2'},...data.overview.agents.map(agentCard)),section('安装与会话边界'),el('div',{class:'panel'},el('p',{},'注册成功只代表 Skill 文件和绝对路径已写入；请在真实客户端的新会话里验收。CLI 安装或登录不会由网页自动完成。'),code('atm setup\natm setup --apply\natm agents list\natm doctor --tool ffmpeg.probe'),el('p',{class:'quiet'},'仅针对本机同一系统用户。纯云端会话无法据此访问本地文件或凭证。')));
    main.append(section('已知 CLI 程序','绑定不会执行该程序'),cliTable());
  } else if(active==='tools') renderTools(main);
  else if(active==='extensions') renderExtensions(main);
  else if(active==='connections') renderConnections(main);
  else if(active==='jobs') renderJobs(main);
  else if(active==='sync') renderSync(main);
  else if(active==='access') renderAccess(main);
}
function cliTable() {
  return table(['程序','本地状态','检测到的入口','配置'],data.clis.map(c=>el('tr',{},el('td',{},brandIdentity(c.name,[el('strong',{},c.name)],'',true)),el('td',{},badge(c.state)),el('td',{},el('small',{},c.path || c.detected_path || '未安装 / 不在 PATH')),el('td',{},btn('查看配置计划',()=>setupDialog([], [c.name]))))));
}
function table(headers,rows) {
  return el('div',{class:'table-wrap'},el('table',{},el('thead',{},el('tr',{},...headers.map(h=>el('th',{},h)))),el('tbody',{},...(rows.length?rows:[el('tr',{},el('td',{colSpan:headers.length,class:'empty'},'没有匹配的记录。'))]))));
}
function renderTools(main) {
  main.append(heading('一个目录，两种 Agent。','启停状态写入本地数据库。停用会阻止 ATM 新调用，不会取消已提交的上游任务。'));
  const q=el('input',{placeholder:'搜索工具、供应商或能力…',ariaLabel:'搜索工具',value:toolFilters.q});
  const mode=el('select',{ariaLabel:'执行方式'},el('option',{value:''},'全部执行方式'),...['api','cli','mcp','browser','desktop','human','workflow'].map(x=>el('option',{value:x},x.toUpperCase())));
  const status=el('select',{ariaLabel:'工具状态'},el('option',{value:''},'全部状态'),el('option',{value:'enabled'},'已启用'),el('option',{value:'disabled'},'已停用'));
  mode.value=toolFilters.mode;status.value=toolFilters.status;
  const count=el('small',{class:'quiet'}), host=el('div');
  const draw=()=>{
    Object.assign(toolFilters,{q:q.value,mode:mode.value,status:status.value});
    const rows=data.tools.filter(t=>{
      const m=t.adapter==='web_recipe'?'browser':['browser','desktop','human','mcp','workflow'].includes(t.adapter)?t.adapter:['command','ffmpeg','ffprobe','xyq'].includes(t.adapter)?'cli':'api';
      return JSON.stringify([t.id,t.title,t.provider,window.ATM_BRANDS.get(t.provider,t.id).name,t.capabilities]).toLowerCase().includes(q.value.toLowerCase())&&(!mode.value||mode.value===m)&&(!status.value||(status.value==='enabled')===t.enabled);
    });count.textContent=rows.length+' 个动作';
    host.replaceChildren(table(['工具 / 能力','入口','配置状态','可用开关','详情'],rows.map(t=>el('tr',{class:t.enabled?'':'muted-row'},
      el('td',{},brandIdentity(t.provider,[el('strong',{},t.id),el('small',{},t.title)],t.id,true)),el('td',{},badge(t.adapter)),el('td',{},badge(t.health.state)),
      el('td',{},btn(t.enabled?'已启用 · 停用':'已停用 · 启用',async()=>{
        if(!confirm((t.enabled?'停用 ':'启用 ')+t.id+'？此变更同时影响 Claude Code 与 Codex。'))return;
        await api('/api/tools/toggle',{tool:t.id,enabled:!t.enabled,expected_enabled:t.enabled});await refresh();toast('工具状态已更新。');
      },t.enabled?'secondary':'plain')),
      el('td',{},btn('查看',async()=>{const d=await api('/api/tools/'+encodeURIComponent(t.id));openModal(t.id,el('p',{},t.title),el('p',{class:'quiet'},'以下为输入 schema 与动作权限，不是对上游账户的实时验证。'),code(d),code('atm describe '+t.id));},'plain'))))));
  };
  q.oninput=draw;mode.onchange=draw;status.onchange=draw;
  main.append(el('div',{class:'filterbar'},q,mode,status,count),host);draw();
}
function renderConnections(main) {
  main.append(heading('连接与凭证','密钥写入现有加密库；网页不回读明文，不在浏览器持久存储。',btn('添加 / 更新连接',()=>connectionDialog(),'primary')));
  const vault=data.connections.vault;
  main.append(el('div',{class:'panel'},el('div',{class:'card-head'},el('div',{},el('h3',{},'本地凭证库'),el('p',{class:'quiet'},'后端：'+(vault.backend || '未初始化')+' · '+display(vault.state))),!vault.backend?btn('初始化凭证库',vaultDialog):badge('保留现有凭证库','good')),el('p',{class:'quiet'},'口令模式仅在本次保存/检查请求中解锁，不提供后台永久解锁。系统 keyring 可能要求系统确认。')));
  const add=btn('绑定 1Password / Passkey',passkeyDialog);
  add.disabled=!vault.backend || !data.passkeys.available || !window.ATM_PASSKEY?.supported();
  main.append(el('div',{class:'panel',id:'passkeys-panel'},el('div',{class:'card-head'},brandIdentity('1password',[el('h3',{},'Passkey 解锁'),el('small',{},'本机绑定 · 主密码保留')]),badge('1Password / Passkey')),
    el('p',{},'使用支持 PRF 的 Passkey 保护现有主密钥；在 1Password 提示中由你保存并确认。解锁仍固定 30 分钟，不自动增加项目或 Key。'),
    !data.passkeys.dependency_present?el('p',{class:'quiet'},'Passkey 验证依赖尚待安装。'):null,
    data.passkeys.state_error?el('p',{class:'notice'},data.passkeys.state_error.code+': 本机绑定记录校验失败；密码恢复入口保留，请核对本地记录。'):null,
    !data.passkeys.origin_supported?el('p',{class:'quiet'},'请从新版 atm ui 打开的 localhost 窗口使用。'):null,
    el('div',{class:'card-actions'},add),
    ...data.passkeys.credentials.map(c=>el('div',{},el('strong',{},c.label+' · '+(c.disabled?'已停用':'已绑定')),
      !c.disabled?btn('停用 '+c.label,()=>disablePasskeyDialog(c),'plain danger'):null))));
  for (const c of data.connections.oauth || []) {
    const states={missing:'尚未登录',pending:'等待本机浏览器确认',ready:'已登录',expired:'令牌到期',refreshing:'续期中',refresh_unknown:'续期结果待确认，请重新登录',needs_login:'需要重新登录',denied:'登录未批准'};
    main.append(el('article',{class:'panel'},el('div',{class:'card-head'},brandIdentity('higgsfield',[el('h3',{},'Higgsfield 订阅 · ATM OAuth')]),badge(states[c.status] || c.status)),
      el('p',{},'独立加密保存订阅登录令牌，不读取官方 CLI 登录文件。项目 Key 的 30 分钟解锁期保持不变。'),
      el('p',{class:'quiet'},'自动续期：'+(c.keep_login?(c.status==='ready'&&c.refreshable&&c.service?.status==='loaded'?'已启用':'已请求，待连接 / 服务就绪'):'未启用')+' · 后台服务：'+(c.service?.status || 'not_installed')+(c.last_error?' · '+c.last_error:'')),
      el('p',{class:'quiet'},c.expires_at?'当前令牌有效至 '+new Date(c.expires_at*1000).toLocaleString():'登录后显示令牌有效期。'),
      el('div',{class:'card-actions'},btn(c.status==='missing'?'浏览器登录':'重新登录',()=>oauthDialog(c)),btn('刷新状态',()=>refresh()),
        c.keep_login?btn('停止自动续期',async()=>{await api('/api/oauth/keep-login',{provider:c.provider,enabled:false});await refresh();}):null)));
  }
  const q=el('input',{placeholder:'搜索连接提供方…',ariaLabel:'搜索连接'}), host=el('div',{class:'connection-grid'});
  const draw=()=>host.replaceChildren(...data.connections.connections.filter(c=>[c.provider,c.label,window.ATM_BRANDS.get(c.provider).name].join(' ').toLowerCase().includes(q.value.toLowerCase())).map(c=>el('article',{class:'card'},
    el('div',{class:'card-head'},brandIdentity(c.provider,[el('h3',{},window.ATM_BRANDS.get(c.provider).name),el('small',{},c.provider)]),badge(c.expired?'凭证已过期':c.configured?'已保存':'未连接',c.expired?'bad':c.configured?'good':'')),
    el('p',{},c.configured?'凭证已持久保存，未保证当前权限与余额。':'仅在需要这项工具时配置；不必连接所有服务。'),
    el('div',{class:'card-actions'},c.connect_supported?btn(c.configured?'更新连接':'连接',()=>connectionDialog(c.provider)):null,c.configured?btn('检查',()=>verifyDialog(c.provider),'plain'):null,c.configured?btn('移除',()=>removeConnection(c.provider),'plain danger'):null))));
  q.oninput=draw; main.append(section('供应商连接','浏览器与 CLI 的官方登录态仍由原工具管理'),el('div',{class:'filterbar'},q),host);draw();
}
function oauthDialog(connection) {
  const pass=passphraseField(),keep=el('input',{type:'checkbox'}),replace=el('input',{type:'checkbox'});
  keep.disabled=data.connections.vault.backend!=='keyring';
  openModal('Higgsfield 订阅登录',el('p',{},'打开官方 OAuth 页面，由你完成登录和授权；不生成内容、不消费订阅额度。'),
    el('label',{},keep,'保持登录：系统 keyring 加密保存，安装本用户后台续期服务；供应商撤销或要求验证时提示重新登录'),
    el('label',{},replace,'明确替换已有 ATM OAuth 连接（官方 CLI 登录保持原样）'),
    data.connections.vault.backend==='passphrase'?pass.node:null,
    el('div',{class:'dialog-actions'},btn('打开官方登录窗口',async()=>{
      try{const r=await api('/api/oauth/login',{provider:connection.provider,keep_login:keep.checked,replace:replace.checked,...(pass.input.value?{passphrase:pass.input.value}:{})});await refresh();closeModal();toast(r.browser_opened?'请在官方页面完成登录和授权，然后刷新状态。':'登录窗口尚未打开或已有请求，请查看连接状态。');}
      finally{pass.input.value='';}
    },'primary')));
}
function renderJobs(main) {
  main.append(heading('任务记录','读取 ATM 的实际任务摘要；不显示提示词、原始响应和带签名的素材链接。'));
  main.append(table(['任务','工具','状态','验收等级','费用'],data.jobs.map(j=>el('tr',{},el('td',{},el('strong',{},j.id.slice(0,8)),el('small',{},new Date(j.created*1000).toLocaleString())),el('td',{},j.tool),el('td',{},badge(j.status)),el('td',{},el('small',{},j.verification || '未知')),el('td',{},j.cost_usd===null?'未知':String(j.cost_usd))))));
  main.append(el('div',{class:'notice'},'只展示最近 50 条任务。网页不会自动轮询供应商或重新提交；需要继续某个任务时，由 Agent 使用 atm jobs get ID --refresh。'));
}
function setupDialog(agentNames=['claude','codex'],cliNames=[]) {
  const controls=Object.fromEntries(['claude','codex'].map(name=>[name,el('input',{type:'checkbox',checked:agentNames.includes(name)})]));
  const cli=el('select',{ariaLabel:'绑定 CLI'},el('option',{value:''},'暂不新增 CLI 绑定'),...data.clis.map(c=>el('option',{value:c.name,selected:cliNames.includes(c.name)},c.name+(c.detected_path?' · 检测到':' · 未检测到'))));
  const replace=el('input',{type:'checkbox'}), output=el('div'); let plan=null;
  const body=()=>({agents:Object.entries(controls).filter(([,v])=>v.checked).map(([k])=>k),clis:cli.value?[cli.value]:[],replace_skills:replace.checked});
  const applyButton=btn('批准并应用',async()=>{
    if(!plan)return;
    const result=await api('/api/setup/apply',{...body(),approved_sha256:plan.plan_sha256});
    await refresh();closeModal();toast(display(result.status));
  },'primary');applyButton.disabled=true;
  const invalidate=()=>{plan=null;output.replaceChildren();applyButton.disabled=true;};
  for(const input of [...Object.values(controls),cli,replace])input.addEventListener('change',invalidate);
  openModal('注册与绑定计划',el('p',{class:'quiet'},'只修改选中的本地配置。不安装软件、不登录供应商、不读取密钥。'),
    el('div',{class:'checkrow'},...Object.entries(controls).map(([k,v])=>el('label',{},v,k==='claude'?'Claude Code':'Codex'))),
    el('label',{},'可选：绑定一个已安装的 CLI',cli),el('label',{},replace,'已审阅：允许备份并替换不同的 Skill 内容'),output,
    el('div',{class:'dialog-actions'},btn('预览变更',async()=>{plan=await api('/api/setup/preview',body());output.replaceChildren(code(plan));applyButton.disabled=plan.status==='needs_review';}),applyButton));
}
function passwordField(label) {const input=el('input',{type:'password',autocomplete:'off'});return {input,node:el('label',{},label,input)};}
function passkeyDialog(){
  const pass=passwordField('现有 ATM 主密码（首次绑定验证）');pass.input.autocomplete='current-password';
  const label=el('input',{value:'1Password',maxLength:80});
  openModal('绑定 Passkey',el('p',{},'将出现保存凭证及 PRF 验证提示。请选择 1Password 并亲自确认；没有 PRF 时保留主密码入口。密码、Key、Passkey 私钥及解锁状态均不进入 ATM 同步。'),
    el('label',{},'非秘密名称',label),data.connections.vault.backend==='passphrase'?pass.node:null,
    btn('开始绑定',async()=>{
      let password=pass.input.value;pass.input.value='';
      try{await window.ATM_PASSKEY.register(api,password,label.value);closeModal();await refresh();toast('Passkey 已绑定，原有凭证密文保持原样。');}
      finally{password=null;pass.input.value='';}
    },'primary'));
}
function disablePasskeyDialog(credential){
  const pass=passwordField('现有 ATM 主密码（验证停用）');pass.input.autocomplete='current-password';
  openModal('停用 '+credential.label,el('p',{},'停用本机绑定；1Password 中的凭证及已有会话保持原样。需要立即终止新调用时另点“立即锁定”。'),
    data.connections.vault.backend==='passphrase'?pass.node:null,
    btn('确认停用',async()=>{let password=pass.input.value;pass.input.value='';
      try{await api('/api/passkeys/disable',{credential_id:credential.id,confirm:credential.id,...(password?{passphrase:password}:{})});closeModal();await refresh();}
      finally{password=null;}
    },'secondary danger'));
}
function passkeyUnlockControl(){
  const credentials=data.passkeys?.credentials.filter(c=>!c.disabled) || [];
  if(!credentials.length || !data.passkeys.available || !window.ATM_PASSKEY?.supported())return null;
  const select=el('select',{ariaLabel:'解锁 Passkey'},...credentials.map(c=>el('option',{value:c.id},c.label)));
  return el('div',{},select,btn('用 Passkey 解锁 30 分钟',async()=>{
    let proof=await window.ATM_PASSKEY.authenticate(api,'/api/passkeys/auth/begin',{credential_id:select.value},'/api/passkeys/cancel');
    try{await api('/api/session/unlock',{passkey:proof});closeModal();await refresh();toast('Passkey 已解锁。');}
    finally{proof=null;}
  },'primary'));
}
function passphraseField() {return passwordField('现有凭证库口令（仅口令模式需要；仅用于本次请求）');}
function connectionDialog(provider) {
  if(data.session?.session_mode_enabled&&!data.session.unlocked){unlockDialog();return;}
  const options=data.connections.connections.filter(c=>c.connect_supported);
  const select=el('select',{ariaLabel:'连接提供方'},...options.map(c=>el('option',{value:c.provider,selected:c.provider===provider},c.provider+(c.configured?' · 已保存':''))));
  const secret=passwordField('API Key / 凭证（仅写入，无法回读）'), pass=passphraseField(), replace=el('input',{type:'checkbox'}), expiry=el('input',{placeholder:'可选，例如 2026-12-31T00:00:00Z'});
  openModal('保存一个连接',el('p',{class:'quiet'},'Higgsfield 使用 KEY_ID:KEY_SECRET；DataForSEO 使用 login:password。不要把网页登录 Cookie 当作 API Key。'),el('label',{},'提供方',select),secret.node,el('label',{},'已知有效期（包含时区）',expiry),el('label',{},replace,'明确替换这个连接的已有凭证'),data.connections.vault.backend==='passphrase'&&!data.session?.unlocked?pass.node:null,
    el('div',{class:'dialog-actions'},btn('加密保存',async()=>{
      const body={provider:select.value,value:secret.input.value,replace:replace.checked};
      if(expiry.value)body.expires_at=expiry.value;if(pass.input.value)body.passphrase=pass.input.value;
      try{const result=await api('/api/connections/save',body);await refresh();closeModal();toast(display(result.status));}
      finally{secret.input.value='';pass.input.value='';body.value='';delete body.passphrase;}
    },'primary')));
}
function vaultDialog() {
  const backend=el('select',{},el('option',{value:'keyring'},'系统 keyring（推荐）'),el('option',{value:'passphrase'},'口令加密（无系统凭证库时）'));
  const pass=passwordField('新口令（选择口令模式时至少 12 个字符）'), confirmPass=passwordField('再次输入新口令');
  openModal('初始化凭证库',el('p',{class:'quiet'},'仅能初始化空库；已有库永远不会被覆盖。不提供明文降级。'),el('label',{},'后端',backend),pass.node,confirmPass.node,
    el('div',{class:'dialog-actions'},btn('初始化',async()=>{
      if(backend.value==='passphrase'&&pass.input.value!==confirmPass.input.value)throw new Error('两次口令不一致。');
      try{await api('/api/vault/init',{backend:backend.value,...(backend.value==='passphrase'?{passphrase:pass.input.value}:{})});await refresh();closeModal();toast('凭证库已初始化。');}
      finally{pass.input.value='';confirmPass.input.value='';}
    },'primary')));
}
async function verifyDialog(provider) {
  const plan=await api('/api/verify',{provider}), pass=passphraseField();
  const button=btn('批准本次账户检查',async()=>{
    try{const r=await api('/api/verify',{provider,allow_network:true,...(pass.input.value?{passphrase:pass.input.value}:{})});await refresh();closeModal();openModal('账户检查结果',code(r));}finally{pass.input.value='';}
  },'primary');button.disabled=plan.status!=='planned';
  openModal('检查 '+provider,code(plan),el('p',{class:'quiet'},'仅检查列明的账户接口，不生成内容。供应商配额或限流可能适用。通过不代表所有业务动作可用。'),data.connections.vault.backend==='passphrase'?pass.node:null,el('div',{class:'dialog-actions'},button));
}
function removeConnection(provider) {
  if(data.session?.session_mode_enabled&&!data.session.unlocked){unlockDialog();return;}
  const pass=passphraseField(),confirmation=el('input',{placeholder:'输入 '+provider+' 确认'});
  openModal('移除本地连接',el('p',{},'仅删除本机保存的 '+provider+' 凭证，不会撤销供应商端的 Key。备份可能仍包含密文。'),el('label',{},'确认提供方',confirmation),data.connections.vault.backend==='passphrase'&&!data.session?.unlocked?pass.node:null,
    el('div',{class:'dialog-actions'},btn('确认移除',async()=>{
      try{await api('/api/connections/remove',{provider,confirm:confirmation.value,...(pass.input.value?{passphrase:pass.input.value}:{})});await refresh();closeModal();toast('本地连接已移除。');}finally{pass.input.value='';}
    },'secondary danger')));
}
function renderSync(main) {
  const sync=data.sync;
  main.append(heading('密钥跨设备，主密钥不出门。','仅同步明确选择的服务凭证；CLI 路径、浏览器会话、授权策略留在各自机器。',btn(sync.device?'导入加密包':'初始化本机身份',()=>sync.device?importDialog():deviceDialog(),'primary')));
  if(!sync.device){main.append(el('div',{class:'panel'},el('p',{},'先初始化本机凭证库，再生成这台机器独立的加密与签名身份。不会上传你的 Key。'),btn('初始化设备身份',deviceDialog)));return;}
  main.append(el('div',{class:'panel'},section(sync.device.name,'DEVICE IDENTITY'),el('code',{class:'path'},sync.device.id),el('p',{class:'quiet'},'通过另一条可信通道核对完整指纹。公开身份文件可以交换，私钥不可以。'),btn('查看 / 导出公开身份',()=>openModal('本机公开身份（不含秘密）',code(sync.device),btn('下载公开身份',()=>downloadJson(sync.device,'atm-device.public.json')))),btn('配对另一台机器',trustDialog)));
  main.append(section('已配对设备','只读状态 · 需要明确发送和接收范围'),table(['设备','发送这些凭证','接收这些凭证','操作'],sync.peers.map(p=>el('tr',{},el('td',{},el('b',{},p.card.name),el('small',{class:'path'},p.card.id.slice(0,16)+'…'),badge(p.revoked?'已撤销':'已配对',p.revoked?'warn':'good')),el('td',{},p.send.join(', ')||'无'),el('td',{},p.receive.join(', ')||'无'),el('td',{},p.revoked?null:btn('导出加密包',()=>exportDialog(p)),p.revoked?null:btn('撤销本机信任',async()=>{if(!confirm('撤销此设备？已收到的旧 Key 不能收回；应在供应商轮换。'))return;await api('/api/sync/revoke',{device:p.card.id,confirm:p.card.id});await refresh();}))))));
  const conflicts=sync.records.filter(r=>r.state==='conflict');
  main.append(section('待解决冲突',String(conflicts.length)+' 个 · 不按时间覆盖'),...conflicts.map(r=>el('div',{class:'panel'},el('h3',{},r.provider),el('p',{},'并发修改均已加密保留；本地调用暂停。选择一个完整版本，不能拼接 Key。'),...r.heads.map(h=>btn((h.deleted?'删除版本':'保留版本')+' '+h.revision.slice(0,12)+' · '+h.author.slice(0,10),()=>resolveDialog(r,h))))));
  main.append(section('同步循环','文件可通过已有 rsync / SFTP / 同步盘传递'),code('atm sync exchange --directory /path/to/encrypted-sync\natm sync exchange --directory /path/to/encrypted-sync --apply'),el('div',{class:'notice'},'单次 exchange 或显式启动有限期 sync watch；不会自行部署云同步。旧包重放不会覆盖已知较新版本；整库恢复、丢失设备和离线撤销仍需人工恢复流程。'));
}
function downloadJson(value,name){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a',{href:url,download:name});a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function secretRequest(pass){return pass.input.value?{passphrase:pass.input.value}:{};}
function deviceDialog(){const name=el('input',{placeholder:'例如 laptop 或 build-server'}),pass=passphraseField();openModal('初始化本机同步身份',el('label',{},'设备名称',name),pass.node,btn('生成独立身份',async()=>{try{await api('/api/sync/init',{name:name.value,...secretRequest(pass)});await refresh();closeModal();}finally{pass.input.value='';}},'primary'));}
function trustDialog(){const card=el('textarea',{rows:8,placeholder:'粘贴另一台机器的公开身份 JSON（不含私钥）'}),fp=el('input',{placeholder:'通过可信通道核对的完整指纹'}),send=el('input',{placeholder:'fal,elevenlabs'}),receive=el('input',{placeholder:'fal,elevenlabs'});let plan;
const values=()=>({card:JSON.parse(card.value),fingerprint:fp.value.trim(),send:send.value.split(',').map(s=>s.trim()).filter(Boolean),receive:receive.value.split(',').map(s=>s.trim()).filter(Boolean)});
const view=code('先预览。'),apply=btn('批准配对',async()=>{const current=values();if(JSON.stringify(current)!==plan)throw new Error('表单已变化，请重新预览。');await api('/api/sync/trust',{...current,apply:true});await refresh();closeModal();},'primary');apply.disabled=true;
openModal('配对设备',el('label',{},'公开身份',card),el('label',{},'独立核对指纹',fp),el('label',{},'允许发送',send),el('label',{},'允许接收 / 修改',receive),view,el('div',{class:'dialog-actions'},btn('预览设备权限',async()=>{const v=values(),r=await api('/api/sync/trust',v);view.textContent=JSON.stringify(r,null,2);plan=JSON.stringify(v);apply.disabled=false;}),apply));}
function exportDialog(peer){const pass=passphraseField();openModal('向 '+peer.card.name+' 导出',el('p',{},'只包含发送白名单中的当前版本 / 冲突 / 删除标记。加密包仅对应接收设备可解密。'),pass.node,btn('生成并下载加密包',async()=>{try{const r=await api('/api/sync/export',{device:peer.card.id,...secretRequest(pass)});downloadJson(r.encrypted_packet,'atm-'+r.encrypted_packet.header.packet+'.atmsync');closeModal();}finally{pass.input.value='';}},'primary'));}
function importDialog(){const file=el('input',{type:'file',accept:'.atmsync,.json'}),pass=passphraseField(),view=code('选择加密包后预览。');let packet=null;
file.onchange=()=>{packet=null;apply.disabled=true;};
const apply=btn('批准导入',async()=>{try{const r=await api('/api/sync/import',{packet,apply:true,...secretRequest(pass)});await refresh();closeModal();toast(r.conflicts?'存在冲突，已保留版本并暂停相关调用。':'加密凭证已合并到本机。');}finally{pass.input.value='';}},'primary');apply.disabled=true;
openModal('导入加密同步包',file,pass.node,view,el('div',{class:'dialog-actions'},btn('预览同步变化',async()=>{if(!file.files[0]||file.files[0].size>8*1024*1024)throw new Error('请选择不超过 8 MiB 的加密包。');packet=JSON.parse(await file.files[0].text());const r=await api('/api/sync/import',{packet,...secretRequest(pass)});view.textContent=JSON.stringify(r,null,2);apply.disabled=false;}),apply));}
function resolveDialog(record,head){const pass=passphraseField();openModal('解决 '+record.provider+' 的冲突',code(head),el('p',{},'选择的是整个凭证记录。新合并版本包含所有已见分支；若其间又收到新修改，会拒绝这个过期选择。'),pass.node,btn('批准此版本',async()=>{try{await api('/api/sync/resolve',{provider:record.provider,choose:head.revision,expected:record.expected,apply:true,...secretRequest(pass)});await refresh();closeModal();}finally{pass.input.value='';}},'primary'));}
function renderAccess(main){const access=data.access;
main.append(heading('授权一次，在范围内持续使用。','Agent 只获得工具、项目与有效期受限的访问凭据；不会获得供应商 Key 或同步管理员权限。',btn('新增 Agent 授权',grantDialog,'primary')));
main.append(el('div',{class:'panel'},section('本机会话 Broker','前台进程 · 独立于网页管理台'),code('atm broker serve --ttl-hours 8\n# 另一个终端，授权并注册后：\natm --client claude broker status\natm setup --broker --replace-skills --apply'),el('p',{class:'quiet'},'Owner 在私有终端解锁一次。有效期内的新 Agent 进程复用会话；到期、停止或撤销后失败关闭，不退回直接读取 vault。'),code(access.broker||{state:'not_started'})));
main.append(section('本地 Agent 授权','撤销只阻止新请求，不取消已受理的远端任务'),table(['Agent / 授权 ID','可用工具与项目','有效期','操作'],access.grants.map(g=>el('tr',{},el('td',{},el('b',{},g.agent),el('small',{class:'path'},g.id)),el('td',{},g.tools.join(', '),el('small',{class:'path'},g.workspace)),el('td',{},badge(g.revoked?'已撤销':g.expires_at<access.clock?'已过期':'有效',g.revoked?'warn':'good'),el('small',{},new Date(g.expires_at*1000).toLocaleString())),el('td',{},g.revoked?null:btn('撤销授权',async()=>{if(!confirm('撤销 '+g.agent+' 的这份授权？'))return;await api('/api/access/revoke',{id:g.id,confirm:g.id});await refresh();}))))));
main.append(el('div',{class:'notice'},'这是受限 API 的逻辑权限，不是同系统用户恶意进程之间的强隔离。默认 socket 与客户端文件为 owner-only。不要把 client profile 放进 Git、聊天或共享文件夹。'));
}
function grantDialog(){const agent=el('select',{},el('option',{value:'claude'},'Claude Code'),el('option',{value:'codex'},'Codex')),tools=el('input',{placeholder:'ffmpeg.probe'}),workspace=el('input',{placeholder:'已存在的项目绝对路径'}),hours=el('input',{type:'number',min:1,max:720,value:168}),paid=el('input',{type:'checkbox'}),permissions=['external_write','production','execute_code'].map(k=>({key:k,input:el('input',{type:'checkbox'})}));let reviewed=null,hash=null;
const values=()=>({agent:agent.value,tools:tools.value.split(',').map(v=>v.trim()).filter(Boolean),workspace:workspace.value,ttl_hours:Number(hours.value),allow_paid:paid.checked,permissions:permissions.filter(p=>p.input.checked).map(p=>p.key)}),view=code('预览后批准。');
const apply=btn('批准并写入私有客户端文件',async()=>{const v=values();if(JSON.stringify(v)!==reviewed)throw new Error('权限已变化，请重新预览。');await api('/api/access/grant',{...v,apply:true,approved_sha256:hash});await refresh();closeModal();},'primary');apply.disabled=true;
openModal('创建有范围的 Agent 授权',el('label',{},'客户端',agent),el('label',{},'精确工具 ID（逗号分隔）',tools),el('label',{},'允许的项目目录',workspace),el('label',{},'授权小时数（最多 720）',hours),el('label',{},paid,'允许所选工具消耗上游额度（不是金额上限）'),...permissions.map(p=>el('label',{},p.input,p.key)),view,el('div',{class:'dialog-actions'},btn('预览授权',async()=>{const v=values(),r=await api('/api/access/grant',v);reviewed=JSON.stringify(v);hash=r.approval_sha256;view.textContent=JSON.stringify(r,null,2);apply.disabled=false;}),apply));}

document.querySelectorAll('[data-nav]').forEach(n=>n.onclick=()=>{active=n.dataset.nav;render();});
$('#modal-close').onclick=closeModal;
$('#modal').addEventListener('cancel',()=>$('#modal-body').replaceChildren());
$('#refresh').onclick=action(refresh);
$('#lock').onclick=()=>{forgetToken();data=null;closeModal();$('#main').replaceChildren();$('#gate').hidden=false;};
$('#session-form').onsubmit=action(async e=>{e.preventDefault();token=$('#session-token').value;$('#session-token').value='';await refresh();tabToken.set(token);});
if(token)refresh().catch(e=>{toast(e.message,true);$('#gate').hidden=false;});

function renderExtensions(main) {
  main.append(heading('扩展工坊','列表不是能力上限。独立管理新 Key，安装经审阅的 API、CLI 或网页配方。',btn('新增凭证槽',credentialSlotDialog,'primary')));
  main.append(el('div',{class:'notice'},'不把真实 Key 放进工具定义、提示词或代码包。验证只检查结构，不代表网站已跑通；网页配方的登录在本机终端完成。'));
  main.append(el('div',{class:'grid2'},el('article',{class:'card'},el('h3',{},'让 Agent 制作工具'),el('p',{},'从官方文档或已观察的网页操作起草，验证后批准安装。生成结果不会自行获得权限。'),btn('验证 / 安装定义',extensionDialog)),el('article',{class:'card'},el('h3',{},'网页 → 可复用 CLI'),el('p',{},'限定站点和操作的 Playwright 配方。配方可打包，登录态加密保留在当前设备。'),code('atm make new studio.export --kind web --url https://example.com/ --out studio.json\natm make pack studio.json --out studio-cli'))));
  main.append(section('已安装自定义工具'),table(['动作','入口','权限','定义摘要'],data.extensions.custom_tools.map(t=>el('tr',{},el('td',{},t.id),el('td',{},t.adapter),el('td',{},t.permissions.join(', ')),el('td',{},t.sha256.slice(0,16))))));
  main.append(section('本机加密网页登录态','不随 API Key 同步'),table(['会话','站点范围','状态'],data.extensions.browser_sessions.map(s=>el('tr',{},el('td',{},s.name),el('td',{},s.origins.join(', ')),el('td',{},s.expired?'已过期':'已保存 · 未验证登录')))));
}
function credentialSlotDialog(){
  const name=el('input',{ariaLabel:'新凭证槽',placeholder:'例如 acme.production'}),label=el('input',{ariaLabel:'凭证槽标签',placeholder:'非秘密显示名称'});
  openModal('新增凭证槽',el('p',{},'只登记名称，不填写 Key；无需先实现该供应商适配器。'),name,label,btn('登记',async()=>{
    await api('/api/credentials/declare',{name:name.value,label:label.value||name.value,apply:true});await refresh();closeModal();toast('已登记。可到连接与凭证页面输入 Key。');
  },'primary'));
}
function extensionDialog(){
  let approved=null;
  const input=el('textarea',{ariaLabel:'工具定义 JSON',rows:16,placeholder:'粘贴不含秘密的 manifest JSON'}),preview=el('div',{});
  const apply=btn('批准安装定义',async()=>{
    if(!approved)return;
    const manifest=JSON.parse(input.value);
    await api('/api/extensions/install',{manifest,approved_sha256:approved.sha256,...(approved.previous_sha256?{expected_sha256:approved.previous_sha256}:{})});
    await refresh();closeModal();toast('工具定义已安装。尚未执行或进行真实网站验收。');
  },'primary');apply.disabled=true;
  input.oninput=()=>{approved=null;apply.disabled=true;preview.replaceChildren();};
  openModal('验证并批准扩展',el('p',{},'检查参数、目的站点和隐含权限。修改定义会使旧的 Broker 授权失效。'),input,btn('验证定义',async()=>{
    approved=null;apply.disabled=true;const value=await api('/api/extensions/validate',{manifest:JSON.parse(input.value)});approved=value;preview.replaceChildren(code(value));apply.disabled=false;
  }),preview,apply);
}


function sessionPanel(){
  const unlocked=!!data.session?.unlocked;
  return el('div',{class:'panel',id:'credential-session'},
    section('凭证使用会话','SECRETS FIRST · 无需工具定义'),
    el('p',{},unlocked?'已解锁：网页凭证管理与获准 CLI 共用一次解锁。':'已锁定：凭证仍在，不需要重新填写已有 Key。'),
    el('strong',{id:'lease-countdown'},unlocked?'限时有效':'LOCKED'),
    el('div',{class:'card-actions'},btn(unlocked?'刷新会话状态':'解锁 30 分钟',()=>unlocked?refresh():unlockDialog(),'primary'),
      unlocked?btn('立即锁定',async()=>{await api('/api/session/lock',{});await refresh();toast('新凭证调用已停止；已运行程序可能仍持有获准的 Key。');},'secondary danger'):null),
    el('p',{class:'quiet'},'固定 30 分钟，不因 Agent 访问而自动续期。调用权限独立授权；网页不提供执行任意程序或返回 Key 原文的接口。'));
}
function unlockDialog(){
  const pass=passwordField('现有库口令（仅本机解锁，不写入文件）');
  openModal('解锁凭证会话',el('p',{},'解锁后 30 分钟内，获准的 Claude / Codex 新进程复用会话。此窗口启动的会话随管理台进程关闭而结束。'),
    passkeyUnlockControl(),
    data.connections.vault.backend==='passphrase'?pass.node:null,
    btn('确认解锁 30 分钟',async()=>{const body={ttl:'30m'};if(pass.input.value)body.passphrase=pass.input.value;
      try{await api('/api/session/unlock',body);closeModal();await refresh();toast('会话已解锁。');}
      finally{pass.input.value='';delete body.passphrase;}},'primary'));
}
setInterval(()=>{const n=$('#lease-countdown');if(!n||!data?.session?.unlocked)return;
 const left=Math.max(0,Math.floor(data.session.seconds_remaining-(Date.now()-data.sessionFetchedAt)/1000));
 n.textContent=left?String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0')+' 剩余':'已到期 · 请刷新';},1000);
