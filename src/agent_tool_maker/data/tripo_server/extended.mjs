// Reviewed visible UI only. No provider API, cookie, profile or hidden runtime state.
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync, existsSync, lstatSync, mkdirSync, openSync, closeSync, writeFileSync, fsyncSync, renameSync } from 'node:fs';
import { resolve, dirname, join, isAbsolute, basename } from 'node:path';
import { ORIGIN, StudioError, unwrap, pollDOM, readAccountDOM } from './core.mjs';

const sha = value => createHash('sha256').update(value).digest('hex');
const UUID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
export const PANEL = 'div.rounded-r-5:has(h2)';
export const EXPORT_DIALOG = '[role="dialog"]:has(input[maxlength="255"])';
export const ROUTES = { retopo: 'retopology', rig: 'rigging', asset: 'generate', export: 'generate' };
export const EXTENDED_FILES = ['account.js', 'assets.js', 'core.mjs', 'quote.js', 'generate.js', 'paid.mjs', 'extended.mjs', 'extended.js'];
export function extendedDigest() {
  const hash = createHash('sha256');
  for (const name of EXTENDED_FILES) hash.update(name + '\0').update(readFileSync(new URL(name, import.meta.url))).update('\0');
  return hash.digest('hex');
}
export function checkExtendedPin(pin) {
  if (!/^[a-f0-9]{64}$/.test(pin || '') || pin !== extendedDigest()) throw new StudioError('definition_changed', 'Review and rebuild extended adapters before use.');
}
export function assetId(id) {
  if (!UUID.test(id || '')) throw new StudioError('invalid_argument', 'Use a real asset UUID, not the thumbnail preview task UUID.');
  return id;
}
export function parseSettings(operation, value = '{}') {
  let settings;
  try { settings = typeof value === 'string' ? JSON.parse(value) : value; } catch { throw new StudioError('invalid_argument', 'settings must be a JSON object.'); }
  if (!settings || typeof settings !== 'object' || Array.isArray(settings)) throw new StudioError('invalid_argument', 'settings must be an object.');
  const allowed = operation === 'retopo' ? ['topology', 'polygon_count', 'smart_mesh'] : operation === 'rig' ? ['rigging_type', 'skeleton'] : [];
  if (Object.keys(settings).some(key => !allowed.includes(key))) throw new StudioError('invalid_argument', 'Unknown setting; arbitrary selectors are not accepted.');
  if ('topology' in settings && !['Quad', 'Triangle'].includes(settings.topology)) throw new StudioError('invalid_argument', 'topology must be Quad or Triangle.');
  if ('polygon_count' in settings && (!Number.isSafeInteger(settings.polygon_count) || settings.polygon_count < 500 || settings.polygon_count > 200000)) throw new StudioError('invalid_argument', 'polygon_count must be an integer from 500 to 200000, also within current UI limits.');
  if ('smart_mesh' in settings && typeof settings.smart_mesh !== 'boolean') throw new StudioError('invalid_argument', 'smart_mesh must be boolean.');
  if ('rigging_type' in settings && !['Humanoid', 'Other'].includes(settings.rigging_type)) throw new StudioError('invalid_argument', 'Select Humanoid or Other.');
  if ('skeleton' in settings && !['ActorCore', 'Mixamo', 'UE5 Mannequin', 'VRM 1.0 Humanoid', 'Unity Humanoid Compatible'].includes(settings.skeleton)) throw new StudioError('invalid_argument', 'Select an observed skeleton preset.');
  return settings;
}
export function readLocation() { return { origin: location.origin, path: location.pathname }; }
export function readRouteLinkDOM(id, route) {
  const links = Array.from(document.querySelectorAll('a[href]')).filter(el => {
    if (el.closest('[role="tabpanel"]')) return false;
    const url = new URL(el.getAttribute('href'), location.origin);
    return url.origin === location.origin && url.pathname.startsWith('/workspace/' + route + '/') && url.pathname.endsWith(id) && !url.search && !url.hash;
  });
  return links.length === 1 ? { href: links[0].getAttribute('href') } : { href: null };
}
export function readAssetEntryLinkDOM(id) {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const panel = document.querySelector('[role="tabpanel"]');
  if (!panel) {
    if (/Something went wrong|Please try again later/.test(document.querySelector('main')?.innerText || '')) return { kind: 'site_error' };
    return { kind: 'pending' };
  }
  const links = Array.from(panel.querySelectorAll('a[href]')).filter(el => {
    const url = new URL(el.getAttribute('href'), location.origin);
    return el.getClientRects().length && url.origin === location.origin &&
      /^\/workspace\/(?:generate|retopology|rigging)\//.test(url.pathname) &&
      url.pathname.endsWith(id) && !url.search && !url.hash;
  });
  if (links.length === 1) return { kind: 'ready', href: links[0].getAttribute('href') };
  return { kind: links.length ? 'asset_ambiguous' : 'asset_not_in_workspace', href: null };
}
export function findTextDOM(selector, text) {
  const matches = Array.from(document.querySelectorAll(selector));
  const indices = matches.map((el, i) => el.getClientRects().length && el.innerText.trim() === text ? i : -1).filter(i => i >= 0);
  return { count: indices.length, nth: indices[0] };
}
async function clickText(page, selector, text) {
  // SPA routes/modal controls mount asynchronously. Wait for one semantic
  // target before the single click; never interpret a not-yet-mounted control
  // as a changed contract or retry a side effect.
  const target = await pollDOM({ evaluate: async () => {
    const next = unwrap(await page.evaluate(findTextDOM, selector, text));
    return { ...next, kind: next?.count === 1 ? 'ready' : next?.count === 0 ? 'pending' : 'layout_changed' };
  } }, findTextDOM);
  await page.click(selector, { nth: target.nth });
}

