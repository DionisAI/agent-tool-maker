import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';

// The Fake-IP copy and hint mapping of the console view model, loaded as the page loads it.
const root = new URL('../src/agent_tool_maker/data/web/', import.meta.url);
const context = vm.createContext({window: {}});
for (const name of ['brand-data.js', 'brands.js', 'model.js']) vm.runInContext(readFileSync(new URL(name, root), 'utf8'), context, {filename: name});
const M = context.window.ATM_MODEL, T = M.T, N = T.network;
const NOW = 1_800_000_000;
const plain = value => JSON.parse(JSON.stringify(value));
const LEAD = '官方地址被解析成了 198.18.x.x（通常是网络代理的 Fake-IP 模式，例如 Shadowrocket、Clash、Surge）。ATM 默认不连接这类地址，所以没有发出任何请求。';

function data({network, oauth = [], jobs = [], tools = []} = {}) {
  return {
    overview: {version: '0.8.0', home: '/fake/home', agents: [], credits: {providers: []}, ...(network === undefined ? {} : {network})},
    tools, connections: {connections: [], oauth, vault: {backend: 'keyring', state: 'unlock_not_checked'}, verification_history: []},
    jobs, clis: [], sync: {device: null, peers: [], records: []}, access: {grants: [], clock: NOW, broker: null, requests: []},
    extensions: {custom_tools: [], credential_slots: [], browser_sessions: []}, session: {unlocked: false}, passkeys: {credentials: []},
  };
}
const refused = (extra = {}) => ({provider: 'higgsfield', status: 'needs_login', keep_login: false, last_error: 'oauth_dns_policy',
  last_error_hint: 'fake_ip_tunnel', service: {status: 'not_installed'}, ...extra});
const fal = {id: 'fal.generate', title: 'fal.generate', provider: 'fal', adapter: 'fal', capabilities: [], permissions: [], paid: true,
  credentials: ['fal'], optional_credentials: [], enabled: true, health: {id: 'fal.generate', state: 'configured_not_verified'}};
const job = (status, extra = {}) => ({id: 'job-' + status, tool: 'fal.generate', status, kind: 'tool', created: NOW - 60, updated: NOW - 30,
  verification: null, cost_usd: null, cost_status: 'unknown', artifact_count: 0, ...extra});

test('the hint picks the Fake-IP sentence; the code alone keeps a plain Chinese one with its technical text', () => {
  assert.equal(T.errorText('oauth_dns_policy', 'fake_ip_tunnel'), LEAD);
  assert.equal(N.oauth, LEAD);
  const plainLogin = T.errorText('oauth_dns_policy');
  assert.equal(plainLogin, 'Higgsfield 的官方登录地址被解析成了本机、局域网或其他保留地址。ATM 不连接这类地址，所以没有发出任何请求。');
  assert.ok(!plainLogin.includes('198.18') && !plainLogin.includes('oauth_dns_policy'));
  assert.equal(T.errorText('unsafe_download', 'fake_ip_tunnel'), N.request);
  assert.equal(T.errorText('unsafe_download'), '服务地址被解析成了本机、局域网或其他保留地址。ATM 不连接这类地址，所以没有发出这个请求。');
  assert.equal(T.errorText('dns_error'), '找不到服务地址（域名解析失败）。请检查网络或代理后再试。');
  // The hint means nothing on another code, and another hint means nothing on these codes.
  assert.equal(T.errorText('vault_locked', 'fake_ip_tunnel'), T.errorText('vault_locked'));
  assert.equal(T.errorText('oauth_login_timeout', 'fake_ip_tunnel'), '登录超时，请重新登录。');
  assert.equal(T.errorText('oauth_dns_policy', 'other_hint'), plainLogin);
  assert.equal(T.errorText('oauth_strange', 'fake_ip_tunnel'), 'Higgsfield 登录没有完成（oauth_strange）。');
  for (const [code, hint, yes] of [['oauth_dns_policy', 'fake_ip_tunnel', true], ['unsafe_download', 'fake_ip_tunnel', true],
    ['dns_error', 'fake_ip_tunnel', false], ['oauth_dns_policy', undefined, false], ['constructor', 'fake_ip_tunnel', false]])
    assert.equal(T.fakeIpHint(code, hint), yes, code + ' ' + hint);
  for (const code of ['oauth_dns_policy', 'unsafe_download', 'dns_error', 'oauth_network']) {
    assert.ok(T.knownError(code), code);
    assert.ok(T.keepsDetail(code), code);  // 技术信息 stays under the Chinese sentence.
  }
  assert.ok(!T.keepsDetail('vault_locked') && !T.keepsDetail('constructor'));
});

