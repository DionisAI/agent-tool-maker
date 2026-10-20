import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';

// The console view model, loaded exactly as the page loads it: brand data, brands, then model.js.
const root = new URL('../src/agent_tool_maker/data/web/', import.meta.url);
const context = vm.createContext({window: {}});
for (const name of ['brand-data.js', 'brands.js', 'model.js']) vm.runInContext(readFileSync(new URL(name, root), 'utf8'), context, {filename: name});
const M = context.window.ATM_MODEL;
const NOW = 1_800_000_000;
const plain = value => JSON.parse(JSON.stringify(value));

function tool(id, adapter, provider, state, extra = {}) {
  const {health = {}, ...rest} = extra;
  return {id, title: id, provider, adapter, capabilities: [], implementation: 'native', permissions: [], paid: false,
    credentials: [], optional_credentials: [], executable: null, server: null, oauth: null, url: null, session: null, origins: [],
    enabled: state !== 'disabled', ...rest, health: {id, state, authentication: 'not_verified', ...health}};
}
const conn = (provider, extra = {}) => ({provider, label: provider, configured: false, configured_at: null, expires_at: null,
  sync_conflict: false, expired: false, connect_supported: true, ...extra});
function data(parts = {}) {
  return {
    overview: {version: '0.8.0', home: '/fake/home', agents: parts.agents || [], credits: {providers: parts.credits || []}},
    tools: parts.tools || [],
    connections: {connections: parts.connections || [], oauth: parts.oauth || [], vault: parts.vault || {backend: 'passphrase', state: 'needs_unlock'},
      verification_history: parts.history || []},
    jobs: parts.jobs || [], clis: parts.clis || [], sync: parts.sync || {device: null, peers: [], records: []},
    access: parts.access || {grants: [], clock: NOW, broker: null, requests: []},
    extensions: parts.extensions || {custom_tools: [], credential_slots: [], browser_sessions: []},
    session: parts.session || {unlocked: false, seconds_remaining: 0, session_mode_enabled: true},
    passkeys: parts.passkeys || {available: true, credentials: []},
  };
}

test('say() looks up own keys only, so prototype names fall back', () => {
  const dict = {known: '已知'};
  assert.equal(M.say(dict, 'known', 'x'), '已知');
  for (const code of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) {
    assert.equal(M.say(dict, code, '操作没有完成（{code}）。'), `操作没有完成（${code}）。`);
    assert.equal(M.say(M.T.error, code, '操作没有完成（{code}）。'), `操作没有完成（${code}）。`);
  }
  assert.equal(M.T.creditLabel('constructor'), '读取失败 · constructor');
  assert.equal(M.T.creditLabel('cli_not_configured'), '程序未绑定');
  assert.equal(M.T.errorText('vault_locked'), 'ATM 主密码不正确（或保管库数据已损坏）。Key 仍是锁定的。');
  assert.equal(M.T.errorText('oauth_strange'), 'Higgsfield 登录没有完成（oauth_strange）。');
  assert.equal(M.T.errorText('passkey_strange'), 'Passkey 验证没有完成（passkey_strange）。');
  assert.equal(M.T.errorText('fixture_unknown'), '操作没有完成（fixture_unknown）。');
});

test('derive() tolerates every payload being missing', () => {
  for (const value of [undefined, {}, {tools: undefined, overview: undefined}, {extensions: undefined, session: undefined, passkeys: undefined}]) {
    const model = M.derive(value, NOW);
    assert.equal(model.inbox.length, 0);
    assert.deepEqual(plain(model.requests), []);
    assert.equal(model.firstRun.show, true);
    assert.equal(model.counts.toolsTotal, 0);
  }
  const partial = data({tools: [tool('ffmpeg.probe', 'ffprobe', 'ffmpeg', 'configured_not_verified', {executable: 'ffprobe'})]});
  delete partial.extensions; delete partial.session; delete partial.passkeys; delete partial.access.requests;
  const model = M.derive(partial, NOW);
  assert.equal(model.byKey.get('ffmpeg').routes[0].kind, 'program');
  assert.deepEqual(plain(model.requests), []);
});

test('every health state maps to one readiness state, word, sentence and fix', () => {
  const rows = {
    configured_not_verified: ['ready', '可以使用', '可以使用（ATM 不会提前联网验证）。', null],
    missing_credential: ['setup', '待设置', '缺少 Key：elevenlabs', '添加 API Key'],
    credential_expired: ['blocked', 'Key 已过期', 'elevenlabs 的 Key 已过期。', '更换 API Key'],
    sync_conflict: ['blocked', 'Key 冲突', 'elevenlabs 的 Key 在两台设备上不一致，已暂停。', '选择版本'],
    cli_not_configured: ['setup', '待设置', '需要先绑定一个本机程序。', '查看设置步骤'],
    executable_unpinned: ['attention', '需要处理', '程序已绑定，但没有记录程序指纹。', '查看确认方法'],
    executable_changed: ['blocked', '程序已更新', '程序已更新，需要你重新确认。', '查看确认方法'],
    executable_missing: ['blocked', '程序不见了', '找不到之前绑定的程序。', '查看确认方法'],
    executable_not_executable: ['blocked', '不能运行', '程序没有执行权限。', '查看确认方法'],
    executable_unreadable: ['blocked', '无法读取', '无法读取程序。', '查看确认方法'],
    mcp_not_configured: ['setup', '待设置', 'MCP 服务 elevenlabs 还没设置。', '查看设置命令'],
    missing_origin: ['setup', '待设置', '需要先设置服务地址。', '查看设置命令'],
    browser_dependency_missing: ['setup', '待设置', '需要安装 ATM 的网页组件。', '查看安装方法'],
    browser_session_missing: ['setup', '待设置', '还没有用 ATM 登录这个网站。', '查看登录命令'],
    browser_session_expired: ['blocked', '登录已过期', 'ATM 网页登录已过期。', '查看登录命令'],
    browser_session_scope: ['blocked', '登录范围不符', '已保存的登录不包含这个工具需要的网站。', '查看登录命令'],
    browser_login_unknown: ['handoff', '无需设置', '在 Agent 的浏览器里登录，ATM 里无需设置。', null],
    host_desktop_required: ['handoff', '无需设置', '由你或 Agent 在桌面软件里操作。', null],
    host_human_required: ['handoff', '无需设置', '由人来完成。', null],
    workflow_dependencies_not_verified: ['handoff', '看各步骤', '组合流程：能否使用取决于其中每一步。', null],
    catalog_only: ['handoff', '仅供参考', '目录条目，不能直接运行。', null],
    disabled: ['off', '已停用', '你已停用：Claude Code 和 Codex 都不能调用它。', null],
    keyring_unavailable: ['blocked', '无法读取 Key', '无法打开 Key 保管库。已保存的 Key 没有丢失。', '查看'],
    keyring_key_missing: ['blocked', '无法读取 Key', '无法打开 Key 保管库。已保存的 Key 没有丢失。', '查看'],
    vault_corrupt: ['blocked', '无法读取 Key', '无法打开 Key 保管库。已保存的 Key 没有丢失。', '查看'],
    not_initialized: ['setup', '待设置', '先设置 Key 的保管方式。', '开始设置'],
    vault_not_initialized: ['setup', '待设置', '先设置 Key 的保管方式。', '开始设置'],
    fixture_new_state: ['attention', '需要处理', 'ATM 返回了未知状态（fixture_new_state）。', '查看详情'],
  };
  for (const [state, [expected, word, sentence, fix]] of Object.entries(rows)) {
    const t = tool('elevenlabs.tts', 'elevenlabs', 'elevenlabs', state, {credentials: ['elevenlabs'], health: {credential: 'elevenlabs'}});
    const r = M.toolReadiness(t, data());
    assert.equal(r.state, expected, state);
    assert.equal(r.word, word, state);
    assert.equal(r.sentence, sentence, state);
    assert.equal(r.fix?.label ?? null, fix, state);
  }
});

