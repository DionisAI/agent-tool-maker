// Text-only paid path. Fixed DOM, explicit quote confirmation, durable pre-click claim.
import { createHash, randomUUID } from 'node:crypto';
import { existsSync, lstatSync, mkdirSync, openSync, closeSync, writeFileSync, readFileSync, fsyncSync, renameSync } from 'node:fs';
import { resolve, dirname, join, isAbsolute } from 'node:path';
import { ORIGIN, StudioError, pollDOM, unwrap, bundleDigest, readAccountDOM } from './core.mjs';

export const TEXT_MODE = 'button:has([class~="i-tripo:pen"])';
export const TEXT_INPUT = 'textarea[placeholder="Describe what you want to create in 3D…"]';
export const GENERATE_BUTTON = 'button.animate-button';
const hash = text => createHash('sha256').update(text).digest('hex');
export function paidDigest() {
  const sha = createHash('sha256').update(bundleDigest());
  for (const name of ['quote.js', 'generate.js', 'paid.mjs']) sha.update(name + '\0').update(readFileSync(new URL(name, import.meta.url))).update('\0');
  return sha.digest('hex');
}
export function checkPaidPin(pin) {
  if (!/^[a-f0-9]{64}$/.test(pin || '') || pin !== paidDigest()) throw new StudioError('definition_changed', 'Review and rebuild the paid adapter before execution.');
}