test('the Fake-IP copy is complete, has no raw placeholder and keeps CJK-Latin spacing', () => {
  assert.equal(N.allow, '允许通过本机代理连接…');
  assert.equal(N.allowed, '已允许。再点一次“打开官方登录页面”。');
  // A passphrase vault: the failed attempt cleared the field, so the line asks for it again.
  assert.equal(N.allowedPassphrase, '已允许。输入 ATM 主密码后，再点一次“打开官方登录页面”。');
  assert.equal(T.allowedNext('重新登录'), '已允许。再点“重新登录”。');
  assert.equal(N.label, '通过本机代理的 Fake-IP 连接（198.18.0.0/15）');
  assert.equal(N.confirm, '允许');
  for (const word of ['198.18.0.0/15']) assert.ok(N.changes.includes(word));
  // Honest about what stays: only answers resolved straight to private addresses; the proxy decides where it forwards.
  for (const word of ['HTTPS 证书', '直接解析成本机、局域网或其他私有地址的应答', '固定的官方域名']) assert.ok(N.stays.includes(word), word);
  assert.ok(!N.stays.includes('仍然拒绝本机'));
  assert.ok(N.tradeoff.includes('真实目的地址') && N.tradeoff.includes('代理负责') && N.tradeoff.includes('由代理决定'));
  assert.ok(N.onDetail.includes('直接解析成') && N.onDetail.includes('由代理决定'));
  for (const word of ['fake-ip-filter', 'always-real-ip', 'Clash', 'Surge', 'Shadowrocket', 'mcp.higgsfield.ai', 'clerk.higgsfield.ai']) assert.ok(N.alternative.includes(word), word);
  assert.ok(!N.alternative.includes('这些域名'));
  for (const word of T.networkLiterals) assert.ok(N.alternative.includes(word) || N.owner.includes(word), word);  // Shown as unbreakable code.
  // The cause is likely, not certain: no copy asserts that a proxy is running.
  for (const key of ['oauth', 'request', 'download']) assert.ok(N[key].includes('通常是网络代理的 Fake-IP 模式') && !N[key].includes('你的网络代理'), key);
  // Honest about the boundary: no ATM command writes it, but a program running as the owner can (SECURITY.md).
  for (const word of ['没有 ATM 命令', '以你的用户身份运行的程序', 'SECURITY.md']) assert.ok(N.owner.includes(word), word);
  assert.ok(!N.owner.includes('都不能'));
  const texts = Object.entries(plain(N));
  assert.ok(texts.length >= 20);
  for (const [key, text] of texts) {
    assert.equal(typeof text, 'string', key);
    assert.ok(text.trim(), key);
    assert.ok(!/[{}]/.test(text), key);
    assert.ok(!/[一-鿿][A-Za-z0-9]|[A-Za-z0-9][一-鿿]/.test(text), key + ': ' + text);
    assert.ok(!/[一-鿿] [一-鿿]/.test(text), key + ': ' + text);
  }
  for (const code of ['oauth_dns_policy', 'unsafe_download', 'dns_error', 'oauth_network']) {
    const text = T.error[code];
    assert.ok(!/[{}]/.test(text) && !/[一-鿿][A-Za-z0-9]|[A-Za-z0-9][一-鿿]/.test(text), code);
  }
});