test('a saved Key reads ready whatever the lock: the lock lives only in the pill', () => {
  const t = tool('elevenlabs.tts', 'elevenlabs', 'elevenlabs', 'needs_unlock', {credentials: ['elevenlabs']});
  for (const state of ['needs_unlock', 'unlock_not_checked', 'unlocked_in_this_process']) {
    t.health.state = state;
    const locked = M.toolReadiness(t, data({session: {unlocked: false}}));
    assert.equal(locked.state, 'ready');
    assert.equal(locked.word, '可以使用');
    assert.equal(locked.sentence, '可以使用。Key 已保存；Key 锁定时，Agent 会打开授权窗口请你解锁。');
    assert.equal(M.toolReadiness(t, data({session: {unlocked: true}})).sentence, '可以使用。Key 已解锁。');
    assert.equal(M.toolReadiness(t, data({vault: {backend: 'keyring', state: 'unlock_not_checked'}})).sentence, '可以使用。Key 保存在系统钥匙串里。');
    assert.ok(!JSON.stringify(locked).includes('需要解锁'));
  }
  const vendor = tool('wrangler.deploy', 'command', 'cloudflare_wrangler', 'configured_not_verified',
    {executable: 'wrangler', health: {cli_authentication: 'vendor_login_not_verified'}});
  assert.equal(M.toolReadiness(vendor, data()).sentence, '可以使用（ATM 不会提前联网验证）。登录由 wrangler 自己管理，ATM 不检查。');
});

test('each tool maps to exactly one route kind, with and without the reference fields', () => {
  const cases = [
    [tool('catalog.x', 'rest', 'acme', 'catalog_only'), 'catalog'],
    [tool('elevenlabs.web', 'browser', 'elevenlabs', 'browser_login_unknown'), 'agent_browser'],
    [tool('clo.handoff', 'desktop', 'clo', 'host_desktop_required'), 'desktop'],
    [tool('upwork.handoff', 'human', 'upwork', 'host_human_required'), 'human'],
    [tool('fixture.flow', 'workflow', 'fixture', 'workflow_dependencies_not_verified'), 'workflow'],
    [tool('fixture.export', 'web_recipe', 'fixture', 'browser_session_missing', {session: 'fixture-login'}), 'recipe'],
    [tool('linear.mcp_tools', 'mcp', 'linear', 'configured_not_verified', {server: 'linear', oauth: 'higgsfield'}), 'oauth'],
    [tool('linear.mcp_tools', 'mcp', 'linear', 'configured_not_verified', {server: 'linear'}), 'mcp'],
    [tool('tripo.studio.account', 'command', 'tripo', 'configured_not_verified', {executable: 'opencliapp'}), 'chrome'],
    [tool('tripo.server.account', 'command', 'tripo', 'cli_not_configured', {executable: 'atm'}), 'studio_server'],
    [tool('ffmpeg.probe', 'ffprobe', 'ffmpeg', 'configured_not_verified', {executable: 'ffprobe'}), 'program'],
    [tool('xyq.image', 'xyq', 'xyq', 'configured_not_verified', {executable: 'xyq'}), 'program'],
    [tool('comfyui.queue', 'rest', 'comfyui', 'missing_origin'), 'origin'],
    [tool('fal.generate', 'fal', 'fal', 'credential_expired', {credentials: ['fal']}), 'key'],
    [tool('apify.run', 'rest', 'apify', 'missing_credential', {credentials: ['apify']}), 'key'],
  ];
  for (const [t, kind] of cases) assert.equal(M.routeKindOf(t), kind, t.id);
  // Without B1 (older payloads): the id and bound program still classify website and server tools.
  const legacy = t => { const copy = {...t}; for (const key of ['credentials', 'optional_credentials', 'executable', 'server', 'oauth', 'url', 'session', 'origins']) delete copy[key]; return copy; };
  assert.equal(M.routeKindOf(legacy(tool('xyq.web.account', 'command', 'xyq', 'configured_not_verified'))), 'chrome');
  assert.equal(M.routeKindOf(legacy(tool('fixture.reader', 'command', 'fixture', 'configured_not_verified', {health: {binary: {path: '/Applications/OpenCLIApp.app/Contents/MacOS/opencliapp'}}}))), 'chrome');
  assert.equal(M.routeKindOf(legacy(tool('tripo.server.login', 'command', 'tripo', 'cli_not_configured'))), 'studio_server');
  assert.equal(M.routeKindOf(legacy(tool('higgsfield.mcp', 'mcp', 'higgsfield', 'configured_not_verified', {server: 'higgsfield'}))), 'oauth');
  assert.equal(M.routeKindOf(legacy(tool('ffmpeg.trim', 'command', 'ffmpeg', 'cli_not_configured', {health: {next_action: 'Review atm setup --cli ffmpeg, then --apply.'}}))), 'program');
});

test('service keys join tools, Keys, credits and OAuth through the brand registry', () => {
  assert.equal(M.serviceKeyOf('tripo', 'tripo.studio.account'), 'tripo');
  assert.equal(M.serviceKeyOf('studio', 'tripo.server.account'), 'tripo');
  assert.equal(M.serviceKeyOf('xyq', 'pippit.cli.credit_balance'), 'xyq');
  assert.equal(M.serviceKeyOf('youtube_data'), 'youtube');
  assert.equal(M.serviceKeyOf('google_oauth'), 'google');
  assert.equal(M.serviceKeyOf('shopify_admin'), 'shopify');
  assert.equal(M.serviceKeyOf('acme.production'), 'acme.production');
  assert.match(M.serviceKeyOf('<img src=x onerror=alert(1)>'), /^[a-z0-9][a-z0-9_.-]{0,79}$/);
  const model = M.derive(data({
    tools: [tool('youtube_data.upload', 'rest', 'youtube_data', 'missing_credential', {credentials: ['google_oauth'], health: {credential: 'google_oauth'}})],
    connections: [conn('google_oauth'), conn('acme.production', {label: 'Acme 生产环境'})],
  }), NOW);
  const youtube = model.byKey.get('youtube');
  assert.equal(youtube.routes[0].title, 'API Key · google_oauth');
  assert.equal(youtube.keys[0].sharedFrom, 'google');
  assert.equal(model.byKey.get('acme.production').name, 'Acme 生产环境');
  assert.deepEqual(plain(model.keys.get('google_oauth').usedBy), ['youtube_data.upload']);
});

