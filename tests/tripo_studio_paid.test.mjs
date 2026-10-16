import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, existsSync, symlinkSync } from 'node:fs';
import { join } from 'node:path';
import { generate, quote, prepareText, quoteFingerprint, readWorkspaceDOM, readSubmittedDOM, readLocationDOM, validatePaidArgs, paidDigest, checkPaidPin, GENERATE_BUTTON } from '../examples/opencli/tripo-studio/paid.mjs';

const FORM = { kind: 'ready', credits: 20155, price: 40, model: 'H3.1 – Best Quality', privacy: 'Private', switches: ['false', 'false'], text_mode: true, prompt_value: '', button_label: 'Generate 40', button_enabled: true };
const ASSET = '11111111-2222-3333-4444-555555555555';
function args(extra = {}) { return { prompt: 'One blue cube', budget: 40, quote: quoteFingerprint(FORM), key: 'fake-paid-once', confirm: true, ledger: mkdtempSync('/private/tmp/atm-tripo-paid-'), ...extra }; }
function fakePage(a, { form = {}, failClick = false } = {}) {
  const calls = []; const data = { ...FORM, ...form };
  return { calls,
    goto: async () => calls.push('goto'),
    evaluate: async fn => fn === readLocationDOM ? { origin: 'https://studio.tripo3d.ai', path: '/workspace/generate', workspace_link: true } : fn === readWorkspaceDOM ? { ...data } : fn === readSubmittedDOM ? { kind: 'ready', asset_id: ASSET } : assert.fail('Unknown DOM reader'),
    fillText: async (_, text) => { calls.push('fill'); data.prompt_value = text; },
    click: async selector => {
      assert.equal(selector, GENERATE_BUTTON);
      const dir = join(a.ledger, '.atm/tripo-studio-paid');
      const receipts = readdirSync(dir).filter(name => name.endsWith('.json'));
      assert.equal(receipts.length, 1);
      assert.equal(JSON.parse(readFileSync(join(dir, receipts[0]))).status, 'dispatch_claimed');
      calls.push('paid_click');
      if (failClick) throw new Error('fixture transport disconnected');
    },
  };
}
test('paid adapter pin mandatory and checks all code', () => { checkPaidPin(paidDigest()); assert.throws(() => checkPaidPin(''), /review/i); assert.throws(() => checkPaidPin('0'.repeat(64)), /review/i); });
test('quote preserves existing page/draft: no reload, fill or generate', async () => { const a = args(); const p = fakePage(a, { form: { prompt_value: 'Existing draft' } }); const q = (await quote(p))[0]; assert.equal(q.quoted_credits, 40); assert.equal(q.paid_submitted, false); assert.deepEqual(p.calls, []); });
test('confirmation mandatory before browser work', async () => { const a = args({ confirm: false }); const p = fakePage(a); await assert.rejects(generate(p, a), e => e.code === 'confirmation_required'); assert.deepEqual(p.calls, []); });
test('strict arguments and canonical budget fingerprint', () => { const a = args(); for (const extra of [{ budget: 0 }, { budget: 1.5 }, { prompt: 'x'.repeat(1001) }, { quote: '' }, { key: '../bad' }, { ledger: '/' }]) assert.throws(() => validatePaidArgs({ ...a, ...extra })); assert.equal(validatePaidArgs(a).fingerprint, validatePaidArgs({ ...a, budget: '40' }).fingerprint); });
test('changed price/model/settings or insufficient credit stops before fill/click', async () => { for (const form of [{ price: 65 }, { model: 'Other Model' }, { privacy: 'Sharing Only' }, { switches: ['true', 'false'] }, { credits: 10 }]) { const a = args(); const p = fakePage(a, { form }); await assert.rejects(generate(p, a)); assert.deepEqual(p.calls, []); } });
test('credit ceiling below quoted price stops before fill/click', async () => { const a = args({ budget: 39 }); const p = fakePage(a); await assert.rejects(generate(p, a), e => e.code === 'quote_changed'); assert.deepEqual(p.calls, []); });
test('final price drift after filling stops before receipt claim or paid click', async () => {
  const a = args(); const p = fakePage(a); const original = p.evaluate; let filled = false;
  p.fillText = async (_, text) => { p.calls.push('fill'); filled = true; };
  p.evaluate = async fn => filled && fn === readWorkspaceDOM ? { ...FORM, price: 65, prompt_value: a.prompt } : original(fn);
  await assert.rejects(generate(p, a), e => e.code === 'quote_changed');
  assert.deepEqual(p.calls, ['fill']);
  const directory = join(a.ledger, '.atm/tripo-studio-paid');
  assert.equal(readdirSync(directory).filter(name => name.endsWith('.json')).length, 0);
  assert.equal(existsSync(join(directory, 'active.lock')), false);
});
test('visible Workspace SPA link avoids cold route reload from assets', async () => {
  const calls = [];
  const p = { evaluate: async fn => fn === readLocationDOM ? { origin: 'https://studio.tripo3d.ai', path: '/assets', workspace_link: true } : { ...FORM },
    goto: async () => assert.fail('Use observed SPA link instead of reloading'),
    click: async selector => calls.push(selector) };
  assert.equal((await prepareText(p)).kind, 'ready');
  assert.deepEqual(calls, ['a[href="/workspace/generate"]']);
});
test('existing private draft preserved', async () => { const a = args(); const p = fakePage(a, { form: { prompt_value: 'Keep this draft' } }); await assert.rejects(generate(p, a), e => e.code === 'draft_present'); assert.deepEqual(p.calls, []); });
test('claim precedes only click; success says submitted, not model completed; reuse performs no browser action', async () => { const a = args(); const p = fakePage(a); const result = (await generate(p, a))[0]; assert.equal(result.status, 'submitted'); assert.equal(result.asset_id, ASSET); assert.match(result.acceptance, /not_model_completion/); assert.deepEqual(p.calls, ['fill', 'paid_click']); p.calls.length = 0; assert.equal((await generate(p, a))[0].reused, true); assert.deepEqual(p.calls, []); await assert.rejects(generate(p, { ...a, prompt: 'Changed' }), e => e.code === 'request_conflict'); });
test('click failure retains receipt and active lock; same or new keys do not resubmit', async () => { const a = args(); const p = fakePage(a, { failClick: true }); await assert.rejects(generate(p, a), e => e.code === 'submission_unknown'); assert.ok(existsSync(join(a.ledger, '.atm/tripo-studio-paid/active.lock'))); p.calls.length = 0; await assert.rejects(generate(p, a), e => e.code === 'submission_unknown'); await assert.rejects(generate(p, { ...a, key: 'do-not-bypass' }), e => e.code === 'workspace_busy'); assert.deepEqual(p.calls, []); });
test('symlink ledger never reaches browser', async () => { const root = mkdtempSync('/private/tmp/atm-tripo-symlink-'); const target = mkdtempSync('/private/tmp/atm-tripo-target-'); const link = join(root, 'link'); symlinkSync(target, link); const a = args({ ledger: link }); const p = fakePage(a); await assert.rejects(generate(p, a), e => e.code === 'unsafe_path'); assert.deepEqual(p.calls, []); });