test('the ATM login route and inbox explain a Fake-IP refusal and offer the switch only while it is off', () => {
  let model = M.derive(data({oauth: [refused()]}), NOW);
  let route = model.byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
  assert.ok(route.body.includes(LEAD));
  const allow = route.actions.find(a => a.label === N.allow);
  // C6 names the login to click again; it never retries it.
  assert.deepEqual(plain(allow), {label: N.allow, kind: 'dialog', target: {d: 'fake-ip', next: '重新登录'}});
  assert.equal(route.actions[0].label, '重新登录');  // The login stays the fix; the switch never retries it.
  // The cause is in the body; the code is under 技术信息, not a raw fact.
  assert.ok(!route.facts.some(([term]) => /最近一次/.test(term)));
  assert.equal(route.tech, 'oauth_dns_policy');
  const line = model.inbox.find(i => i.id === 'oauth:needs_login');
  assert.equal(line.detail, LEAD);
  // Logging in again with the setting off fails again: the inbox line offers the switch first.
  assert.deepEqual(plain(line.action), {label: N.allow, kind: 'dialog', target: {d: 'fake-ip', next: '重新登录'}});
  for (const variant of [data({oauth: [refused()], network: {fake_ip_tunnel: true, changed_at: NOW - 5}}),
    data({oauth: [refused({last_error_hint: undefined})]}), data({oauth: [refused({last_error: 'oauth_invalid_grant'})]})]) {
    model = M.derive(variant, NOW);
    route = model.byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
    assert.ok(!route.body.includes(LEAD) && !route.actions.some(a => a.label === N.allow));
    const line = model.inbox.find(i => i.id === 'oauth:needs_login');
    assert.equal(line.detail, 'Higgsfield MCP 工具暂时不能使用。');
    assert.deepEqual(plain(line.action), {label: '重新登录', kind: 'dialog', target: {d: 'oauth', keep: false}});
  }
  assert.equal(T.fakeIpOn(data({network: {fake_ip_tunnel: true}})), true);
  for (const value of [undefined, {}, {fake_ip_tunnel: 'true'}, {fake_ip_tunnel: 1}, null]) assert.equal(T.fakeIpOn(data({network: value})), false);
  assert.equal(T.fakeIpOn(undefined), false);
});

test('a renewal stopped by a Fake-IP answer while the login still works is raised in the inbox with the switch', () => {
  // Nothing was sent, so the login stays usable until it expires (pre-send failures keep the refresh token).
  for (const status of ['ready', 'refreshing']) {
    const model = M.derive(data({oauth: [refused({status, expires_at: NOW + 600})]}), NOW);
    const line = model.inbox.find(i => i.id === 'oauth:renew_blocked');
    assert.equal(line.sev, 'warn');
    assert.equal(line.title, 'Higgsfield 的 ATM 登录没能续期');
    assert.equal(line.detail, LEAD);
    assert.deepEqual(plain(line.action), {label: N.allow, kind: 'dialog', target: {d: 'fake-ip', next: '重新登录'}});
    const route = model.byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
    assert.ok(route.body.includes(LEAD) && route.actions.some(a => a.label === N.allow));
  }
  for (const variant of [data({oauth: [refused({status: 'ready'})], network: {fake_ip_tunnel: true}}),
    data({oauth: [refused({status: 'ready', last_error_hint: undefined})]}), data({oauth: [refused({status: 'needs_login'})]})])
    assert.ok(!M.derive(variant, NOW).inbox.some(i => i.id === 'oauth:renew_blocked'));
});