export function readAssetDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const match = location.pathname.match(/^\/workspace\/(?:generate|retopology|rigging)\/.*?([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  if (!match) return { kind: 'pending' };
  const main = document.querySelector('main');
  if (!main) return { kind: 'pending' };
  if (/Something went wrong|Please try again later/.test(main.innerText)) return { kind: 'site_error' };
  const paragraphs = Array.from(main.querySelectorAll('p')).filter(el => el.getClientRects().length);
  const numberAfter = label => {
    const node = paragraphs.find(el => el.innerText.trim() === label)?.nextElementSibling;
    const value = node?.innerText?.trim();
    // Quad sources show one count; triangle sources observed current/total.
    if(!/^\d+(?:\s*\/\s*\d+)?$/.test(value||''))return null;
    const count=Number(value.split('/')[0]);return Number.isSafeInteger(count)?count:null;
  };
  const faces = numberAfter('Faces'), vertices = numberAfter('Vertices');
  const processing = paragraphs.some(el => /^(Generating\.{0,3}|Processing\.{0,3}|Retopologizing\.{0,3}|Rigging\.{0,3})$/i.test(el.innerText.trim()));
  const failed = paragraphs.some(el => /^(Generation failed|Unknown server error|Task failed)/i.test(el.innerText.trim()));
  const exports = Array.from(main.querySelectorAll('button')).filter(el => el.innerText.trim() === 'Export' && !el.closest('[role="dialog"]'));
  const exportEnabled = exports.length === 1 && !exports[0].disabled;
  const status = failed ? 'failed' : processing ? 'generating' : faces > 0 && vertices > 0 && exportEnabled ? 'ready' : 'pending';
  return { kind: 'ready', status, asset_id: match[1], faces, vertices, export_enabled: exportEnabled, processing };
}
export async function navigateAsset(page, id, operation = 'asset') {
  assetId(id);
  const route = ROUTES[operation];
  if (!route) throw new StudioError('invalid_argument', 'Unsupported asset operation.');
  const target = '/workspace/' + route + '/' + id;
  let where = unwrap(await page.evaluate(readLocation));
  const initial = where.origin === ORIGIN ? unwrap(await page.evaluate(readAssetDOM)) : null;
  if (where.origin !== ORIGIN || !where.path.endsWith(id) || initial?.kind === 'site_error') {
    // UUID-only routes work as SPA links but cold navigation produced a visible
    // server error. Enter through the observed Workspace link, then the asset
    // sidebar; never guess a slug or replay an internal endpoint.
    if (where.origin !== ORIGIN) {
      await page.goto(ORIGIN + '/assets'); await pollDOM(page, readAccountDOM);
      where = unwrap(await page.evaluate(readLocation));
    }
    if (!/^\/workspace\/(?:generate|retopology|rigging)(?:\/|$)/.test(where.path) ||
        initial?.kind === 'site_error') {
      await page.click('a[href="/workspace/generate"]');
    }
    let entry;
    try {
      // Workspace mounts the sidebar before its cards. A missing card in that
      // first frame is not authoritative absence. Wait without another click;
      // keep a bounded, explicit missing-asset error if it never appears.
      entry = await pollDOM({ evaluate: async () => {
        const next = unwrap(await page.evaluate(readAssetEntryLinkDOM, id));
        return next.kind === 'asset_not_in_workspace' ? { kind: 'pending' } : next;
      } }, readAssetEntryLinkDOM);
    } catch (error) {
      if (error instanceof StudioError && error.code === 'page_not_ready')
        throw new StudioError('asset_not_in_workspace', 'Requested asset did not appear in the bounded sidebar wait; use asset-resolve for older cards.');
      throw error;
    }
    if (!/^\/workspace\/[a-z-]+\/[a-z0-9-]+$/.test(entry.href || '')) throw new StudioError('layout_changed', 'Expected an observed asset sidebar link; use asset-resolve for older cards.');
    const priorId = where.path.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/)?.[1] || null;
    await page.click('a[href="' + entry.href + '"]');
    // Native click completion is not SPA route completion. Only the exact
    // known previous source may remain during this bounded transition; a
    // third source still fails immediately, and the final identity guard stays.
    const data = await pollDOM({ evaluate: async () => {
      const next = unwrap(await page.evaluate(readAssetDOM));
      if (next.kind === 'ready' && next.asset_id !== id)
        return { kind: next.asset_id === priorId ? 'pending' : 'asset_mismatch' };
      return next;
    } }, readAssetDOM);
    if (data.asset_id !== id) throw new StudioError('asset_mismatch', 'Selected asset differs from the request.');
    where = unwrap(await page.evaluate(readLocation));
  }
  if (!(where.path.startsWith('/workspace/' + route + '/') && where.path.endsWith(id)) && where.path !== target) {
    const observed = unwrap(await page.evaluate(readRouteLinkDOM, id, route));
    if (!observed?.href || !/^\/workspace\/[a-z-]+\/[a-z0-9-]+$/.test(observed.href)) throw new StudioError('layout_changed', 'Expected one visible workspace route link.');
    await page.click('a[href="' + observed.href + '"]');
  }
  const data = await pollDOM(page, readAssetDOM);
  if (data.asset_id !== id) throw new StudioError('asset_mismatch', 'Selected asset differs from the request.');
  return data;
}
export async function inspectAsset(page, args) {
  const wait = Number(args.wait || 0);
  if (!Number.isInteger(wait) || wait < 0 || wait > 120) throw new StudioError('invalid_argument', 'wait must be 0-120 seconds.');
  await navigateAsset(page, args.asset);
  const end = Date.now() + wait * 1000;
  let data;
  do {
    data = await pollDOM(page, readAssetDOM);
    if (data.status === 'ready' || data.status === 'failed' || Date.now() >= end) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  } while (true);
  return [{ status: data.status, asset_id: data.asset_id, faces: data.faces, vertices: data.vertices,
    export_enabled: data.export_enabled, model_completed: data.status === 'ready', paid_submitted: false }];
}

export function readPanelDOM(operation) {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const route = { retopo: '/workspace/retopology/', rig: '/workspace/rigging/', image: '/workspace/generate' }[operation];
  if (!route || (operation === 'image' ? location.pathname !== route : !location.pathname.startsWith(route))) return { kind: 'pending' };
  const panels = document.querySelectorAll('div.rounded-r-5:has(h2)');
  if (panels.length !== 1) {
    if (/Something went wrong|Please try again later/.test(document.querySelector('main')?.innerText || '')) return { kind: 'site_error' };
    if (/Sign up\/Log in|Sign in|Log in/.test(document.body.innerText)) return { kind: 'login_required' };
    return { kind: 'pending' };
  }
  const panel = panels[0], heading = panel.querySelector('h2').innerText.trim();
  const expected = { retopo: 'Retopology', rig: '3D Rigging', image: 'Generate Model' }[operation];
  if (heading !== expected) return { kind: ['Retopology', '3D Rigging', 'Generate Model'].includes(heading) ? 'pending' : 'layout_changed' };
  const button = panel.querySelector('button.animate-button');
  if (!button || panel.querySelectorAll('button.animate-button').length !== 1) return { kind: 'pending' };
  const label = button.innerText.replace(/\s+/g, ' ').trim();
  const prefix = { retopo: 'Retopology', rig: 'Auto Rig', image: 'Generate' }[operation];
  if (!label.startsWith(prefix + ' ') || !/^\d+$/.test(label.slice(prefix.length + 1))) return { kind: 'layout_changed' };
  const price = Number(label.slice(prefix.length + 1));
  const credit = document.querySelector('[class~="i-tripo:bolt:search"]')?.parentElement?.querySelector('p[title]')?.getAttribute('title');
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(credit || '') || !Number.isSafeInteger(price) || price <= 0) return { kind: 'layout_changed' };
  const settings = {};
  let image = null;
  if (operation === 'retopo') {
    const topology = panel.querySelector('button[aria-pressed="true"]')?.innerText.trim();
    const count = panel.querySelector('input[type="text"]')?.value;
    const toggle = panel.querySelector('[role="switch"]')?.getAttribute('aria-checked');
    const slider = panel.querySelector('[role="slider"]');
    if (!['Quad', 'Triangle'].includes(topology) || !/^\d+$/.test(count || '') || !['true', 'false'].includes(toggle)) return { kind: 'layout_changed' };
    settings.topology = topology; settings.polygon_count = Number(count); settings.smart_mesh = toggle === 'true';
    settings.ui_min = Number(slider?.getAttribute('aria-valuemin')); settings.ui_max = Number(slider?.getAttribute('aria-valuemax'));
  } else if (operation === 'rig') {
    settings.rigging_type = panel.querySelector('[role="radio"][aria-checked="true"]')?.innerText.trim();
    const presets = Array.from(panel.querySelectorAll('button[aria-expanded]')).filter(el => ['ActorCore', 'Mixamo', 'UE5 Mannequin', 'VRM 1.0 Humanoid', 'Unity Humanoid Compatible'].includes(el.innerText.trim()));
    if (!['Humanoid', 'Other'].includes(settings.rigging_type) || presets.length > 1) return { kind: 'layout_changed' };
    settings.skeleton = presets[0]?.innerText.trim() || null;
    settings.warning = Array.from(panel.querySelectorAll('button')).find(el => /T- or A-pose/.test(el.innerText))?.innerText.trim() || null;
  } else {
    if (panel.querySelector('textarea')) return { kind: 'draft_present' };
    const files = panel.querySelector('input[type="file"]');
    if (!files || panel.querySelectorAll('input[type="file"]').length !== 1) return { kind: 'layout_changed' };
    const combos = Array.from(panel.querySelectorAll('[role="combobox"]'));
    settings.privacy = combos.find(el => /^(Private|Sharing Only)$/.test(el.innerText.trim()))?.innerText.trim();
    settings.model = combos.find(el => /Best Quality|Tripo/.test(el.innerText))?.innerText.trim();
    settings.switches = Array.from(panel.querySelectorAll('[role="switch"]')).map(el => el.getAttribute('aria-checked'));
    if (!settings.model || !settings.privacy || settings.switches.length !== 2 || settings.switches.some(s => !['true', 'false'].includes(s))) return { kind: 'layout_changed' };
    const selected = Array.from(files.files || []).map(f => ({ name: f.name, size: f.size, last_modified: f.lastModified }));
    const previews = Array.from(panel.querySelectorAll('img')).filter(el => el.getClientRects().length).map(el => {
      // Keep the opaque blob identity so replacing a cleared-input preview
      // changes the approved quote too. Strip search/hash authentication data.
      try { const url = new URL(el.getAttribute('src'), location.origin); return url.protocol === 'blob:' ? 'blob-preview:' + url.pathname : url.origin + url.pathname; } catch { return null; }
    });
    image = { files: selected, previews };
  }
  const match = location.pathname.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  return { kind: 'ready', operation, asset_id: match?.[1] || null, credits: Number(credit.replaceAll(',', '')), price, settings,
    image, button_enabled: !button.disabled && button.getAttribute('aria-disabled') !== 'true', button_label: label,
    blocked: /Not Ready for Auto-Rigging|Unknown server error|Task failed/i.test(panel.innerText) };
}
async function panelData(page, operation) { return pollDOM({ evaluate: () => page.evaluate(readPanelDOM, operation) }, readPanelDOM); }
export function quoteHash(data, imageSha = null) {
  return sha(JSON.stringify({ operation: data.operation, asset_id: data.asset_id, price: data.price, settings: data.settings, image: data.image, image_sha256: imageSha }));
}
export async function applySettings(page, operation, settings) {
  let before = await panelData(page, operation);
  if (operation === 'retopo') {
    if ('topology' in settings && settings.topology !== before.settings.topology) { await clickText(page, PANEL + ' button', settings.topology); before = await panelData(page, operation); }
    if ('smart_mesh' in settings && settings.smart_mesh !== before.settings.smart_mesh) { await page.setChecked(PANEL + ' [role="switch"]', settings.smart_mesh); before = await panelData(page, operation); }
    if ('polygon_count' in settings && settings.polygon_count !== before.settings.polygon_count) {
      if (!(before.settings.ui_min > 0 && before.settings.ui_max >= before.settings.ui_min) || settings.polygon_count < before.settings.ui_min || settings.polygon_count > before.settings.ui_max) throw new StudioError('invalid_argument', 'Polygon count is outside the observed UI limits.');
      await page.fillText(PANEL + ' input[type="text"]', String(settings.polygon_count)); await page.pressKey('Tab');
    }
  } else if (operation === 'rig') {
    if ('rigging_type' in settings && settings.rigging_type !== before.settings.rigging_type) { await clickText(page, PANEL + ' [role="radio"]', settings.rigging_type); before = await panelData(page, operation); }
    if ('skeleton' in settings && settings.skeleton !== before.settings.skeleton) {
      if (!before.settings.skeleton) throw new StudioError('invalid_argument', 'No skeleton selector for this rigging type.');
      await clickText(page, PANEL + ' button[aria-expanded]', before.settings.skeleton);
      await clickText(page, '[role="option"]', settings.skeleton);
    }
  }
  const after = await panelData(page, operation);
  if (Object.entries(settings).some(([key, value]) => after.settings[key] !== value)) throw new StudioError('settings_changed', 'UI did not retain the requested settings.');
  return after;
}
export async function operationQuote(page, args) {
  const settings = parseSettings(args.operation, args.settings);
  await navigateAsset(page, args.asset, args.operation);
  const data = await applySettings(page, args.operation, settings);
  if (data.asset_id !== args.asset) throw new StudioError('asset_mismatch', 'Quote belongs to another asset.');
  return [{ status: data.blocked ? 'blocked' : 'quoted', operation: args.operation, asset_id: data.asset_id,
    credits: data.credits, quoted_credits: data.price, settings: data.settings, button_enabled: data.button_enabled,
    quote_sha256: quoteHash(data), billing: 'studio_subscription', paid_submitted: false }];
}

