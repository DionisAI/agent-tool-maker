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
let token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
if (location.hash) history.replaceState(null, '', location.pathname);
let data = null, active = 'overview', noticeTimer;
const toolFilters={q:'',mode:'',status:''};
const labels = {
  configured_not_verified:'已配置 · 未验证', not_registered:'未注册', registered_not_host_verified:'已注册 · 待宿主验收',
  registration_changed:'注册文件已变化', cli_not_configured:'CLI 未绑定', missing_credential:'未连接', needs_unlock:'需要解锁',
  unlock_not_checked:'未检查解锁', unlocked_in_this_process:'本次请求已解锁', not_initialized:'尚未初始化',
  keyring_unavailable:'系统凭证库不可用', executable_changed:'程序已变化', executable_missing:'程序缺失',
  credential_expired:'凭证已过期', browser_login_unknown:'交给浏览器', host_desktop_required:'交给桌面工具',
  host_human_required:'等待人工', mcp_not_configured:'MCP 未绑定', workflow_dependencies_not_verified:'待检查依赖',
  disabled:'已停用', missing_origin:'未设服务地址', probe_passed:'账户探针通过', completed:'完成',
  queued:'已排队', running:'运行中', submitting:'提交中', submission_unknown:'提交状态待核对', failed:'失败',
  requires_browser:'等待浏览器', requires_desktop:'等待桌面', requires_human:'等待人工', planned:'待确认',
  applied:'配置已应用', needs_dependencies:'仍有依赖待安装', already_configured:'已有连接，已保留', saved:'已加密保存'
};
const display = value => labels[value] || value || '未知';
const badge = (value, kind='') => el('span',{class:'badge '+kind},display(value));
const code = value => el('pre',{class:'codebox'},typeof value === 'string' ? value : JSON.stringify(value,null,2));
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
    if(r.status===401) {token=''; $('#gate').hidden=false;}
    throw new Error((value.error?.code || 'request_failed')+': '+(value.error?.message || '请求未完成'));
  }
  return value;
}
async function refresh() {
  const [overview,tools,connections,jobs,clis]=await Promise.all(['/api/overview','/api/tools','/api/connections','/api/jobs','/api/clis'].map(p=>api(p)));
  data={overview,tools:tools.tools,connections,jobs:jobs.jobs,clis:clis.clis};
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
function openModal(title,...content) {$('#modal-title').textContent=title;$('#modal-body').replaceChildren(...content);if(!$('#modal').open)$('#modal').showModal();}
function closeModal() {$('#modal').close();$('#modal-body').replaceChildren();}
function agentCard(a) {
  const registered=a.state==='registered_not_host_verified';
  return el('article',{class:'card'},
    el('div',{class:'card-head'},el('div',{class:'agent-title'},el('span',{class:'agent-icon '+a.agent},a.agent==='claude'?'✳':'›_'),el('div',{},el('h3',{},a.label),el('small',{},'默认支持 · 用户级 Skill'))),badge(registered?'已注册':'待配置',registered?'good':'warn')),
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
    const c=data.overview.counts;
    main.append(el('div',{class:'stats'},...[[c.tools,'工具动作','API · CLI · MCP · 外部交接'],[c.enabled,'启用的动作','同一开关作用于所有本地 Agent'],[c.connections,'已保存连接','已配置不等于上游已验证'],[c.recent_jobs,'最近任务','最多统计最近 50 条']].map(([n,t,h])=>el('div',{class:'stat'},el('small',{},t),el('strong',{},n),el('span',{},h)))));
    main.append(section('默认客户端','共用 ATM · 不复制密钥'),el('div',{class:'grid2'},...data.overview.agents.map(agentCard)));
    main.append(el('div',{class:'notice'},'本页只检查本地配置，不执行生成、发帖或部署。网页修改与 CLI 即时共用；新会话复用同一持久状态目录。'));
    main.append(section('从配置到交付','YOUR CONTROL LOOP'),el('div',{class:'panel workflow'},
      ...[['01 / CONNECT','准备工具入口','注册客户端、绑定已安装的 CLI。只为缺少的连接提供凭证。'],['02 / INSPECT','按任务检查状态','查看参数、权限与连接状态。把“已保存”与“可用”分开判断。'],['03 / EXECUTE','由 Agent 完成任务','主 Agent 通过 ATM CLI 执行；在这里查看脱敏的任务摘要。']].map(([i,t,p])=>el('div',{class:'step'},el('b',{},i),el('h3',{},t),el('p',{},p)))));
    main.append(el('p',{class:'quiet'},'持久状态目录：'+data.overview.home));
  } else if(active==='agents') {
    main.append(heading('Agent 客户端','默认支持 Claude Code、Codex；所有客户端调用同一个 ATM 执行器。',btn('预览默认注册',()=>setupDialog(),'primary')));
    main.append(el('div',{class:'grid2'},...data.overview.agents.map(agentCard)),section('安装与会话边界'),el('div',{class:'panel'},el('p',{},'注册成功只代表 Skill 文件和绝对路径已写入；请在真实客户端的新会话里验收。CLI 安装或登录不会由网页自动完成。'),code('atm setup\natm setup --apply\natm agents list\natm doctor --tool ffmpeg.probe'),el('p',{class:'quiet'},'仅针对本机同一系统用户。纯云端会话无法据此访问本地文件或凭证。')));
    main.append(section('已知 CLI 程序','绑定不会执行该程序'),cliTable());
  } else if(active==='tools') renderTools(main);
  else if(active==='connections') renderConnections(main);
  else if(active==='jobs') renderJobs(main);
}
function cliTable() {
  return table(['程序','本地状态','检测到的入口','配置'],data.clis.map(c=>el('tr',{},el('td',{},el('strong',{},c.name)),el('td',{},badge(c.state)),el('td',{},el('small',{},c.path || c.detected_path || '未安装 / 不在 PATH')),el('td',{},btn('查看配置计划',()=>setupDialog([], [c.name]))))));
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
      const m=['browser','desktop','human','mcp','workflow'].includes(t.adapter)?t.adapter:['command','ffmpeg','ffprobe','xyq'].includes(t.adapter)?'cli':'api';
      return JSON.stringify([t.id,t.title,t.provider,t.capabilities]).toLowerCase().includes(q.value.toLowerCase())&&(!mode.value||mode.value===m)&&(!status.value||(status.value==='enabled')===t.enabled);
    });count.textContent=rows.length+' 个动作';
    host.replaceChildren(table(['工具 / 能力','入口','配置状态','可用开关','详情'],rows.map(t=>el('tr',{class:t.enabled?'':'muted-row'},
      el('td',{},el('strong',{},t.id),el('small',{},t.title)),el('td',{},badge(t.adapter)),el('td',{},badge(t.health.state)),
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
  const q=el('input',{placeholder:'搜索连接提供方…',ariaLabel:'搜索连接'}), host=el('div',{class:'connection-grid'});
  const draw=()=>host.replaceChildren(...data.connections.connections.filter(c=>c.provider.includes(q.value.toLowerCase())).map(c=>el('article',{class:'card'},
    el('div',{class:'card-head'},el('h3',{},c.provider),badge(c.expired?'凭证已过期':c.configured?'已保存':'未连接',c.expired?'bad':c.configured?'good':'')),
    el('p',{},c.configured?'凭证已持久保存，未保证当前权限与余额。':'仅在需要这项工具时配置；不必连接所有服务。'),
    el('div',{class:'card-actions'},c.connect_supported?btn(c.configured?'更新连接':'连接',()=>connectionDialog(c.provider)):null,c.configured?btn('检查',()=>verifyDialog(c.provider),'plain'):null,c.configured?btn('移除',()=>removeConnection(c.provider),'plain danger'):null))));
  q.oninput=draw; main.append(section('供应商连接','浏览器与 CLI 的官方登录态仍由原工具管理'),el('div',{class:'filterbar'},q),host);draw();
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
function passphraseField() {return passwordField('现有凭证库口令（仅口令模式需要；仅用于本次请求）');}
function connectionDialog(provider) {
  const options=data.connections.connections.filter(c=>c.connect_supported);
  const select=el('select',{ariaLabel:'连接提供方'},...options.map(c=>el('option',{value:c.provider,selected:c.provider===provider},c.provider+(c.configured?' · 已保存':''))));
  const secret=passwordField('API Key / 凭证（仅写入，无法回读）'), pass=passphraseField(), replace=el('input',{type:'checkbox'}), expiry=el('input',{placeholder:'可选，例如 2026-12-31T00:00:00Z'});
  openModal('保存一个连接',el('p',{class:'quiet'},'Higgsfield 使用 KEY_ID:KEY_SECRET；DataForSEO 使用 login:password。不要把网页登录 Cookie 当作 API Key。'),el('label',{},'提供方',select),secret.node,el('label',{},'已知有效期（包含时区）',expiry),el('label',{},replace,'明确替换这个连接的已有凭证'),data.connections.vault.backend==='passphrase'?pass.node:null,
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
  const pass=passphraseField(),confirmation=el('input',{placeholder:'输入 '+provider+' 确认'});
  openModal('移除本地连接',el('p',{},'仅删除本机保存的 '+provider+' 凭证，不会撤销供应商端的 Key。备份可能仍包含密文。'),el('label',{},'确认提供方',confirmation),data.connections.vault.backend==='passphrase'?pass.node:null,
    el('div',{class:'dialog-actions'},btn('确认移除',async()=>{
      try{await api('/api/connections/remove',{provider,confirm:confirmation.value,...(pass.input.value?{passphrase:pass.input.value}:{})});await refresh();closeModal();toast('本地连接已移除。');}finally{pass.input.value='';}
    },'secondary danger')));
}
document.querySelectorAll('[data-nav]').forEach(n=>n.onclick=()=>{active=n.dataset.nav;render();});
$('#modal-close').onclick=closeModal;
$('#modal').addEventListener('cancel',()=>$('#modal-body').replaceChildren());
$('#refresh').onclick=action(refresh);
$('#lock').onclick=()=>{token='';data=null;closeModal();$('#main').replaceChildren();$('#gate').hidden=false;};
$('#session-form').onsubmit=action(async e=>{e.preventDefault();token=$('#session-token').value;$('#session-token').value='';await refresh();});
if(token)refresh().catch(e=>{toast(e.message,true);$('#gate').hidden=false;});