test('a download stopped by a Fake-IP answer explains the cause in 记录 and the inbox, and links to the switch', () => {
  const failed = job('download_failed', {error_hint: 'fake_ip_tunnel'});
  let model = M.derive(data({tools: [fal], jobs: [failed]}), NOW);
  let view = model.jobs[0];
  assert.ok(view.fakeIp);
  assert.equal(view.sentence, '结果文件的地址被解析成了 198.18.x.x（通常是网络代理的 Fake-IP 模式，例如 Shadowrocket、Clash、Surge）。ATM 默认不连接这类地址，所以没有下载。在“设置 › 高级”里允许后，让 Agent 刷新这个任务重试下载。');
  assert.deepEqual(plain(view.network), {label: '打开网络设置', kind: 'nav', target: 'settings/advanced', focus: 'network:fake-ip'});
  const line = model.inbox.find(i => i.id === 'job-needs:job-download_failed');
  assert.equal(line.detail, view.sentence);
  assert.deepEqual(plain(line.action), plain(view.network));
  // Already allowed: the same cause, the retry, no link; the inbox goes back to the record.
  model = M.derive(data({tools: [fal], jobs: [failed], network: {fake_ip_tunnel: true}}), NOW);
  view = model.jobs[0];
  assert.equal(view.network, null);
  assert.ok(view.sentence.endsWith('现在已允许通过本机代理连接：让 Agent 刷新这个任务重试下载。'));
  assert.equal(model.inbox.find(i => i.id === 'job-needs:job-download_failed').action.label, '查看记录');
  // A refused MCP or REST call failed before sending: run it again; a completed job never shows an old hint.
  model = M.derive(data({tools: [fal], jobs: [job('failed', {error_hint: 'fake_ip_tunnel'}), job('completed', {error_hint: 'fake_ip_tunnel'}), job('queued')]}), NOW);
  const by = Object.fromEntries(model.jobs.map(j => [j.status, j]));
  assert.equal(by.failed.sentence, N.request + '在“设置 › 高级”里允许后，让 Agent 重新运行。');
  assert.ok(!by.completed.fakeIp && by.completed.network === null && by.completed.sentence === '');
  assert.ok(!by.queued.fakeIp && !by.queued.sentence.includes('198.18'));
  // Without the hint, the existing download sentence is unchanged.
  assert.equal(M.derive(data({tools: [fal], jobs: [job('download_failed')]}), NOW).jobs[0].sentence, '结果文件没能下载下来。让 Agent 刷新这个任务后重试下载。');
});

test('the ATM login card names its last failure in Chinese, with the code under 技术信息', () => {
  const card = extra => M.derive(data({oauth: [refused(extra)]}), NOW).byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
  const fact = route => route.facts.find(([term]) => /最近一次/.test(term));
  // A login (not a renewal) refused without the hint: plain Chinese, the code kept.
  let route = card({last_error_hint: undefined});
  assert.deepEqual(plain(fact(route)), ['最近一次失败', T.error.oauth_dns_policy]);
  assert.equal(route.tech, 'oauth_dns_policy');
  route = card({last_error: 'oauth_invalid_grant', last_error_hint: undefined});
  assert.deepEqual(plain(fact(route)), ['最近一次失败', 'Higgsfield 登录没有完成（oauth_invalid_grant）。']);
  assert.equal(route.tech, 'oauth_invalid_grant');
  route = card({status: 'ready', expires_at: NOW + 3600, last_error: 'oauth_refresh_token_missing', last_error_hint: undefined});
  assert.deepEqual(plain(fact(route)), ['最近一次失败', 'Higgsfield 没有给出续期凭证，ATM 登录到期后需要重新登录。']);
  // The Fake-IP refusal once the owner allowed it: resolved, so neither a fact nor a code is left.
  route = M.derive(data({oauth: [refused()], network: {fake_ip_tunnel: true}}), NOW).byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
  assert.equal(fact(route), undefined);
  assert.equal(route.tech, '');
  assert.ok(!JSON.stringify(plain(route)).includes('最近一次续期失败'));
  // No failure: nothing.
  route = card({last_error: null, last_error_hint: undefined});
  assert.equal(fact(route), undefined);
  assert.equal(route.tech, '');
});
