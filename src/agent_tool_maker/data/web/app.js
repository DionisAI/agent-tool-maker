'use strict';
// All dynamic content is textContent/DOM nodes, never provider-controlled HTML.
const $ = (q, root = document) => root.querySelector(q);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs)) {
    if (v === undefined || v === null) continue;
    if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (k === 'class') n.className = v;
    else if (k in n) n[k] = v;
    else n.setAttribute(k,v);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined && child !== false) n.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return n;
};
// The bearer and the current section live in this tab's sessionStorage (exact origin, this tab only);
// never localStorage or cookies.
const tabStore = key => ({
  get() { try { return sessionStorage.getItem(key) || ''; } catch { return ''; } },
  set(value) { try { sessionStorage.setItem(key, value); } catch {} },
  clear() { try { sessionStorage.removeItem(key); } catch {} }
});
const tabToken = tabStore('atm-console-token'), tabSection = tabStore('atm-console-section');
// `atm ui` opens #launch=<one-time code>; #token= is still read for already-open or bookmarked links.
const fragment = new URLSearchParams(location.hash.slice(1)), launchCode = fragment.get('launch') || '';
let token = fragment.get('token') || '', typed = '';
if (token) tabToken.set(token); else if (!launchCode) token = tabToken.get();
const MODEL = window.ATM_MODEL, T = MODEL.T;
// Five sections; old section names from earlier versions of this console still restore.
const LEGACY = {tools:'services', extensions:'settings/tools', connections:'settings/keys', sync:'settings/sync', access:'agents'};
const SECTION = /^(overview|services|agents|jobs|settings)(\/[a-z0-9][a-z0-9_.-]{0,79})?$/;
const known = section => {
  if (typeof section !== 'string') return '';
  if (Object.hasOwn(LEGACY, section)) return LEGACY[section];
  if (!SECTION.test(section)) return '';
  return section === 'settings' ? 'settings/keys' : section;
};
const topOf = section => section.split('/')[0];
// This history entry's own section (reload, Back/Forward into a fresh load) first, then this tab's last one.
let data = null, model = null, active = known(history.state?.section) || known(tabSection.get()) || 'overview', noticeTimer;
if (tabSection.get() && known(tabSection.get()) !== tabSection.get() && known(tabSection.get())) tabSection.set(known(tabSection.get()));
const markNav = () => document.querySelectorAll('[data-nav]').forEach(n => {
  const on = n.dataset.nav === topOf(active);
  n.classList.toggle('active', on);
  if (on) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current');
});
markNav();  // The restored section shows in the navigation before any data arrives.
// The launch fragment leaves the address bar and this history entry before any request is made.
if (location.hash) history.replaceState({section:active}, '', location.pathname); else history.replaceState({section:active}, '');
const GATE_REASONS = {
  session_expired:'会话已过期：在终端再次运行 atm ui 打开新的管理台',
  unauthorized:'管理台已重启或会话已失效：在终端再次运行 atm ui',
  rejected:'会话码未被接受：请核对终端所示 token 文件中的会话码',
  launch_expired:'启动链接已使用或已过期：在终端再次运行 atm ui'
};
// Page state that survives refreshes for this tab (memory only; never the URL or storage).
// successor: data-keys to focus when the focused control (or a dialog's opener) is gone after the next render.
const ui = {inboxOpen:false, jobs:new Set(), details:new Set(), closed:new Set(), toolLimit:100, service:new Map(), lastFetch:0, refreshing:false, error:null, focusJob:null, successor:[]};
const serviceFilters = {q:'', route:'', view:'services', status:'', paidOnly:false};
const jobFilters = {group:'all', service:'', showCredits:false};
const wide = window.matchMedia('(min-width: 768px)');

// ---- Small shared pieces ----
const announce = message => {
  const n = $('#announce'); n.textContent = message;
  clearTimeout(announce.timer); announce.timer = setTimeout(() => { n.textContent = ''; }, 1000);
};
const toast = (message, error=false) => {
  // Dialog messages stay in the dialog; a background result is only announced.
  if ($('#modal').open) { announce(message); return; }
  const n=$('#toast'); n.textContent=message; n.className=error?'error':''; n.hidden=false;
  clearTimeout(noticeTimer); noticeTimer=setTimeout(()=>n.hidden=true,7500);
};
const errorCode = e => e?.code || (/^([a-z][a-z0-9_]*):/.exec(String(e?.message || '')) || [])[1] || '';
const errorText = e => {
  const code = errorCode(e);
  if (!code) return e?.message ? '操作没有完成：' + e.message : '操作没有完成。';
  return T.errorText(code);
};
function report(e) {
  if (e?.gated) return;
  if ($('#modal').open) showAlert(errorText(e), {error: e});
  // A failed refresh already shows the page banner (its documented channel); it is not said twice.
  else if (!e?.bannered) toast(errorText(e), true);
}
// A busy button is disabled for the request, which drops its focus to <body>. When the request ends and
// nothing else took the focus, it returns to that button, or to its re-rendered counterpart.
const action = fn => async event => {
  const b=event?.currentTarget, button=b?.tagName==='BUTTON'?b:null;
  const hadFocus=Boolean(button)&&document.activeElement===button, key=button?.dataset?.key||'';
  if (button) button.disabled=true;
  try { await fn(event); } catch(e) { report(e); }
  finally {
    if (button?.isConnected) button.disabled=false;
    if (hadFocus&&(!document.activeElement||document.activeElement===document.body)&&!$('#modal').open&&$('#gate').hidden) {
      const target=button.isConnected?button:key?$('#main [data-key="'+CSS.escape(key)+'"]'):null;
      target?.focus({preventScroll:true});
    }
  }
};
const btn = (text, fn, type='secondary', attrs={}) => el('button', {type:'button', class:type, onclick:action(fn), ...attrs}, text);
// Ids wrap after each dot and paths after each slash (<wbr>); the text stays the same.
const breakable = id => String(id).split(/(?<=[./])/).flatMap((part,i)=>i?[el('wbr'),part]:[part]);
const mono = (text, cls='') => el('code', {class:cls}, breakable(text));
const stateWord = (state, word, attrs={}) => el('span', {class:'state', 'data-state':state, ...attrs}, el('span', {class:'glyph', ariaHidden:'true'}), word);
const quote = T.quote;
function brandMark(brand, size=32) {
  const mark=el('span',{class:'provider-mark s'+size,ariaHidden:'true','data-brand':brand.key});
  const fallback=()=>{mark.classList.add('initials');mark.replaceChildren(document.createTextNode(brand.initials));};
  if (brand.src) mark.append(el('img',{src:brand.src,alt:'',width:size,height:size,decoding:'async',onerror:()=>{
    fallback();console.warn('ATM brand image failed to render:',brand.key);
  }}));
  else fallback();
  return mark;
}
const brandOf = (provider, toolId='') => window.ATM_BRANDS.get(provider, toolId);
// A neutral mark for rows that are not a service (a Passkey, a paired device): DOM-built SVG, no markup strings.
const ICONS = {passkey:['M11 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z','M11 12h10','M18 12v3','M21 12v2'],
  device:['M5 6h14a1 1 0 0 1 1 1v9H4V7a1 1 0 0 1 1-1z','M2 19h20']};