test('Key state precedence: conflict, then expired, then an unreadable vault, then missing, then expiring', () => {
  const vault = {backend: 'keyring', state: 'keyring_unavailable'};
  const keyState = (c, v = {backend: 'passphrase', state: 'needs_unlock'}) => M.derive(data({connections: [c], vault: v}), NOW).keys.get(c.provider);
  assert.equal(keyState(conn('exa', {sync_conflict: true, expired: true, configured: true}), vault).word, '版本冲突');
  assert.equal(keyState(conn('fal', {expired: true, configured: true, expires_at: NOW - 10}), vault).word, '已过期');
  assert.equal(keyState(conn('fal', {configured: true}), vault).word, '无法读取');
  assert.equal(keyState(conn('fal', {configured: false}), vault).word, '待设置');
  assert.equal(keyState(conn('fal', {configured: true, expires_at: NOW + 3 * 86400})).word, '即将到期');
  assert.equal(keyState(conn('fal', {configured: true, expires_at: NOW + 30 * 86400})).word, '可以使用');
  for (const [c, state] of [[conn('exa', {sync_conflict: true}), 'blocked'], [conn('fal', {configured: true}), 'ready'], [conn('fal'), 'setup']])
    assert.equal(keyState(c).state, state);
});

test('route and service states aggregate, and the lead sentence follows them', () => {
  const eleven = [tool('elevenlabs.tts', 'elevenlabs', 'elevenlabs', 'missing_credential', {credentials: ['elevenlabs'], paid: true, health: {credential: 'elevenlabs'}}),
    tool('elevenlabs.web', 'browser', 'elevenlabs', 'browser_login_unknown', {url: 'https://elevenlabs.io/app/', paid: true})];
  let service = M.derive(data({tools: eleven, connections: [conn('elevenlabs')]}), NOW).byKey.get('elevenlabs');
  assert.equal(service.state, 'setup');
  assert.equal(service.lead, '还没有设置。还没有 API Key，elevenlabs.tts 暂时不能使用。elevenlabs.web 不需要在 ATM 设置。');
  assert.equal(service.primary.label, '添加 API Key');
  assert.deepEqual(plain(service.routes.map(r => r.kind)), ['key', 'agent_browser']);
  const browser = service.routes[1];
  assert.equal(browser.word, '无需在 ATM 设置');
  assert.ok(browser.info[0].includes('不在 ATM 里登录') && browser.info[0].includes('在它自己的浏览器里打开 elevenlabs.io'));
  assert.ok(browser.info.some(line => line.includes('在上面的“API Key”里保存 Key')));
  eleven[0].health = {id: 'elevenlabs.tts', state: 'needs_unlock'};
  service = M.derive(data({tools: eleven, connections: [conn('elevenlabs', {configured: true, configured_at: NOW - 86400})]}), NOW).byKey.get('elevenlabs');
  assert.equal(service.state, 'ready');
  assert.equal(service.primary, null);
  assert.equal(service.lead, '可以使用。Agent 可以通过 API Key、交给 Agent 的浏览器使用 2 个工具。');
  // A working Key: the Agent-browser route no longer suggests saving one.
  assert.ok(!service.routes.find(r => r.kind === 'agent_browser').info.some(line => line.includes('保存 Key')));
  assert.deepEqual(plain(service.routes[0].facts[0]), ['用于', 'elevenlabs.tts']);
  assert.ok(service.routes[0].actions.map(a => a.label).join() === '联网测试,更换,移除');
  // Blocked beats ready in the lead, which says the other routes still work.
  const ffmpeg = [tool('ffmpeg.trim', 'command', 'ffmpeg', 'executable_changed', {executable: 'ffmpeg', health: {binary: {path: '/fake/ffmpeg'}}}),
    tool('ffmpeg.probe', 'ffprobe', 'ffmpeg', 'configured_not_verified', {executable: 'ffprobe'})];
  service = M.derive(data({tools: ffmpeg, clis: [{name: 'ffmpeg', state: 'executable_changed', path: '/fake/ffmpeg'}, {name: 'ffprobe', state: 'configured_not_verified', path: '/fake/ffprobe'}]}), NOW).byKey.get('ffmpeg');
  assert.equal(service.state, 'attention');
  assert.equal(service.lead, 'ffmpeg 已更新，需要你重新确认；其余方式可以使用。');
  assert.equal(service.routes[0].word, '程序已更新');
  assert.equal(service.routes[0].commands[0].text, "atm cli bind ffmpeg '/fake/ffmpeg'");
  // The command box has its own 复制 button: no second copy button; the header jumps to the command.
  assert.deepEqual(plain(service.routes[0].actions), []);
  assert.equal(service.primary.label, '查看确认方法');
  assert.equal(service.primary.kind, 'route');
  assert.deepEqual(plain(service.primary.target), {service: 'ffmpeg', kind: 'program', id: 'ffmpeg', anchor: 'route-program-ffmpeg', focus: 'command'});
  // Only blocked: the service is blocked. All disabled: off, with one bulk primary.
  service = M.derive(data({tools: [ffmpeg[0]], clis: [{name: 'ffmpeg', state: 'executable_changed', path: '/fake/ffmpeg'}]}), NOW).byKey.get('ffmpeg');
  assert.equal(service.state, 'blocked');
  const off = [tool('suno.web', 'browser', 'suno', 'disabled', {enabled: false})];
  service = M.derive(data({tools: off}), NOW).byKey.get('suno');
  assert.equal(service.state, 'off');
  assert.equal(service.lead, '你已停用全部 1 个工具。');
  assert.equal(service.primary.label, '全部允许…');
  // Hand-off only.
  service = M.derive(data({tools: [tool('canva.web', 'browser', 'canva', 'browser_login_unknown')]}), NOW).byKey.get('canva');
  assert.equal(service.state, 'handoff');
  assert.equal(service.lead, '无需在 ATM 设置。Agent 会在它自己的浏览器或软件里完成，ATM 只记录结果。');
  // Route order is fixed and never follows state.
  const order = M.T.kindOrder;
  assert.deepEqual(plain(order.slice(0, 5)), ['key', 'chrome', 'studio_server', 'program', 'oauth']);
});