function safeDirectory(path) {
  if (!isAbsolute(path) || resolve(path) === '/') throw new StudioError('unsafe_path', 'Use the exact absolute project path.');
  for (let p = resolve(path); ; p = dirname(p)) {
    if (existsSync(p) && (lstatSync(p).isSymbolicLink() || !lstatSync(p).isDirectory())) throw new StudioError('unsafe_path', 'Ledger parents must be direct directories.');
    if (p === dirname(p)) break;
  }
  mkdirSync(path, { recursive: true, mode: 0o700 });
}
function durable(path, data, exclusive = false) {
  if (existsSync(path) && lstatSync(path).isSymbolicLink()) throw new StudioError('unsafe_path', 'Receipt symlink rejected.');
  const dest = exclusive ? path : path + '.' + randomUUID() + '.tmp';
  const fd = openSync(dest, 'wx', 0o600);
  try { writeFileSync(fd, JSON.stringify(data)); fsyncSync(fd); } finally { closeSync(fd); }
  if (!exclusive) renameSync(dest, path);
  const parent = openSync(dirname(path), 'r');
  try { fsyncSync(parent); } finally { closeSync(parent); }
}
export function validateExecution(args, { paid = true } = {}) {
  if (args.confirm !== true) throw new StudioError('confirmation_required', 'Confirm the exact operation, source and quoted budget first.');
  const budget = Number(args.budget);
  if (paid && (!/^\d+$/.test(String(args.budget)) || !Number.isSafeInteger(budget) || budget < 1 || budget > 10000)) throw new StudioError('invalid_argument', 'budget must be 1-10000 credits.');
  if (!/^[a-f0-9]{64}$/.test(args.quote || '') || !/^[A-Za-z0-9_.:-]{1,160}$/.test(args.key || '')) throw new StudioError('invalid_argument', 'Use an approved quote digest and stable request key.');
  if (!isAbsolute(args.ledger || '') || resolve(args.ledger) === '/') throw new StudioError('unsafe_path', 'Use the exact approved project path.');
  return { ...args, budget };
}
export async function claimedOperation(args, fingerprint, work) {
  const directory = join(args.ledger, '.atm', 'tripo-studio-paid');
  safeDirectory(directory);
  const receiptPath = join(directory, 'extended-' + sha(args.key) + '.json');
  if (existsSync(receiptPath)) {
    if (lstatSync(receiptPath).isSymbolicLink() || lstatSync(receiptPath).size > 25000) throw new StudioError('receipt_invalid', 'Inspect the retained receipt.');
    let prior;
    try { prior = JSON.parse(readFileSync(receiptPath, 'utf8')); } catch { throw new StudioError('receipt_invalid', 'Inspect the retained receipt.'); }
    if (prior.fingerprint !== fingerprint) throw new StudioError('request_conflict', 'Stable key has different inputs.');
    if (!['submitted', 'quoted', 'exported'].includes(prior.status)) throw new StudioError('submission_unknown', 'Inspect the retained receipt and provider before any new request.');
    return { ...prior, reused: true };
  }
  const lock = join(directory, 'active.lock'); // Shared with the original text generation.
  try { durable(lock, { fingerprint, request_key: args.key, operation: args.operation }, true); }
  catch (error) { if (error.code === 'EEXIST') throw new StudioError('workspace_busy', 'A pending or uncertain operation retains the shared lock.'); throw error; }
  const record = { status: 'dispatch_claimed', fingerprint, request_key: args.key, operation: args.operation, created_at: new Date().toISOString() };
  let claimed = false;
  try {
    const result = await work(async stage => { record.stage = stage; durable(receiptPath, record, true); claimed = true; });
    Object.assign(record, result); durable(receiptPath, record);
    renameSync(lock, join(directory, 'released-' + randomUUID() + '.lock'));
    return { ...record, reused: false };
  } catch (error) {
    if (claimed) {
      record.status = 'submission_unknown'; record.failure_code = error instanceof StudioError ? error.code : 'bridge_failure';
      // Retain bounded typed diagnostics, never raw bridge messages/URLs which
      // can contain authentication or signed media parameters.
      const types = ['TypeError', 'TargetError', 'CommandExecutionError', 'Error'];
      record.failure_type = error instanceof StudioError ? 'StudioError' : types.includes(error?.name) ? error.name : 'unexpected_error';
      const codes = ['not_file_input', 'selector_not_found', 'selector_ambiguous', 'selector_nth_out_of_range', 'invalid_selector', 'COMMAND_EXEC', 'CDP_ERROR', 'EXTENSION_ERROR', 'BROWSER_NOT_CONNECTED'];
      if (codes.includes(error?.code)) record.bridge_error_code = error.code;
      if (String(error?.message || '').startsWith('setFileInput returned no count')) record.bridge_error_code = 'upload_backend_no_count';
      durable(receiptPath, record); // Keep shared lock too, including for uncertain upload/export.
      const cause = [record.failure_code, record.failure_type, record.bridge_error_code].filter(Boolean).join('/');
      throw new StudioError('submission_unknown', 'Operation may have reached Tripo; inspect retained ' + record.stage + ' receipt. Cause: ' + cause);
    }
    renameSync(lock, join(directory, 'not-submitted-' + randomUUID() + '.lock')); throw error;
  }
}
export function readSubmissionDOM(priorId) {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const match = location.pathname.match(/^\/workspace\/(?:generate|retopology|rigging)\/.*?([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  const processing = Array.from(document.querySelectorAll('main p')).some(el => el.getClientRects().length && /^(Generating\.{0,3}|Processing\.{0,3}|Retopologizing\.{0,3}|Rigging\.{0,3})$/i.test(el.innerText.trim()));
  if (match && (match[1] !== priorId || processing)) return { kind: 'ready', asset_id: match[1], acceptance: processing ? 'processing_ui_observed_not_model_completion' : 'new_asset_route_observed_not_model_completion' };
  return { kind: 'pending' };
}
export async function executePaid(page, raw) {
  const args = validateExecution(raw);
  if (!['retopo', 'rig'].includes(args.operation)) throw new StudioError('invalid_argument', 'Select retopo or rig.');
  assetId(args.asset);
  const fingerprint = sha(JSON.stringify([args.operation, args.asset, args.quote, args.budget]));
  const result = await claimedOperation(args, fingerprint, async claim => {
    await navigateAsset(page, args.asset, args.operation);
    const data = await panelData(page, args.operation);
    if (data.asset_id !== args.asset || quoteHash(data) !== args.quote || data.price > args.budget) throw new StudioError('quote_changed', 'Asset, price or settings differ from the approved quote.');
    if (data.blocked || !data.button_enabled) throw new StudioError('prerequisite_missing', 'Current asset does not meet the visible operation prerequisites.');
    if (data.credits < data.price) throw new StudioError('insufficient_credits', 'Balance is below the quote.');
    await claim('paid_click');
    await page.click(PANEL + ' button.animate-button');
    const accepted = await pollDOM({ evaluate: () => page.evaluate(readSubmissionDOM, args.asset) }, readSubmissionDOM);
    return { status: 'submitted', source_asset_id: args.asset, asset_id: accepted.asset_id, quoted_credits: data.price,
      max_credits: args.budget, quote_sha256: args.quote, settings: data.settings, paid_submitted: true, acceptance: accepted.acceptance };
  });
  return [result];
}

export function inspectImageFile(file, workspace) {
  if (!isAbsolute(file || '') || !isAbsolute(workspace || '') || !resolve(file).startsWith(resolve(workspace) + '/')) throw new StudioError('unsafe_path', 'Select an image within the approved project.');
  for (let p = resolve(file); p !== dirname(p); p = dirname(p)) if (existsSync(p) && lstatSync(p).isSymbolicLink()) throw new StudioError('unsafe_path', 'Image symlink rejected.');
  const info = lstatSync(file);
  if (!info.isFile() || info.size <= 0 || info.size > 20 * 1024 * 1024 || !/\.(png|jpe?g|webp)$/i.test(file)) throw new StudioError('invalid_image', 'Use a regular PNG/JPEG/WEBP up to 20 MiB.');
  const bytes = readFileSync(file);
  const png = bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]));
  const jpg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
  const webp = bytes.toString('ascii', 0, 4) === 'RIFF' && bytes.toString('ascii', 8, 12) === 'WEBP';
  if (!(png || jpg || webp)) throw new StudioError('invalid_image', 'File signature does not match an accepted raster image.');
  return { name: basename(file), size: info.size, sha256: sha(bytes) };
}
export async function imageQuote(page, raw) {
  if (raw.confirm !== true || !/^[A-Za-z0-9_.:-]{1,160}$/.test(raw.key || '')) throw new StudioError('confirmation_required', 'Explicit approval of this image upload and a stable key are required.');
  const info = inspectImageFile(raw.file, raw.ledger);
  const args = { ...raw, operation: 'image_upload' };
  const fingerprint = sha(JSON.stringify([args.operation, resolve(raw.file), info.sha256]));
  const result = await claimedOperation(args, fingerprint, async claim => {
    let where = unwrap(await page.evaluate(readLocation));
    if (where.origin !== ORIGIN || where.path !== '/workspace/generate') {
      if (where.origin !== ORIGIN) { await page.goto(ORIGIN + '/assets'); await pollDOM(page, readAccountDOM); }
      await page.click('a[href="/workspace/generate"]');
    }
    const before = await panelData(page, 'image');
    if (before.image.files.length || before.image.previews.length) throw new StudioError('draft_present', 'Existing image draft is preserved.');
    if (before.settings.privacy !== 'Private') throw new StudioError('privacy_changed', 'Select Private before uploading.');
    // The installed bridge passed DOM target/CDP preflight but failed its
    // uploadFiles/set-file-input path. Use the documented DOM file-input
    // operation directly, not a hidden provider request or JS file injection.
    if (typeof page.cdp !== 'function') throw new StudioError('upload_backend_missing', 'This image adapter requires the reviewed CDP DOM file-input bridge.');
    const doc = unwrap(await page.cdp('DOM.getDocument', { depth: 0 }));
    if (!Number.isSafeInteger(doc?.root?.nodeId) || doc.root.nodeId <= 0) throw new StudioError('bridge_protocol', 'Upload preflight did not return a DOM root node.');
    const input = unwrap(await page.cdp('DOM.querySelector', { nodeId: doc.root.nodeId, selector: PANEL + ' input[type="file"]' }));
    if (!Number.isSafeInteger(input?.nodeId) || input.nodeId <= 0) throw new StudioError('layout_changed', 'Upload preflight did not find the previously observed unique file input.');
    // Re-read bytes immediately before upload; the file is explicit, not a profile.
    if (inspectImageFile(raw.file, raw.ledger).sha256 !== info.sha256) throw new StudioError('input_changed', 'Image changed before upload.');
    await claim('image_upload');
    await page.cdp('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [raw.file] });
    const data = await pollDOM({ evaluate: async () => {
      const next = unwrap(await page.evaluate(readPanelDOM, 'image'));
      return next.kind === 'ready' && !(next.image.previews.length && next.button_enabled) ? { kind: 'pending' } : next;
    } }, readPanelDOM);
    if (data.image.files.length && (data.image.files.length !== 1 || data.image.files[0].name !== info.name || data.image.files[0].size !== info.size)) throw new StudioError('input_changed', 'Uploaded draft differs from the approved image.');
    return { status: 'quoted', asset_id: null, image_sha256: info.sha256, image_name: info.name,
      quoted_credits: data.price, credits: data.credits, settings: data.settings, image: data.image,
      quote_sha256: quoteHash(data, info.sha256), paid_submitted: false, acceptance: 'visible_image_preview_ready_not_generation' };
  });
  return [result];
}
export async function generateImage(page, raw) {
  const args = { ...validateExecution(raw), operation: 'image_generate' };
  if (!/^[a-f0-9]{64}$/.test(args.image_sha || '')) throw new StudioError('invalid_argument', 'Use the image SHA from the upload quote.');
  const fingerprint = sha(JSON.stringify([args.operation, args.image_sha, args.quote, args.budget]));
  return [await claimedOperation(args, fingerprint, async claim => {
    const where = unwrap(await page.evaluate(readLocation));
    if (where.origin !== ORIGIN || where.path !== '/workspace/generate') throw new StudioError('draft_missing', 'Use the quoted image draft without navigating away.');
    const data = await panelData(page, 'image');
    if (!data.image.previews.length || data.settings.privacy !== 'Private' || quoteHash(data, args.image_sha) !== args.quote || data.price > args.budget) throw new StudioError('quote_changed', 'Image draft, settings or price changed.');
    if (!data.button_enabled || data.credits < data.price) throw new StudioError('prerequisite_missing', 'Image is not ready or balance is insufficient.');
    await claim('paid_click'); await page.click(PANEL + ' button.animate-button');
    const accepted = await pollDOM({ evaluate: () => page.evaluate(readSubmissionDOM, null) }, readSubmissionDOM);
    return { status: 'submitted', asset_id: accepted.asset_id, image_sha256: args.image_sha,
      quoted_credits: data.price, max_credits: args.budget, quote_sha256: args.quote, settings: data.settings,
      paid_submitted: true, acceptance: accepted.acceptance };
  })];
}

export function readExportDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const dialogs = document.querySelectorAll('[role="dialog"]:has(input[maxlength="255"])');
  if (!dialogs.length) return { kind: 'pending' };
  if (dialogs.length !== 1) return { kind: 'layout_changed' };
  const dialog = dialogs[0], combos = Array.from(dialog.querySelectorAll('[role="combobox"]'));
  const button = dialog.querySelector('button.animate-button');
  if (!/^Export\s*$/.test(button?.innerText || '') || dialog.querySelectorAll('button.animate-button').length !== 1 || combos.length !== 2) return { kind: 'layout_changed' };
  const match = location.pathname.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  if (!match) return { kind: 'asset_mismatch' };
  return { kind: 'ready', operation: 'export', asset_id: match[1], price: 0,
    settings: { format: combos[0].innerText.trim(), texture_resolution: combos[1].innerText.replace(/\s+/g, ' ').trim() },
    filename: dialog.querySelector('input[maxlength="255"]').value, image: null,
    button_enabled: !button.disabled && button.getAttribute('aria-disabled') !== 'true' };
}
async function prepareExport(page, id) {
  await navigateAsset(page, id, 'export');
  const data = await pollDOM(page, readAssetDOM);
  if (data.status !== 'ready' || !data.export_enabled) throw new StudioError('model_not_ready', 'Wait for the completed model before export.');
  const open = unwrap(await page.evaluate(readExportDOM));
  if (open.kind === 'pending') await clickText(page, 'main button', 'Export');
  const quote = await pollDOM(page, readExportDOM);
  if (quote.asset_id !== id || quote.settings.format !== 'GLB') throw new StudioError('format_changed', 'This reviewed exporter supports GLB; select GLB in the local export dialog.');
  return quote;
}
export async function exportQuote(page, args) {
  const data = await prepareExport(page, assetId(args.asset));
  return [{ status: 'quoted', operation: 'export', asset_id: args.asset, quoted_credits: 0,
    settings: data.settings, quote_sha256: quoteHash(data), button_enabled: data.button_enabled,
    paid_submitted: false, acceptance: 'visible_unpriced_subscription_export_quote' }];
}
export function validateGLB(bytes) {
  if (bytes.length < 20 || bytes.length > 150 * 1024 * 1024 || bytes.toString('ascii', 0, 4) !== 'glTF' || bytes.readUInt32LE(4) !== 2 || bytes.readUInt32LE(8) !== bytes.length) throw new StudioError('invalid_download', 'Downloaded file is not a complete bounded GLB v2.');
  const length = bytes.readUInt32LE(12);
  if (bytes.readUInt32LE(16) !== 0x4e4f534a || length < 2 || length + 20 > bytes.length) throw new StudioError('invalid_download', 'GLB JSON chunk is invalid.');
  let json;
  try { json = JSON.parse(bytes.toString('utf8', 20, 20 + length).trim()); } catch { throw new StudioError('invalid_download', 'GLB JSON chunk failed to parse.'); }
  if (!json.meshes?.length || !json.meshes.some(m => m.primitives?.length)) throw new StudioError('invalid_download', 'GLB has no mesh primitives.');
  return { sha256: sha(bytes), bytes: bytes.length, mesh_count: json.meshes.length, validation: 'glb_v2_header_length_json_and_meshes' };
}
function writeDownload(output, bytes, workspace) {
  if (!isAbsolute(output || '') || !resolve(output).startsWith(resolve(workspace) + '/')) throw new StudioError('unsafe_path', 'Export output must be within the approved project.');
  safeDirectory(dirname(output));
  const info = validateGLB(bytes);
  const fd = openSync(output, 'wx', 0o600);
  try { writeFileSync(fd, bytes); fsyncSync(fd); } finally { closeSync(fd); }
  return { ...info, path: output };
}
export async function exportModel(page, raw) {
  const args = { ...validateExecution(raw, { paid: false }), operation: 'export' };
  assetId(args.asset);
  if (!isAbsolute(args.output || '') || !resolve(args.output).startsWith(resolve(args.ledger) + '/')) throw new StudioError('unsafe_path', 'Use an output path within this project.');
  const fingerprint = sha(JSON.stringify([args.operation, args.asset, args.quote]));
  const result = await claimedOperation(args, fingerprint, async claim => {
    if (existsSync(args.output)) throw new StudioError('unsafe_path', 'Existing export output is preserved.');
    const data = await prepareExport(page, args.asset);
    if (quoteHash(data) !== args.quote || !data.button_enabled) throw new StudioError('quote_changed', 'Export format, texture or asset changed.');
    const filename = 'atm-tripo-' + args.asset + '-' + sha(args.key).slice(0,10);
    await page.fillText(EXPORT_DIALOG + ' input[maxlength="255"]', filename);
    const final = await pollDOM(page, readExportDOM);
    if (final.filename !== filename || quoteHash(final) !== args.quote || !final.button_enabled) throw new StudioError('quote_changed', 'Final export parameters changed.');
    await claim('download_click');
    const waiting = page.waitForDownload(filename, 60000);
    // Attach rejection handling before click so a bridge failure is never unhandled.
    const captured = waiting.then(value => ({ value }), error => ({ error }));
    await page.click(EXPORT_DIALOG + ' button.animate-button');
    const download = await captured;
    if (download.error) throw download.error;
    const file = unwrap(download.value);
    if (!file?.downloaded || file.state !== 'complete' || !isAbsolute(file.filename || '') || !basename(file.filename).startsWith(filename) || !/\.glb$/i.test(file.filename)) throw new StudioError('download_unknown', 'A matching completed GLB download was not observed.');
    if (lstatSync(file.filename).isSymbolicLink() || !lstatSync(file.filename).isFile() || lstatSync(file.filename).size > 150 * 1024 * 1024) throw new StudioError('invalid_download', 'Download path must be a bounded regular file.');
    const artifact = writeDownload(args.output, readFileSync(file.filename), args.ledger);
    return { status: 'exported', asset_id: args.asset, quoted_credits: 0, quote_sha256: args.quote,
      paid_submitted: false, artifact, acceptance: 'completed_download_and_validated_glb' };
  });
  if (result.reused) {
    const original = result.artifact;
    if (!original?.path || !resolve(original.path).startsWith(resolve(args.ledger) + '/') || lstatSync(original.path).isSymbolicLink()) throw new StudioError('artifact_missing', 'Inspect the prior export artifact.');
    const bytes = readFileSync(original.path);
    if (sha(bytes) !== original.sha256) throw new StudioError('artifact_changed', 'Prior export artifact changed.');
    if (resolve(args.output) !== resolve(original.path)) result.artifact = writeDownload(args.output, bytes, args.ledger);
  }
  return [result];
}

