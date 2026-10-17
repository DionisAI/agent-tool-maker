// Observed visible-UI contract. No authentication files, storage or private APIs.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';

export class XyqError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
export const ORIGIN = 'https://xyq.jianying.com';
export const FILES = ['core.mjs', 'inspect.js'];
export function bundleDigest() {
  const hash = createHash('sha256');
  for (const name of FILES) {
    hash.update(name + '\0'); hash.update(readFileSync(new URL(name, import.meta.url))); hash.update('\0');
  }
  return hash.digest('hex');
}
export function checkPin(pin) {
  if (!/^[a-f0-9]{64}$/.test(pin || '') || pin !== bundleDigest())
    throw new XyqError('definition_changed', 'Review the changed XYQ browser adapter bundle.');
}

// Self-contained so the bridge can serialize it into the browser's DOM scope.
export function readHomeDOM(context={}) {
  if (location.origin !== 'https://xyq.jianying.com') return {kind:'origin_mismatch'};
  if (location.pathname === '/login') return {kind:'login_required'};
  if (location.pathname !== '/home') return {kind:'unsupported_surface'};
  // Radix masks a mode menu's rendered background from accessibility. Reading
  // that exact mask needs the owning workflow and mutual trigger/menu IDs.
  let modeMask=null;
  if(context?.owned_mode_menu===true){
    const ts=document.querySelectorAll('#title-section-prompt-container button[aria-label="选择创作模式"]');
    if(ts.length===1&&ts[0].getAttribute('data-state')==='open'){
      const trigger=ts[0],layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]'));
      if(!layers.length)return{kind:'pending'};
      const m=layers[0];if(layers.length!==1||m.getAttribute('role')!=='menu'||m.getAttribute('data-slot')!=='dropdown-menu-content'||!m.querySelector('[role="menuitemradio"] [data-slot="dropdown-menu-item-title"]')||!trigger.id||!m.id||trigger.getAttribute('aria-controls')!==m.id||m.getAttribute('aria-labelledby')!==trigger.id||trigger.getAttribute('aria-expanded')!=='true')return{kind:'mode_context_changed'};
      modeMask=trigger.closest('[aria-hidden="true"]');
    }
  }
  const visible = e => !!e && !!e.getClientRects().length && !e.closest('[hidden]') && (!e.closest('[aria-hidden="true"]')||e.closest('[aria-hidden="true"]')===modeMask);
  const text = e => (e?.innerText || '').replace(/\s+/g, ' ').trim();
  const label = e => (e.getAttribute('aria-label') || text(e)).trim();
  const nodes = (root, selector) => Array.from(root.querySelectorAll(selector)).filter(visible);
  const buttons = nodes(document, 'button');
  const personal = buttons.filter(e => e.getAttribute('aria-label') === '打开个人导航');
  const login = buttons.some(e => /^(?:登录|登录\/注册|立即登录)$/.test(label(e)));
  if (login && personal.length) return {kind:'layout_changed'};
  if (login) return {kind:'login_required'};
  const nav = document.querySelector('nav[aria-label="功能导航"]');
  const root = document.querySelector('#title-section-prompt-container');
  if (!visible(nav) || !visible(root) || personal.length !== 1) return {kind:'pending'};
  const credits = nodes(document, 'header button[aria-haspopup="dialog"]')
    .filter(e => !e.getAttribute('aria-label'));
  if (credits.length !== 1) return {kind: credits.length ? 'layout_changed' : 'pending'};
  const balance = text(credits[0]);
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(balance)) return {kind:'layout_changed'};
  const creditValue = Number(balance.replaceAll(',', ''));
  if (!Number.isFinite(creditValue) || creditValue > Number.MAX_SAFE_INTEGER) return {kind:'layout_changed'};
  const control = e => ({label:label(e), role:e.getAttribute('role') || 'button',
    disabled:!!e.disabled || e.getAttribute('aria-disabled') === 'true'});
  const navigation = nodes(nav, 'button').map(control);
  const shortcuts = nodes(document, 'nav[aria-label="创作快捷入口"] button').map(control);
  if (navigation.length > 40 || shortcuts.length > 40 || [...navigation,...shortcuts].some(x=>!x.label || x.label.length>512))
    return {kind:'layout_changed'};
  const agentLists = nodes(root, '[role="tablist"][aria-label="Agent 类型"]');
  if (agentLists.length !== 1) return {kind:'layout_changed'};
  const agents = nodes(agentLists[0], '[role="tab"]').map(e=>({...control(e), selected:e.getAttribute('aria-selected')==='true'}));
  const selected = agents.filter(e=>e.selected);
  if (selected.length !== 1 || !['创作','短剧','营销'].includes(selected[0].label)) return {kind:'layout_changed'};
  const modes = nodes(root, 'button[aria-label="选择创作模式"]');
  const pref = nodes(root, 'button[aria-label^="模型选择和偏好设置"]');
  const editors = nodes(root, '[role="textbox"][contenteditable="true"]');
  const submit = nodes(root, 'button[aria-label="开始生成"],button[aria-label="生成"]');
  const canvas = nodes(root, '[role="switch"][aria-label="画布"]');
  if ([modes,pref,editors,submit,canvas].some(es=>es.length>1)) return {kind:'layout_changed'};
  const formReady = editors.length===1 && pref.length===1 && submit.length===1 && canvas.length===1;
  let preferencesOpen = formReady && pref[0].getAttribute('data-state')==='open';
  if(formReady && pref[0].hasAttribute('aria-expanded')){
    // The current generation popover keeps data-state=closed while open.
    // Its expanded state is authoritative only with the exact controlled panel.
    const expanded=pref[0].getAttribute('aria-expanded');
    if(!['true','false'].includes(expanded))return{kind:'preferences_context_changed'};
    preferencesOpen=expanded==='true';
    const id=pref[0].getAttribute('aria-controls');
    const panels=nodes(document,'[role="dialog"]').filter(e=>id&&e.id===id);
    if(preferencesOpen){
      if(!id)return{kind:'preferences_context_changed'};
      if(!panels.length)return{kind:'pending'};
      if(panels.length!==1||panels[0].getAttribute('data-slot')!=='generation-preferences-panel-positioner'||panels[0].getAttribute('data-state')!=='open'||nodes(panels[0],'section[aria-label="模型选择"]').length!==1||nodes(panels[0],'section[aria-label="偏好设置"]').length!==1)return{kind:'preferences_context_changed'};
    }else if(panels.length)return{kind:'preferences_context_changed'};
  }
  const editorText = formReady ? (editors[0].innerText || '').replace(/\r\n/g,'\n') : '';
  // No prompt, user identity, history titles, signed URLs or raw file names returned.
  const observedCosts = nodes(root, '[aria-label^="积分消耗"]')
    .map(e=>({label:e.getAttribute('aria-label'), text:text(e)}));
  if (observedCosts.length>2 || observedCosts.some(e=>e.label.length>128 || e.text.length>256)) return {kind:'layout_changed'};
  return {kind:'ready', logged_in:true, credits:creditValue, navigation, shortcuts, agents,
    agent:selected[0].label, form:formReady ? {
      mode:modes.length ? text(modes[0]) : selected[0].label+' Agent',
      preferences:label(pref[0]), preferences_open:preferencesOpen,
      prompt_empty:editorText.trim().length===0, prompt_characters:editorText.length,
      canvas:{checked:canvas[0].getAttribute('aria-checked')==='true',disabled:control(canvas[0]).disabled},
      submit:{label:label(submit[0]),enabled:!control(submit[0]).disabled},
      visible_cost_observations:observedCosts, quote_status:'not_final',
      file_inputs:Array.from(root.querySelectorAll('input[type="file"]')).map(e=>({accept:e.getAttribute('accept'),multiple:e.hasAttribute('multiple')}))
    } : null};
}