test('the Chrome route explains OpenCLIApp and the website login in three steps', () => {
  const tools = [tool('tripo.studio.account', 'command', 'tripo', 'configured_not_verified', {executable: 'opencliapp', health: {binary: {path: '/fake/opencliapp'}}}),
    tool('tripo.studio.generate', 'command', 'tripo', 'configured_not_verified', {executable: 'opencliapp', paid: true})];
  const credits = [{provider: 'tripo_studio', label: 'Tripo Studio', brand: 'tripo', installed: true, bound: true, source: 'tripo.studio.account',
    source_kind: 'website', status: 'error', error: {code: 'login_required', message: 'x'}, checked_at: NOW - 3 * 86400, next_source: 'tripo.studio.account', sources: ['tripo.studio.account', 'tripo.server.account']}];
  let route = M.derive(data({tools, credits, clis: [{name: 'opencliapp', state: 'configured_not_verified', path: '/fake/opencliapp'}]}), NOW).byKey.get('tripo').routes.find(r => r.kind === 'chrome');
  assert.equal(route.title, '你的 Chrome 登录 · Tripo Studio');
  assert.equal(route.steps.length, 3);
  assert.equal(route.steps[0].text, '已安装 2 个 Tripo Studio 工具');
  assert.equal(route.steps[1].text, '已绑定 OpenCLIApp');
  assert.equal(route.steps[2].text, '上次检查时，Chrome 里没有登录 Tripo Studio（3 天前）。登录后点“检查 Chrome 登录”。');
  assert.equal(route.state, 'attention');
  assert.equal(route.word, '需要登录');
  assert.equal(route.actions[0].label, '检查 Chrome 登录');
  assert.deepEqual(plain(route.check), {provider: 'tripo_studio', host: 'studio.tripo3d.ai', name: 'Tripo Studio'});
  route = M.derive(data({tools, clis: [{name: 'opencliapp', state: 'cli_not_configured', detected_path: null}]}), NOW).byKey.get('tripo').routes.find(r => r.kind === 'chrome');
  tools.forEach(t => { t.health.state = 'cli_not_configured'; });
  route = M.derive(data({tools, clis: [{name: 'opencliapp', state: 'cli_not_configured', detected_path: null}]}), NOW).byKey.get('tripo').routes.find(r => r.kind === 'chrome');
  assert.equal(route.state, 'setup');
  assert.equal(route.steps[1].text, '还没绑定 OpenCLIApp。');
  assert.equal(route.steps[1].command, "atm cli bind opencliapp '<OpenCLIApp 程序的完整路径>'");
  assert.equal(route.steps[2].text, '还没检查过 Chrome 是否已登录。');
  route = M.derive(data({tools: tools.slice(1), clis: [{name: 'opencliapp', state: 'cli_not_configured', detected_path: '/fake/found/opencliapp'}]}), NOW).byKey.get('tripo').routes.find(r => r.kind === 'chrome');
  assert.equal(route.steps[1].text, '在 /fake/found/opencliapp 找到了 OpenCLIApp，确认后即可使用。');
  assert.equal(route.steps[1].action.label, '绑定');
  assert.equal(route.steps[2].text, '登录状态只能在 Agent 使用时确认。');
  assert.equal(route.actions[0].label, '绑定');
});

test('OAuth, MCP, recipe and origin routes carry their own words and commands', () => {
  const oauth = [{provider: 'higgsfield', status: 'ready', keep_login: true, expires_at: NOW + 3600, service: {status: 'load_failed'}}];
  let model = M.derive(data({oauth, tools: [tool('higgsfield.generate', 'higgsfield', 'higgsfield', 'missing_credential', {credentials: ['higgsfield']})]}), NOW);
  const route = model.byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
  assert.equal(route.title, 'ATM 登录 · Higgsfield MCP');
  assert.equal(route.state, 'attention');
  assert.ok(route.facts.some(([term, value]) => term === '后台续期服务' && value === '启动失败'));
  assert.ok(route.actions.some(a => a.label === '停止自动续期'));
  for (const [status, word] of [['missing', '尚未登录'], ['pending', '等你在浏览器里确认'], ['expired', '登录已过期'], ['denied', '登录没有获批'], ['refresh_unknown', '续期结果不确定，请重新登录']]) {
    model = M.derive(data({oauth: [{provider: 'higgsfield', status, keep_login: false, service: {status: 'not_installed'}}]}), NOW);
    assert.equal(model.byKey.get('higgsfield').routes.find(r => r.kind === 'oauth').word, word, status);
  }
  model = M.derive(data({tools: [tool('linear.mcp_tools', 'mcp', 'linear', 'mcp_not_configured', {server: 'linear'})]}), NOW);
  assert.equal(model.byKey.get('linear').routes[0].commands[0].text, "atm mcp bind linear --config '<配置文件路径>' --approve-config");
  model = M.derive(data({tools: [tool('fixture.export', 'web_recipe', 'fixture', 'browser_session_missing', {session: 'fixture-login'})]}), NOW);
  assert.equal(model.byKey.get('fixture').routes[0].commands[0].text, 'atm web login fixture.export');
  model = M.derive(data({tools: [tool('comfyui.queue', 'rest', 'comfyui', 'missing_origin')]}), NOW);
  assert.equal(model.byKey.get('comfyui').routes[0].commands[0].text, "atm origin set comfyui '<服务地址>' --approve-origin");
  assert.equal(M.T.quote("it's"), "'it'\\''s'");
});

function inboxFixture() {
  return data({
    tools: [
      tool('fal.generate', 'fal', 'fal', 'credential_expired', {credentials: ['fal'], health: {credential: 'fal'}}),
      tool('exa.search', 'exa', 'exa', 'sync_conflict', {credentials: ['exa'], health: {credential: 'exa'}}),
      tool('ffmpeg.trim', 'command', 'ffmpeg', 'executable_changed', {executable: 'ffmpeg'}),
      tool('fixture.export', 'web_recipe', 'fixture', 'browser_session_expired', {session: 'fixture-login'}),
      tool('linear.mcp_tools', 'mcp', 'linear', 'missing_credential', {server: 'linear', credentials: ['linear'], health: {credential: 'linear'}}),
      tool('tripo.server.account', 'command', 'tripo', 'cli_not_configured', {executable: 'atm'}),
      tool('runway.generate', 'rest', 'runway', 'missing_credential', {credentials: ['runway'], health: {credential: 'runway'}}),
      tool('tripo.studio.generate', 'command', 'tripo', 'configured_not_verified', {executable: 'opencliapp'}),
    ],
    connections: [conn('fal', {configured: true, expired: true, expires_at: NOW - 86400}), conn('exa', {sync_conflict: true}),
      conn('tripo', {configured: true, expires_at: NOW + 2 * 86400}), conn('runway'), conn('acme.production', {label: 'Acme 生产环境'})],
    clis: [{name: 'ffmpeg', state: 'executable_changed', path: '/fake/ffmpeg'}, {name: 'atm', state: 'cli_not_configured'}],
    oauth: [{provider: 'higgsfield', status: 'ready', keep_login: true, expires_at: NOW + 3600, service: {status: 'load_failed'}}],
    credits: [{provider: 'higgsfield', label: 'Higgsfield', brand: 'higgsfield', installed: true, bound: true, source: 'higgsfield.subscription.account',
      source_kind: 'cli', status: 'error', error: {code: 'login_required'}, next_executable: 'higgsfield', sources: ['higgsfield.subscription.account']}],
    jobs: [{id: 'job-unknown', tool: 'tripo.studio.generate', status: 'submission_unknown', created: NOW - 600, updated: NOW - 600, verification: null, cost_usd: null, cost_status: 'unknown', artifact_count: 0, kind: 'tool'},
      {id: 'job-human', tool: 'tripo.studio.generate', status: 'requires_human', created: NOW - 300, updated: NOW - 300, verification: null, cost_usd: null, cost_status: 'unknown', artifact_count: 0, kind: 'tool'},
      {id: 'job-credits', tool: 'xyq.web.account', status: 'blocked', created: NOW - 60, updated: NOW - 60, verification: null, cost_usd: null, cost_status: 'unknown', artifact_count: 0, kind: 'credits_refresh'}],
    agents: [{agent: 'claude', label: 'Claude Code', state: 'registered_not_host_verified', skill_path: '/fake/claude/SKILL.md'},
      {agent: 'codex', label: 'Codex', state: 'not_registered', detected_executable: '/fake/bin/codex', default_skill_path: '/fake/codex/SKILL.md'}],
    extensions: {custom_tools: [{id: 'tripo.server.account'}], credential_slots: ['acme.production'], browser_sessions: []},
    passkeys: {available: true, credentials: [], state_error: {code: 'passkey_state_digest'}},
  });
}