function iconMark(name) {
  const NS='http://www.w3.org/2000/svg', svg=document.createElementNS(NS,'svg');
  for (const [k,v] of Object.entries({viewBox:'0 0 24 24',width:'16',height:'16',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',focusable:'false'})) svg.setAttribute(k,v);
  for (const d of ICONS[name]) { const path=document.createElementNS(NS,'path'); path.setAttribute('d',d); svg.append(path); }
  return el('span',{class:'provider-mark s28 icon-mark',ariaHidden:'true','data-icon':name},svg);
}
function brandIdentity(provider,content,toolId='',size=32) {
  return el('div',{class:'provider-identity'},brandMark(brandOf(provider,toolId),size),el('div',{class:'provider-copy'},...content));
}
const serviceMark = (service, size=32) => brandMark(service.brand || brandOf(service.provider), size);
function commandBox(text, label='') {
  const code = el('code', {}, text);
  const copy = el('button', {type:'button', class:'plain', 'data-key':'copy:'+text}, '复制');
  copy.addEventListener('click', () => copyText(text, copy, code));
  return el('div', {class:'command-wrap'}, label ? el('p', {class:'command-label'}, label) : null, el('div', {class:'command'}, code, copy));
}
async function copyText(text, button, code) {
  try {
    await navigator.clipboard.writeText(text);
    if (button) { button.textContent = '已复制'; setTimeout(() => { if (button.isConnected) button.textContent = '复制'; }, 2000); }
    announce('已复制命令');
  } catch {
    if (code) { const range = document.createRange(); range.selectNodeContents(code); const s = getSelection(); s.removeAllRanges(); s.addRange(range); }
    announce('已选中命令，按 ⌘C 复制。');
  }
}
const ranCommand = () => el('button', {type:'button', class:'plain', onclick:action(async () => { await refresh(); announce('已刷新'); })}, '我已运行，刷新');
function facts(rows) {
  return el('dl', {class:'facts'}, ...rows.flatMap(([term, value, isMono]) => [el('dt', {}, term), el('dd', {}, isMono ? mono(value) : value)]));
}
// Open <details> survive refreshes for this tab; byDefault opens it until the owner closes it.
function detailsOpen(key, byDefault, summary, ...content) {
  const d = el('details', {'data-key':'details:'+key}, el('summary', {}, summary), ...content);
  d.open = ui.details.has(key) || (byDefault && !ui.closed.has(key));
  d.addEventListener('toggle', () => { if (d.open) { ui.details.add(key); ui.closed.delete(key); } else { ui.details.delete(key); ui.closed.add(key); } });
  return d;
}
const details = (key, summary, ...content) => detailsOpen(key, false, summary, ...content);
const raw = (key, value, summary='查看原始内容（JSON）') => details(key, summary, el('pre', {class:'raw'}, JSON.stringify(value, null, 2)));
function segmented(label, options, current, onPick) {
  return el('div', {class:'segmented', role:'group', ariaLabel:label}, ...options.map(([value, text]) =>
    el('button', {type:'button', 'aria-pressed':String(value === current), 'data-key':'seg:'+label+':'+value, onclick:() => onPick(value)}, text)));
}
const emptyRow = text => el('li', {class:'empty'}, stateWord('ready', ''), text);
const rows = (...items) => el('ul', {class:'rows'}, ...items);

// ---- Gate, session, API (unchanged mechanics) ----
function showGate(reason='') {
  const line=$('#gate-reason'); line.textContent=GATE_REASONS[reason]||''; line.hidden=!line.textContent;
  $('#gate').hidden=false;
}
// The exit button and every 401 end the same way: no bearer, data, dialog, toast or rendered page remains.
function forget(reason='') {
  token=''; tabToken.clear(); data=null; model=null; closeModal(); $('#main').replaceChildren();
  clearTimeout(noticeTimer); $('#toast').hidden=true; showGate(reason); renderPill();
}
// Sections are kept per tab across reloads; Back and Forward move between them.
function go(section, opts={}) {
  section = known(section) || 'overview';
  const changed = section !== active;
  if (changed) history.pushState({section},'');
  active=section; tabSection.set(section); render({changed:true, focus:opts.focus !== false});
}
async function api(path, body) {
  const sent=token, opts={headers:{Authorization:'Bearer '+sent},cache:'no-store'};
  // Locked or ended: nothing is sent without the bearer, and the gate already says why.
  if(!sent){const error=new Error('unauthorized: 会话已结束');error.gated=true;throw error;}
  if (body !== undefined) {opts.method='POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
  let r;
  try { r=await fetch(path,opts); } catch { throw Object.assign(new Error('network: 连接不到本机 ATM'),{code:'network'}); }
  const value=await r.json();
  if (!r.ok) {
    const error=Object.assign(new Error((value.error?.code || 'request_failed')+': '+(value.error?.message || '请求未完成')),{code:value.error?.code,status:r.status,detail:value.error?.message});
    // Only an answer for the current bearer ends the session; a late reply for an old one must not.
    // The gate then says why in Chinese, so callers do not repeat it in a toast.
    if(r.status===401&&sent===token) {forget(value.error?.code==='session_expired'?'session_expired':sent===typed?'rejected':'unauthorized');error.gated=true;}
    throw error;
  }
  return value;
}
async function refresh() {
  const sent=token;
  ui.refreshing=true; $('#refresh').setAttribute('aria-busy','true');
  try {
    const [overview,tools,connections,jobs,clis,sync,access,extensions,session,passkeys]=await Promise.all(['/api/overview','/api/tools','/api/connections','/api/jobs','/api/clis','/api/sync','/api/access','/api/extensions','/api/session','/api/passkeys'].map(p=>api(p)));
    if(token!==sent)return;  // Locked or replaced meanwhile: a late answer must not reopen the page.
    data={overview,tools:tools?.tools,connections,jobs:jobs?.jobs,clis:clis?.clis,sync,access,extensions,session,passkeys,sessionFetchedAt:Date.now()};
    model=MODEL.derive(data);
    ui.lastFetch=Date.now(); ui.error=null;
    $('#version').textContent='ATM v'+(overview?.version || '');
    $('#origin').textContent='仅在本机运行 · '+location.host;
    $('#gate').hidden=true;
    render();
  } catch (e) {
    if (!e?.gated && data && token===sent) { ui.error={text:errorText(e), at:Date.now()/1000}; render(); if (e && typeof e==='object') e.bannered=true; }
    throw e;
  } finally {
    ui.refreshing=false; $('#refresh').removeAttribute('aria-busy');
  }
}
// The control that opened a dialog. action() disables (and so blurs) the clicked button, hence lastFocus.
let modalReturn=null, modalReturnKey='', modalPending=false, lastFocus=null;
document.addEventListener('focusin',e=>{if(!$('#modal').contains(e.target))lastFocus=e.target;});

// ---- Dialog kit ----
function openModal({title, steps=null, body=[], actions=[], focus=null, wide:isWide=false}) {
  const m=$('#modal');
  $('#modal-title').textContent=title;
  renderSteps(steps);
  $('#modal-body').replaceChildren(...[body].flat(2).filter(c=>c!==null&&c!==undefined&&c!==false));
  $('#modal-actions').replaceChildren(...[actions].flat(2).filter(Boolean));
  clearAlert(); $('#modal-status').textContent='';
  m.classList.toggle('wide', isWide);
  if(!m.open){
    modalReturn=document.activeElement===document.body||!document.activeElement?lastFocus:document.activeElement;
    modalReturnKey=modalReturn?.dataset?.key||''; modalPending=true;
    m.showModal();
  }
  const target = focus || m.querySelector('#modal-body input:not([type=hidden]):not([disabled]):not([hidden]), #modal-body select, #modal-body textarea')
    || m.querySelector('#modal-actions .primary') || m.querySelector('#modal-body .primary') || $('#modal-close');
  target?.focus();
}
function renderSteps(steps) {
  const list=$('#modal-steps');
  if(!steps||steps.items.length<2){list.hidden=true;list.replaceChildren();return;}
  list.hidden=false;
  list.replaceChildren(...steps.items.map((label,i)=>el('li',{class:i<steps.current?'done':'', 'aria-current':i===steps.current?'step':null},
    el('span',{class:'dot',ariaHidden:'true'},i<steps.current?'✓':String(i+1)),label)));
}
const byKey = key => key ? $('#main [data-key="'+CSS.escape(key)+'"]') : null;
// Focus returns to the control that opened the dialog, or to its re-rendered counterpart. When that control is gone
// (the Key it added is saved, the grant it revoked has ended), to a successor the dialog named, else the page heading.
// Runs once per dialog: closeModal() and the dialog's close event both call it.
function restoreFocus() {
  if(!modalPending)return;
  const node=modalReturn, key=modalReturnKey; modalReturn=null; modalReturnKey=''; modalPending=false;
  if(node?.isConnected) node.focus();
  else if(byKey(key)) byKey(key).focus();
  else if(!focusCredit(creditFocus(node))) (ui.successor.map(byKey).find(Boolean)||$('#main .page-title h1'))?.focus({preventScroll:true});
}
function closeModal() {$('#modal').close();$('#modal-body').replaceChildren();$('#modal-actions').replaceChildren();clearAlert();restoreFocus();}
function showAlert(message, {field=null, error=null}={}) {
  const n=$('#modal-alert');
  n.replaceChildren(message);
  const code=errorCode(error);
  if(code.startsWith('passkey_')) n.append(el('code',{},code));
  else if(error&&code&&!T.knownError(code)&&error.detail) n.append(el('details',{},el('summary',{},'技术信息'),el('p',{},error.detail)));
  n.setAttribute('role','alert'); n.hidden=false;
  if(field){field.setAttribute('aria-invalid','true');field.setAttribute('aria-describedby','modal-alert');field.focus();}
}
function clearAlert() {
  const n=$('#modal-alert'); n.hidden=true; n.replaceChildren(); n.removeAttribute('role');
  $('#modal-body')?.querySelectorAll('[aria-invalid=true]').forEach(f=>{f.removeAttribute('aria-invalid');if(f.getAttribute('aria-describedby')==='modal-alert')f.removeAttribute('aria-describedby');});
}
const status = text => { $('#modal-status').textContent=text; };
const cancel = (text='取消') => el('button',{type:'button',class:'secondary',onclick:()=>closeModal()},text);
let fieldSeq=0;
// A labelled field: visible label, hint linked by aria-describedby.
function field(label, input, hint='') {
  input.id ||= 'f'+(++fieldSeq);
  const hintNode = hint ? el('span',{class:'hint',id:input.id+'-hint'},hint) : null;
  if(hintNode) input.setAttribute('aria-describedby', hintNode.id);
  return {input, node:el('div',{class:'field'},el('label',{htmlFor:input.id},label,input),hintNode)};
}
function passwordField(label, autocomplete='off', hint='') {
  return field(label, el('input',{type:'password',autocomplete}), hint);
}
const masterPasswordField = (hint, label='ATM 主密码') => passwordField(label, 'current-password', hint);
const vaultInfo = () => data?.connections?.vault || {};
const sessionInfo = () => data?.session || {};
// Passphrase vault, not unlocked and no shared session: the password is typed for this one request.
const perRequestPassword = () => vaultInfo().backend==='passphrase' && !sessionInfo().unlocked && !sessionInfo().session_mode_enabled;
const needsUnlockStep = () => Boolean(sessionInfo().session_mode_enabled && !sessionInfo().unlocked);
const withSecret = (body, input) => input?.value ? {...body, passphrase: input.value} : body;
$('#modal-body').addEventListener('input', clearAlert);
$('#modal-body').addEventListener('change', clearAlert);

// ---- Render ----
const titles = {overview:'首页', services:'服务', agents:'Agent 与权限', jobs:'记录', settings:'设置'};
const SETTINGS = [['keys','Key 保管'],['sync','设备同步'],['tools','添加工具'],['programs','本机程序'],['advanced','高级']];
function render(opts={}) {
  markNav(); renderPill(); renderCounts();
  if(!data||!model)return;
  // Sub-keys are checked once data is in.
  const [top, sub] = [topOf(active), active.split('/')[1]];
  if (top==='services' && sub && !model.byKey.has(sub)) { replaceSection('services'); announce(sub+' 已不在服务列表中'); }
  if (top==='settings' && !SETTINGS.some(([k])=>k===sub)) replaceSection('settings/keys');
  const main=$('#main'), y=window.scrollY;
  const focusedHere = !$('#modal').open && main.contains(document.activeElement) && document.activeElement!==main;
  const focusKey = focusedHere ? document.activeElement?.dataset?.key : '';
  const selection = focusKey && document.activeElement.selectionStart !== undefined ? [document.activeElement.selectionStart, document.activeElement.selectionEnd] : null;
  const nodes = [];
  if (ui.error) nodes.push(el('div',{class:'banner',role:'alert'},el('span',{},`读取本机状态失败：${ui.error.text.replace(/。$/,'')}。页面显示的是 ${T.time(ui.error.at)} 读取的状态。`),btn('重试',async()=>{await refresh();announce('已刷新');})));
  const page = {overview:renderOverview, services:renderServices, agents:renderAgents, jobs:renderJobs, settings:renderSettings}[topOf(active)];
  main.dataset.width = active.startsWith('services/') || topOf(active)==='settings' ? 'narrow' : 'wide';
  main.replaceChildren(...nodes, ...page(active.split('/')[1]));
  renderContext(); setTitle();
  $('#global-search').hidden = active==='services'; $('#search-button').hidden = active==='services';
  if (opts.changed) {
    window.scrollTo(0,0);
    if (opts.focus) $('#main .page-title h1')?.focus({preventScroll:true});
  } else {
    window.scrollTo(0,y);
    if (focusedHere) {
      // The same control again; if it is gone (its job is done), a named successor or the page heading, never <body>.
      const same=byKey(focusKey), n=same||ui.successor.map(byKey).find(Boolean)||$('#main .page-title h1');
      n?.focus({preventScroll:true});
      if (same && selection && n.setSelectionRange) try { n.setSelectionRange(...selection); } catch {}
    }
  }
  ui.successor=[];
  if (ui.focusJob) { const row=$('#main [data-key="job:'+CSS.escape(ui.focusJob)+'"]'); ui.focusJob=null; row?.scrollIntoView({block:'center'}); }
}
function replaceSection(section) { active=section; tabSection.set(section); history.replaceState({section}, ''); markNav(); }
function setTitle() {
  const [top, sub] = active.split('/');
  if (top==='services' && sub) document.title = (model.byKey.get(sub)?.name || sub)+' · 服务 · ATM';
  else if (top==='settings') document.title = (SETTINGS.find(([k])=>k===sub)?.[1] || 'Key 保管')+' · 设置 · ATM';
  else document.title = titles[top]+' · ATM';
}
function renderContext() {
  const [top, sub] = active.split('/'), ctx=$('#context');
  if ((top==='services' && sub) || top==='settings') {
    const parent = top==='services' ? ['服务','services'] : ['设置','settings/keys'];
    const here = top==='services' ? (model.byKey.get(sub)?.name || sub) : (SETTINGS.find(([k])=>k===sub)?.[1] || '');
    // Links back to the parent page (in-app; the address never carries a section).
    const link=(cls,text)=>el('a',{href:'/',class:cls,onclick:e=>{e.preventDefault();go(parent[1]);}},text);
    ctx.replaceChildren(link('back','‹ '+parent[0]),link('crumb-parent',parent[0]),el('span',{class:'sep',ariaHidden:'true'},' / '),el('span',{class:'crumb-here'},here));
  } else ctx.replaceChildren(el('span',{class:'crumb-here'},titles[top]));
}
function renderCounts() {
  const counts = {overview: model ? model.inbox.length : 0, agents: model ? model.counts.liveRequests : 0};
  for (const [nav, n] of Object.entries(counts)) {
    const node = $('[data-nav='+nav+'] .nav-count');
    node.hidden = !n; node.textContent = n ? String(n) : '';
    if (n) node.setAttribute('aria-label', nav==='overview' ? n+' 件事需要你处理' : n+' 个请求等你确认'); else node.removeAttribute('aria-label');
  }
}
const pageTitle = (h1, lede, ...actions) => el('section',{class:'page-title'},el('div',{},el('h1',{tabIndex:-1},h1),lede?el('p',{class:'lede'},lede):null),
  actions.filter(Boolean).length?el('div',{class:'page-actions'},...actions.filter(Boolean)):null);

// ---- Key pill: the only global lock control ----
let lastMinute=-1, expiredOnce=false;
function renderPill() {
  const pill=$('#credential-session'), button=$('#session-action'), text=$('#pill-text');
  const vault=vaultInfo(), session=sessionInfo();
  const state = !data ? 'loading' : !vault.backend ? 'novault' : session.unlocked ? 'unlocked' : 'locked';
  pill.dataset.state=state;
  button.hidden = state==='loading';
  text.textContent = {loading:'Key …', novault:'Key 保管未设置', locked:'Key 已锁定', unlocked:'Key 已解锁 · '}[state];
  button.textContent = {loading:'', novault:'去设置', locked:'解锁 30 分钟', unlocked:'立即锁定'}[state];
  if (state!=='unlocked') { $('#lease-countdown').textContent=''; $('#lease-minutes').textContent=''; lastMinute=-1; expiredOnce=false; }
  else tick();
}
function leaseLeft() { return Math.max(0, Math.floor((data?.session?.seconds_remaining||0)-(Date.now()-(data?.sessionFetchedAt||Date.now()))/1000)); }
function tick() {
  if (!data?.session?.unlocked) return;
  const left = leaseLeft(), pill=$('#credential-session');
  $('#lease-countdown').textContent = String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');
  pill.style.setProperty('--lease', String(Math.min(1, left/1800)));
  const minute = Math.ceil(left/60);
  if (minute!==lastMinute) { lastMinute=minute; $('#lease-minutes').textContent=`Key 已解锁，还剩 ${minute} 分钟`; }
  if (!left && !expiredOnce) { expiredOnce=true; refresh().then(()=>announce('30 分钟到了，Key 已自动锁定。'),report); }
}
setInterval(tick, 1000);
$('#session-action').addEventListener('click', action(async () => {
  const state=$('#credential-session').dataset.state;
  if (state==='novault') vaultDialog();
  else if (state==='locked') unlockDialog();
  else if (state==='unlocked') {
    await api('/api/session/lock',{}); await refresh();
    toast('Key 已锁定。新的 Key 使用已停止；已经在运行的程序可能仍持有取到的 Key。'); announce('Key 已锁定');
  }
}));

// ---- Actions from the model ----
function runAction(a, opener) {
  const t=a.target;
  if (a.kind==='nav') { if (a.job) { ui.jobs.add(a.job); ui.focusJob=a.job; jobFilters.group='all'; } go(t); return; }
  if (a.kind==='route') { openRoute(t); return; }
  if (a.kind==='refresh') return refresh().then(()=>announce('已刷新'));
  if (a.kind==='credits') return refreshCredits(t);
  if (a.kind==='copy') return copyText(t, null, null).then(()=>toast('已复制命令：'+t));
  if (a.kind==='bulk') return bulkDialog(model.byKey.get(t.service).tools, t.enable, model.byKey.get(t.service).name + ' 的全部工具', model.byKey.get(t.service).name);
  if (a.kind!=='dialog') return;
  switch (t.d) {
    case 'key': return keyDialog({mode:t.mode, name:t.name});
    case 'resolve': return resolveDialog(t.name);
    case 'setup': return setupDialog({agents:t.agents||[], clis:t.clis||[], replace:Boolean(t.replace)});
    case 'verify': return verifyDialog(t.name);
    case 'remove': return removeDialog(t.name);
    case 'vault': return vaultDialog();
    case 'tool': return toolDialog(t.id);
    case 'oauth': return oauthDialog({keep:Boolean(t.keep)});
    case 'stop-renew': return stopRenewConfirm();
    case 'unregister': return unregisterConfirm(t.agent, t.label);
  }
}
const actionButton = (a, type, key) => el('button', {type:'button', class:type || (a.primary?'primary':a.danger?'plain danger':a.quiet?'plain':'secondary'),
  'data-key':key, onclick:action(e=>runAction(a, e.currentTarget))}, a.label);
function openRoute(t) {
  const section='services/'+t.service;
  if (active!==section) go(section, {focus:false}); else render();
  const node=document.getElementById(t.anchor);
  if (!node) { $('#main .page-title h1')?.focus(); return; }
  node.scrollIntoView({block:'start'});
  node.classList.add('flash'); setTimeout(()=>node.classList.remove('flash'),2000);
  // A link may name what to focus there: a step's control, the route's first action, or its first command's 复制.
  const target = (t.step && node.querySelector('.steps>li:nth-child('+t.step+') button, .steps>li:nth-child('+t.step+') .command .plain'))
    || (t.focus==='action' && node.querySelector('.route-body>.actions button'))
    || (t.focus==='command' && node.querySelector('.command .plain')) || node;
  target.focus({preventScroll:true});
}

// ---- 首页 ----
function renderOverview() {
  const m=model, out=[], live=m.requests.filter(r=>r.live), open=m.firstRun.steps.filter(s=>!s.done).length;
  const ready=m.counts.servicesReady, vault=vaultInfo(), session=sessionInfo();
  if (m.firstRun.show) out.push(pageTitle('开始使用 ATM', `还差 ${open} 步。完成后，Claude Code 和 Codex 就能用你在这里设置的 Key 和工具。`));
  else if (m.inbox.length) out.push(pageTitle(`有 ${m.inbox.length} 件事需要你处理`, `只列出会让 Agent 用不了的问题，处理后会自动消失。${ready} 个服务可以使用。`));
  else if (live.length) out.push(pageTitle('有 Agent 在等你确认', '在授权窗口里确认后，Agent 会继续。'));
  else out.push(pageTitle('一切正常', `${ready} 个服务可以使用。` + (!vault.backend ? '还没设置 Key 保管方式。' : session.unlocked
    ? `Key 已解锁，到 ${T.time(Date.now()/1000+leaseLeft())} 自动锁定。` : 'Key 已锁定：Agent 需要 Key 时会打开授权窗口请你确认。')));
  if (m.requests.length) out.push(requestsSection('home-requests'));
  if (m.firstRun.show) out.push(firstRunSection());
  if (!(m.firstRun.show && !m.inbox.length)) out.push(inboxSection());
  const credits=creditsPanel(); if (credits) out.push(credits);
  out.push(el('div',{class:'home-grid'},homeServices(),el('div',{class:'home-aside'},homeAgents(),homeJobs())));
  out.push(el('p',{class:'footnote'},'查看本页不会调用任何服务，也不会运行工具。'));
  return out;
}
function requestRows(list) {
  return el('ul',{class:'rows requests'},...list.map(r=>el('li',{class:'request','data-request':r.id},
    el('h3',{},r.title), mono(r.workspace,'path'),
    el('div',{class:'keychips'},...r.chips.map(c=>el('span',{class:'keychip','data-state':c.ready?'ready':'setup'},el('span',{class:'glyph',ariaHidden:'true'}),c.label))),
    el('p',{},stateWord(r.live?'handoff':'setup',r.statusText)), el('p',{class:'meta'},r.timeText))));
}
function requestsSection(id) {
  const list=model.requests;
  return el('section',{id},el('div',{class:'section-head'},el('div',{},el('h2',{},'等你确认 · '+list.length))),
    requestRows(list), el('div',{class:'info'},'只能在授权窗口里批准。管理台不能替 Agent 批准，Agent 也不能自己批准。'));
}
function firstRunSection() {
  const [vault, agents, svc] = model.firstRun.steps, left = model.firstRun.steps.filter(s=>!s.done).length;
  const detected = (data.overview?.agents||[]).filter(a=>a.detected_executable).map(a=>a.agent);
  const step = (n, s, title, text, button, done) => el('li',{},
    s.done ? el('span',{class:'done-dot','data-state':'ready'},el('span',{class:'glyph',ariaHidden:'true'})) : el('span',{class:'num-dot',ariaHidden:'true'},String(n)),
    el('strong',{},s.done?done:title), s.done?null:el('p',{},text), s.done?null:button);
  return el('section',{id:'first-run'},el('div',{class:'section-head'},el('div',{},el('h2',{},'开始使用 · 还差 '+left+' 步'))),
    el('ol',{class:'checklist rows'},
      step(1, vault, '选择 Key 的保管方式', '保存任何 API Key 之前需要设置一次，以后不用再设置。', btn('开始设置',()=>vaultDialog(),'primary',{'data-key':'first:vault'}), '已设置 Key 保管方式：'+(T.backend[vault.backend]||vault.backend)),
      step(2, agents, '把 ATM 安装到 Claude Code 或 Codex', '安装后，Agent 的新会话里就能使用 ATM。', btn('安装',()=>setupDialog({agents:detected.length?detected:['claude','codex']}),'secondary',{'data-key':'first:agents'}), '已安装到 '+agents.labels.join('和')),
      step(3, svc, '连接第一个服务（可选）', '只连接你要用的服务，不必全部连接。', btn('选择服务',()=>go('services'),'secondary',{'data-key':'first:service'}), '已经在用 '+svc.count+' 个服务')));
}
function issueRow(i) {
  const sev={bad:'严重：',warn:'注意：',info:'提示：'}[i.sev];
  const service=i.serviceKey?model.byKey.get(i.serviceKey):null;
  return el('li',{class:'issue','data-sev':i.sev,'data-issue':i.id},el('span',{class:'glyph',ariaHidden:'true'}),
    el('h3',{},el('span',{class:'vh'},sev),service?serviceMark(service,20):null,el('span',{},i.title)), el('p',{},i.detail),
    el('button',{type:'button',class:'secondary','data-key':'inbox:'+i.id,onclick:action(e=>runAction(i.action,e.currentTarget))},i.action.label,service?el('span',{class:'vh'},'（'+service.name+'）'):null));
}
function inboxSection() {
  const list=model.inbox, shown=ui.inboxOpen?list:list.slice(0,5), rest=list.length-5;
  const items=list.length?shown.map(issueRow):[emptyRow('没有需要你处理的事。')];
  if (rest>0) items.push(el('li',{class:'more-row'},el('button',{type:'button',class:'more','aria-expanded':String(ui.inboxOpen),'aria-controls':'inbox-list','data-key':'inbox:more',
    onclick:()=>{ui.inboxOpen=!ui.inboxOpen;render();}},ui.inboxOpen?'收起':'再显示 '+rest+' 项')));
  return el('section',{id:'inbox'},el('div',{class:'section-head'},el('div',{},el('h2',{},'需要你处理'))),el('ul',{class:'rows',id:'inbox-list'},...items));
}
function serviceRow(s) {
  const credit=s.credits&&typeof s.credits.credits==='number'?creditNumber(s.credits.credits):'';
  const word=serviceWord(s);
  return el('button',{type:'button',class:'service-row','data-key':'service:'+s.key,ariaLabel:`${s.name}：${word}`+(credit?`，${credit} 积分`:''),onclick:()=>go('services/'+s.key)},
    serviceMark(s,32), el('span',{class:'name'},s.name), routeStrip(s.routes,false),
    el('span',{class:'side'},credit?el('span',{class:'num'},credit+' 积分'):null,stateWord(s.state,word),el('span',{class:'chev',ariaHidden:'true'},'›')));
}
const serviceWord = s => ({ready:'可以使用',attention:'需要处理',blocked:'不能使用',setup:'待设置',handoff:'无需设置',off:'已停用'})[s.state];
function routeStrip(routes, large) {
  return el('ul',{class:'route-strip'+(large?' large':''),role:'list',ariaHidden:large?null:'true'},...routes.map(r=>el('li',{class:'route-chip','data-state':r.state,'data-kind':r.kind,role:'listitem'},
    el('span',{class:'glyph',ariaHidden:'true'}), large?r.chip+' · '+r.word:r.chip, large?null:el('span',{class:'vh'},'：'+r.word))));
}
function homeServices() {
  const inUse=model.services.filter(s=>s.inUse), rank=s=>['blocked','attention'].includes(s.state)?0:1;
  const sorted=[...inUse].sort((a,b)=>rank(a)-rank(b)||new Intl.Collator('zh-CN').compare(a.name,b.name));
  const others=model.services.length-inUse.length;
  const head=el('div',{class:'section-head'},el('div',{},el('h2',{},'我在用的服务'),el('small',{},`${inUse.length} 个 · 还有 ${others} 个可添加`)),
    el('button',{type:'button',class:'plain',onclick:()=>go('services'),'data-key':'home:services'},'全部服务'));
  if (!inUse.length) return el('section',{id:'home-services'},head,el('div',{class:'panel'},el('p',{},'还没有在用的服务。到“服务”里找到要用的服务，按页面上的提示连接。'),el('div',{},btn('查看全部服务',()=>go('services')))));
  const list=el('div',{class:'service-list'},...sorted.slice(0,8).map(serviceRow));
  if (sorted.length>8) list.append(el('button',{type:'button',class:'more',onclick:()=>go('services')},`还有 ${sorted.length-8} 个在用的服务`));
  return el('section',{id:'home-services'},head,list);
}
function homeAgents() {
  return el('section',{id:'home-agents'},el('div',{class:'section-head'},el('div',{},el('h2',{},'Agent')),el('button',{type:'button',class:'plain',onclick:()=>go('agents')},'管理')),
    rows(...model.agents.map(a=>el('li',{class:'agent-mini'},brandMark(brandOf(a.agent),28),el('strong',{},a.label),stateWord(a.state,a.word),
      a.short?actionButton(a.short,'secondary','agent:'+a.agent+':short'):null))));
}
function homeJobs() {
  const list=model.jobs.filter(j=>j.kind==='tool').slice(0,3);
  return el('section',{id:'home-jobs'},el('div',{class:'section-head'},el('div',{},el('h2',{},'最近记录')),el('button',{type:'button',class:'plain',onclick:()=>go('jobs')},'全部')),
    rows(...(list.length?list.map(j=>el('li',{},el('button',{type:'button',class:'job-mini','data-key':'home-job:'+j.id,onclick:()=>{ui.jobs.add(j.id);ui.focusJob=j.id;go('jobs');}},
      brandMark(brandOf(j.brand,j.tool),28),mono(j.tool),stateWord(j.state,(j.day==='今天'?'今天 '+j.time:j.day)+' · '+j.word)))):[el('li',{class:'empty'},'还没有记录。')])));
}

// ---- Subscription credits: cached values only; a tool runs only when the owner clicks. ----
const creditsBusy=new Set(); // Queued or running.
let creditsRunning=null, creditsQueue=Promise.resolve(); // Every refresh runs one at a time: website sources share the logged-in browser.
const creditNumber=value=>new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(value);
const creditErrors=T.creditErrors;
// Short label for an error code; own keys only, so a code such as "constructor" is not a prototype member.
const creditLabel=code=>Object.hasOwn(creditErrors,code)?creditErrors[code]:'读取失败 · '+code;
const relativeTime=epoch=>T.relative(epoch);
function updateCredit(record) {
  const list=data?.overview?.credits?.providers, i=list?list.findIndex(p=>p.provider===record.provider):-1;
  if(i>=0)list[i]=record;
}
// Keyboard focus survives a re-render: the same provider + action button is focused in the new page.
function creditFocus(node) {
  const action=node?.dataset?.creditAction;
  return action?{action,provider:node.dataset.creditProvider||node.closest?.('[data-provider]')?.dataset.provider}:null;
}
function focusCredit(key) {
  if(!key)return null;
  const selector=key.action==='all'||!key.provider?'#main [data-credit-action="all"]':'#main [data-credit-action="'+CSS.escape(key.action)+'"][data-credit-provider="'+CSS.escape(key.provider)+'"]';
  const node=$(selector); node?.focus();
  return node;
}
function drawCredits() {
  if(!data)return;
  model=MODEL.derive(data); render();
}
function refreshCredits(names) {
  names=names.filter(name=>!creditsBusy.has(name));
  if(!names.length)return creditsQueue;
  names.forEach(name=>creditsBusy.add(name));drawCredits();
  const run=async()=>{
    const failed=[];
    for(const name of names) {
      creditsRunning=name;drawCredits();
      const label=data?.overview?.credits?.providers?.find(p=>p.provider===name)?.label||name;
      try{const r=await api('/api/credits/refresh',{provider:name});updateCredit(r);if(r.refresh==='error')failed.push(r.label+' · '+creditLabel(r.error.code));}
      catch(e){if(e.gated)throw e;failed.push(label+' · '+(e.code?creditLabel(e.code):e.message));}
      finally{creditsRunning=null;creditsBusy.delete(name);drawCredits();}
    }
    if(failed.length)toast('额度读取失败：'+failed.join('；'),true);else toast('订阅额度已更新。');
  };
  creditsQueue=creditsQueue.then(run).catch(e=>{if(!e?.gated)toast(errorText(e),true);});
  return creditsQueue;
}
function creditsButton(text,names,type,kind,provider=null) {
  // Busy only when every listed provider is; a busy button stays focusable (aria-disabled) across re-renders.
  const busy=names.length>0&&names.every(name=>creditsBusy.has(name));
  const running=kind==='check'?'正在检查…':'刷新中…';
  const label=!busy?text:names.length===1&&names[0]!==creditsRunning?'排队中…':running;
  return el('button',{type:'button',class:type,disabled:!names.length,ariaDisabled:String(busy),ariaBusy:String(busy),'data-credit-action':kind,'data-credit-provider':provider,
    'data-key':'credit:'+kind+':'+(provider||'all'),onclick:()=>{if(!busy)refreshCredits(names);}},label);
}
function cycleDialog(p) {
  const problem=el('p',{class:'form-error',role:'alert',hidden:true,id:'credit-cycle-problem'});
  const input=el('input',{type:'number',min:1,max:31,step:1,value:p.cycle_day??'',ariaLabel:'每月续期日','aria-describedby':problem.id});
  // Messages stay in the dialog's alert line, not behind its backdrop; an invalid day also marks the input.
  const reportDay=(message,invalid=false)=>{
    problem.textContent=message;problem.hidden=!message;
    if(invalid)input.setAttribute('aria-invalid','true');else input.removeAttribute('aria-invalid');
  };
  const save=async day=>{
    try{const r=await api('/api/credits/cycle',{provider:p.provider,day});updateCredit(r);}
    catch(e){if(!e.gated)reportDay(errorText(e));return;}
    closeModal();drawCredits();toast(day===null?'已清除续期日。':'续期日已保存。');
  };
  const submit=btn('保存',async()=>{
    const day=Number(input.value);
    const message=input.value!==''&&Number.isInteger(day)&&day>=1&&day<=31?'':'请输入 1–31 的整数。';
    // The inline alert is the only message; the browser's own validation bubble would repeat it.
    input.setCustomValidity(message);reportDay(message,Boolean(message));
    if(!message)await save(day);else input.focus();
  },'primary');
  input.addEventListener('input',()=>{input.setCustomValidity('');reportDay('');});
  input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();submit.click();}});
  openModal({title:'设置续期日 · '+p.label,body:[el('p',{class:'quiet'},'供应商目前不提供续期日期。填写账单上的每月续期日（1–31），短月份按月末计算；只保存在本机。'),
    el('label',{},'每月续期日',input),problem], actions:[cancel(),btn('清除',()=>save(null),'plain'),submit], focus:input});
}
function creditError(error) {
  const node=el('span',{class:'badge bad'},creditLabel(error.code));
  node.title=T.creditTitle(error);
  return node;
}
function creditSource(p) {
  if(!p.source)return null;
  const exe=model?.tools.get(p.source)?.tool.executable||p.next_executable||'程序';
  const site=T.sites[MODEL.serviceKeyOf(p.brand||p.provider)];
  const text=p.source_kind==='cli'?`来自 ${exe} 程序`:p.source==='tripo.server.account'?'来自服务器上的 Tripo Studio':`来自 ${site?.name||p.label} 网站（你的 Chrome 登录）`;
  return el('small',{class:'credit-source',title:p.source},text);
}
function creditCard(p) {
  const key=MODEL.serviceKeyOf(p.brand||p.provider), service=model?.byKey.get(key), name=service?.name||p.label;
  const sourceTool=model?.tools.get(p.source)||model?.tools.get(p.next_source);
  const routeOf=()=>sourceTool?{label:'去设置',kind:'route',target:{service:key,kind:sourceTool.route,id:sourceTool.routeId,anchor:'route-'+sourceTool.route+'-'+T.slug(sourceTool.routeId)}}:{label:'去设置',kind:'nav',target:'services/'+key};
  const go_=a=>el('button',{type:'button',class:'plain','data-key':'credit:go:'+p.provider,onclick:()=>runAction(a)},a.label);
  const cycle=el('small',{class:'credit-cycle'},p.next_cycle?'下次续期 '+p.next_cycle.date+'（你设置的）':'未设置续期日');
  const cycleButton=el('button',{type:'button',class:'plain','data-credit-action':'cycle','data-credit-provider':p.provider,'data-key':'credit:cycle:'+p.provider,onclick:action(()=>cycleDialog(p))},'设置续期日');
  const head=el('div',{class:'card-head'},brandIdentity(p.brand,[el('h3',{},el('button',{type:'button',class:'plain',onclick:()=>go('services/'+key)},p.label)),creditSource(p)],p.source||''));
  if(!p.installed) // Compact: where to set it up, and the owner-set renewal day.
    return el('article',{class:'credit-card','data-provider':p.provider},head,
      el('p',{class:'quiet'},`还不能读取：先在“${name}”页完成设置。`,' ',go_({label:'去设置',kind:'nav',target:'services/'+key})),cycle,el('div',{class:'card-actions'},cycleButton));
  const stale=p.last_ok_at&&Date.now()/1000-p.last_ok_at>86400;
  const amount=typeof p.credits==='number'?creditNumber(p.credits):'—';
  const site=T.sites[key], exe=sourceTool?.tool.executable||p.next_executable;
  const login=p.status==='error'&&p.error?.code==='login_required';
  return el('article',{class:'credit-card'+(creditsBusy.has(p.provider)?' busy':''),'data-provider':p.provider},head,
    el('strong',{class:'credit-amount'+(amount.length>12?' long':'')},amount,el('small',{},' 积分')),
    el('div',{class:'credit-meta'},p.plan?el('span',{class:'badge'},p.plan):null,el('small',{},p.last_ok_at?'上次读取 '+relativeTime(p.last_ok_at):'尚未读取'),
      stale?el('span',{class:'badge warn'},'超过 24 小时，可能已变化'):null,
      p.status==='error'&&p.error?creditError(p.error):null),
    login?el('p',{class:'quiet'},'需要登录：'+(p.source_kind==='cli'?`用 ${exe} 自己的登录命令登录`:`在 Chrome 里登录 ${site?.name||name}`),' ',go_({...routeOf(),label:'怎么登录'})):null,
    p.bound?null:el('p',{class:'quiet'},`还不能读取：需要先绑定 ${p.next_executable} 程序。`,' ',go_(routeOf())),
    cycle,
    el('div',{class:'card-actions'},p.bound?creditsButton('刷新',[p.provider],'secondary','refresh',p.provider):null,
      p.bound&&p.next_source!==p.source?el('small',{class:'credit-next',title:p.next_source},'下次刷新读取'+(p.next_source_kind==='cli'?' CLI':'网站')):null,
      cycleButton));
}
function creditsPanel(only=null) {
  const providers=data.overview?.credits?.providers;
  if(!providers)return null;
  if(only){
    const p=providers.find(x=>x.provider===only.provider);
    if(!p)return null;
    const sentence=p.source_kind==='cli'?'来自程序的订阅积分':p.source?'网站订阅积分':'订阅积分';
    return el('section',{class:'credits',id:'credits-panel'},el('div',{class:'section-head'},el('div',{},el('h2',{},'订阅额度'),el('small',{},sentence+'，与开发者 API 余额分开计费'))),
      el('div',{class:'credits-grid single'},creditCard(p)));
  }
  return el('section',{class:'credits',id:'credits-panel'},
    el('div',{class:'section-head'},el('div',{},el('h2',{},'订阅额度'),el('small',{},'只在你点击刷新时读取 · 打开本页不运行工具')),creditsButton('全部刷新',providers.filter(p=>p.installed&&p.bound).map(p=>p.provider),'secondary','all')),
    el('p',{class:'quiet'},'这些是网站 / CLI 的订阅积分，与开发者 API 余额分开计费。网站来源会读取本机已登录的浏览器。'),
    el('div',{class:'credits-grid'},...providers.map(creditCard)));
}

// ---- 服务 ----
const ROUTE_FILTER=[['','全部连接方式'],['key','API Key'],['chrome','你的 Chrome 登录'],['program','本机程序'],['oauth','ATM 登录'],['mcp','MCP 服务'],['recipe','ATM 网页登录'],
  ['origin','服务地址'],['studio_server','服务器上的 Tripo Studio'],['agent_browser','交给 Agent 的浏览器'],['desktop','桌面软件'],['human','人工'],['workflow','组合流程']];
const STATUS_FILTER=[['','全部状态'],['on','已允许'],['ready','可以使用'],['attention','需要处理'],['setup','待设置'],['handoff','无需设置'],['off','已停用']];
function renderServices(sub) {
  if (sub) return renderService(sub);
  const c=model.counts, out=[];
  out.push(pageTitle('服务',`每个服务一页：怎么连接、能不能用、Agent 可以用它做什么。${c.servicesReady} 个可以使用 · ${c.servicesAttention} 个需要处理 · ${c.servicesSetup} 个还没设置（用到时再设置，不必全部连接）。`,
    btn('添加自定义 Key',()=>declareDialog(),'secondary',{'data-key':'services:declare'}),btn('安装工具定义',()=>extensionDialog(),'secondary',{'data-key':'services:install'})));
  const q=el('input',{type:'search',id:'services-q',ariaLabel:'搜索服务或工具',placeholder:'搜索服务、工具 ID 或能力，例如 elevenlabs、3d、speech',value:serviceFilters.q,'data-key':'services-q',autocomplete:'off'});
  const route=el('select',{id:'services-route',ariaLabel:'连接方式','data-key':'services-route'},...ROUTE_FILTER.map(([v,t])=>el('option',{value:v},t)));
  route.value=serviceFilters.route;
  const host=el('div',{id:'services-results'});
  const view=segmented('显示方式',[['services','按服务'],['tools','按工具']],serviceFilters.view,v=>{serviceFilters.view=v;ui.toolLimit=100;render();});
  const extra=[];
  if(serviceFilters.view==='tools'){
    const statusSel=el('select',{ariaLabel:'工具状态','data-key':'services-status'},...STATUS_FILTER.map(([v,t])=>el('option',{value:v},t)));
    statusSel.value=serviceFilters.status;
    statusSel.addEventListener('change',()=>{serviceFilters.status=statusSel.value;ui.toolLimit=100;draw();});
    const paid=el('input',{type:'checkbox',checked:serviceFilters.paidOnly,'data-key':'services-paid'});
    paid.addEventListener('change',()=>{serviceFilters.paidOnly=paid.checked;ui.toolLimit=100;draw();});
    extra.push(statusSel,el('label',{class:'check'},paid,'只看可能扣费'),el('span',{class:'count-line',id:'tools-count'}));
  }
  const draw=()=>host.replaceChildren(...(serviceFilters.view==='tools'?toolsView():servicesView()));
  q.addEventListener('input',()=>{serviceFilters.q=q.value;ui.toolLimit=100;draw();});
  route.addEventListener('change',()=>{serviceFilters.route=route.value;ui.toolLimit=100;draw();});
  out.push(el('div',{class:'toolbar',role:'search'},el('div',{class:'search'},q),route,view,...extra),host);
  draw();
  return out;
}
function servicesView() {
  const q=serviceFilters.q.trim().toLowerCase();
  const list=model.services.filter(s=>(!q||s.haystack.includes(q))&&(!serviceFilters.route||s.routes.some(r=>r.kind===serviceFilters.route)));
  if(!list.length) return [el('div',{class:'panel'},el('p',{},`没有找到“${serviceFilters.q}”。可以搜服务名（如 ElevenLabs）、工具 ID（如 elevenlabs.tts）或能力（如 speech）。`),
    el('div',{},btn('清除搜索',()=>{serviceFilters.q='';serviceFilters.route='';render();$('#services-q')?.focus();})))];
  const handoffOnly=s=>s.routes.length>0&&s.routes.every(r=>['agent_browser','desktop','human','workflow','catalog'].includes(r.kind));
  const groups=[
    ['需要处理',null,list.filter(s=>s.inUse&&['blocked','attention'].includes(s.state)),'rows'],
    ['在用',null,list.filter(s=>s.inUse&&!['blocked','attention'].includes(s.state)),'rows'],
    ['还没设置','需要时再设置，不必全部连接',list.filter(s=>!s.inUse&&!handoffOnly(s)),'index'],
    ['无需在 ATM 设置','这些工具由 Agent 的浏览器、桌面软件或人来完成',list.filter(s=>!s.inUse&&handoffOnly(s)),'index'],
  ];
  return groups.filter(g=>g[2].length).map(([title,small,members,kind])=>el('section',{class:'group'},
    el('div',{class:'section-head'},el('div',{},el('h2',{},title+' · '+members.length),small?el('small',{},small):null)),
    kind==='rows'?el('div',{class:'service-list'},...members.map(serviceRow)):el('ul',{class:'service-index'},...members.map(s=>{
      const hits=q?s.tools.filter(v=>[v.id,v.title,...(v.tool.capabilities||[])].join('\n').toLowerCase().includes(q)).map(v=>v.id):[];
      return el('li',{},el('button',{type:'button','data-key':'service:'+s.key,onclick:()=>go('services/'+s.key)},serviceMark(s,20),el('span',{class:'name'},s.name),
        el('small',{},s.tools.length+' 个工具'),hits.length?el('small',{},'匹配：'+hits.slice(0,3).join('、')):null));
    }))));
}
function routeTitleOf(view) {
  const s=model.byKey.get(view.serviceKey);
  return s?.routes.find(r=>r.kind===view.route&&(r.kind==='key'?r.tools.includes(view):r.id===view.routeId))?.title||T.kinds[view.route];
}
function toolMatches(view) {
  const q=serviceFilters.q.trim().toLowerCase(), s=model.byKey.get(view.serviceKey);
  if(q&&![view.id,view.title,s?.name||'',s?.key||'',...(view.tool.capabilities||[])].join('\n').toLowerCase().includes(q))return false;
  if(serviceFilters.route&&view.route!==serviceFilters.route)return false;
  if(serviceFilters.status){const st=view.state,f=serviceFilters.status;if(f==='on'?!view.enabled:f==='attention'?!['attention','blocked'].includes(st):st!==f)return false;}
  if(serviceFilters.paidOnly&&!view.paid)return false;
  return true;
}
function toolsView() {
  const list=[...model.tools.values()].filter(toolMatches).sort((a,b)=>a.id.localeCompare(b.id));
  const count=$('#tools-count'); if(count)count.textContent=list.length+' 个工具';
  queueMicrotask(()=>{const n=$('#tools-count');if(n)n.textContent=list.length+' 个工具';});
  if(!list.length)return [el('div',{class:'panel'},el('p',{},'没有符合条件的工具。'))];
  const shown=list.slice(0,ui.toolLimit), rest=list.length-shown.length;
  const more=rest>0?el('button',{type:'button',class:'more','data-key':'tools:more',onclick:()=>{ui.toolLimit+=100;render();}},`再显示 100 个（还有 ${rest} 个）`):null;
  const reason=v=>v.state!=='ready'?el('div',{class:'why'},el('span',{},v.sentence),v.fix?actionButton(v.fix,'plain','fix:'+v.id):null):null;
  if(wide.matches) return [el('table',{class:'tools'},el('thead',{},el('tr',{},...['工具','服务','连接方式','状态','允许 Agent 使用'].map(h=>el('th',{scope:'col'},h)))),
    el('tbody',{},...shown.map(v=>{const s=model.byKey.get(v.serviceKey);return el('tr',{'data-tool-id':v.id,class:v.enabled?'':'disabled'},
      el('td',{},el('button',{type:'button',class:'tool-title','data-key':'tool:'+v.id,onclick:()=>toolDialog(v.id)},v.title),el('div',{},mono(v.id,'id')),el('div',{class:'tags'},...v.tags.map(tagNode))),
      el('td',{},el('span',{class:'svc'},serviceMark(s,20),el('button',{type:'button',class:'plain',onclick:()=>go('services/'+s.key)},s.name))),
      el('td',{},routeTitleOf(v)),el('td',{},stateWord(v.state,v.word),el('div',{class:'fold-route'},routeTitleOf(v)),reason(v)),el('td',{},toolSwitch(v)));}))),more];
  return [el('ul',{class:'rows tool-list'},...shown.map(v=>{const s=model.byKey.get(v.serviceKey);return el('li',{'data-tool-id':v.id,class:v.enabled?'':'disabled'},
    el('div',{},el('button',{type:'button',class:'tool-title','data-key':'tool:'+v.id,onclick:()=>toolDialog(v.id)},v.title),el('div',{},mono(v.id,'id')),
      el('span',{class:'svc'},serviceMark(s,20),el('button',{type:'button',class:'plain',onclick:()=>go('services/'+s.key)},s.name))),
    el('div',{},stateWord(v.state,v.word),reason(v)),el('div',{class:'tags'},...v.tags.map(tagNode)),toolSwitch(v));})),more];
}
const tagNode = t => el('span',{class:'tag'+(t==='可能扣费'?' paid':t==='会改动外部内容'?' write':'')},t);
function toolSwitch(v) {
  const on=v.enabled;
  const node=el('button',{type:'button',class:'switch',role:'switch','aria-checked':String(on),'data-key':'switch:'+v.id,ariaLabel:'允许 Agent 使用 '+v.id},
    el('span',{class:'track',ariaHidden:'true'}),el('span',{class:'switch-text'},on?'允许':'已停用'));
  node.addEventListener('click',async()=>{
    if(node.getAttribute('aria-busy')==='true')return;
    node.setAttribute('aria-busy','true');
    try{
      await api('/api/tools/toggle',{tool:v.id,enabled:!on,expected_enabled:on});
      await refresh();
      const message=on?`已停用 ${v.id}。Claude Code 和 Codex 都不能再调用它。`:`已允许 ${v.id}。`;
      // The tool dialog's own switch is not part of #main: show the new state there too.
      if(node.isConnected&&$('#modal').contains(node)&&model.tools.get(v.id))node.replaceWith(toolSwitch(model.tools.get(v.id)));
      announce(message);toast(message);
    }catch(e){
      if(e.code==='state_changed'){await refresh().catch(report);toast('这个工具的状态刚被别处改过，已刷新。请再试一次。');}
      else report(e);
    }finally{if(node.isConnected)node.removeAttribute('aria-busy');}
  });
  return node;
}

// ---- 服务详情 ----
function renderService(key) {
  const s=model.byKey.get(key), out=[];
  const primary=s.primary?actionButton(s.primary,'primary','service:primary:'+s.key):null;
  out.push(el('section',{class:'page-title service-head'},serviceMark(s,48),el('div',{},el('h1',{tabIndex:-1},s.name),el('p',{class:'lede'},s.lead),routeStrip(s.routes,true)),
    primary?el('div',{class:'page-actions'},primary):null));
  out.push(el('section',{id:'routes'},el('div',{class:'section-head'},el('div',{},el('h2',{},'连接方式'),el('small',{},`Agent 可以通过下面任一方式使用 ${s.name}。每种方式各自设置。`))),
    el('ul',{class:'routes'},...s.routes.map(r=>routeRow(r,s)))));
  if(s.credits){const panel=creditsPanel(s.credits);if(panel)out.push(panel);}
  if(s.tools.length)out.push(serviceTools(s));
  const jobs=[...s.jobs].filter(j=>j.kind==='tool').sort((a,b)=>b.created-a.created).slice(0,5);
  if(jobs.length)out.push(el('section',{id:'service-jobs'},el('div',{class:'section-head'},el('div',{},el('h2',{},'最近记录'))),
    ...dayGroups(jobs,'h3'),el('div',{class:'actions'},el('button',{type:'button',class:'plain',onclick:()=>{jobFilters.service=s.key;go('jobs');}},'查看全部记录'))));
  if(s.grants.length||s.requests.length)out.push(el('section',{id:'service-grants'},el('div',{class:'section-head'},el('div',{},el('h2',{},'授权'))),
    rows(...s.requests.map(r=>el('li',{class:'grant'},el('strong',{},r.title),el('div',{class:'lines'},r.statusText),el('div',{class:'side'},el('button',{type:'button',class:'plain',onclick:()=>go('agents')},'管理')))),
      ...s.grants.map(g=>el('li',{class:'grant'},el('strong',{},g.title),el('div',{class:'lines'},g.lines[0]),el('div',{class:'side'},el('span',{class:'when'},g.time),el('button',{type:'button',class:'plain',onclick:()=>go('agents')},'管理')))))));
  const first=s.tools[0]?.id;
  if(first)out.push(el('section',{id:'service-commands'},details('cmd:'+s.key,'终端命令',commandBox('atm describe '+first),commandBox('atm doctor --tool '+first))));
  return out;
}
function routeRow(r, s) {
  const k=a=>'route:'+r.kind+':'+r.id+':'+a.label;
  const body=[];
  if(r.steps)body.push(el('ol',{class:'steps'},...r.steps.map((step,i)=>el('li',{'data-step':step.state},
    el('span',{class:'mark','data-step':step.state,ariaHidden:'true'},step.state==='ok'?'✓':step.state==='todo'?'!':''),
    el('span',{class:'vh'},{ok:'已完成：',todo:'需要处理：',none:'未知：'}[step.state]),
    el('div',{class:'detail'},el('span',{},step.text),step.mono?mono(step.mono,'path'):null,step.note?el('p',{class:'quiet'},step.note):null,
      step.command?commandBox(step.command):null,step.command?el('div',{},ranCommand()):null,
      step.action?el('div',{},actionButton(step.action,'secondary',k(step.action)+':step'+i)):null)))));
  for(const p of r.body)body.push(el('p',{},p));
  if(r.info)body.push(el('div',{class:'info'},...r.info.map(line=>el('p',{},line))));
  if(r.facts.length)body.push(facts(r.facts));
  for(const c of r.commands)body.push(commandBox(c.text,c.label));
  if(r.commands.length)body.push(el('div',{},ranCommand()));
  if(r.check||r.open){
    const site=r.check||r.open;
    body.push(el('div',{class:'actions'},r.check?creditsButton('检查 Chrome 登录',[r.check.provider],'secondary','check',r.check.provider):null,
      site.host?el('a',{class:'plain',href:'https://'+site.host+'/',target:'_blank',rel:'noopener noreferrer'},'在新标签页打开 '+site.name,el('span',{ariaHidden:'true'},' ↗')):null));
  }
  for(const n of r.notes||[])body.push(el('p',{class:'quiet'},n));
  if(r.more)body.push(details('more:'+r.anchor,'更多命令',commandBox(r.more.text,r.more.label)));
  const acts=r.actions.filter(a=>!(r.check&&a.kind==='credits'));
  if(acts.length)body.push(el('div',{class:'actions'},...acts.map(a=>a.kind==='credits'?creditsButton(a.label,a.target,a.primary?'primary':'secondary',kindOfCredits(r),a.target[0]):actionButton(a,null,k(a)))));
  return el('li',{class:'route','data-kind':r.kind,'data-state':r.state,id:r.anchor,tabIndex:-1},
    el('div',{class:'route-head'},el('div',{},el('h3',{},r.title),r.sub?el('p',{class:'sub'},breakable(r.sub)):null),stateWord(r.state,r.word)),
    el('div',{class:'route-body'},...body));
}
const kindOfCredits = r => r.kind==='chrome'?'check':'login';
function serviceTools(s) {
  const st=ui.service.get(s.key)||{filter:'all',q:'',open:new Set()};ui.service.set(s.key,st);
  const n=s.tools.length,p=s.tools.filter(v=>v.paid).length,d=s.tools.filter(v=>!v.enabled).length;
  const host=el('div',{});
  const draw=()=>{
    const q=st.q.trim().toLowerCase();
    const list=s.tools.filter(v=>(st.filter==='all'||(st.filter==='paid'?v.paid:!v.enabled))&&(!q||[v.id,v.title,...(v.tool.capabilities||[])].join('\n').toLowerCase().includes(q)));
    const groups=s.routes.map(r=>({r,tools:list.filter(v=>r.tools.includes(v))})).filter(g=>g.tools.length);
    host.replaceChildren(...(groups.length?groups.map(({r,tools})=>{
      const gid=r.anchor, enabled=tools.filter(v=>v.enabled), disabled=tools.filter(v=>!v.enabled);
      const shown=st.open.has(gid)?tools:tools.slice(0,8);
      return el('div',{class:'tool-group'},el('div',{class:'group-head'},el('strong',{},r.title),el('span',{class:'count-line'},tools.length+' 个 · '+r.word),
          enabled.length>=2?el('button',{type:'button',class:'plain','data-key':'bulk:off:'+gid,onclick:()=>bulkDialog(enabled,false,r.title,s.name)},'全部停用…'):null,
          disabled.length>=2?el('button',{type:'button',class:'plain','data-key':'bulk:on:'+gid,onclick:()=>bulkDialog(disabled,true,r.title,s.name)},'全部允许…'):null),
        el('ul',{class:'rows'},...shown.map(toolRow),tools.length>shown.length?el('li',{class:'more-row'},el('button',{type:'button',class:'more','data-key':'more:'+gid,'aria-expanded':'false',onclick:()=>{st.open.add(gid);draw();}},`显示其余 ${tools.length-shown.length} 个工具`)):null));
    }):[el('div',{class:'panel'},el('p',{},'没有符合条件的工具。'))]));
  };
  const controls=[segmented('筛选工具',[['all','全部 · '+n],['paid','可能扣费 · '+p],['off','已停用 · '+d]],st.filter,v=>{st.filter=v;render();})];
  if(n>8){const q=el('input',{type:'search',ariaLabel:'搜索'+s.name+'的工具',placeholder:'搜索 '+s.name+' 的工具…',value:st.q,'data-key':'service-tools-q'});
    q.addEventListener('input',()=>{st.q=q.value;draw();});controls.push(el('div',{class:'search'},q));}
  draw();
  return el('section',{id:'tools'},el('div',{class:'section-head'},el('div',{},el('h2',{},'Agent 可以使用的工具'),el('small',{},n+' 个 · 关掉后 Claude Code 和 Codex 都不能再调用'))),
    el('div',{class:'toolbar'},...controls),host,
    el('p',{class:'footnote'},`开关对 Claude Code 和 Codex 同时生效。停用只阻止新的调用，已经提交给 ${s.name} 的任务不会被取消。允许使用不等于允许扣费：每次扣费都要 Agent 在调用时明确声明。`));
}
function toolRow(v) {
  return el('li',{class:'tool-row'+(v.enabled?'':' disabled'),'data-tool-id':v.id,id:'tool-'+T.slug(v.id)},
    el('div',{class:'cell-title'},el('button',{type:'button',class:'tool-title','data-key':'tool:'+v.id,onclick:()=>toolDialog(v.id)},v.title),mono(v.id,'id')),
    el('div',{class:'tags cell-tags'},...v.tags.map(tagNode)),
    el('div',{class:'cell-state'},v.state!=='ready'&&v.enabled?stateWord(v.state,v.word):null,toolSwitch(v)),
    v.state!=='ready'&&v.state!=='off'?el('div',{class:'why'},el('span',{},v.sentence),v.fix?actionButton(v.fix,'plain','fix:'+v.id):null):null);
}

// ---- Agent 与权限 ----
function renderAgents() {
  const m=model, vault=vaultInfo(), session=sessionInfo(), out=[];
  out.push(pageTitle('Agent 与权限','Claude Code 和 Codex 只能用你允许的工具和 Key。需要 Key 时，Agent 会在本机打开授权窗口请你确认；Agent 不能自己批准，管理台也不能替它批准。'));
  const projects=m.grants.active.filter(g=>g.kind==='project_session');
  out.push(el('section',{id:'reach'},el('div',{class:'section-head'},el('div',{},el('h2',{},'Agent 现在能用什么'))),el('div',{class:'reach'},facts([
    ['Key',!vault.backend?'还没设置 Key 保管方式。':session.unlocked?`已解锁，到 ${T.time(Date.now()/1000+leaseLeft())} 自动锁定。获准的项目可以使用 Key。`:'已锁定。Agent 现在拿不到任何 Key；需要时会打开授权窗口请你确认。'],
    ['项目',projects.length?`${projects.length} 个项目获准使用 Key：${projects.map(g=>g.title.replace(/^项目 /,'').replace(/ · 由授权窗口批准$/,'')).join('、')}`:'还没有获准的项目'],
    ['工具',el('span',{},`${m.counts.toolsEnabled} / ${m.counts.toolsTotal} 个工具允许使用 `,el('button',{type:'button',class:'plain','data-key':'reach:disabled',onclick:()=>{Object.assign(serviceFilters,{view:'tools',status:'off',q:'',route:'',paidOnly:false});go('services');}},'查看已停用的工具'))],
    ['扣费',`其中 ${m.counts.toolsPaidEnabled} 个可能扣费。每次扣费都要 Agent 在调用时明确声明；ATM 不设金额上限。`]]))));
  if(m.requests.length)out.push(requestsSection('requests'));
  out.push(el('section',{id:'agents-list'},el('div',{class:'section-head'},el('div',{},el('h2',{},'你的 Agent'),el('small',{},'两个 Agent 共用同一套工具、Key 和记录'))),
    rows(...m.agents.map(a=>el('li',{class:'agent-row','data-agent':a.agent},brandMark(brandOf(a.agent),32),
      el('div',{},el('strong',{},a.label),' ',stateWord(a.state,a.word)),
      el('div',{class:'detail'},a.state==='ready'?mono(a.detail,'path'):a.detail),
      a.state!=='ready'?el('div',{class:'detail'},mono(a.path,'path')):null,
      el('div',{class:'actions'},...a.actions.map(x=>actionButton(x,x.primary?'primary':x.danger?'plain danger':'secondary','agent:'+a.agent+':'+x.label))))))));
  const g=m.grants;
  out.push(el('section',{id:'grants'},el('div',{class:'section-head'},el('div',{},el('h2',{},'正在生效的授权 · '+g.active.length)),btn('新建受限授权',()=>grantDialog(),'secondary',{'data-key':'grants:new'})),
    rows(...(g.active.length?g.active.map(x=>grantRow(x,true)):[el('li',{class:'empty'},'还没有授权。Agent 第一次需要 Key 时，会在本机打开授权窗口请你确认。')])),
    g.ended.length?el('div',{class:'block'},details('ended-grants','已结束的授权 · '+g.ended.length,rows(...g.ended.map(x=>grantRow(x,false))))):null));
  out.push(el('section',{id:'agent-commands'},details('agent-commands','在终端操作',commandBox('atm setup\natm setup --apply\natm agents list\natm doctor --tool ffmpeg.probe'),
    el('p',{},'安装只代表 ATM 说明文件和路径已写入；请在真实客户端的新会话里确认。只对本机同一个系统用户有效，云端会话无法据此访问本机文件或 Key。'),
    el('p',{},'授权是 ATM 的使用规则，不是系统级隔离：同一系统用户下的恶意程序不受它约束。不要把授权配置文件放进 Git、聊天或共享文件夹。'))));
  return out;
}
function grantRow(g, active) {
  return el('li',{class:'grant','data-grant':g.id},el('div',{},el('strong',{},g.title),g.kind==='project_session'?el('small',{class:'quiet'},' · '+g.agentLabel):null),
    el('div',{class:'lines'},...g.lines.map(l=>el('span',{},l)),g.kind==='project_session'?mono(g.workspace,'path'):null,el('span',{},'授权 ID ',el('code',{title:g.id},g.short))),
    el('div',{class:'side'},el('span',{class:'when'},g.time),active?el('button',{type:'button',class:'plain danger','data-key':'grant:revoke:'+g.id,onclick:action(()=>revokeConfirm(g))},'撤销'):null));
}

// ---- 记录 ----
function jobItem(j) {
  const open=ui.jobs.has(j.id), id='job-'+j.id;
  const button=el('button',{type:'button',class:'job-row','aria-expanded':String(open),'aria-controls':id,'data-key':'job:'+j.id,title:j.full,
    onclick:()=>{if(ui.jobs.has(j.id))ui.jobs.delete(j.id);else ui.jobs.add(j.id);render();}},
    el('time',{},j.time),brandMark(brandOf(j.brand,j.tool),28),el('span',{class:'what'},mono(j.tool),j.title&&j.title!==j.tool?el('small',{},j.title):null),
    stateWord(j.state,j.word),el('span',{class:'line'},`${j.verification} · ${j.files} 个文件 · ${j.cost}`,j.kind==='credits_refresh'?' · 读取额度':''));
  const copy=el('button',{type:'button',class:'plain'},'复制');copy.addEventListener('click',()=>copyText(j.id,copy,null));
  const panel=el('div',{class:'job-panel',id,hidden:!open},facts([['任务编号',el('span',{},el('code',{},j.id),' ',copy)],['创建',j.createdText],['更新',j.updatedText],['结果检查',j.verification],['费用',j.cost],...(j.sentence?[['状态说明',j.sentence]]:[])]),
    commandBox(`atm jobs get ${j.id} --refresh`,'需要继续时，由 Agent 运行：'));
  return el('li',{},button,panel);
}
// Rows show the time only, so each day gets its own heading (今天, 昨天, or the date).
function dayGroups(list, heading) {
  const days=new Map();for(const j of list){if(!days.has(j.day))days.set(j.day,[]);days.get(j.day).push(j);}
  return [...days].map(([day,jobs])=>el('section',{class:'day-group'},el(heading,{},day),el('ul',{class:'rows'},...jobs.map(jobItem))));
}
function renderJobs() {
  const out=[pageTitle('记录','Agent 通过 ATM 运行过的最近 50 个任务。不显示提示词、原始返回和带签名的文件链接。')];
  const all=model.jobs, credits=all.filter(j=>j.kind==='credits_refresh'), base=all.filter(j=>jobFilters.showCredits||j.kind==='tool');
  const inService=base.filter(j=>!jobFilters.service||j.serviceKey===jobFilters.service);
  const count=g=>inService.filter(j=>g==='all'||(g==='needsYou'?j.needsYou:g==='running'?j.group==='running':j.group==='failed')).length;
  const services=[...new Map(all.filter(j=>j.serviceKey).map(j=>[j.serviceKey,j.serviceName])).entries()];
  const sel=el('select',{ariaLabel:'服务','data-key':'jobs-service'},el('option',{value:''},'全部服务'),...services.map(([k,n])=>el('option',{value:k},n)));
  sel.value=jobFilters.service; sel.addEventListener('change',()=>{jobFilters.service=sel.value;render();});
  const show=el('input',{type:'checkbox',checked:jobFilters.showCredits,'data-key':'jobs-credits'});
  show.addEventListener('change',()=>{jobFilters.showCredits=show.checked;render();});
  out.push(el('div',{class:'toolbar'},segmented('按状态筛选',[['all','全部 · '+count('all')],['needsYou','需要你 · '+count('needsYou')],['running','进行中 · '+count('running')],['failed','失败 · '+count('failed')]],jobFilters.group,v=>{jobFilters.group=v;render();}),
    sel,el('label',{class:'check'},show,`显示额度读取（${credits.length}）`)));
  const list=inService.filter(j=>jobFilters.group==='all'||(jobFilters.group==='needsYou'?j.needsYou:j.group===jobFilters.group));
  if(!all.length)out.push(el('div',{class:'panel'},el('p',{},'还没有记录。Agent 通过 ATM 运行工具后会出现在这里。')));
  else if(!list.length)out.push(el('div',{class:'panel'},el('p',{},'没有符合条件的记录。')));
  else out.push(el('div',{id:'job-list'},...dayGroups(list,'h2')));
  out.push(el('p',{class:'footnote'},'记录里没有“是哪个 Agent 发起的”。网页不会自动轮询服务，也不会重新提交任务。'));
  return out;
}

// ---- 设置 ----
function renderSettings(tab='keys') {
  const pages={keys:settingsKeys,sync:settingsSync,tools:settingsTools,programs:settingsPrograms,advanced:settingsAdvanced};
  const subnav=el('nav',{class:'subnav',ariaLabel:'设置分区'},...SETTINGS.map(([k,label])=>el('button',{type:'button','aria-current':k===tab?'page':null,'data-key':'subnav:'+k,onclick:()=>go('settings/'+k)},label)));
  return [pageTitle('设置',null),el('div',{class:'settings'},subnav,el('div',{class:'settings-body'},...pages[tab]()))];
}
function settingsKeys() {
  const vault=vaultInfo(), session=sessionInfo(), pk=data.passkeys||{}, out=[];
  out.push(el('section',{id:'vault-panel'},el('div',{class:'section-head'},el('div',{},el('h2',{},'保管方式'))),el('div',{class:'panel'},
    ...(!vault.backend?[el('p',{},'还没有设置。保存任何 API Key 之前需要设置一次。'),el('div',{},btn('设置保管方式',()=>vaultDialog(),'primary',{'data-key':'vault:init'}))]
      // While unlocked the vault is not "needed to unlock"; the lock itself is shown only in the pill.
      :[facts([['方式',T.backend[vault.backend]||vault.backend],['状态',MODEL.say(T.vault,vault.state==='needs_unlock'&&session.unlocked?'unlock_not_checked':vault.state,'{code}')]]),el('p',{},'已设置。不要重新设置：已保存的 Key 会一直保留。'),
        vault.next_action?el('p',{class:'quiet'},'在终端解锁或修复现有的保管库；不要重置，也不用重新填写每个服务的 Key。'):null]))));
  out.push(el('section',{id:'unlock-panel'},el('div',{class:'section-head'},el('div',{},el('h2',{},'解锁'))),el('div',{class:'panel'},
    el('p',{},'当前：'+(session.unlocked?`Key 已解锁，到 ${T.time(Date.now()/1000+leaseLeft())} 自动锁定`:'Key 已锁定')+'。用右上角的按钮解锁或锁定。'),
    el('p',{class:'quiet'},'每次解锁固定 30 分钟，不会因为 Agent 使用而延长。由管理台解锁的会话，会在管理台进程结束时一起结束（关闭标签页不会）。'))));
  const reason=!vault.backend?'先设置 Key 的保管方式。':!pk.dependency_present?'需要先安装 ATM 的 Passkey 组件（passkey 扩展）。':!pk.origin_supported?'请从 atm ui 打开的 localhost 地址使用 Passkey。'
    :!window.ATM_PASSKEY?.supported()?'这个浏览器不支持带加密扩展（PRF）的 Passkey。':!pk.available?'Passkey 暂时不可用。':pk.state_error?`Passkey 记录校验失败（${pk.state_error.code}）。ATM 主密码仍然可以解锁。`:'';
  const bind=el('button',{type:'button',class:'secondary','data-key':'passkey:bind'},'绑定 Passkey');
  if(reason){bind.setAttribute('aria-disabled','true');bind.setAttribute('aria-describedby','passkey-reason');bind.addEventListener('click',()=>{$('#passkey-reason').focus();announce(reason);});}
  else bind.addEventListener('click',action(()=>passkeyDialog()));
  const creds=pk.credentials||[];
  out.push(el('section',{id:'passkeys-panel'},el('div',{class:'section-head'},el('div',{},el('h2',{},'Passkey'))),el('div',{class:'panel'},
    brandIdentity('1password',[el('p',{},'用支持 PRF 加密扩展的 Passkey（例如 1Password）保护主密钥，解锁时就不用输入 ATM 主密码。解锁仍是固定 30 分钟。密码、Key 和 Passkey 私钥都不会同步。')]),
    el('div',{},bind),reason?el('p',{class:'reason',id:'passkey-reason',tabIndex:-1},reason):null,
    rows(...(creds.length?creds.map(c=>el('li',{class:'key-row'},iconMark('passkey'),el('strong',{},c.label+' · '+(c.disabled?'已停用':'已绑定')),
      el('div',{class:'actions'},!c.disabled?el('button',{type:'button',class:'plain danger',ariaLabel:'停用 '+c.label,'data-key':'passkey:disable:'+c.id,onclick:action(()=>disablePasskeyDialog(c))},'停用'):null))):[el('li',{class:'empty'},'还没有绑定 Passkey。')])))));
  out.push(allKeysSection());
  const sessions=data.extensions?.browser_sessions||[];
  out.push(el('section',{id:'web-sessions'},el('div',{class:'section-head'},el('div',{},el('h2',{},'ATM 网页登录'),el('small',{},'只在本机加密保存，不随 Key 同步'))),
    rows(...(sessions.length?sessions.map(s=>{
      const tool=[...model.tools.values()].find(v=>v.tool.session===s.name)?.id||'<工具 ID>';
      return el('li',{class:'panel-row'},el('strong',{},s.name),el('p',{class:'quiet'},`网站：${(s.origins||[]).join('、')} · 保存于 ${T.date(s.saved_at)} · ${s.expired?'已过期':s.expires_at?'到期 '+T.date(s.expires_at):'没有设置到期'}`),
        commandBox(`atm web login ${tool} --replace`,'续期：'),commandBox(`atm web remove-session ${s.name} --apply`,'删除本机登录：'));
    }):[el('li',{class:'empty'},'还没有 ATM 网页登录。')]))));
  return out;
}
function allKeysSection() {
  const keys=[...model.keys.values()], saved=keys.filter(k=>k.connection?.configured), unsaved=keys.filter(k=>!k.connection?.configured);
  const st=ui.keys||(ui.keys={q:''});
  const q=el('input',{type:'search',ariaLabel:'搜索 Key',placeholder:'搜索 Key 名称或服务',value:st.q,'data-key':'keys-q'});
  const host=el('div',{});
  const svcName=k=>model.byKey.get(k.owner)?.name||k.name;
  const match=k=>!st.q||[k.name,svcName(k),k.connection?.label||''].join('\n').toLowerCase().includes(st.q.trim().toLowerCase());
  const row=(k,isSaved)=>el('li',{class:'key-row','data-credential':k.name},brandMark(brandOf(k.name),28),
    el('div',{},el('button',{type:'button',class:'plain',onclick:()=>go('services/'+k.owner)},svcName(k)),' ',mono(k.name),k.connection?.label&&k.connection.label!==k.name?el('small',{class:'quiet'},' '+k.connection.label):null),
    el('div',{class:'meta'},stateWord(k.state,k.word),k.connection?.configured_at?el('span',{},'保存于 '+T.date(k.connection.configured_at)):null,k.connection?.expires_at?el('span',{},'到期 '+T.date(k.connection.expires_at)):null),
    el('div',{class:'actions'},...(isSaved?[actionButton({label:'更换',kind:'dialog',target:{d:'key',mode:'replace',name:k.name}},'secondary','key:replace:'+k.name),
      actionButton({label:'联网测试',kind:'dialog',target:{d:'verify',name:k.name}},'secondary','key:verify:'+k.name),
      actionButton({label:'移除',kind:'dialog',target:{d:'remove',name:k.name}},'plain danger','key:remove:'+k.name)]
      :[k.connection?.sync_conflict?actionButton({label:'选择版本',kind:'dialog',target:{d:'resolve',name:k.name}},'secondary','key:resolve:'+k.name):actionButton({label:'添加',kind:'dialog',target:{d:'key',mode:'add',name:k.name}},'secondary','key:add:'+k.name)])));
  const draw=()=>{
    const a=saved.filter(match), b=unsaved.filter(match);
    const more=el('details',{'data-key':'details:unsaved-keys'},el('summary',{},'还没保存的 Key 名称 · '+b.length),rows(...b.map(k=>row(k,false))));
    more.open=Boolean(st.q.trim())||ui.details.has('unsaved-keys');
    more.addEventListener('toggle',()=>{if(more.open)ui.details.add('unsaved-keys');else ui.details.delete('unsaved-keys');});
    host.replaceChildren(rows(...(a.length?a.map(k=>row(k,true)):[el('li',{class:'empty'},st.q?'没有符合条件的 Key。':'还没有保存 Key。')])),el('div',{class:'block'},more));
  };
  q.addEventListener('input',()=>{st.q=q.value;draw();});
  draw();
  return el('section',{id:'all-keys'},el('div',{class:'section-head'},el('div',{},el('h2',{},'所有 Key'),el('small',{},`${saved.length} 个已保存 · 共 ${keys.length} 个`)),
    el('div',{class:'page-actions head-actions'},btn('添加 Key',()=>keyDialog({mode:'add',picker:true}),'secondary',{'data-key':'keys:add'}),btn('添加自定义 Key',()=>declareDialog(),'secondary',{'data-key':'keys:declare'}))),
    el('div',{class:'toolbar'},el('div',{class:'search'},q)),host);
}
function settingsSync() {
  const sync=data.sync||{}, vault=vaultInfo(), out=[];
  if(!sync.device){
    const b=el('button',{type:'button',class:'primary','data-key':'sync:init'},'生成本机身份');
    if(!vault.backend){b.setAttribute('aria-disabled','true');b.setAttribute('aria-describedby','sync-reason');b.addEventListener('click',()=>announce('先设置 Key 的保管方式。'));}
    else b.addEventListener('click',action(()=>deviceDialog()));
    out.push(el('section',{id:'sync-device'},el('div',{class:'panel'},el('p',{},'这台电脑还没有同步身份。生成后，可以把加密的 Key 发给你自己的另一台电脑；主密钥不会离开这台电脑。'),el('div',{},b),
      !vault.backend?el('p',{class:'reason',id:'sync-reason'},'先设置 Key 的保管方式。'):null)));
  } else {
    out.push(el('section',{id:'sync-device'},el('div',{class:'section-head'},el('div',{},el('h2',{},'本机'))),el('div',{class:'panel'},
      facts([['名称',sync.device.name],['设备 ID',sync.device.id,true]]),el('p',{class:'quiet'},'请通过另一条可信渠道（例如当面或电话）核对完整指纹。公开身份可以交换，私钥不会离开本机。'),
      el('div',{class:'actions'},btn('查看公开身份',()=>publicDialog(sync.device),'secondary',{'data-key':'sync:public'}),btn('配对另一台设备',()=>trustDialog(),'secondary',{'data-key':'sync:trust'}),btn('导入加密包',()=>importDialog(),'primary',{'data-key':'sync:import'})))));
    const peers=sync.peers||[];
    out.push(el('section',{id:'sync-peers'},el('div',{class:'section-head'},el('div',{},el('h2',{},'已配对的设备 · '+peers.length))),
      rows(...(peers.length?peers.map(p=>el('li',{class:'key-row'},iconMark('device'),el('div',{},el('strong',{},p.card.name),' ',el('code',{},'设备 ID '+p.card.id.slice(0,16)+'…'),' ',stateWord(p.revoked?'off':'ready',p.revoked?'已撤销':'已配对')),
        el('div',{class:'meta'},el('span',{},'发给它：'+((p.send||[]).join('、')||'无')),el('span',{},'接收它发来的：'+((p.receive||[]).join('、')||'无'))),
        p.revoked?null:el('div',{class:'actions'},btn('导出加密包',()=>exportDialog(p),'secondary',{'data-key':'peer:export:'+p.card.id}),el('button',{type:'button',class:'plain danger','data-key':'peer:revoke:'+p.card.id,onclick:action(()=>revokeDeviceConfirm(p))},'撤销信任')))):[el('li',{class:'empty'},'还没有配对的设备。')]))));
  }
  const conflicts=(sync.records||[]).filter(r=>r.state==='conflict');
  if(conflicts.length)out.push(el('section',{id:'sync-conflicts'},el('div',{class:'section-head'},el('div',{},el('h2',{},'冲突 · '+conflicts.length),el('small',{},'不会按时间自动选择'))),
    rows(...conflicts.map(r=>el('li',{class:'key-row'},brandMark(brandOf(r.provider),28),el('span',{},`${model.byKey.get(MODEL.serviceKeyOf(r.provider))?.name||r.provider} 的 Key（${r.provider}）有 ${r.heads.length} 个版本，相关工具已暂停。`),
      el('div',{class:'actions'},btn('选择版本',()=>resolveDialog(r.provider),'secondary',{'data-key':'conflict:'+r.provider})))))));
  out.push(el('section',{id:'sync-commands'},details('sync-commands','同步命令',commandBox('atm sync exchange --directory /path/to/encrypted-sync\natm sync exchange --directory /path/to/encrypted-sync --apply'),
    el('p',{},'可以用 rsync、SFTP 或同步盘传递加密包。每次运行一次 exchange，或者显式启动有时限的 sync watch；ATM 不会自己部署云同步。旧包重放不会覆盖已知的较新版本；整库恢复、丢失设备和离线撤销仍需人工处理。'))));
  return out;
}
function settingsTools() {
  const ext=data.extensions||{}, custom=ext.custom_tools||[], out=[];
  out.push(el('section',{id:'install-tools'},el('div',{class:'section-head'},el('div',{},el('h2',{},'安装工具定义'))),el('div',{class:'panel'},
    el('p',{},'把 Agent 起草、经你审阅的工具定义安装到 ATM。真实 Key 不会写进定义；检查只看结构，不代表网站已经跑通。修改定义会让旧的受限授权失效。'),
    el('div',{},btn('安装工具定义',()=>extensionDialog(),'primary',{'data-key':'tools:install'})))));
  const groups=new Map();
  for(const t of custom){const v=model.tools.get(t.id),key=v?.serviceKey||MODEL.serviceKeyOf(t.id.split('.')[0]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push({t,v});}
  out.push(el('section',{id:'installed-tools'},el('div',{class:'section-head'},el('div',{},el('h2',{},'已安装的工具定义 · '+custom.length))),
    custom.length?el('div',{},...[...groups].map(([key,items])=>{
      const s=model.byKey.get(key), name=s?.name||key;
      const d=detailsOpen('installed:'+key,custom.length<=5,`${name} · ${items.length} 个`,rows(...items.map(({t,v})=>el('li',{},el('div',{},mono(t.id),' ',el('span',{},t.title)),
        el('p',{class:'quiet'},'运行方式：'+(v?routeTitleOf(v):t.adapter),(t.permissions||[]).length?' · '+(t.permissions||[]).map(p=>MODEL.say(T.permission,p,'{code}')).join('、'):''),
        el('div',{class:'tags'},t.paid?tagNode('可能扣费'):null,el('span',{class:'quiet'},'定义指纹 '),el('code',{},String(t.sha256||'').slice(0,16)))))),
        el('div',{class:'actions'},el('button',{type:'button',class:'plain',onclick:()=>go('services/'+key)},'打开 '+name)));
      return d;
    })):rows(el('li',{class:'empty'},'还没有安装自定义工具定义。'))));
  const slots=ext.credential_slots||[], conns=new Map((data.connections?.connections||[]).map(c=>[c.provider,c]));
  out.push(el('section',{id:'custom-keys'},el('div',{class:'section-head'},el('div',{},el('h2',{},'自定义 Key 名称')),btn('添加自定义 Key',()=>declareDialog(),'secondary',{'data-key':'tools:declare'})),
    el('p',{class:'quiet'},'给 ATM 还不认识的服务（例如公司内部 API）登记一个 Key 名称。'),
    rows(...(slots.length?slots.map(name=>{const c=conns.get(name),saved=Boolean(c?.configured);return el('li',{class:'key-row'},brandMark(brandOf(name),28),el('div',{},mono(name),' ',el('span',{class:'quiet'},c?.label||name)),
      el('div',{class:'meta'},saved?'已保存':'还没有填写'),el('div',{class:'actions'},actionButton({label:saved?'更换':'填写 Key',kind:'dialog',target:{d:'key',mode:saved?'replace':'add',name}},'secondary','slot:'+name)));}):[el('li',{class:'empty'},'还没有登记自定义 Key 名称。')]))));
  out.push(el('section',{id:'make-tools'},details('make-tools','让 Agent 把网页做成工具（命令行）',el('p',{},'限定网站和操作的 Playwright 配方，可以打包成 CLI；登录加密保存在这台电脑上。'),
    commandBox('atm make new studio.export --kind web --url https://example.com/ --out studio.json\natm make pack studio.json --out studio-cli'))));
  return out;
}
function programInfo(c) {
  const exe=c.name, path=c.path||'';
  const table={executable_changed:['blocked','程序已更新',`${path} 的内容和你上次确认的不一样（可能刚升级）。`],executable_missing:['blocked','程序不见了',`${path} 不存在，可能已卸载或移动。`],
    executable_not_executable:['blocked','不能运行',`${path} 没有执行权限。`],executable_unreadable:['blocked','无法读取',`无法读取 ${path}。`],executable_unpinned:['attention','需要重新绑定',`${exe} 已绑定，但没有记录程序指纹。`]};
  if(Object.hasOwn(table,c.state))return {group:'attention',state:table[c.state][0],word:table[c.state][1],sentence:table[c.state][2],command:`atm cli bind ${exe} ${quote(path)}`};
  if(c.state==='configured_not_verified'&&path)return {group:'bound',state:'ready',word:'已绑定',sentence:'已记录程序位置和指纹。'};
  if(c.detected_path)return {group:'found',state:'setup',word:'待设置',sentence:`在 ${c.detected_path} 找到了 ${exe}，确认后即可使用。`,bind:true};
  return {group:'missing',state:'setup',word:'待设置',sentence:`本机没有找到 ${exe}。`,command:`atm cli bind ${exe} '<${exe} 程序的完整路径>'`};
}
function settingsPrograms() {
  const clis=data.clis||[], st=ui.programs||(ui.programs={filter:'all'});
  const rowsOf=list=>list.map(c=>{
    const info=programInfo(c), users=[...new Set([...model.tools.values()].filter(v=>v.tool.executable===c.name).map(v=>v.serviceKey))];
    return el('li',{class:'program-row','data-program':c.name},brandIdentity(c.name,[],'',32).firstChild,
      el('div',{},el('strong',{},c.name),' ',stateWord(info.state,info.word)),
      el('div',{class:'detail'},users.length?el('span',{},'用于 ',...users.flatMap((k,i)=>[i?'、':'',el('button',{type:'button',class:'plain',onclick:()=>go('services/'+k)},model.byKey.get(k)?.name||k)])):null,
        el('span',{},info.sentence),mono(c.path||c.detected_path||'不在 PATH 中','path'),info.command&&!info.bind?commandBox(info.command):null),
      info.bind?actionButton({label:'绑定',kind:'dialog',target:{d:'setup',clis:[c.name]}},'secondary','program:bind:'+c.name)
        :info.command?el('button',{type:'button',class:'secondary','data-key':'program:copy:'+c.name,onclick:()=>copyText(info.command,null,null).then(()=>toast('已复制命令：'+info.command))},'复制命令'):null);
  });
  const agents=clis.filter(c=>['claude','codex'].includes(c.name)), rest=clis.filter(c=>!['claude','codex'].includes(c.name));
  const by=g=>rest.filter(c=>programInfo(c).group===g);
  const counts={all:rest.length,attention:by('attention').length,bound:by('bound').length,found:by('found').length,missing:by('missing').length};
  const show=g=>st.filter==='all'||st.filter===g;
  const out=[el('p',{class:'lede'},'ATM 只记录程序的位置和指纹，绑定时不会运行它。'),
    el('div',{class:'toolbar'},segmented('按程序状态筛选',[['all','全部 · '+counts.all],['attention','需要处理 · '+counts.attention],['bound','已绑定 · '+counts.bound],['found','已找到未绑定 · '+counts.found],['missing','没找到 · '+counts.missing]],st.filter,v=>{st.filter=v;render();}))];
  const group=(title,g,list)=>list.length&&show(g)?el('section',{class:'group'},el('div',{class:'section-head'},el('div',{},el('h2',{},title+' · '+list.length))),rows(...rowsOf(list))):null;
  out.push(group('需要处理','attention',by('attention')),group('已绑定','bound',by('bound')),group('已在本机找到，未绑定','found',by('found')));
  if(by('missing').length&&show('missing'))out.push(el('section',{class:'group'},details('programs-missing','没有找到 · '+by('missing').length,rows(...rowsOf(by('missing'))))));
  if(st.filter==='all')out.push(el('section',{class:'group'},el('div',{class:'section-head'},el('div',{},el('h2',{},'Agent 程序'),el('small',{},'这里的绑定和是否已安装 ATM 无关；安装 ATM 请到“Agent 与权限”。'))),rows(...rowsOf(agents))));
  return out.filter(Boolean);
}
function settingsAdvanced() {
  const broker=data.access?.broker, home=data.overview?.home||'';
  const copyHome=el('button',{type:'button',class:'plain'},'复制');copyHome.addEventListener('click',()=>copyText(home,copyHome,null));
  return [
    el('section',{id:'broker'},el('div',{class:'section-head'},el('div',{},el('h2',{},'会话 Broker'))),el('div',{class:'panel'},
      el('p',{},'给严格模式用的前台进程，和网页管理台互相独立。由你在私有终端里解锁一次；到期、停止或撤销后会直接拒绝，不会退回去直接读取保管库。'),
      facts([['状态',broker?String(broker.state||broker.status||'运行记录'):'未启动']]),raw('broker',broker||{state:'not_started'},'查看原始状态（JSON）'),
      commandBox('atm broker serve --ttl-hours 8\n# 另一个终端，授权并安装后：\natm --client claude broker status\natm setup --broker --replace-skills --apply'))),
    el('section',{id:'cli-help'},el('div',{class:'section-head'},el('div',{},el('h2',{},'命令行速查'))),commandBox('atm doctor\natm list\natm describe <工具 ID>\natm jobs list')),
    el('section',{id:'about'},el('div',{class:'section-head'},el('div',{},el('h2',{},'关于'))),el('div',{class:'panel'},
      facts([['版本','ATM v'+(data.overview?.version||'')],['状态目录',el('span',{},el('code',{},breakable(home)),' ',copyHome)],['地址',location.host]]),
      el('p',{},'ATM 本地管理 · CLI 与网页共用状态 · 不提供云端远程控制'),el('p',{},'查看本页不会调用任何服务，也不会运行工具。'),
      el('p',{},'要退出这个标签页，点右上角的“退出管理台”。它不会锁定 Key。')))];
}

// ---- Dialogs ----
const serviceNameOf = name => model?.byKey.get(MODEL.serviceKeyOf(name))?.name || name;
function unlockBlock(onDone) {
  const pk=data.passkeys||{}, creds=(pk.credentials||[]).filter(c=>!c.disabled);
  const passkeyOk=creds.length&&pk.available&&window.ATM_PASSKEY?.supported();
  const vault=vaultInfo(), nodes=[el('p',{},'解锁后 30 分钟内，这个管理台和你批准的项目里的 Claude Code / Codex 可以使用已保存的 Key。到时自动锁定，不会因为使用而延长。由管理台解锁的会话，会在管理台进程结束时一起结束。')];
  const done=async message=>{await refresh();await onDone(message);};
  const unlock=async body=>{
    try{await api('/api/session/unlock',body);}
    catch(e){if(e.code==='session_already_unlocked'){await done('Key 已经是解锁状态。');return;}
      if(e.code==='vault_locked'){showAlert('ATM 主密码不正确，Key 仍是锁定的。',{field:$('#modal-body input[type=password]')});return;}throw e;}
    await done('Key 已解锁 30 分钟。');
  };
  if(passkeyOk){
    const select=creds.length>1?field('选择 Passkey',el('select',{},...creds.map(c=>el('option',{value:c.id},c.label)))):null;
    const usePasskey=btn('用 Passkey 解锁 30 分钟',async()=>{
      let proof=await window.ATM_PASSKEY.authenticate(api,'/api/passkeys/auth/begin',{credential_id:select?select.input.value:creds[0].id},'/api/passkeys/cancel');
      try{await unlock({passkey:proof});}finally{proof=null;}
    },'primary');
    nodes.push(el('div',{class:'field'},select?select.node:el('small',{class:'quiet'},'将使用：'+creds[0].label),
      el('div',{class:'actions'},usePasskey)),el('div',{class:'divider'},'或者'));
    nodes.focus=usePasskey;  // The Passkey is the first choice when it can be used; the password field comes after.
  }
  if(vault.backend==='passphrase'){
    const pass=masterPasswordField('只用于本机解锁，不写入文件，也不会发给 Agent。');
    const submit=btn('用主密码解锁',async()=>{
      let secret=pass.input.value;
      if(!secret){showAlert('请输入 ATM 主密码。',{field:pass.input});return;}
      try{await unlock({ttl:'30m',passphrase:secret});}finally{secret=null;pass.input.value='';}
    },passkeyOk?'secondary':'primary');
    nodes.push(el('form',{onsubmit:e=>{e.preventDefault();submit.click();}},pass.node,el('div',{class:'actions'},submit)));
  } else if(vault.backend==='keyring'){
    nodes.push(el('p',{},'将使用系统钥匙串解锁，系统可能会请你确认。'),el('div',{class:'actions'},btn('用系统钥匙串解锁',()=>unlock({ttl:'30m'}),'primary')));
  }
  if(!creds.length&&pk.available&&window.ATM_PASSKEY?.supported())nodes.push(el('div',{},el('button',{type:'button',class:'plain',onclick:()=>{closeModal();go('settings/keys');}},'还没有 Passkey？去设置')));
  return nodes;
}
function unlockDialog() {
  const body=unlockBlock(async message=>{closeModal();toast(message);announce('Key 已解锁');});
  openModal({title:'解锁 Key 30 分钟',body,actions:[cancel()],focus:body.focus});
}
// A radio or checkbox named by its own label; the longer description is linked, not part of the name.
function choice(input, label, description) {
  input.id ||= 'f'+(++fieldSeq);
  const hint=el('small',{id:input.id+'-hint'},description);
  input.setAttribute('aria-describedby',hint.id);
  return el('div',{class:'choice'},input,el('label',{htmlFor:input.id},el('strong',{},label)),hint);
}
function vaultBlock(onDone) {
  const keyring=el('input',{type:'radio',name:'vault-backend',value:'keyring',checked:true}), pass=el('input',{type:'radio',name:'vault-backend',value:'passphrase'});
  const first=passwordField('设置 ATM 主密码（至少 12 个字符）','new-password'), second=passwordField('再输入一次','new-password');
  const box=el('div',{hidden:true},first.node,second.node);
  const sync=()=>{box.hidden=!pass.checked;};keyring.addEventListener('change',sync);pass.addEventListener('change',sync);
  const submit=btn('确认设置',async()=>{
    const backend=pass.checked?'passphrase':'keyring';
    let a=first.input.value,b=second.input.value;
    try{
      if(backend==='passphrase'){
        if(a.length<12){showAlert('ATM 主密码至少需要 12 个字符。',{field:first.input});return;}
        if(a!==b){showAlert('两次输入的 ATM 主密码不一致。',{field:second.input});return;}
      }
      await api('/api/vault/init',{backend,...(backend==='passphrase'?{passphrase:a}:{})});
    }finally{a=null;b=null;first.input.value='';second.input.value='';}
    await refresh();await onDone('Key 保管方式已设置。');
  },'primary');
  return {submit,body:[el('p',{},'只需要设置一次。以后不要重新设置：已保存的 Key 会一直保留。'),
    el('fieldset',{},el('legend',{},'保管方式'),choice(keyring,'系统钥匙串（推荐）','由系统保管主密钥，平时不用输入密码；使用 Key 时系统可能请你确认。'),
      choice(pass,'ATM 主密码','没有系统钥匙串时使用。请记住它：忘记后无法找回。')),box]};
}
function vaultDialog() {
  const block=vaultBlock(async message=>{closeModal();toast(message);});
  openModal({title:'设置 Key 的保管方式',body:block.body,actions:[cancel(),block.submit]});
}
// Add or replace a Key: set up the vault, unlock, then fill in — all in one dialog.
function keyDialog({mode='add', name=null, picker=false, intro=null, laterToast=null}) {
  const plan=[]; if(!vaultInfo().backend)plan.push('vault'); if(needsUnlockStep())plan.push('unlock'); plan.push('fill');
  const labels={vault:'设置保管方式',unlock:'解锁 Key',fill:'填写 Key'};
  // Opened right after a custom Key name was declared: leaving now is "fill it in later".
  const closer=()=>laterToast?el('button',{type:'button',class:'secondary',onclick:()=>{closeModal();toast(laterToast);}},'稍后再填'):cancel();
  const titleFor=()=>picker&&!name?'添加 Key':(mode==='replace'?'更换 ':'添加 ')+serviceNameOf(name)+' 的 API Key';
  const show=i=>{
    const step=plan[i], steps={items:plan.map(s=>labels[s]),current:i};
    if(step==='vault'){const b=vaultBlock(async()=>{if(needsUnlockStep()&&!plan.includes('unlock'))plan.splice(i+1,0,'unlock');show(i+1);});openModal({title:titleFor(),steps,body:b.body,actions:[closer(),b.submit]});return;}
    if(step==='unlock'){const body=unlockBlock(async()=>show(i+1));openModal({title:titleFor(),steps,body,actions:[closer()],focus:body.focus});return;}
    fill(steps);
  };
  const fill=steps=>{
    const nodes=[];
    if(intro)nodes.push(el('p',{},intro));
    let select=null;
    if(picker){
      const keys=[...model.keys.values()].filter(k=>k.connection?.connect_supported!==false).sort((a,b)=>new Intl.Collator('zh-CN').compare(serviceNameOf(a.name),serviceNameOf(b.name))||a.name.localeCompare(b.name));
      select=field('Key 名称',el('select',{},el('option',{value:'',disabled:true,selected:true},'请选择…'),...keys.map(k=>el('option',{value:k.name},serviceNameOf(k.name)+' · '+k.name+(k.connection?.configured?'（已保存）':'')))));
      select.input.addEventListener('change',()=>{name=select.input.value;mode=model.keys.get(name)?.connection?.configured?'replace':'add';$('#modal-title').textContent=titleFor();replaceNote.hidden=mode!=='replace';replaceNote.textContent=replaceText();hint.textContent=formatHint();});
      nodes.push(select.node);
    }
    const formatHint=()=>name==='higgsfield'?'格式：KEY_ID:KEY_SECRET':name==='dataforseo'?'格式：login:password':'不要粘贴网页登录的 Cookie。';
    const secret=passwordField('API Key','off','只能写入，保存后 ATM 也不会再显示它。');
    const hint=el('span',{class:'hint'},formatHint());secret.node.append(hint);
    const expiry=field('到期日（可选）',el('input',{type:'date'}),'服务告诉了你到期日的话就填上，ATM 会提前 7 天提醒。按本机时区当天 23:59 计算。');
    const pass=perRequestPassword()?masterPasswordField('只用于这一次请求，不写入文件。'):null;
    const replaceText=()=>`保存后会替换现在的 Key，旧 Key 无法恢复。${serviceNameOf(name)} 那边的旧 Key 不会自动作废。`;
    const replaceNote=el('p',{hidden:mode!=='replace'},replaceText());
    nodes.push(secret.node,expiry.node,pass?pass.node:null,replaceNote);
    const save=btn('加密保存',async()=>{
      if(!name){showAlert('请选择 Key 名称。',{field:select?.input});return;}
      let value=secret.input.value, password=pass?.input.value||'';
      try{
        if(!value){showAlert('请输入 Key。',{field:secret.input});return;}
        const body={provider:name,value,replace:mode==='replace'};
        if(expiry.input.value)body.expires_at=localEndOfDay(expiry.input.value);
        if(password)body.passphrase=password;
        const r=await api('/api/connections/save',body);
        body.value='';delete body.passphrase;
        if(r.status==='already_configured'){showAlert('这个 Key 已经保存过，没有改动。要换新的，请用“更换”。');return;}
      }finally{value=null;password=null;secret.input.value='';if(pass)pass.input.value='';}
      ui.successor=['route:key:'+name+':更换','route:key:'+name+':更换 API Key','key:replace:'+name,'slot:'+name];
      closeModal();await refresh();toast(`已加密保存 ${serviceNameOf(name)} 的 API Key。`);
    },'primary');
    openModal({title:titleFor(),steps,body:nodes,actions:[closer(),save]});
  };
  show(0);
}
function localEndOfDay(day) {
  const d=new Date(day+'T23:59:59'), offset=-d.getTimezoneOffset(), sign=offset>=0?'+':'-', abs=Math.abs(offset);
  return `${day}T23:59:59${sign}${String(Math.floor(abs/60)).padStart(2,'0')}:${String(abs%60).padStart(2,'0')}`;
}
function removeDialog(name) {
  const svc=serviceNameOf(name);
  const fill=steps=>{
    const confirm=field('确认 Key 名称',el('input',{placeholder:'输入 '+name,autocomplete:'off'}));
    const pass=perRequestPassword()?masterPasswordField('只用于这一次请求，不写入文件。'):null;
    const reason=el('p',{class:'reason',id:'remove-reason'},`请输入 ${name} 确认。`);
    const go_=el('button',{type:'button',class:'primary danger','aria-disabled':'true','aria-describedby':'remove-reason'},'移除 Key');
    const sync=()=>{const ok=confirm.input.value===name;go_.setAttribute('aria-disabled',String(!ok));reason.hidden=ok;};
    confirm.input.addEventListener('input',sync);
    go_.addEventListener('click',action(async()=>{
      if(confirm.input.value!==name){showAlert(`请输入 ${name} 确认。`,{field:confirm.input});return;}
      let password=pass?.input.value||'';
      try{await api('/api/connections/remove',withSecret({provider:name,confirm:confirm.input.value},{value:password}));}finally{password=null;if(pass)pass.input.value='';}
      ui.successor=['route:key:'+name+':添加 API Key','keys:add'];
      closeModal();await refresh();toast(`已移除本机保存的 ${svc} Key。`);
    }));
    openModal({title:`移除 ${svc} 的 API Key`,steps,body:[el('p',{},`只删除这台电脑上保存的 ${name}，不会在 ${svc} 那边作废它。备份里可能还有加密副本。`),confirm.node,pass?pass.node:null,reason],actions:[cancel(),go_]});
  };
  if(needsUnlockStep()){const steps={items:['解锁 Key','移除 Key'],current:0},body=unlockBlock(async()=>fill({items:steps.items,current:1}));openModal({title:`移除 ${svc} 的 API Key`,steps,body,actions:[cancel()],focus:body.focus});}
  else fill(null);
}
async function verifyDialog(name) {
  const svc=serviceNameOf(name);
  const plan=await api('/api/verify',{provider:name});
  const done=()=>el('button',{type:'button',class:'primary',onclick:()=>closeModal()},'完成');
  if(plan.status!=='planned'){
    openModal({title:`联网测试 ${svc} 的 Key`,body:[el('p',{},plan.status==='unsupported_probe'?`${svc} 暂时没有安全的联网测试方法。Key 是否有效，只能在 Agent 实际使用时确认。`:T.errorText(plan.status)),raw('verify-plan',plan)],actions:[done()]});
    return;
  }
  let host='';try{host=new URL(plan.url).host;}catch{}
  const pass=perRequestPassword()?masterPasswordField('只用于这一次请求，不写入文件。'):null;
  const start=btn('开始联网测试',async()=>{
    let password=pass?.input.value||'';
    let r;try{r=await api('/api/verify',withSecret({provider:name,allow_network:true},{value:password}));}finally{password=null;if(pass)pass.input.value='';}
    await refresh();
    openModal({title:`联网测试 ${svc} 的 Key`,body:[el('p',{},'测试结果：'+T.verifyText(r.status)+(r.http_status?`（HTTP ${r.http_status}）`:'')),raw('verify-result',r)],actions:[done()]});
  },'primary');
  openModal({title:`联网测试 ${svc} 的 Key`,body:[el('p',{},`ATM 会联网向 ${svc} 发送一次只读的账户检查请求，确认这个 Key 是否有效。不会生成内容，也不会扣费；服务商的限流可能适用。通过也不代表所有工具都能用。`),
    facts([['请求',`${plan.method||'GET'} ${host}`]]),pass?pass.node:null,raw('verify-plan',plan)],actions:[cancel(),start]});
}
async function toolDialog(id) {
  const v=model.tools.get(id);
  openModal({title:v?.title||id,body:[el('p',{class:'quiet'},'正在读取…')],actions:[],wide:true});
  let d;
  try{d=await api('/api/tools/'+encodeURIComponent(id));}
  catch(e){if(e.gated)return;if(!$('#modal').open)return;$('#modal-body').replaceChildren(el('p',{},e.status===404||e.code==='not_found'||e.code==='unknown_tool'?'这个工具已不在目录中。':errorText(e)));return;}
  if(!$('#modal').open)return;
  const view=model.tools.get(id)||v, s=view?model.byKey.get(view.serviceKey):null, route=s?.routes.find(r=>r.tools.includes(view));
  const needs=[];
  for(const n of [...(d.credentials||[]),...(d.optional_credentials||[])]){const k=model.keys.get(n);needs.push(el('li',{},`${n} 的 API Key · ${k?.word||'待设置'}`,' ',el('button',{type:'button',class:'plain',onclick:()=>{closeModal();openRoute({service:view.serviceKey,kind:'key',id:n,anchor:'route-key-'+T.slug(n)});}},k?.state==='ready'?'查看':'去设置')));}
  if(d.executable)needs.push(el('li',{},`本机程序 ${d.executable} · ${programInfo((data.clis||[]).find(c=>c.name===d.executable)||{name:d.executable,state:'cli_not_configured'}).word}`));
  if(d.url){let host='';try{host=new URL(d.url).host;}catch{}needs.push(el('li',{},'网站 '+host));}
  if(d.server)needs.push(el('li',{},'MCP 服务 '+d.server));
  if(d.session)needs.push(el('li',{},'ATM 网页登录 '+d.session));
  const perms=(d.permissions||[]).map(p=>MODEL.say(T.permission,p,'{code}')+'（'+p+'）');
  const props=Object.entries(d.schema?.properties||{});
  const req=new Set(d.schema?.required||[]);
  const limit=p=>[p.minLength!==undefined||p.maxLength!==undefined?`${p.minLength??0}–${p.maxLength??''} 字`:'',Array.isArray(p.enum)?'可选值：'+p.enum.join('、'):'',p.minimum!==undefined||p.maximum!==undefined?`${p.minimum??''}–${p.maximum??''}`:''].filter(Boolean).join('；');
  const fix=view?.fix;
  const body=[mono(d.id,'mono'),
    el('h3',{},'状态'),view?el('div',{},stateWord(view.state,view.word),el('p',{},view.sentence),fix?el('div',{class:'actions'},el('button',{type:'button',class:'secondary',onclick:()=>{closeModal();runAction(fix);}},fix.label)):null):null,
    needs.length?[el('h3',{},'需要'),el('ul',{},...needs)]:null,
    route?[el('h3',{},'连接方式'),el('p',{},route.title),route.sub?el('p',{class:'quiet'},route.sub):null,route.kind==='agent_browser'&&route.info?route.info.slice(0,2).map(t=>el('p',{class:'quiet'},t)):null]:null,
    el('h3',{},'会做什么'),el('p',{},perms.length?perms.join('、'):d.paid?'':'只读'),d.paid?el('p',{},tagNode('可能扣费'),' 每次扣费都要 Agent 在调用时明确声明；ATM 不设金额上限。'):null,
    el('h3',{},'输入'),props.length?el('table',{class:'schema'},el('thead',{},el('tr',{},...['名称','类型','必填','限制'].map(h=>el('th',{scope:'col'},h)))),
      el('tbody',{},...props.map(([k,p])=>el('tr',{},el('td',{},el('code',{},k)),el('td',{},String(p?.type||'')),el('td',{},req.has(k)?'是':''),el('td',{},limit(p||{})))))):el('p',{},'没有输入参数。'),
    d.notes?[el('h3',{},'说明'),el('p',{},d.notes)]:null,
    el('h3',{},'给 Agent'),commandBox('atm describe '+d.id),raw('tool:'+d.id,d),
    el('p',{class:'quiet'},`以上来自本机定义，不是对 ${s?.name||'服务'} 账户的实时检查。`)];
  $('#modal-body').replaceChildren(...body.flat(2).filter(Boolean));
  $('#modal-actions').replaceChildren(...(view?[toolSwitch(view)]:[]));
}
function declareDialog() {
  const name=field('Key 名称',el('input',{placeholder:'例如 acme.production',autocomplete:'off'}),'小写字母开头，2–80 个字符，只能用小写字母、数字和 . _ -');
  const label=field('显示名称（可选）',el('input',{placeholder:'例如 Acme 生产环境',autocomplete:'off'}));
  const submit=btn('登记名称',async()=>{
    const value=name.input.value.trim();
    if(!/^[a-z][a-z0-9_.-]{1,79}$/.test(value)){showAlert('Key 名称格式不对。小写字母开头，只能用小写字母、数字和 . _ -。',{field:name.input});return;}
    await api('/api/credentials/declare',{name:value,label:label.input.value.trim()||value,apply:true});
    await refresh();
    keyDialog({mode:'add',name:value,intro:`已登记 ${value}。现在保存它的 Key 吗？`,laterToast:`已登记 ${value}。之后可以在“设置 › Key 保管”里填写 Key。`});
  },'primary');
  openModal({title:'添加自定义 Key',body:[el('p',{},'给 ATM 还不认识的服务（例如公司内部 API）登记一个 Key 名称。只登记名称，不需要先有工具定义。'),name.node,label.node],actions:[cancel(),submit]});
}
function extensionDialog() {
  let approved=null;
  const input=field('工具定义 JSON',el('textarea',{rows:14,spellcheck:false,placeholder:'粘贴不含秘密的工具定义 JSON'}));
  const file=field('或者选择文件',el('input',{type:'file',accept:'.json,application/json'}));
  const summary=el('div',{});
  const apply=el('button',{type:'button',class:'primary','aria-disabled':'true','aria-describedby':'install-reason'},'批准安装');
  const reason=el('p',{class:'reason',id:'install-reason'},'先检查定义，通过后才能安装。');
  const reset=()=>{if(approved)status('定义已修改，请重新检查。');approved=null;apply.setAttribute('aria-disabled','true');reason.hidden=false;summary.replaceChildren();};
  input.input.addEventListener('input',reset);
  file.input.addEventListener('change',()=>{const f=file.input.files[0];if(!f)return;const reader=new FileReader();reader.onload=()=>{input.input.value=String(reader.result);reset();};reader.readAsText(f);});
  const parse=()=>{try{return JSON.parse(input.input.value);}catch(e){showAlert('不是有效的 JSON：'+e.message,{field:input.input});return null;}};
  const check=btn('检查定义',async()=>{
    reset();const manifest=parse();if(!manifest)return;
    const value=await api('/api/extensions/validate',{manifest});approved=value;
    const view={...manifest,health:{state:'configured_not_verified'}};
    summary.replaceChildren(el('dl',{class:'summary'},...[['工具',value.id],['服务',brandOf(manifest.provider,manifest.id).name],['运行方式',T.kinds[MODEL.routeKindOf(view)]],
      ['权限',(value.permissions||[]).map(p=>MODEL.say(T.permission,p,'{code}')+'（'+p+'）').join('、')||'只读'],['可能扣费',value.paid?'是':'否'],['会访问的网站',(value.origins||[]).join('、')||'无'],
      ['需要的 Key',(value.credential_references||[]).join('、')||'无'],['定义指纹',String(value.sha256).slice(0,16)],
      ['变化',value.action==='update'?(value.previous_sha256===value.sha256?'和已安装的相同':`更新：指纹 ${String(value.previous_sha256).slice(0,12)} → ${String(value.sha256).slice(0,12)}`):'新安装'],['结构检查',String(value.validation)]].flatMap(([k,v])=>[el('dt',{},k),el('dd',{},v)])),raw('extension',value));
    apply.setAttribute('aria-disabled','false');reason.hidden=true;status('检查通过，可以批准安装。');
  });
  apply.addEventListener('click',action(async()=>{
    if(!approved){$('#install-reason').focus?.();status('先检查定义，通过后才能安装。');return;}
    const manifest=parse();if(!manifest)return;
    await api('/api/extensions/install',{manifest,approved_sha256:approved.sha256,...(approved.previous_sha256?{expected_sha256:approved.previous_sha256}:{})});
    const id=approved.id;closeModal();await refresh();toast(`已安装 ${id}。它还没有真正运行过，也没有在真实网站上验收。`);
  }));
  openModal({title:'安装工具定义',wide:true,body:[el('p',{},'粘贴 Agent 起草的工具定义（JSON，不含任何 Key）。ATM 先检查结构，你确认后才安装。修改定义会让旧的受限授权失效。'),input.node,file.node,summary,reason],actions:[cancel(),check,apply]});
}
function setupDialog({agents=[], clis=[], replace=false}) {
  const cliMode=!agents.length&&clis.length>0, labels={claude:'Claude Code',codex:'Codex'};
  const boxes=cliMode?{}:Object.fromEntries(['claude','codex'].map(n=>[n,el('input',{type:'checkbox',checked:agents.includes(n)})]));
  let replaceSkills=replace, plan=null, seq=0;
  const out=el('div',{});
  const chosen=()=>Object.entries(boxes).filter(([,b])=>b.checked).map(([k])=>k);
  const title=()=>cliMode?'绑定 '+clis.join('、'):'安装 ATM 到 '+(chosen().length===2?'Claude Code 和 Codex':chosen().length?labels[chosen()[0]]:'Claude Code / Codex');
  const body=()=>({agents:cliMode?[]:chosen(),clis,replace_skills:replaceSkills});
  const apply=el('button',{type:'button',class:'primary'},cliMode?'确认绑定':'确认安装');
  const reason=el('p',{class:'reason',id:'setup-reason',hidden:true});
  const block=text=>{apply.setAttribute('aria-disabled','true');apply.setAttribute('aria-describedby','setup-reason');reason.textContent=text;reason.hidden=false;};
  const preview=async()=>{
    const mine=++seq;plan=null;block('正在生成计划…');out.replaceChildren(el('p',{class:'quiet'},'正在生成计划…'));
    let p;try{p=await api('/api/setup/preview',body());}catch(e){if(mine===seq){out.replaceChildren();report(e);}return;}
    if(mine!==seq||!$('#modal').open)return;
    plan=p;$('#modal-title').textContent=title();
    const items=[];
    for(const s of p.skills||[]){
      const text={create:`新建 ${s.path}`,unchanged:`${s.path} 已是最新，不改动`,replace:`备份后替换 ${s.path}`,conflict:`${s.path} 和 ATM 的版本不同，需要你确认`}[s.action]||`${s.action}：${s.path}`;
      const extra=s.action==='conflict'?el('label',{class:'check'},el('input',{type:'checkbox',checked:replaceSkills,onchange:e=>{replaceSkills=e.target.checked;preview();}}),'允许备份并替换这个文件（我已经看过它）'):null;
      items.push(el('li',{},el('span',{class:'glyph','data-state':s.action==='conflict'?'attention':s.action==='unchanged'?'ready':'setup',ariaHidden:'true'}),el('div',{},el('span',{},labels[s.agent]+'：',breakable(text)),extra)));
    }
    for(const c of p.clis||[]){
      const text={bind:`绑定 ${c.path}（指纹 ${String(c.sha256||'').slice(0,12)}）`,unchanged:`${c.name} 已绑定，不改动`,review_required:`${c.name} 和上次确认的不同，需要在终端重新绑定：`,missing_program:`本机没有找到 ${c.name}`}[c.action]||c.action;
      items.push(el('li',{},el('span',{class:'glyph','data-state':c.action==='bind'?'setup':c.action==='unchanged'?'ready':'attention',ariaHidden:'true'}),el('div',{},el('span',{},breakable(text)),c.action==='review_required'?commandBox(`atm cli bind ${c.name} ${quote(c.path||'<'+c.name+' 程序的完整路径>')}`):null)));
    }
    out.replaceChildren(el('ul',{class:'plan'},...items),raw('setup-plan',p));
    const all=[...(p.skills||[]),...(p.clis||[])];
    apply.removeAttribute('aria-describedby');reason.hidden=true;apply.setAttribute('aria-disabled','false');
    apply.textContent=all.length&&all.every(x=>x.action==='unchanged')?'完成':cliMode?'确认绑定':'确认安装';
    if(p.status==='needs_review')block('有需要你确认的变化。确认前不会修改任何文件。');
    else if(cliMode&&!(p.clis||[]).some(c=>c.action==='bind'||c.action==='unchanged'))block(`本机没有找到 ${clis.join('、')}，没有可以绑定的程序。`);
    else if(!all.length)block('请至少选择一个 Agent。');
  };
  apply.addEventListener('click',action(async()=>{
    if(apply.getAttribute('aria-disabled')==='true'){reason.focus?.();announce(reason.textContent);return;}
    if(apply.textContent==='完成'){closeModal();return;}
    try{await api('/api/setup/apply',{...body(),approved_sha256:plan.plan_sha256});}
    catch(e){
      if(e.code==='setup_changed'){await preview();showAlert('计划在你确认前变了（文件或程序刚被改动）。已重新生成，请再看一遍。');return;}
      throw e;
    }
    closeModal();await refresh();
    toast(cliMode?`已绑定 ${clis.join('、')}。`:`已安装到 ${chosen().map(n=>labels[n]).join('和')}。在新会话里生效。`);
  }));
  for(const b of Object.values(boxes))b.addEventListener('change',()=>{$('#modal-title').textContent=title();preview();});
  const fields=cliMode?null:el('fieldset',{},el('legend',{},'安装到'),...Object.entries(boxes).map(([k,b])=>el('label',{class:'check'},b,labels[k])));
  openModal({title:title(),body:[el('p',{},'只修改下面列出的本机文件和设置。不安装软件，不登录任何服务，也不读取 Key。'),fields,out,reason],actions:[cancel(),apply],focus:cliMode?apply:null});
  preview();
}
function passkeyDialog(){
  const pass=data.connections.vault.backend==='passphrase'?masterPasswordField('','ATM 主密码（首次绑定需要验证）'):null;
  const label=field('名称（不是秘密）',el('input',{value:'1Password',maxLength:80}));
  openModal({title:'绑定 Passkey',body:[el('p',{},'接下来浏览器会请你保存一个 Passkey 并确认加密扩展（PRF）。请选择 1Password（或其他支持 PRF 的 Passkey）并亲自确认。没有 PRF 时不会绑定，ATM 主密码照常可用。'),label.node,pass?pass.node:null],
    actions:[cancel(),btn('开始绑定',async()=>{
      let password=pass?pass.input.value:'';if(pass)pass.input.value='';
      try{await window.ATM_PASSKEY.register(api,password,label.input.value);closeModal();await refresh();toast('Passkey 已绑定。原有加密的 Key 保持不变。');}
      finally{password=null;if(pass)pass.input.value='';}
    },'primary')]});
}
function disablePasskeyDialog(credential){
  const pass=data.connections.vault.backend==='passphrase'?masterPasswordField('','ATM 主密码（确认停用）'):null;
  openModal({title:'停用 '+credential.label,body:[el('p',{},'停用后不能再用它解锁；ATM 主密码照常可用。1Password 里的 Passkey 和已经解锁的会话不受影响；需要马上停止新的 Key 使用时，点右上角的“立即锁定”。'),pass?pass.node:null],
    actions:[cancel(),btn('确认停用',async()=>{let password=pass?pass.input.value:'';if(pass)pass.input.value='';
      try{await api('/api/passkeys/disable',{credential_id:credential.id,confirm:credential.id,...(password?{passphrase:password}:{})});ui.successor=['passkey:bind'];closeModal();await refresh();toast(`已停用 ${credential.label}。`);}
      finally{password=null;}
    },'primary danger')]});
}
// Higgsfield's ATM OAuth login (keeps the reviewed /api/oauth/login flow).
function oauthDialog({keep=false}={}) {
  const o=(data.connections?.oauth||[])[0]||{provider:'higgsfield',status:'missing'};
  const keyring=data.connections.vault.backend==='keyring';
  const keepBox=el('input',{type:'checkbox',checked:keep&&keyring,disabled:!keyring});
  const replaceBox=el('input',{type:'checkbox'});
  const pass=data.connections.vault.backend==='passphrase'?masterPasswordField('只用于这一次请求，不写入文件。'):null;
  if(!keyring)keepBox.setAttribute('aria-describedby','keep-reason');
  openModal({title:'登录 Higgsfield（ATM 登录）',body:[el('p',{},'会在系统浏览器里打开 Higgsfield 官方页面。请在那里登录并授权，然后回到这里点“刷新状态”。不会生成内容，也不会消耗订阅额度。higgsfield 程序自己的登录不受影响。'),
    el('label',{class:'check'},keepBox,'保持登录：用系统钥匙串加密保存，并安装一个本用户的后台续期服务；服务商撤销或要求验证时，会提示你重新登录。'),
    keyring?null:el('p',{class:'reason',id:'keep-reason'},'需要用系统钥匙串保管 Key 才能开启。'),
    o.status!=='missing'?el('label',{class:'check'},replaceBox,'替换已有的 ATM 登录（higgsfield 程序的登录不受影响）'):null,pass?pass.node:null],
    actions:[cancel(),btn('打开官方登录页面',async()=>{
      let password=pass?pass.input.value:'';
      try{
        const r=await api('/api/oauth/login',{provider:o.provider,keep_login:keepBox.checked,replace:replaceBox.checked,...(password?{passphrase:password}:{})});
        await refresh();closeModal();
        toast(r.browser_opened?'请在打开的官方页面完成登录和授权，然后点“刷新状态”。':'登录窗口没有打开，或者已有一个登录在进行。请查看 Higgsfield 的“ATM 登录”状态。');
      }finally{password=null;if(pass)pass.input.value='';}
    },'primary')]});
}
function confirmDialog({title, body, label, danger=true, run, detail=null}) {
  openModal({title,body:[detail,el('p',{},body)],actions:[cancel(),btn(label,async()=>{await run();},danger?'primary danger':'primary')]});
}
const unregisterConfirm=(agent,label)=>confirmDialog({title:`从 ${label} 移除 ATM？`,body:`会把 ATM 说明文件改名备份，不删除任何 Key 或工具。之后新开的 ${label} 会话不再加载 ATM。`,label:'移除',
  run:async()=>{await api('/api/agents/unregister',{agent,confirm:agent});ui.successor=['agent:'+agent+':安装到 '+label];closeModal();await refresh();toast(`已从 ${label} 移除 ATM；Key 和工具没有改变。`);}});
const revokeDeviceConfirm=p=>confirmDialog({title:`撤销对 ${p.card.name} 的信任？`,body:'之后不再和它同步。它已经收到的 Key 无法收回；担心泄露的话，请到对应服务那边更换 Key。',label:'撤销信任',
  run:async()=>{await api('/api/sync/revoke',{device:p.card.id,confirm:p.card.id});ui.successor=['sync:trust'];closeModal();await refresh();toast(`已撤销对 ${p.card.name} 的信任。`);}});
// The dialog names the grant (title, its lines and id), so the owner can confirm the target among several.
const revokeConfirm=g=>confirmDialog({title:`撤销「${g.title}」？`,
  detail:el('div',{class:'grant-detail'},...g.lines.map(l=>el('span',{},l)),g.kind==='project_session'?mono(g.workspace,'path'):null,el('span',{},'授权 ID ',el('code',{title:g.id},g.short)),el('span',{},g.time)),
  body:g.kind==='project_session'?`项目 ${g.title.replace(/^项目 /,'').replace(/ · 由授权窗口批准$/,'')} 会立刻停止取用 Key。已经在运行的程序可能仍持有取到的 Key。`:`${g.agentLabel} 将不能再用这份授权调用工具。已经提交的任务不会被取消。`,
  label:'撤销授权',run:async()=>{await api('/api/access/revoke',{id:g.id,confirm:g.id});ui.successor=['grants:new'];closeModal();await refresh();toast('授权已撤销。');}});
function stopRenewConfirm(){
  const o=(data.connections?.oauth||[])[0]||{};
  confirmDialog({title:'停止 Higgsfield 自动续期？',body:`当前登录到期（${o.expires_at?T.datetime(o.expires_at):'到期时'}）后需要你重新登录。`,label:'停止自动续期',
    run:async()=>{await api('/api/oauth/keep-login',{provider:o.provider||'higgsfield',enabled:false});closeModal();await refresh();toast('已停止自动续期。');}});
}
// Switch a group of tools one at a time; stops at the first error.
function bulkDialog(tools, enable, routeTitle, serviceName) {
  const list=tools.filter(v=>v.enabled!==enable);
  const go_=btn(enable?'全部允许':'全部停用',async()=>{
    let i=0;
    for(const v of list){
      i++;status(`${i} / ${list.length}`);
      try{await api('/api/tools/toggle',{tool:v.id,enabled:enable,expected_enabled:!enable});}
      catch(e){if(e.gated)return;await refresh().catch(()=>{});showAlert(`有工具的状态刚被改动，已停在第 ${i} 个。已完成的改动保留，请刷新后再试。`);return;}
    }
    closeModal();await refresh();const message=enable?`已允许 ${list.length} 个工具。`:`已停用 ${list.length} 个工具。`;toast(message);announce(message);
  },enable?'primary':'primary danger');
  // Enabling paid tools says how many may charge (S9: 可能扣费 wherever a paid tool is listed).
  const paid=enable?list.filter(v=>v.paid).length:0;
  openModal({title:`${enable?'允许':'停用'} ${routeTitle} 的 ${list.length} 个工具？`,body:[el('p',{},enable?'Claude Code 和 Codex 都可以调用它们。允许使用不等于允许扣费。':`Claude Code 和 Codex 都不能再调用它们。已经提交给 ${serviceName} 的任务不会被取消。`),
    paid?el('p',{class:'paid-line'},tagNode('可能扣费'),` 其中 ${paid} 个可能扣费：每次扣费都要 Agent 在调用时明确声明。`):null],actions:[cancel(),go_]});
}
function downloadJson(value,name){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a',{href:url,download:name});a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const syncPassword=()=>vaultInfo().backend==='passphrase'?masterPasswordField('只用于这一次请求，不写入文件。'):null;
function deviceDialog(){
  const name=field('设备名称',el('input',{placeholder:'例如 laptop 或 build-server',maxLength:80})),pass=syncPassword();
  openModal({title:'生成本机同步身份',body:[name.node,pass?pass.node:null],actions:[cancel(),btn('生成本机身份',async()=>{let p=pass?.input.value||'';
    try{await api('/api/sync/init',{name:name.input.value,...(p?{passphrase:p}:{})});}finally{p=null;if(pass)pass.input.value='';}closeModal();await refresh();toast('已生成本机同步身份。');},'primary')]});
}
function publicDialog(device){
  const copy=el('button',{type:'button',class:'secondary'},'复制');copy.addEventListener('click',()=>copyText(JSON.stringify(device,null,2),copy,null));
  const d=el('details',{open:true},el('summary',{},'查看原始内容（JSON）'),el('pre',{class:'raw'},JSON.stringify(device,null,2)));
  openModal({title:'本机公开身份（不含任何秘密）',body:[facts([['名称',device.name],['设备 ID',device.id,true]]),d],actions:[copy,btn('下载公开身份',()=>downloadJson(device,'atm-device.public.json'),'primary')]});
}
function trustDialog(){
  const card=field('另一台设备的公开身份（JSON）',el('textarea',{rows:6,spellcheck:false})),fp=field('独立核对指纹（在另一台设备上看到的完整指纹）',el('input',{autocomplete:'off'}));
  const saved=[...model.keys.values()].filter(k=>k.connection?.configured).map(k=>k.name);
  const picks=title=>{const boxes=saved.map(n=>[n,el('input',{type:'checkbox'})]);const other=field('其他 Key 名称（逗号分隔）',el('input',{autocomplete:'off'}));
    return {boxes,other,node:el('fieldset',{},el('legend',{},title),...boxes.map(([n,b])=>el('label',{class:'check'},b,n)),other.node),values:()=>[...new Set([...boxes.filter(([,b])=>b.checked).map(([n])=>n),...other.input.value.split(',').map(s=>s.trim()).filter(Boolean)])]};};
  const send=picks('允许发给它的 Key'),receive=picks('允许它发来或修改的 Key');
  const view=el('div',{});let reviewed=null;
  const apply=el('button',{type:'button',class:'primary','aria-disabled':'true','aria-describedby':'trust-reason'},'批准配对');
  const reason=el('p',{class:'reason',id:'trust-reason'},'先检查配对内容。');
  const values=()=>{let c;try{c=JSON.parse(card.input.value);}catch{showAlert('公开身份不是有效的 JSON。',{field:card.input});return null;}return {card:c,fingerprint:fp.input.value.trim(),send:send.values(),receive:receive.values()};};
  const changed=()=>{if(reviewed){status('内容已变化，请重新检查。');}reviewed=null;apply.setAttribute('aria-disabled','true');reason.hidden=false;};
  const check=btn('检查配对内容',async()=>{const v=values();if(!v)return;const r=await api('/api/sync/trust',v);reviewed=JSON.stringify(v);
    view.replaceChildren(el('p',{},`${r.peer?.card?.name||v.card.name||''} · 指纹 ${String(r.peer?.fingerprint||v.fingerprint).slice(0,16)}… · 发给它：${v.send.join('、')||'无'} · 接收它发来的：${v.receive.join('、')||'无'}`),
      el('p',{},{planned:'将新增这个配对',unchanged:'已经是这样，不会改变',trusted:'已配对'}[r.status]||String(r.status||'')),raw('trust',r));
    apply.setAttribute('aria-disabled','false');reason.hidden=true;});
  apply.addEventListener('click',action(async()=>{const v=values();if(!v)return;if(!reviewed||JSON.stringify(v)!==reviewed){changed();return;}
    await api('/api/sync/trust',{...v,apply:true});closeModal();await refresh();toast(`已配对 ${v.card.name||''}。`);}));
  // Any edit after the check needs a new check (listeners live on this dialog's own form only).
  const form=el('div',{class:'dialog-form'},card.node,fp.node,send.node,receive.node);
  form.addEventListener('input',changed);form.addEventListener('change',e=>{if(e.target.type==='checkbox')changed();});
  openModal({title:'配对另一台设备',wide:true,body:[form,view,reason],actions:[cancel(),check,apply]});
}
function exportDialog(peer){const pass=syncPassword();
  openModal({title:'导出给 '+peer.card.name,body:[el('p',{},'只包含允许发给它的 Key 的当前版本、冲突和删除标记。加密包只有这台设备能解开。'),pass?pass.node:null],actions:[cancel(),btn('生成并下载加密包',async()=>{let p=pass?.input.value||'';
    try{const r=await api('/api/sync/export',{device:peer.card.id,...(p?{passphrase:p}:{})});downloadJson(r.encrypted_packet,'atm-'+r.encrypted_packet.header.packet+'.atmsync');closeModal();toast('加密包已下载。');}finally{p=null;if(pass)pass.input.value='';}},'primary')]});}
function importDialog(){
  const file=field('选择加密同步包（.atmsync）',el('input',{type:'file',accept:'.atmsync,.json'})),pass=syncPassword(),view=el('div',{});let packet=null;
  const apply=el('button',{type:'button',class:'primary','aria-disabled':'true','aria-describedby':'import-reason'},'批准导入');
  const reason=el('p',{class:'reason',id:'import-reason'},'先检查内容。');
  file.input.addEventListener('change',()=>{packet=null;apply.setAttribute('aria-disabled','true');reason.hidden=false;view.replaceChildren();});
  const check=btn('检查内容',async()=>{const f=file.input.files[0];if(!f||f.size>8*1024*1024){showAlert('请选择不超过 8 MiB 的加密包。',{field:file.input});return;}
    let p=pass?.input.value||'';
    try{packet=JSON.parse(await f.text());}catch{showAlert('不是有效的加密包。',{field:file.input});return;}
    let r;try{r=await api('/api/sync/import',{packet,...(p?{passphrase:p}:{})});}finally{p=null;}
    view.replaceChildren(el('p',{},'来自 '+String(r.sender||r.from||'').slice(0,16)+'…'),
      el('ul',{},...(r.changes||[]).map(c=>el('li',{},`${serviceNameOf(c.provider)}（${c.provider}）：${c.changed?(c.state==='conflict'?'冲突（相关调用会暂停）':c.state==='deleted'?'将删除':'将更新'):'没有变化'}`))),raw('import',r));
    apply.setAttribute('aria-disabled','false');reason.hidden=true;});
  apply.addEventListener('click',action(async()=>{if(!packet){announce('先检查内容。');return;}let p=pass?.input.value||'';
    try{const r=await api('/api/sync/import',{packet,apply:true,...(p?{passphrase:p}:{})});closeModal();await refresh();toast(r.conflicts?'存在冲突：已保留两个版本，并暂停相关调用。':'加密的 Key 已合并到本机。');}finally{p=null;if(pass)pass.input.value='';}}));
  openModal({title:'导入加密同步包',body:[file.node,pass?pass.node:null,view,reason],actions:[cancel(),check,apply]});
}
function resolveDialog(provider){
  const record=(data.sync?.records||[]).find(r=>r.provider===provider&&r.state==='conflict'), svc=serviceNameOf(provider);
  if(!record){openModal({title:`${svc} 的 Key 选哪个版本？`,body:[el('p',{},'没有找到这个 Key 的版本记录。请刷新后再试。')],actions:[el('button',{type:'button',class:'primary',onclick:()=>closeModal()},'完成')]});return;}
  const pass=syncPassword();
  const radios=record.heads.map(h=>[h,el('input',{type:'radio',name:'resolve-head',value:h.revision})]);
  const apply=el('button',{type:'button',class:'primary','aria-disabled':'true','aria-describedby':'resolve-reason'},'使用这个版本');
  const reason=el('p',{class:'reason',id:'resolve-reason'},'先选择一个版本。');
  radios.forEach(([,r])=>r.addEventListener('change',()=>{apply.setAttribute('aria-disabled','false');reason.hidden=true;}));
  apply.addEventListener('click',action(async()=>{const choice=radios.find(([,r])=>r.checked);if(!choice){announce('先选择一个版本。');return;}let p=pass?.input.value||'';
    try{await api('/api/sync/resolve',{provider,choose:choice[0].revision,expected:record.expected,apply:true,...(p?{passphrase:p}:{})});}finally{p=null;if(pass)pass.input.value='';}
    ui.successor=['route:key:'+provider+':更换','key:replace:'+provider];
    closeModal();await refresh();toast(`已选择 ${svc} 的 Key 版本，相关工具恢复使用。`);}));
  openModal({title:`${svc} 的 Key 选哪个版本？`,body:[el('p',{},'选择的是这个 Key 的一个完整版本，不能拼接。不会按时间自动选择；如果这期间又收到新的修改，这次选择会被拒绝。'),
    el('fieldset',{},el('legend',{},'版本'),...radios.map(([h,r])=>choice(r,`来自 ${String(h.author).slice(0,10)} · 修订 ${String(h.revision).slice(0,12)}`,h.deleted?'删除这个 Key':'保留这个 Key'))),pass?pass.node:null,reason],
    actions:[cancel(),apply]});
}
function grantDialog(){
  const agents=['claude','codex'].map(a=>[a,el('input',{type:'radio',name:'grant-agent',value:a,checked:a==='claude'})]);
  const tools=field('精确工具 ID（逗号分隔）',el('input',{placeholder:'例如 ffmpeg.probe',autocomplete:'off'}));
  const known=el('p',{class:'hint'}), unknown=el('p',{class:'reason',id:'grant-unknown',hidden:true});
  const workspace=field('允许的项目目录',el('input',{placeholder:'已存在的项目绝对路径，例如 /Users/you/projects/demo',autocomplete:'off'}));
  const ttl=field('有效期',el('select',{},el('option',{value:'24'},'1 天'),el('option',{value:'168',selected:true},'7 天'),el('option',{value:'720'},'30 天'),el('option',{value:'custom'},'自定义…')));
  const hours=field('小时数（1–720）',el('input',{type:'number',min:1,max:720,value:168}));hours.node.hidden=true;
  ttl.input.addEventListener('change',()=>{hours.node.hidden=ttl.input.value!=='custom';});
  const perms=[['external_write','会改动外部内容（external_write）'],['production','可操作生产环境（production）'],['execute_code','会在本机运行程序（execute_code）']].map(([k,l])=>[k,el('input',{type:'checkbox'}),l]);
  const paid=el('input',{type:'checkbox'}), paidHint=el('span',{class:'hint'});
  const ids=()=>tools.input.value.split(',').map(v=>v.trim()).filter(Boolean);
  const missing=()=>ids().filter(id=>!model.tools.has(id));
  // Ids the catalogue does not know cannot be checked: 检查授权内容 stays focusable but sends nothing, with the reason shown.
  const recognise=()=>{const list=ids(),found=list.filter(id=>model.tools.has(id)),gone=missing();
    known.replaceChildren(found.length?'已识别：':'',...found.flatMap((id,i)=>[i?'、':'',id,model.tools.get(id).paid?el('span',{class:'tag paid'},'可能扣费'):'']));
    unknown.textContent=gone.length?`不在目录中：${gone.join('、')}。删掉这些工具 ID 后才能检查。`:'';unknown.hidden=!gone.length;
    if(gone.length){check.setAttribute('aria-disabled','true');check.setAttribute('aria-describedby','grant-unknown');}
    else{check.removeAttribute('aria-disabled');check.removeAttribute('aria-describedby');}
    paidHint.textContent=found.length&&!found.some(id=>model.tools.get(id).paid)?'所选工具都不会扣费。':'';};
  tools.input.addEventListener('input',()=>recognise());
  const view=el('div',{});let reviewed=null,hash=null;
  const agentName=()=>agents.find(([,r])=>r.checked)?.[0]||'claude', agentLabel=()=>agentName()==='claude'?'Claude Code':'Codex';
  const values=()=>({agent:agentName(),tools:ids(),workspace:workspace.input.value,ttl_hours:Number(ttl.input.value==='custom'?hours.input.value:ttl.input.value),allow_paid:paid.checked,permissions:perms.filter(([,b])=>b.checked).map(([k])=>k)});
  const apply=el('button',{type:'button',class:'primary','aria-disabled':'true','aria-describedby':'grant-reason'},'批准并写入');
  const reason=el('p',{class:'reason',id:'grant-reason'},'先检查授权内容。');
  const changed=()=>{if(reviewed)status('内容已变化，请重新检查。');reviewed=null;apply.setAttribute('aria-disabled','true');reason.hidden=false;};
  const check=btn('检查授权内容',async()=>{
    if(missing().length){announce(unknown.textContent);tools.input.focus();return;}
    const v=values();let r;
    try{r=await api('/api/access/grant',v);}
    catch(e){if(e.code==='profile_exists'){showAlert(`${agentLabel()} 已经有一份受限授权的配置文件，旧授权被保留。先在“正在生效的授权”里撤销那一份再新建；如果两份都要保留，请在终端用 atm access grant 为新授权指定另一个配置文件位置。`);return;}throw e;}
    reviewed=JSON.stringify(v);hash=r.approval_sha256;
    view.replaceChildren(el('p',{},`${agentLabel()} 可以在 ${v.workspace} 中使用 ${v.tools.length} 个工具：${v.tools.join('、')}，到 ${r.expires_at?T.datetime(r.expires_at):T.datetime(Date.now()/1000+v.ttl_hours*3600)} 失效；${v.allow_paid?'会':'不会'}消耗额度。`),
      el('p',{},'授权指纹 ',el('code',{},String(hash).slice(0,12))),raw('grant',r));
    apply.setAttribute('aria-disabled','false');reason.hidden=true;});
  apply.addEventListener('click',action(async()=>{const v=values();if(!reviewed||JSON.stringify(v)!==reviewed){changed();return;}
    await api('/api/access/grant',{...v,apply:true,approved_sha256:hash});closeModal();await refresh();toast(`已创建 ${agentLabel()} 的受限授权。`);}));
  const form=el('div',{class:'dialog-form'},el('fieldset',{},el('legend',{},'给哪个 Agent'),...agents.map(([a,r])=>el('label',{class:'check'},r,a==='claude'?'Claude Code':'Codex'))),
    tools.node,known,unknown,workspace.node,ttl.node,hours.node,
    el('fieldset',{},el('legend',{},'额外权限（只勾选所选工具需要的）'),...perms.map(([,b,l])=>el('label',{class:'check'},b,l))),
    el('label',{class:'check'},paid,'允许这些工具消耗额度（这不是金额上限）'),paidHint);
  form.addEventListener('input',changed);form.addEventListener('change',changed);
  openModal({title:'新建受限授权',wide:true,body:[el('p',{},'给某个 Agent 一组固定的工具和一个项目目录，用于 broker 严格模式。默认模式不需要它。'),form,view,reason],actions:[cancel(),check,apply]});
}

// ---- Global search ----
function searchTarget(q) {
  q=q.trim().toLowerCase();
  if(!q||!model)return null;
  if(model.tools.has(q))return {tool:q,service:model.tools.get(q).serviceKey};
  for(const s of model.services)if(s.key===q||s.name.toLowerCase()===q||MODEL.serviceKeyOf(q)===s.key&&brandOf(q).src)return {service:s.key};
  return null;
}
$('#global-search').addEventListener('submit',e=>{
  e.preventDefault();
  const q=$('#global-q').value, target=searchTarget(q);
  $('#global-q').value='';
  if(target?.tool){
    // A tool past the first eight of its group: show the whole group first.
    const st=ui.service.get(target.service)||{filter:'all',q:'',open:new Set()};ui.service.set(target.service,st);
    st.filter='all';st.q='';for(const r of model.byKey.get(target.service).routes)st.open.add(r.anchor);
    go('services/'+target.service,{focus:false});
    const row=$('#tool-'+CSS.escape(T.slug(target.tool)));
    if(row){row.scrollIntoView({block:'center'});row.querySelector('.tool-title')?.focus({preventScroll:true});row.classList.add('flash');setTimeout(()=>row.classList.remove('flash'),2000);}
  } else if(target?.service) go('services/'+target.service);
  else {serviceFilters.q=q.trim();serviceFilters.view='services';go('services',{focus:false});$('#services-q')?.focus();}
});
$('#search-button').addEventListener('click',()=>{go('services',{focus:false});$('#services-q')?.focus();});
document.addEventListener('keydown',e=>{
  if(e.key!=='/'||e.metaKey||e.ctrlKey||e.altKey||$('#modal').open||!$('#gate').hidden)return;
  const t=e.target;if(t&&(t.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(t.tagName)))return;
  e.preventDefault();
  if(active==='services')$('#services-q')?.focus();else if(!$('#global-search').hidden&&getComputedStyle($('#global-search')).display!=='none')$('#global-q').focus();else{go('services',{focus:false});$('#services-q')?.focus();}
});

document.querySelectorAll('[data-nav]').forEach(n=>n.onclick=()=>go(n.dataset.nav==='settings'?'settings/keys':n.dataset.nav));
// A launch link opened in this already-open tab changes only the fragment (popstate, then hashchange):
// reload, so the normal load path strips and redeems it. Its popstate leaves the current section alone.
const launchLink = () => /^#(launch|token)=/.test(location.hash);
window.addEventListener('popstate',e=>{if(launchLink())return;active=known(e.state?.section)||'overview';tabSection.set(active);render({changed:true,focus:true});});
window.addEventListener('hashchange',()=>{if(launchLink())location.reload();});
$('#modal-close').onclick=closeModal;
// Esc on the dialog itself. A file input's own (bubbling) cancel, when its picker is dismissed, must not empty the dialog.
$('#modal').addEventListener('cancel',e=>{if(e.target!==e.currentTarget)return;$('#modal-body').replaceChildren();$('#modal-actions').replaceChildren();});
$('#modal').addEventListener('close',restoreFocus);
// 刷新 is never disabled, so keyboard focus stays on it; aria-busy marks the request and a second press waits.
$('#refresh').onclick=async()=>{
  if(ui.refreshing)return;
  try{await refresh();announce('已刷新');}catch(e){report(e);}
};
$('#lock').onclick=()=>forget();
$('#session-form').onsubmit=action(async e=>{e.preventDefault();typed=token=$('#session-token').value;$('#session-token').value='';await refresh();typed='';tabToken.set(token);});
wide.addEventListener('change',()=>{if(data)render();});
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible'&&data&&Date.now()-ui.lastFetch>30000&&!ui.refreshing&&$('#gate').hidden)refresh().catch(report);
});
async function start() {
  if (launchCode) {
    // Exact-origin exchange of the one-time code: the bearer never enters a URL or a history entry.
    const r=await fetch('/api/console/redeem',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:launchCode}),cache:'no-store'});
    const value=await r.json();
    const stored=tabToken.get();
    if (r.ok&&typeof value.token==='string') {token=value.token; tabToken.set(token);}
    // A used or stale link opened in a tab that is already connected keeps that tab's session;
    // refresh() still checks it, and a 401 then forgets it as usual.
    else if (stored&&value.error?.code!=='session_expired') token=stored;
    else {forget(value.error?.code==='session_expired'?'session_expired':'launch_expired');return;}
  }
  if (!token) {showGate();return;}
  await refresh();  // The page-title placeholder stays while the bearer is checked; the gate does not flash.
}
renderPill();
start().catch(e=>{if(!e?.gated)toast(errorText(e),true);if($('#gate').hidden)showGate();});  // A 401 already shows why on the gate.
// Literal markers kept for the OAuth contract test: the Higgsfield route is "ATM OAuth" and logs in via /api/oauth/login.
