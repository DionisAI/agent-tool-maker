// Fixed visible-DOM contract. No cookies, browser storage, tokens or private API.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

export const ORIGIN = 'https://studio.tripo3d.ai';
export class StudioError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
export function bundleDigest() {
  const hash = createHash('sha256');
  for (const name of ['account.js', 'assets.js', 'core.mjs']) {
    hash.update(name + '\0');
    hash.update(readFileSync(new URL(name, import.meta.url)));
    hash.update('\0');
  }
  return hash.digest('hex');
}
export function checkPin(value) {
  if (value && (!/^[a-f0-9]{64}$/.test(value) || value !== bundleDigest())) {
    throw new StudioError('definition_changed', 'Tripo adapter files changed; review and regenerate the ATM manifest.');
  }
}
export function parseLimit(value = 20) {
  if (!/^\d+$/.test(String(value)) || !Number.isSafeInteger(Number(value)) || Number(value) < 1 || Number(value) > 100) {
    throw new StudioError('invalid_argument', 'limit must be an integer between 1 and 100.');
  }
  return Number(value);
}

// Serialized by the bridge and executed only in the site's visible DOM.
export function readAccountDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const header = document.querySelector('header');
  if (!header) return { kind: 'pending' };
  const text = header.innerText || '';
  if (/Sign up\/Log in|Sign in|Log in|登录/.test(text)) return { kind: 'login_required' };
  const credit = header.querySelector('[class~="i-tripo:bolt:search"]')?.parentElement?.querySelector('p[title]');
  if (!credit) return { kind: 'pending' };
  const label = credit.getAttribute('title')?.trim();
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(label || '')) return { kind: 'layout_changed' };
  const credits = Number(label.replaceAll(',', ''));
  if (!Number.isFinite(credits)) return { kind: 'layout_changed' };
  return { kind: 'ready', credits };
}

export function readAssetsDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai' || location.pathname !== '/assets') return { kind: 'origin_mismatch' };
  const main = document.querySelector('main');
  if (!main) return { kind: 'pending' };
  if (/Something went wrong|Please try again later/.test(main.innerText || '')) return { kind: 'site_error' };
  if (!/My Assets/.test(main.innerText || '')) return { kind: 'pending' };
  const items = [], seen = new Set();
  for (const img of main.querySelectorAll('img[alt]')) {
    // Image may be opacity:0: the card draws the same image as a background.
    const card = img.closest('div.group');
    if (!card || !card.getClientRects().length) continue;
    let url;
    try { url = new URL(img.getAttribute('src'), location.origin); } catch { return { kind: 'layout_changed' }; }
    if (url.hostname !== 'tripo-data-public.rg1.data.tripo3d.com') continue;
    const match = url.pathname.match(/^\/tripo-studio\/\d{8}\/([a-f0-9-]{36})\/studio_mesh\.webp$/);
    if (!match || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(match[1])) return { kind: 'layout_changed' };
    const title = img.getAttribute('alt')?.trim();
    if (!title || title.length > 1000) return { kind: 'layout_changed' };
    if (seen.has(match[1])) continue;
    seen.add(match[1]);
    items.push({ preview_task_id: match[1], title, task_status: null });
    if (items.length > 200) return { kind: 'result_limit' };
  }
  if (!items.length) {
    // No observed empty-state contract yet: do not turn loading/drift into success [].
    return { kind: 'pending' };
  }
  return { kind: 'ready', items };
}

export function unwrap(value) {
  return value && typeof value === 'object' && 'session' in value && 'data' in value ? value.data : value;
}
export async function pollDOM(page, reader, { timeout = 15000, pause = 250 } = {}) {
  const end = Date.now() + timeout;
  while (true) {
    const data = unwrap(await page.evaluate(reader));
    if (!data || typeof data !== 'object' || !data.kind) throw new StudioError('bridge_protocol', 'Unexpected browser bridge result.');
    if (data.kind === 'ready') return data;
    if (data.kind === 'login_required') throw new StudioError('login_required', 'Sign in to Tripo Studio in the local browser; credentials stay there.');
    if (data.kind !== 'pending') throw new StudioError(data.kind, 'Tripo visible-DOM contract changed; no action was submitted.');
    if (Date.now() >= end) throw new StudioError('page_not_ready', 'Tripo data did not become ready; inspect login, loading or empty-state UI.');
    await new Promise(resolve => setTimeout(resolve, pause));
  }
}
export async function account(page) {
  await page.goto(ORIGIN + '/assets');
  const data = await pollDOM(page, readAccountDOM);
  return [{ status: 'ready', logged_in: true, credits: data.credits, billing: 'studio_subscription',
    source: 'visible_header', secrets_returned: false, paid_submitted: false }];
}
export async function assets(page, limit) {
  limit = parseLimit(limit);
  await page.goto(ORIGIN + '/assets');
  await pollDOM(page, readAccountDOM);
  const data = await pollDOM(page, readAssetsDOM);
  return [{ status: 'ready', assets: data.items.slice(0, limit), returned_count: Math.min(limit, data.items.length),
    loaded_count: data.items.length, coverage: 'currently_loaded_cards', all_assets: false,
    secrets_returned: false, paid_submitted: false }];
}