test('every inbox rule fires from its own fixture, in severity order, with stable ids', () => {
  const model = M.derive(inboxFixture(), NOW);
  const ids = model.inbox.map(i => i.id);
  for (const id of ['key-expired:fal', 'key-conflict:exa', 'program:ffmpeg', 'renew:higgsfield', 'credits-login:higgsfield', 'mcp-key:linear:linear',
    'custom:tripo:studio_server:studio_server', 'key-soon:tripo', 'job-unknown:job-unknown', 'job-needs:job-human', 'agent-missing:codex', 'passkey:state', 'slot:acme.production'])
    assert.ok(ids.includes(id), id + ' in ' + ids.join(' '));
  assert.ok(ids.some(id => id.startsWith('session:')));
  // Never set up is not an issue; credits refreshes are not the owner's jobs.
  assert.ok(!model.inbox.some(i => i.title.includes('Runway') || i.detail.includes('runway')));
  assert.ok(!ids.includes('job-needs:job-credits'));
  const sev = model.inbox.map(i => i.sev);
  assert.deepEqual(plain(sev), [...sev].sort((a, b) => ['bad', 'warn', 'info'].indexOf(a) - ['bad', 'warn', 'info'].indexOf(b)));
  const byId = Object.fromEntries(model.inbox.map(i => [i.id, i]));
  assert.equal(byId['key-expired:fal'].title, 'fal.ai 的 API Key 已过期');
  assert.equal(byId['key-expired:fal'].action.label, '更换 API Key');
  assert.equal(byId['key-conflict:exa'].action.label, '选择版本');
  assert.equal(byId['program:ffmpeg'].title, 'ffmpeg 程序已更新，需要你重新确认');
  assert.equal(byId['program:ffmpeg'].detail, '用到它的 1 个工具已暂停，直到你确认。');
  assert.equal(byId['renew:higgsfield'].title, 'Higgsfield 自动续期没有运行');
  assert.equal(byId['credits-login:higgsfield'].detail, 'higgsfield 程序自己的登录已失效，读不到积分。');
  assert.equal(byId['mcp-key:linear:linear'].title, 'Linear 的 MCP 服务已设置，但缺少 Key：linear');
  assert.equal(byId['job-unknown:job-unknown'].action.target, 'jobs');
  assert.equal(byId['job-unknown:job-unknown'].action.job, 'job-unknown');
  assert.equal(byId['job-needs:job-human'].title, 'tripo.studio.generate：等人工处理');
  assert.equal(byId['agent-missing:codex'].title, '检测到 Codex，还没安装 ATM');
  assert.equal(byId['passkey:state'].detail, 'ATM 主密码仍然可以解锁。错误代码：passkey_state_digest');
  assert.equal(byId['slot:acme.production'].title, 'Acme 生产环境还没有填写 Key');
  // Ids are stable across derivations (focus restoration).
  assert.deepEqual(plain(M.derive(inboxFixture(), NOW + 1).inbox.map(i => i.id).sort()), [...ids].sort());
});

test('inbox: vault, OAuth and pending-login rules', () => {
  let model = M.derive(data({vault: {backend: 'keyring', state: 'keyring_unavailable'}}), NOW);
  assert.equal(model.inbox[0].id, 'vault:keyring_unavailable');
  assert.equal(model.inbox[0].title, '无法打开 Key 保管库');
  for (const [status, sev, words] of [['expired', 'bad', '已过期'], ['needs_login', 'bad', '需要重新登录'], ['denied', 'bad', '没有获批'], ['refresh_unknown', 'warn', '续期结果不确定']]) {
    model = M.derive(data({oauth: [{provider: 'higgsfield', status, keep_login: false, service: {status: 'not_installed'}}]}), NOW);
    assert.equal(model.inbox[0].sev, sev);
    assert.equal(model.inbox[0].title, 'Higgsfield 的 ATM 登录' + words);
  }
  model = M.derive(data({oauth: [{provider: 'higgsfield', status: 'pending', keep_login: false, login_deadline: NOW + 300, service: {status: 'not_installed'}}]}), NOW);
  assert.equal(model.inbox[0].id, 'oauth-pending:higgsfield');
  assert.equal(model.inbox[0].action.kind, 'refresh');
  model = M.derive(data({agents: [{agent: 'claude', label: 'Claude Code', state: 'registration_changed'}]}), NOW);
  assert.equal(model.inbox[0].title, 'Claude Code 里的 ATM 说明文件被改过');
  // A website credits source that needs a login names the website.
  model = M.derive(data({credits: [{provider: 'tripo_studio', label: 'Tripo Studio', brand: 'tripo', installed: true, source: 'tripo.studio.account', source_kind: 'website', status: 'error', error: {code: 'login_required'}}]}), NOW);
  assert.equal(model.inbox[0].detail, 'Chrome 里没有登录 Tripo Studio，读不到积分，相关工具也可能失败。');
});

test('pending approval-window requests are described, never named after a client, and counted when live', () => {
  const access = {grants: [], clock: NOW, requests: [
    {id: 'a'.repeat(32), workspace: '/fake/projects/demo-video', credentials: ['elevenlabs', 'tripo'], status: 'needs_unlock', created_at: NOW - 180, expires_at: NOW + 420, live: true},
    {id: 'b'.repeat(32), workspace: '/fake/projects/other', credentials: ['fal'], status: 'needs_approval', created_at: NOW - 60, expires_at: NOW + 540, live: false},
    {id: 'c'.repeat(32), workspace: '/fake/projects/third', credentials: ['fal'], status: 'needs_approval', created_at: NOW - 30, expires_at: NOW + 570, live: true},
    {id: 'd'.repeat(32), workspace: '/fake/projects/fourth', credentials: ['fal'], status: 'starting', created_at: NOW - 5, expires_at: NOW + 595, live: true}]};
  const model = M.derive(data({access, connections: [conn('tripo', {configured: true}), conn('elevenlabs')]}), NOW);
  const [first, second, third, fourth] = model.requests;
  assert.equal(first.title, '有 Agent 请求在项目 demo-video 中使用 2 个 Key');
  assert.deepEqual(plain(first.chips.map(c => [c.label, c.ready])), [['elevenlabs · 在授权窗口里填写', false], ['Tripo3D · 已保存', true]]);
  assert.equal(first.statusText, '授权窗口已在浏览器里打开：在那里输入 ATM 主密码或用 Passkey 确认。');
  assert.equal(first.timeText, '3 分钟前发起 · 7 分钟后失效');
  assert.equal(second.statusText, '授权窗口已经关闭。请让 Agent 重新运行 atm start 再试。');
  assert.equal(third.statusText, 'Key 已解锁：在授权窗口里点“允许并继续”即可。');
  assert.equal(fourth.statusText, '正在打开授权窗口…');
  assert.equal(model.counts.liveRequests, 3);
  const text = JSON.stringify(model.requests);
  assert.ok(!text.includes('Claude Code') && !text.includes('Codex'));
  assert.deepEqual(plain(M.derive(data({access: {grants: [], clock: NOW}}), NOW).requests), []);
});

