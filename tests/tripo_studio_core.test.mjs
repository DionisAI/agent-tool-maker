import test from 'node:test';
import assert from 'node:assert/strict';
import { account, assets, checkPin, parseLimit, pollDOM, readAccountDOM, readAssetsDOM, bundleDigest } from '../examples/opencli/tripo-studio/core.mjs';

function fixture({ credits = '20,155', login = false, origin = 'https://studio.tripo3d.ai', cards = [], mainText = 'Model My Assets All' } = {}) {
  globalThis.location = { origin, pathname: '/assets' };
  const header = { innerText: login ? 'Sign up/Log in' : 'Upgrade', querySelector: () => credits === null ? null :
    { parentElement: { querySelector: () => ({ getAttribute: () => credits }) } } };
  const main = { innerText: mainText, querySelectorAll: () => cards };
  globalThis.document = { querySelector: selector => selector === 'header' ? header : main };
}
function card(id, title = 'fixture model', src = null) {
  return { closest: () => ({ getClientRects: () => [1] }), getAttribute: key => key === 'alt' ? title :
    src || `https://tripo-data-public.rg1.data.tripo3d.com/tripo-studio/20261002/${id}/studio_mesh.webp?Signature=FAKE_SECRET&Policy=FAKE_POLICY` };
}
const ID = '11111111-2222-3333-4444-555555555555';

test('credits are numeric and no identity/auth data is returned', () => { fixture(); assert.deepEqual(readAccountDOM(), { kind: 'ready', credits: 20155 }); });
test('login wall and pending credits are distinct', () => { fixture({ login: true }); assert.equal(readAccountDOM().kind, 'login_required'); fixture({ credits: null }); assert.equal(readAccountDOM().kind, 'pending'); });
test('malformed and abbreviated credits fail visibly', () => { for (const credits of ['20k', '1,23', '-1', 'NaN']) { fixture({ credits }); assert.equal(readAccountDOM().kind, 'layout_changed'); } });
test('origin mismatch never yields account or asset data', () => { fixture({ origin: 'https://example.com' }); assert.equal(readAccountDOM().kind, 'origin_mismatch'); assert.equal(readAssetsDOM().kind, 'origin_mismatch'); });
test('signed links stripped; preview task id not treated as completed job', () => { fixture({ cards: [card(ID), card(ID)] }); const data = readAssetsDOM(); assert.deepEqual(data.items, [{ preview_task_id: ID, title: 'fixture model', task_status: null }]); assert.doesNotMatch(JSON.stringify(data), /Signature|Policy|FAKE|https:/); });
test('loading or unobserved empty state is not successful empty array', () => { fixture(); assert.equal(readAssetsDOM().kind, 'pending'); });
test('provider error is distinct from loading and empty', () => { fixture({ mainText: 'Something went wrong Please try again later' }); assert.equal(readAssetsDOM().kind, 'site_error'); });
test('changed thumbnail contract fails instead of guessing id', () => { fixture({ cards: [card(ID, 'model', 'https://tripo-data-public.rg1.data.tripo3d.com/changed/model.webp')] }); assert.equal(readAssetsDOM().kind, 'layout_changed'); });
test('strict input bounds', () => { for (const value of [0, 101, -1, 1.5, true, 'x', '']) assert.throws(() => parseLimit(value), /integer/); assert.equal(parseLimit(1), 1); });
test('bundle pin detects drift', () => { checkPin(bundleDigest()); assert.throws(() => checkPin('0'.repeat(64)), /changed/); });
test('bridge envelope and failures are classified', async () => { assert.equal((await pollDOM({ evaluate: async () => ({ session: 'fake', data: { kind: 'ready', credits: 1 } }) }, readAccountDOM)).credits, 1); await assert.rejects(pollDOM({ evaluate: async () => ({ kind: 'login_required' }) }, readAccountDOM), e => e.code === 'login_required'); await assert.rejects(pollDOM({ evaluate: async () => ({ kind: 'pending' }) }, readAccountDOM, { timeout: 0 }), e => e.code === 'page_not_ready'); });
test('account and bounded assets only navigate/evaluate; never click, fetch or read storage', async () => { const calls = []; fixture({ cards: [card(ID)] }); const page = { goto: async url => calls.push(url), evaluate: async fn => fn() }; assert.equal((await account(page))[0].paid_submitted, false); const result = (await assets(page, 1))[0]; assert.equal(result.returned_count, 1); assert.equal(result.all_assets, false); assert.deepEqual(calls, Array(2).fill('https://studio.tripo3d.ai/assets')); });