export function readOptionsDOM() {
  if (location.origin !== 'https://xyq.jianying.com') return {kind:'origin_mismatch'};
  if (location.pathname === '/login') return {kind:'login_required'};
  if (location.pathname !== '/home') return {kind:'unsupported_surface'};
  const visible = e => !!e && !!e.getClientRects().length && !e.closest('[hidden],[aria-hidden="true"]');
  const text = e => (e?.innerText || '').replace(/\s+/g,' ').trim();
  const nodes = (root, selector) => Array.from(root.querySelectorAll(selector)).filter(visible);
  const models = nodes(document,'section[aria-label="模型选择"]');
  const prefs = nodes(document,'section[aria-label="偏好设置"]');
  if (!models.length && !prefs.length) return {kind:'pending'};
  if (models.length!==1 || prefs.length!==1) return {kind:'layout_changed'};
  // Chrome AX presents these pressed buttons as checkboxes. The live DOM uses
  // aria-pressed plus a title slot; role=checkbox alone only passed fake fixtures.
  const modelNodes=nodes(models[0],'button[aria-pressed]:has([data-slot="model-picker-item-title"]),[role="checkbox"]');
  const choices = modelNodes.map(e=>({label:text(e.querySelector('[data-slot="model-picker-item-title"]'))||e.getAttribute('aria-label')||text(e),checked:(e.getAttribute('aria-pressed')||e.getAttribute('aria-checked'))==='true',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'}));
  const radios = nodes(prefs[0],'[role="radio"]').map(e=>({group:e.closest('[role="radiogroup"]')?.getAttribute('aria-label')||text(e.closest('[data-slot="home-direct-generic-parameter-field"]')?.querySelector('[data-slot="home-direct-parameter-label"]'))||null,label:e.getAttribute('aria-label')||text(e),checked:e.getAttribute('aria-checked')==='true',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'}));
  const numbers = nodes(prefs[0],'input[type="number"],input[aria-label="视频时长秒数"]')
    .map(e=>({label:e.getAttribute('aria-label'),value:e.value,min:e.getAttribute('min'),max:e.getAttribute('max')}));
  const toggles = nodes(prefs[0],'[role="checkbox"]').map(e=>({label:e.getAttribute('aria-label')||text(e),checked:e.getAttribute('aria-checked')==='true'}));
  const sliders = nodes(prefs[0],'[role="slider"],input[type="range"]').map(e=>({label:e.getAttribute('aria-label'),min:e.getAttribute('aria-valuemin')??e.getAttribute('min'),max:e.getAttribute('aria-valuemax')??e.getAttribute('max'),value:e.getAttribute('aria-valuenow')??e.value}));
  // Seed's current random/custom controls are pressed buttons, not radios.
  // Expose their actual states without inventing a group or enabling seed writes.
  const pressedNodes=nodes(prefs[0],'button[aria-pressed]');
  if(pressedNodes.some(e=>!['true','false'].includes(e.getAttribute('aria-pressed'))))return{kind:'layout_changed'};
  const pressed_buttons=pressedNodes.map(e=>({label:e.getAttribute('aria-label')||text(e),checked:e.getAttribute('aria-pressed')==='true',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'}));
  if (!choices.length || choices.length>50 || new Set(choices.map(e=>e.label)).size!==choices.length || choices.filter(e=>e.checked).length!==1 || radios.length>100 || numbers.length>10 || toggles.length>20 || sliders.length>10 || pressed_buttons.length>20 || [...choices,...radios,...pressed_buttons].some(e=>!e.label||e.label.length>512)) return {kind:'layout_changed'};
  return {kind:'ready',models:choices,radios,numbers,toggles,sliders,pressed_buttons,coverage:'currently_visible_options',all_options:false};
}

function unwrap(value) { return value && typeof value==='object' && 'session' in value && 'data' in value ? value.data : value; }
export async function pollDOM(page, reader, {timeout=15000,pause=200}={}) {
  const deadline=Date.now()+timeout;
  while (true) {
    let data;
    try { data=unwrap(await page.evaluate(reader)); }
    catch { throw new XyqError('bridge_failed','XYQ DOM read failed; inspect the local browser.'); }
    if (!data || typeof data!=='object' || typeof data.kind!=='string') throw new XyqError('bridge_protocol','Unexpected XYQ bridge response.');
    if (data.kind==='ready') return data;
    if (data.kind!=='pending') throw new XyqError(data.kind,'XYQ visible-UI contract is not ready for this operation.');
    if (Date.now()>=deadline) throw new XyqError('page_not_ready','XYQ visible content did not become ready.');
    await new Promise(resolve=>setTimeout(resolve,pause));
  }
}
const evidence = {source:'visible_dom',secrets_returned:false,paid_submitted:false};
export async function inspect(page, operation) {
  if (!['account','surface','form-inspect','form-options'].includes(operation)) throw new XyqError('invalid_argument','Unknown XYQ inspection operation.');
  const data=await pollDOM(page,readHomeDOM);
  if (operation==='account') return [{result:{status:'ready',logged_in:data.logged_in,credits:data.credits,billing:'website_account',...evidence}}];
  if (operation==='surface') return [{result:{status:'ready',agent:data.agent,agents:data.agents,navigation:data.navigation,shortcuts:data.shortcuts,coverage:'currently_visible_home',full_web_coverage:false,...evidence}}];
  if (!data.form) throw new XyqError('unsupported_surface','Inspect this workspace with its own reviewed domain adapter.');
  if (operation==='form-inspect') return [{result:{status:'ready',agent:data.agent,form:data.form,...evidence}}];
  // This first slice is strictly read-only. The human/Agent's separate UI workflow
  // opens the observed menu; this tool neither opens/closes it nor changes settings.
  if (!data.form.preferences_open) throw new XyqError('options_closed','Open the current model/preferences menu before reading its options.');
  const options=await pollDOM(page,readOptionsDOM);
  const after=await pollDOM(page,readHomeDOM);
  if (!after.form || after.agent!==data.agent || after.form.mode!==data.form.mode || after.form.preferences!==data.form.preferences || !after.form.preferences_open)
    throw new XyqError('draft_changed','XYQ form changed during the options read.');
  return [{result:{status:'ready',agent:data.agent,mode:data.form.mode,preferences:data.form.preferences,options,quote_status:'not_final',...evidence}}];
}