test('grants, jobs, verification and cost words', () => {
  const access = {clock: NOW, requests: [], grants: [
    {id: 'p'.repeat(32), kind: 'project_session', agent: 'local-project', tools: [], workspace: '/fake/demo-video', credential_scope: ['fal', 'tripo'], exec_rules: [], expires_at: NOW + 1500, revoked: false},
    {id: 'e'.repeat(32), kind: 'exec', agent: 'claude', tools: [], workspace: '/fake/app', credential_scope: ['fal'], exec_rules: [{program: '/usr/bin/python3'}], expires_at: NOW + 86400, revoked: false},
    {id: 't'.repeat(32), kind: 'tools', agent: 'codex', tools: ['ffmpeg.probe'], workspace: '/fake/app', credential_scope: [], exec_rules: [], allow_paid: false, permissions: ['execute_code'], expires_at: NOW - 1, revoked: false},
    {id: 'r'.repeat(32), kind: 'tools', agent: 'claude', tools: ['fal.generate'], workspace: '/fake/app', credential_scope: [], exec_rules: [], expires_at: NOW + 99, revoked: true}]};
  const grants = M.derive(data({access}), NOW).grants;
  assert.equal(grants.active.length, 2);
  assert.equal(grants.active[0].title, '项目 demo-video · 由授权窗口批准');
  assert.deepEqual(plain(grants.active[0].lines), ['可用 Key：fal、tripo', '项目里运行的程序都能用这些 Key', '锁定 Key 后立即停止']);
  assert.equal(grants.active[0].time, '还剩 25 分钟');
  assert.equal(grants.active[1].title, '命令授权 · app');
  assert.equal(grants.active[1].lines[1], '允许的程序：python3');
  assert.deepEqual(plain(grants.ended.map(g => g.time)), ['已过期', '已撤销']);
  assert.equal(grants.ended[0].title, 'Codex · 受限授权');
  assert.ok(grants.ended[0].lines.includes('会在本机运行程序'));
  for (const [code, word] of [['completed', '完成'], ['submission_unknown', '不确定是否已提交'], ['requires_browser', '等 Agent 的浏览器'], ['download_failed', '下载失败'], ['fixture_x', '其他状态（fixture_x）']]) {
    const job = M.derive(data({jobs: [{id: code, tool: 'x.y', status: code, created: NOW - 10, updated: NOW, verification: 'ffprobe', cost_usd: 0.004, cost_status: 'provider_estimate', artifact_count: 2}]}), NOW).jobs[0];
    assert.equal(job.word, word);
    assert.equal(job.kind, 'tool');
    assert.equal(job.cost, '$0.0040（估算）');
    assert.equal(job.day, '今天');
  }
  const refresh = M.derive(data({credits: [{provider: 'xyq', brand: 'xyq', sources: ['xyq.web.account']}], jobs: [{id: 'r', tool: 'xyq.web.account', status: 'completed', created: NOW}]}), NOW).jobs[0];
  assert.equal(refresh.kind, 'credits_refresh');  // Fallback without the backend kind field.
  assert.equal(M.T.cost(0.18, 'provider_report'), '$0.18（服务商报告）');
  assert.equal(M.T.cost(null, 'unknown'), '费用未知');
  assert.equal(M.T.cost(1, 'unknown'), '$1.00（未核对）');
  assert.equal(M.T.cost(null, 'local_no_provider_charge'), '本机运行，无服务费');
  assert.equal(M.T.verifyWord(null), '未检查');
  assert.equal(M.T.verifyWord('constructor'), '检查：constructor');
  assert.equal(M.T.relative(NOW - 3 * 86400, NOW), '3 天前');
});

test('agents, first run and counts', () => {
  let model = M.derive(data({vault: {backend: null, state: 'not_initialized'}, agents: [
    {agent: 'claude', label: 'Claude Code', state: 'not_registered', detected_executable: null},
    {agent: 'codex', label: 'Codex', state: 'not_registered', detected_executable: '/fake/codex'}]}), NOW);
  assert.equal(model.firstRun.show, true);
  assert.deepEqual(plain(model.firstRun.steps.map(s => s.done)), [false, false, false]);
  assert.equal(model.agents[0].detail, '本机没有找到 Claude Code。可以先安装 ATM 说明文件，装好 Claude Code 后生效。');
  assert.equal(model.agents[1].detail, '已在本机找到 /fake/codex');
  assert.equal(model.agents[1].actions[0].label, '安装到 Codex');
  model = M.derive(data({agents: [{agent: 'claude', label: 'Claude Code', state: 'registered_not_host_verified', skill_path: '/fake/SKILL.md'}],
    tools: [tool('fal.generate', 'fal', 'fal', 'needs_unlock', {credentials: ['fal'], paid: true}), tool('suno.web', 'browser', 'suno', 'disabled', {enabled: false})],
    connections: [conn('fal', {configured: true})]}), NOW);
  assert.equal(model.firstRun.show, false);
  assert.equal(model.agents[0].word, '已安装 ATM · 新开的会话会加载');
  assert.equal(model.counts.toolsEnabled, 1);
  assert.equal(model.counts.toolsPaidEnabled, 1);
  assert.equal(model.counts.servicesReady, 1);
  assert.ok(model.byKey.get('suno').inUse);  // An owner-disabled tool is something the owner set.
  assert.deepEqual(plain(model.tools.get('fal.generate').tags), ['可能扣费']);
});

test('fill() substitutes CJK keys as well as ASCII ones, and leaves unknown keys alone', () => {
  assert.equal(M.T.fill('到达了 {服务}。请先到 {服务} 网站核对（{code}）。', {'服务': 'Tripo3D', code: 'x'}), '到达了 Tripo3D。请先到 Tripo3D 网站核对（x）。');
  assert.equal(M.T.fill('{未知} {constructor}', {}), '{未知} {constructor}');
});

