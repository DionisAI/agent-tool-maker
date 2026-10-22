import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';

// A pending Higgsfield ATM login: the refusal line and 取消登录, in the console view model as the page loads it.
const root = new URL('../src/agent_tool_maker/data/web/', import.meta.url);
const context = vm.createContext({window: {}});
for (const name of ['brand-data.js', 'brands.js', 'model.js']) vm.runInContext(readFileSync(new URL(name, root), 'utf8'), context, {filename: name});
const M = context.window.ATM_MODEL, T = M.T, O = T.oauth;
const NOW = 1_800_000_000;
const plain = value => JSON.parse(JSON.stringify(value));
const CANCEL = {label: '取消登录', kind: 'oauth-cancel', target: 'higgsfield'};

function data(oauth) {
  return {
    overview: {version: '0.8.0', home: '/fake/home', agents: [], credits: {providers: []}},
    tools: [], connections: {connections: [], oauth, vault: {backend: 'keyring', state: 'unlock_not_checked'}, verification_history: []},
    jobs: [], clis: [], sync: {device: null, peers: [], records: []}, access: {grants: [], clock: NOW, broker: null, requests: []},
    extensions: {custom_tools: [], credential_slots: [], browser_sessions: []}, session: {unlocked: false}, passkeys: {credentials: []},
  };
}
const login = (status, extra = {}) => ({provider: 'higgsfield', status, keep_login: false, service: {status: 'not_installed'}, ...extra});
const route = model => model.byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');

test('the refusal line says how it looks, names both possible causes and points to the higgsfield 程序 route', () => {
  for (const word of ['Higgsfield（Clerk）', 'JSON', 'authorization_invalid', '“Unauthorized request”', 'ATM 客户端'])
    assert.ok(O.refused.includes(word), word);
  // Two causes are possible; the copy names both and claims neither.
  assert.ok(O.refused.includes('可能它只允许部分 OAuth 客户端') && O.refused.includes('也可能你的套餐不含 MCP'));
  for (const word of ['一定', '肯定', '原因是', '因为']) assert.ok(!O.refused.includes(word), word);
  for (const word of ['“higgsfield 程序”', '官方命令行', 'higgsfield auth login', '同样的 Higgsfield 工具']) assert.ok(O.refused.includes(word), word);
  assert.equal(O.cancel, '取消登录');
  const texts = Object.entries(plain(O));
  assert.ok(texts.length >= 6);
  for (const [key, text] of texts) {
    assert.equal(typeof text, 'string', key);
    assert.ok(text.trim() && !/[{}]/.test(text), key);
    assert.ok(!/[一-鿿][A-Za-z0-9]|[A-Za-z0-9][一-鿿]/.test(text), key + ': ' + text);
    assert.ok(!/[一-鿿] [一-鿿]/.test(text), key + ': ' + text);
  }
  // The results of 取消登录 say what is true now.
  assert.ok(O.cancelled.includes('已取消') && O.cancelled.includes('higgsfield 程序'));
  assert.ok(O.restored.includes('原来的 ATM 登录继续有效'));
  assert.ok(O.ended.includes('已经结束'));
  assert.equal(T.errorText('oauth_cancelled'), '你取消了这次登录。');
  assert.ok(T.errorText('oauth_exchanging').includes('刷新状态') && !T.errorText('oauth_exchanging').includes('oauth_'));
});

test('while the ATM login is pending, its route explains a refusal and offers 取消登录 next to 刷新状态', () => {
  const r = route(M.derive(data([login('pending', {login_deadline: NOW + 300})]), NOW));
  assert.equal(r.word, '等你在浏览器里确认');
  assert.ok(r.body.includes(O.refused));
  assert.equal(r.actions[0].label, '刷新状态');  // Its primary look may move to the service header (one per page).
  assert.deepEqual(plain(r.actions[1]), CANCEL);
  assert.equal(r.actions.filter(a => a.label === '取消登录').length, 1);
  // No other state has either.
  for (const status of ['missing', 'ready', 'refreshing', 'expired', 'needs_login', 'denied', 'refresh_unknown']) {
    const other = route(M.derive(data([login(status, {expires_at: NOW + 600})]), NOW));
    assert.ok(!other.body.includes(O.refused), status);
    assert.ok(!other.actions.some(a => a.kind === 'oauth-cancel'), status);
  }
});

test('the 首页 pending line carries the refusal line and 取消登录 beside 刷新状态', () => {
  const model = M.derive(data([login('pending', {login_deadline: NOW + 300})]), NOW);
  const line = model.inbox.find(i => i.id === 'oauth-pending:higgsfield');
  assert.equal(line.title, '等你在浏览器里完成 Higgsfield 登录');
  assert.ok(line.detail.endsWith('完成后点“刷新状态”。' + O.refused), line.detail);
  assert.deepEqual(plain(line.action), {label: '刷新状态', kind: 'refresh'});
  assert.deepEqual(plain(line.also), [CANCEL]);
  for (const item of M.derive(data([login('needs_login')]), NOW).inbox) assert.equal(item.also, undefined, item.id);
});

test('a cancelled login reads as cancelled, with the code under 技术信息; a restored one stays ready', () => {
  let r = route(M.derive(data([login('needs_login', {last_error: 'oauth_cancelled'})]), NOW));
  assert.equal(r.word, '需要重新登录');
  assert.deepEqual(plain(r.facts.find(([term]) => term === '最近一次失败')), ['最近一次失败', '你取消了这次登录。']);
  assert.equal(r.tech, 'oauth_cancelled');
  assert.equal(r.actions[0].label, '重新登录');
  const line = M.derive(data([login('needs_login', {last_error: 'oauth_cancelled'})]), NOW).inbox.find(i => i.id === 'oauth:needs_login');
  assert.equal(line.action.label, '重新登录');
  r = route(M.derive(data([login('ready', {expires_at: NOW + 3600, last_error: 'oauth_cancelled'})]), NOW));
  assert.equal(r.state, 'ready');
  assert.deepEqual(plain(r.facts.find(([term]) => term === '最近一次失败')), ['最近一次失败', '你取消了这次登录。']);
});