export function readCollectionDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai' || location.pathname !== '/assets') return { kind: 'origin_mismatch' };
  const main = document.querySelector('main');
  if (!main) return { kind: 'pending' };
  if (/Something went wrong|Please try again later/.test(main.innerText)) return { kind: 'site_error' };
  // Observed tabs expose data-state, not aria-pressed. A click succeeding does
  // not prove the requested collection is selected (or stayed selected).
  const buttons = [...main.querySelectorAll('button')].filter(button => button.getClientRects().length);
  for (const label of ['Model', 'My Assets', 'All']) {
    const matches = buttons.filter(button => button.innerText.trim() === label);
    if (matches.length > 1) return { kind: 'collection_scope_changed' };
    if (!matches.length) {
      if (label === 'My Assets' && buttons.some(button => button.innerText.trim() === 'Image' && button.getAttribute('data-state') === 'active')) return { kind: 'collection_scope_mismatch' };
      return { kind: 'pending' };
    }
    const state = matches[0].getAttribute('data-state');
    if (!['active', 'inactive'].includes(state)) return { kind: 'collection_scope_changed' };
    if (state !== 'active') return { kind: 'collection_scope_mismatch' };
  }
  if (!/My Assets/.test(main.innerText)) return { kind: 'pending' };
  const items = [], seen = new Set(), cards = new Set();
  for (const img of main.querySelectorAll('img[alt]')) {
    const card = img.closest('div.group');
    if (!card?.getClientRects().length) continue;
    cards.add(card);
    let url;
    try { url = new URL(img.getAttribute('src'), location.origin); } catch { return { kind: 'layout_changed' }; }
    if (url.hostname !== 'tripo-data-public.rg1.data.tripo3d.com') return { kind: 'thumbnail_contract_changed' };
    const match = url.pathname.match(/^\/tripo-studio\/\d{8}\/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})\/studio_(?:mesh|mesh_gray|part|wireframe)\.webp$/);
    if (!match) return { kind: 'thumbnail_contract_changed' };
    if (!img.alt.trim() || img.alt.length > 1000) return { kind: 'layout_changed' };
    if (!seen.has(match[1])) { seen.add(match[1]); items.push({ preview_task_id: match[1], title: img.alt.trim(), task_status: null }); }
  }
  let scroll = main;
  while (scroll.parentElement && !(scroll.scrollHeight > scroll.clientHeight + 5 && /auto|scroll/.test(getComputedStyle(scroll).overflowY))) scroll = scroll.parentElement;
  const footer = main.querySelector('div.min-h-10');
  if (!footer) return { kind: items.length ? 'collection_footer_changed' : 'pending' };
  const empty = /^(No assets yet|No models yet|You have no assets)/i.test(main.innerText.trim());
  if (!items.length && !empty) return { kind: 'pending' };
  if (cards.size !== items.length) return { kind: 'collection_card_identity_changed' };
  return { kind: 'ready', items, rendered_cards: cards.size, scope_verified: true,
    at_end: scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 5,
    loading: !!footer.querySelector('[class*="loading"], [class*="animate-spin"]'),
    explicit_end: /^(No more assets|No more models|You have reached the end)\.?$/i.test(footer.innerText.trim()), empty };
}
export function readVisibleErrorDOM() {
  return { site_error: /Something went wrong|Please try again later/.test(document.querySelector('main')?.innerText || '') };
}
async function navigateAssets(page) {
  let where = unwrap(await page.evaluate(readLocation));
  if (where.origin !== ORIGIN) {
    await page.goto(ORIGIN + '/'); await pollDOM(page, readAccountDOM);
    where = unwrap(await page.evaluate(readLocation));
  }
  const error = unwrap(await page.evaluate(readVisibleErrorDOM));
  if (error.site_error) await clickText(page, 'a', 'Home');
  if (where.path !== '/assets' || error.site_error) await clickText(page, 'a', 'Assets');
  await pollDOM(page, readAccountDOM);
}
export async function assetsAll(page, args, { quietMs = 4000, pause = 250 } = {}) {
  const limit = Number(args.limit), pages = Number(args.pages);
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000 || !Number.isInteger(pages) || pages < 1 || pages > 50) throw new StudioError('invalid_argument', 'limit 1-1000 and pages 1-50 are required.');
  await navigateAssets(page);
  for (const text of ['Model', 'My Assets', 'All']) await clickText(page, 'main button', text);
  const found = new Map(); let data, stop = 'page_limit', rounds = 0;
  for (; rounds < pages; rounds++) {
    data = await pollDOM(page, readCollectionDOM);
    for (const item of data.items) found.set(item.preview_task_id, item);
    if (found.size >= limit) { stop = 'item_limit'; break; }
    if (data.explicit_end || data.empty) { stop = 'explicit_ui_end'; break; }
    const count = found.size;
    // The observed asset grid scrolls inside a div, not window. Use the bridge's
    // structured scroll-to on its visible sentinel, never window-only scroll.
    await page.scrollTo('main div.min-h-10');
    const end = Date.now() + quietMs;
    do {
      data = await pollDOM(page, readCollectionDOM);
      for (const item of data.items) found.set(item.preview_task_id, item);
      if (found.size > count || data.explicit_end || data.empty) break;
      if (Date.now() >= end) break;
      await new Promise(resolve => setTimeout(resolve, pause));
    } while (true);
    if (data.explicit_end || data.empty) { stop = 'explicit_ui_end'; break; }
    if (found.size === count && data.at_end && !data.loading) { stop = 'quiet_scroll_end_no_authoritative_total'; break; }
    if (found.size === count && data.loading) throw new StudioError('page_not_ready', 'Asset pagination remains loading; no full-list claim.');
  }
  const complete = stop === 'explicit_ui_end';
  const items = [...found.values()].slice(0, limit);
  return [{ status: complete ? 'ready' : 'partial', assets: items, returned_count: items.length,
    pages_scanned: Math.min(rounds + 1, pages), coverage: 'automatic_visible_scroll_scan', all_assets: complete,
    scope: { asset_type: 'Model', ownership: 'My Assets', filter: 'All' },
    site_wide_coverage: false, authoritative_total: null,
    coverage_evidence: { scope_verified: data.scope_verified === true, rendered_cards: data.rendered_cards ?? null,
      at_scroll_end: data.at_end === true, loading: data.loading === true,
      explicit_ui_end: data.explicit_end === true || data.empty === true },
    stop_reason: stop, secrets_returned: false, paid_submitted: false }];
}
export function readPreviewTargetDOM(preview) {
  const anchors = Array.from(document.querySelectorAll('main div.group > a'));
  const matches = anchors.map((anchor, nth) => {
    const image = anchor.querySelector('img[alt]');
    if (!image) return null;
    const path = new URL(image.getAttribute('src'), location.origin).pathname;
    return new RegExp('/' + preview + '/studio_(?:mesh|mesh_gray|part|wireframe)\\.webp$').test(path) ? nth : null;
  }).filter(index => index !== null);
  return { count: matches.length, nth: matches[0] };
}
export async function resolveAsset(page, args) {
  assetId(args.preview);
  await navigateAssets(page);
  for (const text of ['Model', 'My Assets', 'All']) await clickText(page, 'main button', text);
  let target = unwrap(await page.evaluate(readPreviewTargetDOM, args.preview));
  if (target.count === 0) {
    await assetsAll(page, { limit: 1000, pages: 50 });
    target = unwrap(await page.evaluate(readPreviewTargetDOM, args.preview));
  }
  if (target.count !== 1) throw new StudioError('asset_not_found', 'Preview card is not uniquely visible in the asset scan.');
  await page.click('main div.group > a', { nth: target.nth });
  await clickText(page, '[role="dialog"] button', 'Edit in Workspace');
  const data = await pollDOM(page, readAssetDOM);
  return [{ status: data.status, asset_id: data.asset_id, preview_task_id: args.preview, paid_submitted: false }];
}