// Every status, every route kind and every inbox rule at once: the owner never reads a raw {placeholder}.
function richFixture() {
  const base = inboxFixture();
  const statuses = Object.keys(M.T.job).concat(['fixture_new_status']);
  base.jobs.push(...statuses.map((status, i) => ({id: 'job-' + status, tool: i % 2 ? 'tripo.studio.generate' : 'fal.generate', status, kind: 'tool',
    created: NOW - 86400 * (i % 3) - 60, updated: NOW - 30, verification: i % 2 ? null : 'ffprobe', cost_usd: i % 2 ? null : 0.18, cost_status: 'provider_report', artifact_count: i})),
  {id: 'job-orphan', tool: 'gone.tool', status: 'login_required', kind: 'tool', created: NOW - 5, updated: NOW - 5},
  {id: 'job-xyq', tool: 'xyq.image', status: 'submission_unknown', kind: 'tool', created: NOW - 7, updated: NOW - 7});
  base.tools.push(
    tool('elevenlabs.tts', 'elevenlabs', 'elevenlabs', 'missing_credential', {credentials: ['elevenlabs'], paid: true, health: {credential: 'elevenlabs'}}),
    tool('elevenlabs.web', 'browser', 'elevenlabs', 'browser_login_unknown', {url: 'https://elevenlabs.io/app/', paid: true}),
    tool('xyq.web.account', 'command', 'xyq', 'configured_not_verified', {executable: 'opencliapp'}),
    tool('pippit.cli.credit_balance', 'xyq', 'xyq', 'configured_not_verified', {executable: 'xyq'}),
    tool('xyq.image', 'xyq', 'xyq', 'configured_not_verified', {executable: 'xyq', paid: true}),
    tool('higgsfield.mcp', 'mcp', 'higgsfield', 'configured_not_verified', {server: 'higgsfield', oauth: 'higgsfield'}),
    tool('comfyui.queue', 'rest', 'comfyui', 'missing_origin'),
    tool('clo.handoff', 'desktop', 'clo', 'host_desktop_required'), tool('upwork.handoff', 'human', 'upwork', 'host_human_required'),
    tool('fixture.flow', 'workflow', 'fixture', 'workflow_dependencies_not_verified'), tool('catalog.x', 'rest', 'acme', 'catalog_only'),
    tool('wrangler.deploy', 'command', 'cloudflare_wrangler', 'configured_not_verified', {executable: 'wrangler', health: {cli_authentication: 'vendor_login_not_verified'}}),
    tool('blender.render', 'command', 'blender', 'cli_not_configured', {executable: 'blender'}),
    tool('mystery.tool', 'rest', 'mystery', 'fixture_new_state', {credentials: ['mystery']}));
  base.clis.push({name: 'opencliapp', state: 'configured_not_verified', path: '/fake/opencliapp'}, {name: 'xyq', state: 'configured_not_verified', path: '/fake/xyq'},
    {name: 'blender', state: 'cli_not_configured', detected_path: '/fake/found/blender'});
  base.overview.credits.providers.push({provider: 'xyq', label: '小云雀', brand: 'xyq', installed: true, bound: true, source: 'pippit.cli.credit_balance', source_kind: 'cli',
    status: 'error', error: {code: 'cli_protocol', message: 'Fixture.'}, next_source: 'pippit.cli.credit_balance', sources: ['xyq.web.account', 'pippit.cli.credit_balance']});
  base.connections.oauth.push({provider: 'higgsfield', status: 'pending', keep_login: false, service: {status: 'fixture_status'}});
  base.access = {clock: NOW, grants: [{id: 'p'.repeat(32), kind: 'project_session', agent: 'local-project', tools: [], workspace: '/fake/demo', credential_scope: ['fal'], exec_rules: [], expires_at: NOW + 99, revoked: false}],
    requests: [{id: 'a'.repeat(32), workspace: '/fake/demo', credentials: ['fal'], status: 'needs_unlock', created_at: NOW - 60, expires_at: NOW + 540, live: true}]};
  return base;
}

test('no rendered sentence, inbox detail, lead or job sentence from derive() contains a raw { or }', () => {
  const model = M.derive(richFixture(), NOW);
  const texts = [];
  const add = (where, value) => { if (typeof value === 'string') texts.push([where, value]); };
  for (const s of model.services) {
    add(s.key + ' lead', s.lead);
    for (const r of s.routes) {
      for (const field of ['title', 'sub', 'word', 'summary']) add(r.anchor + ' ' + field, r[field]);
      for (const line of [...r.body, ...(r.info || []), ...(r.notes || [])]) add(r.anchor + ' body', line);
      for (const step of r.steps || []) add(r.anchor + ' step', step.text);
      for (const [term, value] of r.facts) { add(r.anchor + ' fact', term); add(r.anchor + ' fact', value); }
      for (const a of r.actions) add(r.anchor + ' action', a.label);
    }
  }
  for (const v of model.tools.values()) { add(v.id + ' sentence', v.sentence); add(v.id + ' word', v.word); }
  for (const i of model.inbox) { add(i.id + ' title', i.title); add(i.id + ' detail', i.detail); add(i.id + ' action', i.action.label); }
  for (const j of model.jobs) for (const field of ['word', 'sentence', 'verification', 'cost', 'day']) add(j.id + ' ' + field, j[field]);
  for (const r of model.requests) for (const field of ['title', 'statusText', 'timeText']) add(r.id + ' ' + field, r[field]);
  for (const g of [...model.grants.active, ...model.grants.ended]) { add(g.id, g.title); g.lines.forEach(line => add(g.id, line)); }
  for (const a of model.agents) { add(a.agent, a.word); add(a.agent, a.detail); }
  assert.ok(texts.length > 200, 'the fixture covers a lot of copy');
  const sentences = model.jobs.filter(j => j.sentence).map(j => j.status);
  for (const code of ['submission_unknown', 'login_required']) assert.ok(sentences.includes(code), code);
  const raw = texts.filter(([, value]) => /[{}]/.test(value));
  assert.deepEqual(raw, []);
  const unknown = model.jobs.find(j => j.status === 'submission_unknown' && j.serviceKey === 'tripo');
  assert.equal(unknown.sentence, 'ATM 不能确定这次提交是否到达了 Tripo3D。请先到 Tripo3D 网站核对结果，不要让 Agent 重新提交，以免重复扣费。');
  assert.equal(model.jobs.find(j => j.id === 'job-orphan').sentence, '需要先登录服务。登录后让 Agent 继续这个任务。');
  assert.equal(model.jobs.find(j => j.id === 'job-xyq').sentence, 'ATM 不能确定这次提交是否到达了小云雀。请先到小云雀网站核对结果，不要让 Agent 重新提交，以免重复扣费。');
});

test('a bound MCP service missing its Key is in use, needs the owner, and offers one Key to add', () => {
  const model = M.derive(inboxFixture(), NOW);
  const linear = model.byKey.get('linear');
  assert.ok(linear.inUse);
  assert.equal(linear.state, 'attention');
  assert.equal(linear.lead, 'MCP 服务已设置，还缺少 Key：linear。');
  const mcp = linear.routes.find(r => r.kind === 'mcp'), key = linear.routes.find(r => r.kind === 'key');
  assert.equal(mcp.state, 'attention');
  assert.equal(mcp.word, '缺少 Key');
  assert.deepEqual(plain(mcp.actions), [{label: '到“API Key”里添加', kind: 'route', quiet: true,
    target: {service: 'linear', kind: 'key', id: 'linear', anchor: 'route-key-linear', focus: 'action'}}]);
  // One filled button for the one Key: the header. The Key route's own button is secondary.
  assert.equal(linear.primary.label, '添加 API Key');
  assert.equal(linear.primary.kind, 'dialog');
  assert.equal(key.actions[0].label, '添加 API Key');
  assert.ok(!key.actions[0].primary);
  assert.ok(model.services.filter(s => s.inUse && ['blocked', 'attention'].includes(s.state)).some(s => s.key === 'linear'));
  assert.ok(model.inbox.some(i => i.id === 'mcp-key:linear:linear'));
  // A declared Key name is something the owner set up: in use, like its inbox line says.
  assert.ok(model.byKey.get('acme.production').inUse);
  assert.ok(model.inbox.some(i => i.id === 'slot:acme.production'));
  // The services list and the inbox agree.
  assert.equal(model.counts.servicesAttention, model.services.filter(s => s.inUse && ['blocked', 'attention'].includes(s.state)).length);
  // A tool whose MCP configuration is not bound is still only 待设置 and not in use.
  const unbound = M.derive(data({tools: [tool('linear.mcp_tools', 'mcp', 'linear', 'mcp_not_configured', {server: 'linear'})]}), NOW).byKey.get('linear');
  assert.equal(unbound.inUse, false);
  assert.equal(unbound.state, 'setup');
});