export function readWorkspaceDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai' || location.pathname !== '/workspace/generate') return { kind: 'origin_mismatch' };
  if (/Something went wrong|Please try again later/.test(document.querySelector('main')?.innerText || '')) return { kind: 'site_error' };
  const credit = document.querySelector('[class~="i-tripo:bolt:search"]')?.parentElement?.querySelector('p[title]');
  if (!credit) {
    if (/Sign up\/Log in|Sign in|Log in|登录/.test(document.body.innerText || '')) return { kind: 'login_required' };
    return { kind: 'pending' };
  }
  const credits = Number(credit.getAttribute('title')?.replaceAll(',', ''));
  const combos = Array.from(document.querySelectorAll('[role="combobox"]')).filter(el => el.getClientRects().length);
  const privacy = combos.find(el => /^(Private|Sharing Only)$/.test(el.innerText.trim()))?.innerText.trim();
  const model = combos.find(el => /Best Quality|Tripo/.test(el.innerText))?.innerText.trim();
  const buttons = Array.from(document.querySelectorAll('button')).filter(el => /^Generate\s*\d+$/.test(el.innerText.trim()));
  if (!model || !privacy || buttons.length !== 1 || !Number.isFinite(credits)) return { kind: 'pending' };
  const switches = Array.from(document.querySelectorAll('[role="switch"]')).map(el => el.getAttribute('aria-checked'));
  if (switches.length !== 2 || switches.some(value => !['true', 'false'].includes(value))) return { kind: 'layout_changed' };
  const price = Number(buttons[0].innerText.match(/\d+$/)[0]);
  if (document.querySelectorAll('button.animate-button').length !== 1 || !buttons[0].classList.contains('animate-button')) return { kind: 'layout_changed' };
  if (!Number.isSafeInteger(price) || price <= 0) return { kind: 'layout_changed' };
  const textarea = document.querySelector('textarea[placeholder="Describe what you want to create in 3D…"]');
  const pen = document.querySelector('button:has([class~="i-tripo:pen"])');
  if (!textarea && !pen) return { kind: 'pending' };
  return { kind: 'ready', credits, price, model, privacy, switches, text_mode: !!textarea,
    prompt_value: textarea?.value ?? null, button_label: buttons[0].innerText.replace(/\s+/g, ' ').trim(),
    button_enabled: !buttons[0].disabled && buttons[0].getAttribute('aria-disabled') !== 'true' };
}
export function quoteFingerprint(data) {
  return hash(JSON.stringify({ price: data.price, model: data.model, privacy: data.privacy, switches: data.switches, text_mode: data.text_mode }));
}
export function readLocationDOM() {
  return { origin: location.origin, path: location.pathname,
    workspace_link: document.querySelectorAll('a[href="/workspace/generate"]').length === 1 };
}
export async function prepareText(page) {
  const where = unwrap(await page.evaluate(readLocationDOM));
  // Preserve the existing form instead of reloading it. Tripo's normal SPA link
  // is the observed navigation contract, not its intermittently failing cold route.
  if (where?.origin !== ORIGIN || where?.path !== '/workspace/generate') {
    if (where?.origin !== ORIGIN || !where.workspace_link) {
      await page.goto(ORIGIN + '/assets');
      await pollDOM(page, readAccountDOM);
    }
    await page.click('a[href="/workspace/generate"]');
  }
  let data = await pollDOM(page, readWorkspaceDOM);
  if (!data.text_mode) {
    await page.click(TEXT_MODE);
    data = await pollDOM(page, readWorkspaceDOM);
  }
  if (!data.text_mode) throw new StudioError('layout_changed', 'Text generation field is absent.');
  return data;
}
export async function quote(page) {
  const data = await prepareText(page);
  return [{ status: 'quoted', credits: data.credits, quoted_credits: data.price, model: data.model,
    privacy: data.privacy, parts_enabled: data.switches[0] === 'true', texture_8k_enabled: data.switches[1] === 'true',
    quote_sha256: quoteFingerprint(data), billing: 'studio_subscription', paid_submitted: false }];
}
export function validatePaidArgs(args) {
  if (args.confirm !== true) throw new StudioError('confirmation_required', 'Explicit human approval is required before the paid command.');
  if (typeof args.prompt !== 'string' || !args.prompt.trim() || args.prompt.length > 1000 || /[\x00-\x08]/.test(args.prompt)) throw new StudioError('invalid_argument', 'Use a text prompt of 1-1000 characters.');
  if (!/^\d+$/.test(String(args.budget)) || !Number.isSafeInteger(Number(args.budget)) || Number(args.budget) < 1 || Number(args.budget) > 10000) throw new StudioError('invalid_argument', 'budget must be 1-10000 Studio credits.');
  if (!/^[a-f0-9]{64}$/.test(args.quote || '') || !/^[A-Za-z0-9_.:-]{1,160}$/.test(args.key || '')) throw new StudioError('invalid_argument', 'A reviewed quote digest and stable request key are required.');
  if (!isAbsolute(args.ledger || '') || resolve(args.ledger) === '/') throw new StudioError('invalid_argument', 'ledger must be the exact approved absolute project path.');
  return { ...args, budget: Number(args.budget), fingerprint: hash(JSON.stringify([args.prompt, Number(args.budget), args.quote])) };
}
function safeDir(directory) {
  for (let current = resolve(directory); ; current = dirname(current)) {
    if (existsSync(current) && (lstatSync(current).isSymbolicLink() || !lstatSync(current).isDirectory())) throw new StudioError('unsafe_path', 'Paid ledger path must not traverse symlinks or files.');
    if (dirname(current) === current) break;
  }
  mkdirSync(directory, { recursive: true, mode: 0o700 });
}
function writeDurable(file, value, exclusive = false) {
  if (existsSync(file) && lstatSync(file).isSymbolicLink()) throw new StudioError('unsafe_path', 'Paid receipt must not be a symlink.');
  const destination = exclusive ? file : file + '.' + randomUUID() + '.tmp';
  const fd = openSync(destination, 'wx', 0o600);
  try { writeFileSync(fd, JSON.stringify(value)); fsyncSync(fd); } finally { closeSync(fd); }
  if (!exclusive) renameSync(destination, file);
}
function existing(file, args) {
  if (!existsSync(file)) return null;
  if (lstatSync(file).isSymbolicLink() || lstatSync(file).size > 20000) throw new StudioError('receipt_invalid', 'Inspect the retained paid receipt; no automatic submission.');
  let receipt;
  try { receipt = JSON.parse(readFileSync(file, 'utf8')); } catch { throw new StudioError('receipt_invalid', 'Inspect the retained paid receipt; no automatic submission.'); }
  if (receipt.fingerprint !== args.fingerprint) throw new StudioError('request_conflict', 'This request key belongs to different paid inputs.');
  if (receipt.status !== 'submitted') throw new StudioError('submission_unknown', 'Reconcile the prior submission in Tripo; do not retry with another request key.');
  return [{ ...receipt, reused: true }];
}
export function readSubmittedDOM() {
  if (location.origin !== 'https://studio.tripo3d.ai') return { kind: 'origin_mismatch' };
  const match = location.pathname.match(/^\/workspace\/generate\/.*?([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  return match ? { kind: 'ready', asset_id: match[1] } : { kind: 'pending' };
}

export async function generate(page, rawArgs) {
  const args = validatePaidArgs(rawArgs);
  const directory = join(resolve(args.ledger), '.atm', 'tripo-studio-paid');
  safeDir(directory);
  const receiptPath = join(directory, hash(args.key) + '.json');
  const reused = existing(receiptPath, args);
  if (reused) return reused; // Before any navigation, fill or click.
  const lock = join(directory, 'active.lock');
  try { writeDurable(lock, { fingerprint: args.fingerprint, created_at: new Date().toISOString() }, true); }
  catch (error) {
    if (error.code === 'EEXIST') throw new StudioError('workspace_busy', 'A retained paid lock needs reconciliation, or another call is running.');
    throw error;
  }
  let claimed = false;
  const record = { status: 'dispatch_claimed', fingerprint: args.fingerprint, request_key: args.key,
    quote_sha256: args.quote, max_credits: args.budget, paid_submitted: null, created_at: new Date().toISOString() };
  try {
    const before = await prepareText(page);
    if (quoteFingerprint(before) !== args.quote || before.price > args.budget || before.privacy !== 'Private') throw new StudioError('quote_changed', 'Price or visible settings differ from the approved quote; no Generate click.');
    if (before.credits < before.price) throw new StudioError('insufficient_credits', 'Studio balance is below the displayed price.');
    if (before.prompt_value) throw new StudioError('draft_present', 'An existing text draft is preserved; use an empty generation panel.');
    await page.fillText(TEXT_INPUT, args.prompt);
    const current = unwrap(await page.evaluate(readWorkspaceDOM));
    if (current?.kind !== 'ready' || current.prompt_value !== args.prompt || !current.button_enabled || quoteFingerprint(current) !== args.quote || current.price > args.budget) throw new StudioError('quote_changed', 'Final prompt, price or settings changed; no Generate click.');
    record.quoted_credits = current.price;
    writeDurable(receiptPath, record, true); // Commit BEFORE the only paid click.
    claimed = true;
    await page.click(GENERATE_BUTTON);
    const result = await pollDOM(page, readSubmittedDOM, { timeout: 15000 });
    record.status = 'submitted'; record.asset_id = result.asset_id; record.paid_submitted = true;
    record.acceptance = 'new_asset_route_observed_not_model_completion';
    writeDurable(receiptPath, record);
    renameSync(lock, join(directory, 'released-' + randomUUID() + '.lock')); // Recoverable move, no deletion.
    return [{ ...record, reused: false }];
  } catch (error) {
    if (claimed) {
      record.status = 'submission_unknown';
      writeDurable(receiptPath, record);
      // Retain active.lock too: changing the key does not silently bypass uncertainty.
      throw new StudioError('submission_unknown', 'Paid click may have reached Tripo; inspect task history and retained receipt before any new submission.');
    }
    renameSync(lock, join(directory, 'not-submitted-' + randomUUID() + '.lock'));
    throw error;
  }
}