test('one primary per intent: the header fix is not repeated, and an optional setup is secondary', () => {
  const model = M.derive(inboxFixture(), NOW);
  for (const s of model.services) {
    const filled = s.routes.flatMap(r => r.actions.filter(a => a.primary));
    for (const a of filled) assert.ok(!(s.primary && a.label === s.primary.label && JSON.stringify(a.target) === JSON.stringify(s.primary.target)), s.key + ' repeats ' + a.label);
    for (const r of s.routes) if (r.state === 'setup' && s.routes.some(o => o !== r && ['ready', 'attention', 'blocked'].includes(o.state)))
      assert.ok(!r.actions.some(a => a.primary), s.key + ' ' + r.anchor);
    for (const r of s.routes) assert.ok(!r.actions.some(a => a.kind === 'copy' && r.commands.some(c => c.text === a.target)), r.anchor);
  }
  // Higgsfield: the CLI login fix is the header; the Key route and the CLI route do not add more filled buttons.
  const higgs = M.derive(data({
    tools: [tool('higgsfield.generate', 'higgsfield', 'higgsfield', 'missing_credential', {credentials: ['higgsfield'], health: {credential: 'higgsfield'}}),
      tool('higgsfield.subscription.account', 'command', 'higgsfield', 'configured_not_verified', {executable: 'higgsfield'})],
    clis: [{name: 'higgsfield', state: 'configured_not_verified', path: '/fake/higgsfield'}],
    credits: [{provider: 'higgsfield', label: 'Higgsfield', brand: 'higgsfield', installed: true, bound: true, source: 'higgsfield.subscription.account', source_kind: 'cli',
      status: 'error', error: {code: 'login_required'}, next_source: 'higgsfield.subscription.account', sources: ['higgsfield.subscription.account']}],
    oauth: [{provider: 'higgsfield', status: 'ready', keep_login: true, expires_at: NOW + 3600, service: {status: 'load_failed'}}]}), NOW).byKey.get('higgsfield');
  assert.equal(higgs.primary.label, '检查登录');
  assert.deepEqual(plain(higgs.routes.flatMap(r => r.actions.filter(a => a.primary).map(a => a.label))), []);
});

test('a Key no tool reads does not lead: GitHub shows one filled button, and its lead matches it', () => {
  const github = M.derive(data({tools: ['repo', 'issues'].map(x => tool('github.' + x, 'command', 'github_cli', 'cli_not_configured', {executable: 'gh'})),
    connections: [conn('github')]}), NOW).byKey.get('github');
  assert.equal(github.state, 'setup');
  assert.equal(github.primary.label, '查看设置步骤');
  assert.equal(github.primary.route, github.routes.find(r => r.kind === 'program').anchor);
  assert.ok(!github.lead.includes('Key'), github.lead);
  assert.deepEqual(plain(github.routes.flatMap(r => r.actions.filter(a => a.primary).map(a => a.label))), []);
  // A Key that a program tool reads is that tool's fix, so it leads the header.
  const reads = M.derive(data({tools: [tool('acme.cli', 'command', 'acme', 'missing_credential', {executable: 'acme', credentials: ['acme'], health: {credential: 'acme'}})],
    connections: [conn('acme')]}), NOW).byKey.get('acme');
  assert.equal(reads.primary.label, '添加 API Key');
  assert.deepEqual(plain(reads.routes.flatMap(r => r.actions.filter(a => a.primary).map(a => a.label))), []);
});

test('a working ATM login can be replaced: 重新登录 sits next to 刷新状态', () => {
  for (const [status, keep, service] of [['ready', false, 'not_installed'], ['refreshing', false, 'not_installed'], ['ready', true, 'load_failed']]) {
    const route = M.derive(data({vault: {backend: 'keyring', state: 'unlock_not_checked'}, oauth: [{provider: 'higgsfield', status, keep_login: keep, expires_at: NOW + 3600, service: {status: service}}]}), NOW)
      .byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
    const relogin = route.actions.find(a => a.label === '重新登录');
    assert.ok(relogin, status);
    assert.deepEqual(plain(relogin.target), {d: 'oauth', keep});
    assert.ok(!relogin.primary);
    assert.ok(route.actions.some(a => a.label === '刷新状态'));
  }
  const missing = M.derive(data({oauth: [{provider: 'higgsfield', status: 'missing', keep_login: false, service: {status: 'not_installed'}}]}), NOW).byKey.get('higgsfield').routes.find(r => r.kind === 'oauth');
  assert.deepEqual(plain(missing.actions.map(a => a.label)), ['登录 Higgsfield', '刷新状态']);
});

test('a site whose credits come from a CLI explains the Chrome login and still offers the website', () => {
  const model = M.derive(richFixture(), NOW);
  const chrome = model.byKey.get('xyq').routes.find(r => r.kind === 'chrome');
  assert.equal(chrome.steps[2].text, '积分从 xyq 程序读取，不会检查 Chrome。Chrome 里是否已登录小云雀，在 Agent 使用时确认；可以先在 Chrome 里打开网站登录好。');
  assert.equal(chrome.check, undefined);
  assert.deepEqual(plain(chrome.open), {host: 'xyq.jianying.com', name: '小云雀'});
  // Credits failure codes read in Chinese; a translated code stays in the badge title.
  assert.equal(M.T.creditLabel('cli_protocol'), '程序返回的内容无法识别');
  assert.equal(M.T.creditTitle({code: 'cli_protocol', message: 'Fixture.'}), 'Fixture.（cli_protocol）');
  assert.equal(M.T.creditTitle({code: 'cli_failed', message: 'Fixture failure.'}), 'Fixture failure.');
  assert.equal(M.T.creditLabel('fixture_new_code'), '读取失败 · fixture_new_code');
  assert.equal(M.T.errorText('unknown_tool'), '有工具 ID 不在目录中，删掉后再检查。');
});

test('generated copy keeps a space between Chinese and Latin words, and none between two Chinese words', () => {
  // The copy template itself: names may be Chinese or Latin.
  for (const [name, text] of [['小云雀', '与小云雀共用'], ['Tripo Studio', '与 Tripo Studio 共用'], ['a、b 等 4 个工具', '与 a、b 等 4 个工具共用']])
    assert.equal(M.T.zh`与 ${name} 共用`, text);
  assert.equal(M.T.zh`（${'3 天前'}）`, '（3 天前）');
  assert.equal(M.T.zh`${'2 小时前'}检查`, '2 小时前检查');
  const model = M.derive(richFixture(), NOW);
  const texts = [...model.services.flatMap(s => [s.lead, ...s.routes.flatMap(r => [r.summary, r.sub, ...r.body, ...(r.info || []), ...(r.steps || []).map(x => x.text)])]),
    ...model.inbox.flatMap(i => [i.title, i.detail]), ...model.jobs.map(j => j.sentence)].filter(Boolean);
  const tight = texts.filter(t => /[一-鿿][A-Za-z0-9]|[A-Za-z0-9][一-鿿]/.test(t.replace(/\d+ (月|日|年)/g, '')));
  assert.deepEqual(tight, []);
  const loose = texts.filter(t => /[\u4e00-\u9fff] [\u4e00-\u9fff]/.test(t));
  assert.deepEqual(loose, []);
  // A Chinese service name gets no stray spaces either.
  assert.match(model.byKey.get('xyq').routes.find(r => r.kind === 'chrome').steps[0].text, /^已安装 \d+ 个小云雀工具$/);
});
