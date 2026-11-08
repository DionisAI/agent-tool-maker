'use strict';
// The console's view model: the ten bootstrap payloads in, states and Chinese words out.
// Pure: no DOM, no fetch, no storage. Every payload may be missing. Provider text is data only;
// the page inserts it as textContent.
(() => {
  const W = typeof window !== 'undefined' ? window : globalThis;
  const own = (dict, key) => dict !== null && typeof dict === 'object' && typeof key === 'string' && Object.hasOwn(dict, key);
  const arr = value => Array.isArray(value) ? value : [];
  const obj = value => value !== null && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const str = value => typeof value === 'string' ? value : '';
  // Keys may be CJK (for example {服务}); \w would only match ASCII.
  const fill = (text, vars = {}) => String(text).replace(/\{([^{}\s]+)\}/g, (match, key) => own(vars, key) ? String(vars[key]) : match);
  // Copy templates (zh`…`): where an interpolated name meets the text, Chinese and Latin are joined by one space and
  // two Chinese characters by none, whichever the name turns out to be (小云雀 or Tripo Studio, 等 4 个工具 or a tool id).
  // Full-width punctuation never takes a space; anything else is kept as written.
  const HAN = /[\u3400-\u4dbf\u4e00-\u9fff]/, WIDE = /[\u3000-\u303f\uff00-\uffef“”‘’]/, LATIN = /[A-Za-z0-9]/;
  const charKind = ch => !ch ? '' : WIDE.test(ch) ? 'wide' : HAN.test(ch) ? 'han' : LATIN.test(ch) ? 'latin' : 'other';
  function seam(left, right) {
    const a = charKind(left.replace(/ $/, '').slice(-1)), b = charKind(right.replace(/^ /, '').slice(0, 1));
    if (!a || !b || a === 'other' || b === 'other' || (a === 'latin' && b === 'latin')) return left + right;
    const sep = a === 'han' && b === 'han' || a === 'wide' || b === 'wide' ? '' : ' ';
    return left.replace(/ $/, '') + sep + right.replace(/^ /, '');
  }
  function zh(strings, ...values) {
    let out = strings[0];
    values.forEach((value, i) => { for (const piece of [String(value), strings[i + 1]]) if (piece) out = seam(out, piece); });
    return out;
  }
  // fill() with the same seams, for copy kept as {key} templates (job sentences).
  const fillZh = (text, vars = {}) => String(text).split(/\{([^{}\s]+)\}/)
    .reduce((out, piece, i) => { const value = i % 2 ? (own(vars, piece) ? String(vars[piece]) : '{' + piece + '}') : piece; return value ? seam(out, value) : out; }, '');
  // Code → copy lookups use own keys only: a code such as "constructor" is not a prototype member.
  function say(dict, code, fallback = '') {
    return own(dict, code) ? dict[code] : fill(fallback, {code: String(code)});
  }
  const collator = new Intl.Collator('zh-CN');
  const byName = (a, b) => collator.compare(a.name, b.name) || collator.compare(a.key, b.key);
  const basename = path => str(path).replace(/\/+$/, '').split('/').pop() || str(path);
  const unique = values => [...new Set(values.filter(Boolean))];

  // ---- Dates (local time) ----
  const PARTS = new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'});
  const FULL = new Intl.DateTimeFormat('zh-CN', {dateStyle: 'long', timeStyle: 'medium'});
  function parts(epoch) {
    const out = {};
    for (const p of PARTS.formatToParts(new Date(epoch * 1000))) out[p.type] = p.value;
    return {year: Number(out.year), month: Number(out.month), day: Number(out.day), hour: out.hour.padStart(2, '0'), minute: out.minute.padStart(2, '0')};
  }
  const nowSeconds = () => Date.now() / 1000;
  function date(epoch, now = nowSeconds()) {
    if (typeof epoch !== 'number' || !Number.isFinite(epoch)) return '';
    const p = parts(epoch), n = parts(now);
    return p.year === n.year ? `${p.month} 月 ${p.day} 日` : `${p.year} 年 ${p.month} 月 ${p.day} 日`;
  }
  function time(epoch) {
    if (typeof epoch !== 'number' || !Number.isFinite(epoch)) return '';
    const p = parts(epoch);
    return p.hour + ':' + p.minute;
  }
  const datetime = (epoch, now = nowSeconds()) => date(epoch, now) + ' ' + time(epoch);
  const fullDate = epoch => typeof epoch === 'number' && Number.isFinite(epoch) ? FULL.format(new Date(epoch * 1000)) : '';
  function day(epoch, now = nowSeconds()) {
    const p = parts(epoch), n = parts(now), y = parts(now - 86400);
    if (p.year === n.year && p.month === n.month && p.day === n.day) return '今天';
    if (p.year === y.year && p.month === y.month && p.day === y.day) return '昨天';
    return date(epoch, now);
  }
  function relative(epoch, now = nowSeconds()) {
    if (typeof epoch !== 'number' || !Number.isFinite(epoch)) return '';
    const s = Math.max(0, Math.round(now - epoch));
    return s < 60 ? '刚刚' : s < 3600 ? Math.floor(s / 60) + ' 分钟前' : s < 86400 ? Math.floor(s / 3600) + ' 小时前' : Math.floor(s / 86400) + ' 天前';
  }
  const daysLeft = (epoch, now) => Math.max(0, Math.ceil((epoch - now) / 86400));

  // ---- Words ----
  const STATE_WORDS = {ready: '可以使用', attention: '需要处理', blocked: '不能使用', setup: '待设置', handoff: '无需设置', off: '已停用'};
  const SEVERITY = ['blocked', 'attention', 'setup', 'ready', 'handoff'];
  const severity = state => { const i = SEVERITY.indexOf(state); return i < 0 ? SEVERITY.length : i; };
  const worst = states => states.reduce((a, b) => severity(b) < severity(a) ? b : a, 'handoff');
  const job = {
    completed: ['完成', 'done', 'ready'], queued: ['排队中', 'running', 'setup'], running: ['进行中', 'running', 'setup'],
    submitting: ['正在提交', 'running', 'setup'], awaiting_download: ['等待下载结果', 'running', 'setup'],
    requires_browser: ['等 Agent 的浏览器', 'running', 'handoff'], requires_desktop: ['等桌面软件', 'running', 'handoff'],
    submission_unknown: ['不确定是否已提交', 'needsYou', 'attention'], awaiting_confirmation: ['等你确认', 'needsYou', 'attention'],
    login_required: ['需要登录', 'needsYou', 'attention'], requires_human: ['等人工处理', 'needsYou', 'attention'],
    blocked: ['已受阻', 'needsYou', 'attention'], download_failed: ['下载失败', 'needsYou', 'blocked'],
    delivery_failed: ['交付失败', 'needsYou', 'blocked'], failed: ['失败', 'failed', 'blocked'],
  };
  const JOB_SENTENCE = {
    submission_unknown: 'ATM 不能确定这次提交是否到达了 {服务}。请先到 {服务} 网站核对结果，不要让 Agent 重新提交，以免重复扣费。',
    awaiting_confirmation: '需要你确认后才会继续（例如报价）。按 Agent 的提示操作。',
    login_required: '需要先登录 {服务}。登录后让 Agent 继续这个任务。',
    requires_human: '需要一个人来完成这一步。完成后由 Agent 把结果交回 ATM。',
    requires_browser: '正在等 Agent 在它自己的浏览器里完成。如果网站要求登录，请在那个浏览器窗口里登录。',
    requires_desktop: '正在等桌面软件里的操作完成。',
    blocked: '任务被挡住了，需要 Agent 或你处理后才能继续。',
    download_failed: '结果文件没能下载下来。让 Agent 刷新这个任务后重试下载。',
    delivery_failed: '结果没能交付到项目里。让 Agent 刷新这个任务。',
  };
  const VERIFY = {
    ffprobe: '已用 ffprobe 检查媒体文件', basic_file_validation: '已检查文件格式', file_exists_and_hash: '已确认文件存在并记录指纹',
    parsed_json: '返回内容是有效的 JSON', waiting_for_files: '等待交回文件', waiting_for_external_execution: '等待外部完成',
    browser_login_required: '需要在浏览器里登录', browser_recipe_steps_and_files: '网页步骤完成并收到文件',
    all_declared_child_jobs_completed: '所有子任务已完成', workflow_incomplete: '组合任务未完成',
    cli_exit_and_declared_outputs: '程序正常结束并产出了声明的文件', http_and_json_only: '只确认了请求成功',
    mcp_response_not_business_acceptance: '只确认 MCP 有回应', process_exit: '只确认程序已结束', not_started: '尚未检查',
  };
  const verifyWord = code => code === null || code === undefined ? '未检查' : say(VERIFY, code, '检查：{code}');
  function cost(cost_usd, status) {
    status = str(status);
    if (status === 'local_no_provider_charge') return '本机运行，无服务费';
    if (typeof cost_usd !== 'number' || !Number.isFinite(cost_usd)) return '费用未知';
    const amount = '$' + cost_usd.toFixed(cost_usd !== 0 && Math.abs(cost_usd) < 0.01 ? 4 : 2);
    const note = status.includes('estimate') ? '估算' : status.includes('report') ? '服务商报告' : status === 'unknown' || !status ? '未核对' : status;
    return amount + '（' + note + '）';
  }
  const VERIFY_RESULT = {probe_passed: '通过', unexpected_or_rejected_response: '返回内容不符合预期', auth_or_scope_rejected: 'Key 被拒绝或权限不够',
    rate_limited: '被限流，请稍后再试', service_unavailable: '服务暂时不可用'};
  const verifyResult = status => say(VERIFY_RESULT, status, '没有通过（{code}）');
  const VAULT = {unlock_not_checked: '可以使用', unlocked_in_this_process: '可以使用', needs_unlock: '可以使用 · 使用时需要解锁',
    keyring_unavailable: '系统钥匙串无法使用', keyring_key_missing: '系统钥匙串里找不到 ATM 的主密钥', vault_corrupt: '保管库数据损坏',
    not_initialized: '未设置'};
  const BACKEND = {keyring: '系统钥匙串', passphrase: 'ATM 主密码'};
  const PERMISSION = {external_write: '会改动外部内容', production: '可操作生产环境', execute_code: '会在本机运行程序'};
  const TAG = {paid: '可能扣费', external_write: '会改动外部内容', production: '生产环境', execute_code: '运行本机程序', custom: '自定义'};
  // Short labels for credits refresh errors; anything else shows its code.
  const CREDIT_ERRORS = {cli_not_configured: '程序未绑定', login_required: '需要登录', refresh_in_progress: '正在读取',
    credits_unreadable: '无法读取额度', runtime_unavailable: '服务未运行', cli_failed: '读取失败'};
  const CREDIT_REASONS = {cli_protocol: '程序返回的内容无法识别', cli_timeout: '读取超时', cli_start_failed: '程序无法启动',
    cli_output_limit: '程序输出过多', executable_changed: '程序已更新，需要重新确认', refresh_failed: '读取没有完成',
    execution_interrupted: '读取被中断', tool_disabled: '读取工具已停用', upstream_schema: '返回内容格式不对',
    upstream_rejected: '服务拒绝了读取请求', unsafe_path: '本机路径不安全，没有读取'};
  const creditLabel = code => own(CREDIT_ERRORS, code) ? CREDIT_ERRORS[code] : own(CREDIT_REASONS, code) ? CREDIT_REASONS[code] : '读取失败 · ' + code;
  // The badge title: the message; a code translated into a reason keeps the code there too.
  const creditTitle = error => { const code = str(error?.code), message = str(error?.message);
    return own(CREDIT_REASONS, code) ? (message ? message + '（' + code + '）' : code) : message; };
  const OAUTH_SERVICE = {loaded: '运行中', load_failed: '启动失败', load_conflict: '和已有服务冲突', not_installed: '未安装', foreground_only: '只在前台运行'};
  const ERROR = {
    vault_locked: 'ATM 主密码不正确（或保管库数据已损坏）。Key 仍是锁定的。',
    session_locked: 'Key 已锁定。请先点右上角的“解锁 30 分钟”。', broker_locked: 'Key 已锁定。请先点右上角的“解锁 30 分钟”。',
    needs_unlock: 'Key 已锁定。请先点右上角的“解锁 30 分钟”。',
    session_already_unlocked: 'Key 已经是解锁状态。', session_busy: '正在处理另一个解锁请求，请稍候。',
    interactive_required: '这一步需要你在本机终端里完成。',
    vault_not_initialized: '还没有设置 Key 保管方式。', not_initialized: '还没有设置 Key 保管方式。',
    vault_exists: '已经设置过保管方式。不要重新设置，已有 Key 会保留。',
    vault_corrupt: '保管库数据损坏。不要重新设置；请按文档里的恢复步骤处理。',
    keyring_unavailable: '系统钥匙串现在无法使用。已保存的 Key 没有丢失，不要重新设置。',
    keyring_key_missing: '系统钥匙串里找不到 ATM 的主密钥。不要重新设置，请按文档里的恢复步骤处理。',
    weak_passphrase: 'ATM 主密码至少需要 12 个字符。', bad_backend: '不支持这种保管方式。',
    bad_credential: 'Key 不能为空，也不能包含换行。', bad_expiry: '到期日格式不正确。', unknown_provider: 'ATM 不认识这个 Key 名称。',
    invalid_credential_name: 'Key 名称格式不对。小写字母开头，只能用小写字母、数字和 . _ -。',
    missing_credential: '还没有保存这个 Key。', credential_expired: '这个 Key 已过期，请先更换。',
    sync_conflict: '这个 Key 有版本冲突，相关调用已暂停。', state_changed: '状态刚被别处改过，已刷新。请再试一次。',
    setup_changed: '内容在你确认前变了，请重新检查后再批准。', plan_changed: '内容在你确认前变了，请重新检查后再批准。',
    definition_changed: '内容在你确认前变了，请重新检查后再批准。', approval_mismatch: '内容在你确认前变了，请重新检查后再批准。',
    grant_stale: '内容在你确认前变了，请重新检查后再批准。', conflict_changed: '内容在你确认前变了，请重新检查后再批准。',
    connection_changed: '内容在你确认前变了，请重新检查后再批准。', peer_policy_changed: '内容在你确认前变了，请重新检查后再批准。',
    approval_required: '确认内容不一致，没有做任何修改。',
    setup_conflict: '有内容不同的文件或已变化的程序，没有做任何修改。', skill_conflict: '有内容不同的文件或已变化的程序，没有做任何修改。',
    registration_changed: 'ATM 说明文件被手动改过，请先查看再决定是否替换。', unsupported_cli: '这个程序不在 ATM 的工具里。',
    unsupported_agent: '只支持 Claude Code 和 Codex。', invalid_agent: '只支持 Claude Code 和 Codex。',
    profile_conflict: '这个项目已有一份不同类型的授权配置，已保留原样。',
    invalid_grant: '授权不存在或已变化，已刷新。', grant_not_found: '授权不存在或已变化，已刷新。',
    unsafe_workspace: '请选择一个具体的项目目录，不要选整个主目录、根目录或 ATM 自己的目录。', workspace_missing: '这个项目目录不存在。',
    refresh_in_progress: '正在读取，请稍候。', credits_unreadable: '没能读到积分，已保留上次的数值。', invalid_cycle_day: '请输入 1–31 的整数。',
    tool_exists: '内置工具不能被工具定义替换。', invalid_toggle: '这个工具不能切换。', request_too_large: '文件太大（最多 8 MiB）。',
    forbidden_request: '请求被本机安全检查拒绝。请从 atm ui 打开的地址使用管理台。', invalid_request: '请求内容不完整或格式不对。',
    not_found: '找不到这一项，可能已被删除。', socket_path_too_long: '本机状态目录的路径太长，系统无法创建本地连接。请换一个更短的 ATM 目录。',
    sync_not_initialized: '还没有生成本机同步身份。', oauth_busy: '已经有一个登录在进行。', oauth_needs_keyring: '需要用系统钥匙串保管 Key 才能保持登录。',
    oauth_login_timeout: '登录超时，请重新登录。', oauth_conflict: '已经有 ATM 登录。要重新登录，请勾选“替换已有的 ATM 登录”。',
    oauth_needs_login: '需要重新登录 Higgsfield。', passkey_cancelled: '已取消。',
    passkey_prf_missing: '这个 Passkey 不支持加密扩展（PRF），没有绑定。请换用 1Password 等支持 PRF 的 Passkey。',
    passkey_prf_invalid: '加密扩展返回的数据无效，没有绑定。', passkey_cancel_cleanup_failed: '已取消，但清理本机绑定记录时出错。请刷新后再试。',
    passkey_vault_mismatch: '这个 Passkey 打不开当前的保管库，请改用 ATM 主密码。', passkey_expired: '操作超时，请重试。',
    passkey_busy: '正在处理另一个 Passkey 请求，请稍候。', passkey_dependency_missing: '需要先安装 Passkey 组件。',
    passkey_origin: '请从 atm ui 打开的 localhost 地址使用 Passkey。', passkey_limit: '已经绑定了允许的最多数量的 Passkey。',
    network: '连接不到本机 ATM。请确认 atm ui 还在运行。', unknown_tool: '有工具 ID 不在目录中，删掉后再检查。',
  };
  function errorText(code) {
    code = str(code);
    if (own(ERROR, code)) return ERROR[code];
    if (code.startsWith('oauth_')) return zh`Higgsfield 登录没有完成（${code}）。`;
    if (code.startsWith('passkey_')) return zh`Passkey 验证没有完成（${code}）。`;
    return zh`操作没有完成（${code || 'unknown'}）。`;
  }
  const knownError = code => own(ERROR, code);

  // ---- Joins ----
  function brandOf(provider, toolId = '') {
    const api = W.ATM_BRANDS;
    if (api && typeof api.get === 'function') return api.get(provider, toolId);
    const name = str(provider).trim();
    return {key: name.toLowerCase(), name: name || '自定义工具', initials: Array.from(name || '自定').slice(0, 2).join('').toUpperCase(), src: null};
  }
  // A service key is a navigable section part: lowercase letters, digits, . _ -.
  function slug(key) {
    let value = str(key).toLowerCase().replace(/[^a-z0-9_.-]/g, '_').slice(0, 80);
    if (!/^[a-z0-9]/.test(value)) value = ('x' + value).slice(0, 80);
    return value || 'custom';
  }
  const serviceKeyOf = (provider, toolId = '') => slug(brandOf(provider, toolId).key);
  const SITES = {
    tripo: {name: 'Tripo Studio', host: 'studio.tripo3d.ai', credits: 'tripo_studio', account: 'tripo.studio.account'},
    xyq: {name: '小云雀', host: 'xyq.jianying.com', credits: 'xyq', account: 'xyq.web.account'},
  };
  const siteOf = (key, name) => own(SITES, key) ? SITES[key] : {name: zh`${name} 网站`, host: null, credits: null, account: null};
  const KIND_ORDER = ['key', 'chrome', 'studio_server', 'program', 'oauth', 'mcp', 'recipe', 'origin', 'agent_browser', 'desktop', 'human', 'workflow', 'catalog'];
  const HANDOFF_KINDS = new Set(['agent_browser', 'desktop', 'human', 'workflow', 'catalog']);
  const KIND_TITLES = {key: 'API Key', chrome: '你的 Chrome 登录', program: '本机程序', oauth: 'ATM 登录', mcp: 'MCP 服务', recipe: 'ATM 网页登录',
    origin: '服务地址', studio_server: '服务器上的 Tripo Studio', agent_browser: '交给 Agent 的浏览器', desktop: '桌面软件', human: '人工',
    workflow: '组合流程', catalog: '仅供参考'};
  const KIND_CHIPS = {key: 'API Key', chrome: '你的 Chrome', program: '本机程序', oauth: 'ATM 登录', mcp: 'MCP', recipe: 'ATM 网页登录',
    origin: '服务地址', studio_server: '服务器浏览器', agent_browser: 'Agent 浏览器', desktop: '桌面软件', human: '人工', workflow: '组合流程', catalog: '仅供参考'};

  function exeOf(tool) {
    if (str(tool?.executable)) return tool.executable;
    const binary = basename(tool?.health?.binary?.path);
    if (binary) return binary;
    const hint = /--cli ([a-z0-9_.-]+)/.exec(str(tool?.health?.next_action));
    return hint ? hint[1] : '程序';
  }
  const serverOf = tool => str(tool?.server) || str(tool?.id).split('.')[0];
  const sessionOf = tool => str(tool?.session) || str(tool?.id);
  function credentialNames(tool) {
    const names = [...arr(tool?.credentials)];
    if (str(tool?.health?.credential)) names.push(tool.health.credential);
    return unique(names);
  }

  function routeKindOf(tool) {
    const adapter = tool?.adapter, state = tool?.health?.state, id = str(tool?.id);
    if (state === 'catalog_only' || adapter === 'catalog_only') return 'catalog';
    if (adapter === 'browser') return 'agent_browser';
    if (adapter === 'desktop') return 'desktop';
    if (adapter === 'human') return 'human';
    if (adapter === 'workflow') return 'workflow';
    if (adapter === 'web_recipe') return 'recipe';
    if (adapter === 'mcp') {
      const viaOauth = tool.oauth === 'higgsfield' || (tool.oauth === undefined && serviceKeyOf(tool.provider, id) === 'higgsfield' && serverOf(tool).includes('higgsfield'));
      return viaOauth ? 'oauth' : 'mcp';
    }
    const binary = basename(tool?.health?.binary?.path);
    if (tool.executable === 'opencliapp' || (tool.executable === undefined && (/^(tripo\.studio|xyq\.web)\./.test(id) || binary === 'opencliapp'))) return 'chrome';
    if ((tool.executable === 'atm' || tool.executable === undefined) && id.startsWith('tripo.server.')) return 'studio_server';
    if (['command', 'ffmpeg', 'ffprobe', 'xyq'].includes(adapter)) return 'program';
    // A self-hosted service API: its address is the setting (it may need no Key at all).
    if (state === 'missing_origin' || (!credentialNames(tool).length && !arr(tool?.optional_credentials).length && adapter === 'rest')) return 'origin';
    return 'key';
  }
  function routeIdOf(tool, kind = routeKindOf(tool)) {
    if (kind === 'program') return exeOf(tool);
    if (kind === 'mcp') return serverOf(tool);
    if (kind === 'recipe') return sessionOf(tool);
    if (kind === 'key') return credentialNames(tool)[0] || 'key';
    return kind;
  }
  const routeAnchor = (kind, id) => 'route-' + kind + '-' + slug(id);
  const routeAction = (label, service, kind, id, extra = {}) => ({label, kind: 'route', target: {service, kind, id, anchor: routeAnchor(kind, id), ...extra}});
  const dialog = (label, target, extra = {}) => ({label, kind: 'dialog', target, ...extra});
  const nav = (label, section, extra = {}) => ({label, kind: 'nav', target: section, ...extra});

  function tags(tool, custom) {
    const list = [];
    if (tool?.paid) list.push(TAG.paid);
    const permissions = arr(tool?.permissions);
    for (const key of ['external_write', 'production', 'execute_code']) if (permissions.includes(key)) list.push(TAG[key]);
    if (custom && custom.has(tool?.id)) list.push(TAG.custom);
    return list;
  }

  // Six states; each health code maps to one state, a word, a sentence and the fix the owner can take.
  function toolReadiness(tool, data = {}) {
    const health = obj(tool?.health), code = str(health.state), exe = exeOf(tool), server = serverOf(tool);
    const credential = str(health.credential) || credentialNames(tool)[0] || '';
    const vault = obj(data?.connections?.vault ?? data?.overview?.vault), session = obj(data?.session);
    const service = serviceKeyOf(tool?.provider, tool?.id), kind = routeKindOf(tool), id = routeIdOf(tool, kind);
    const toRoute = label => routeAction(label, service, kind, id);
    let r;
    const set = (state, sentence, fix = null, word = STATE_WORDS[state]) => { r = {state, word, sentence, fix}; };
    switch (code) {
      case 'configured_not_verified': set('ready', '可以使用（ATM 不会提前联网验证）。'); break;
      case 'needs_unlock': case 'unlock_not_checked': case 'unlocked_in_this_process':
        // The vault-lock rule: the Key is saved; whether it is unlocked lives only in the Key pill.
        set('ready', session.unlocked ? '可以使用。Key 已解锁。' : vault.backend === 'keyring' ? '可以使用。Key 保存在系统钥匙串里。'
          : '可以使用。Key 已保存；Key 锁定时，Agent 会打开授权窗口请你解锁。'); break;
      case 'missing_credential':
        // An MCP tool reports a missing Key only after its reviewed configuration is bound: half set up, so it needs the owner.
        if (kind === 'mcp') set('attention', zh`MCP 服务已设置，还缺少 Key：${credential}。`, dialog('添加 API Key', {d: 'key', mode: 'add', name: credential}), '缺少 Key');
        else set('setup', '缺少 Key：' + credential, dialog('添加 API Key', {d: 'key', mode: 'add', name: credential})); break;
      case 'credential_expired': set('blocked', credential + ' 的 Key 已过期。', dialog('更换 API Key', {d: 'key', mode: 'replace', name: credential}), 'Key 已过期'); break;
      case 'sync_conflict': set('blocked', credential + ' 的 Key 在两台设备上不一致，已暂停。', dialog('选择版本', {d: 'resolve', name: credential}), 'Key 冲突'); break;
      case 'cli_not_configured': set('setup', exe === '程序' ? '需要先绑定一个本机程序。' : zh`需要本机程序 ${exe}。`, toRoute('查看设置步骤')); break;
      case 'executable_unpinned': set('attention', zh`${exe} 已绑定，但没有记录程序指纹。`, toRoute('查看确认方法')); break;
      case 'executable_changed': set('blocked', zh`${exe} 已更新，需要你重新确认。`, toRoute('查看确认方法'), '程序已更新'); break;
      case 'executable_missing': set('blocked', zh`找不到之前绑定的 ${exe}。`, toRoute('查看确认方法'), '程序不见了'); break;
      case 'executable_not_executable': set('blocked', zh`${exe} 没有执行权限。`, toRoute('查看确认方法'), '不能运行'); break;
      case 'executable_unreadable': set('blocked', zh`无法读取 ${exe}。`, toRoute('查看确认方法'), '无法读取'); break;
      case 'mcp_not_configured': set('setup', zh`MCP 服务 ${server} 还没设置。`, toRoute('查看设置命令')); break;
      case 'missing_origin': set('setup', '需要先设置服务地址。', toRoute('查看设置命令')); break;
      case 'browser_dependency_missing': set('setup', '需要安装 ATM 的网页组件。', toRoute('查看安装方法')); break;
      case 'browser_session_missing': set('setup', '还没有用 ATM 登录这个网站。', toRoute('查看登录命令')); break;
      case 'browser_session_expired': set('blocked', 'ATM 网页登录已过期。', toRoute('查看登录命令'), '登录已过期'); break;
      case 'browser_session_scope': set('blocked', '已保存的登录不包含这个工具需要的网站。', toRoute('查看登录命令'), '登录范围不符'); break;
      case 'browser_login_unknown': set('handoff', '在 Agent 的浏览器里登录，ATM 里无需设置。'); break;
      case 'host_desktop_required': set('handoff', '由你或 Agent 在桌面软件里操作。'); break;
      case 'host_human_required': set('handoff', '由人来完成。'); break;
      case 'workflow_dependencies_not_verified': set('handoff', '组合流程：能否使用取决于其中每一步。', null, '看各步骤'); break;
      case 'catalog_only': set('handoff', '目录条目，不能直接运行。', null, '仅供参考'); break;
      case 'disabled': set('off', '你已停用：Claude Code 和 Codex 都不能调用它。'); break;
      case 'keyring_unavailable': case 'keyring_key_missing': case 'vault_corrupt':
        set('blocked', '无法打开 Key 保管库。已保存的 Key 没有丢失。', nav('查看', 'settings/keys'), '无法读取 Key'); break;
      case 'not_initialized': case 'vault_not_initialized': set('setup', '先设置 Key 的保管方式。', dialog('开始设置', {d: 'vault'})); break;
      default: set('attention', zh`ATM 返回了未知状态（${code || 'unknown'}）。`, dialog('查看详情', {d: 'tool', id: tool?.id}));
    }
    if (health.cli_authentication === 'vendor_login_not_verified') r.sentence += zh`登录由 ${exe} 自己管理，ATM 不检查。`;
    return r;
  }

  // Up to three names joined by 、, then 等 n 个工具.
  function listTools(ids, max = 3) {
    ids = unique(ids);
    if (!ids.length) return '';
    return ids.slice(0, max).join('、') + (ids.length > max ? zh` 等 ${ids.length} 个工具` : '');
  }
  const quote = value => "'" + String(value).replaceAll("'", "'\\''") + "'";
  const command = (exe, path) => `atm cli bind ${exe} ${path ? quote(path) : `'<${exe} 程序的完整路径>'`}`;
  const stripStop = text => str(text).replace(/[。.]$/, '');
  const hostOf = url => (/^https?:\/\/([^/?#@\s]+)/i.exec(str(url)) || [])[1] || '';

  function keyView(name, c, vault, now) {
    let state = 'ready', word = '可以使用', why = 'ready';
    if (c?.sync_conflict) [state, word, why] = ['blocked', '版本冲突', 'conflict'];
    else if (c?.expired) [state, word, why] = ['blocked', '已过期', 'expired'];
    else if (['keyring_unavailable', 'keyring_key_missing', 'vault_corrupt'].includes(vault.state) && c?.configured) [state, word, why] = ['blocked', '无法读取', 'vault'];
    else if (!c?.configured) [state, word, why] = ['setup', '待设置', 'setup'];
    else if (typeof c.expires_at === 'number' && c.expires_at - now <= 7 * 86400) [state, word, why] = ['attention', '即将到期', 'soon'];
    return {name, connection: c || null, state, word, why, usedBy: [], sharedFrom: null, optional: false};
  }

  function derive(data = {}, now = nowSeconds()) {
    data = obj(data);
    const overview = obj(data.overview), tools = arr(data.tools), conns = obj(data.connections), jobsIn = arr(data.jobs), clis = arr(data.clis);
    const sync = obj(data.sync), access = obj(data.access), ext = obj(data.extensions), session = obj(data.session), passkeys = obj(data.passkeys);
    const vault = obj(conns.vault ?? overview.vault);
    const connList = arr(conns.connections).filter(c => str(c?.provider));
    const connBy = new Map(connList.map(c => [c.provider, c]));
    const oauthRows = arr(conns.oauth).filter(o => str(o?.provider));
    const creditRows = arr(overview?.credits?.providers);
    const custom = new Set(arr(ext.custom_tools).map(t => t?.id));
    const clisBy = new Map(clis.map(c => [c?.name, c]));
    const sessions = arr(ext.browser_sessions);
    const history = new Map(arr(conns.verification_history).map(v => [v?.provider, v]));
    const peers = arr(sync.peers);
    const services = new Map();
    const ensure = (key, provider, nameHint, toolId = '') => {
      if (!services.has(key)) {
        const brand = brandOf(provider, toolId);
        services.set(key, {key, name: nameHint || brand.name || key, provider, brand: {...brand, key: brand.key}, tools: [], keyNames: new Map(),
          routes: [], keys: [], credits: null, oauth: null, jobs: [], grants: [], requests: [], inUse: false});
      }
      return services.get(key);
    };
    const toolViews = new Map();
    for (const tool of tools) {
      if (!str(tool?.id)) continue;
      const key = serviceKeyOf(tool.provider, tool.id), service = ensure(key, tool.provider, brandOf(tool.provider, tool.id).name, tool.id);
      const kind = routeKindOf(tool), readiness = toolReadiness(tool, data);
      const view = {id: tool.id, title: str(tool.title) || tool.id, tool, serviceKey: key, route: kind, routeId: routeIdOf(tool, kind),
        enabled: tool.enabled !== false, paid: tool.paid === true, tags: tags(tool, custom), custom: custom.has(tool.id), ...readiness};
      toolViews.set(tool.id, view);
      service.tools.push(view);
      for (const name of arr(tool.credentials)) service.keyNames.set(name, {...service.keyNames.get(name), required: true});
      for (const name of arr(tool.optional_credentials)) service.keyNames.set(name, {optional: true, ...service.keyNames.get(name)});
      if (str(tool.health?.credential)) service.keyNames.set(tool.health.credential, {...service.keyNames.get(tool.health.credential), required: true});
    }
    for (const c of connList) {
      const key = serviceKeyOf(c.provider), label = str(c.label) && c.label !== c.provider ? c.label : '';
      const service = ensure(key, c.provider, label || brandOf(c.provider).name);
      if (!service.keyNames.has(c.provider)) service.keyNames.set(c.provider, {own: true});
    }
    for (const row of creditRows) {
      if (!str(row?.provider)) continue;
      const key = serviceKeyOf(row.brand || row.provider);
      ensure(key, row.brand || row.provider).credits = row;
    }
    for (const row of oauthRows) ensure(serviceKeyOf(row.provider), row.provider).oauth = row;
    // Which tools read each Key (any service).
    const usedBy = new Map();
    for (const view of toolViews.values()) for (const name of [...credentialNames(view.tool), ...arr(view.tool.optional_credentials)]) {
      if (!usedBy.has(name)) usedBy.set(name, []);
      usedBy.get(name).push(view.id);
    }
    const keyIndex = new Map();
    const keyOf = name => {
      if (!keyIndex.has(name)) {
        const view = keyView(name, connBy.get(name), vault, now);
        view.usedBy = unique(usedBy.get(name) || []);
        view.owner = serviceKeyOf(name);
        keyIndex.set(name, view);
      }
      return keyIndex.get(name);
    };
    const jobsAll = jobsIn.filter(j => str(j?.id)).map(j => jobView(j, toolViews, services, creditRows, now));
    const grants = grantViews(access, now);
    const requests = requestViews(access, connBy, services, now);
    // Routes per service.
    for (const service of services.values()) {
      const site = siteOf(service.key, service.name);
      const groups = new Map();
      for (const view of service.tools) {
        if (view.route === 'key') continue;
        const gid = view.route + ':' + view.routeId;
        if (!groups.has(gid)) groups.set(gid, {kind: view.route, id: view.routeId, tools: []});
        groups.get(gid).tools.push(view);
      }
      if (service.oauth && ![...groups.values()].some(g => g.kind === 'oauth')) groups.set('oauth:oauth', {kind: 'oauth', id: 'oauth', tools: []});
      const keyNames = [...service.keyNames.keys()].sort(collator.compare);
      const kinds = new Set([...groups.values()].map(g => g.kind));
      const context = {service, site, data, vault, session, clisBy, creditRows, sessions, history, peers, now, services, kinds, keyNames, toolViews};
      for (const name of keyNames) {
        const key = keyOf(name), info = service.keyNames.get(name) || {};
        const routeTools = service.tools.filter(v => v.route === 'key' && credentialNames(v.tool).includes(name));
        const shared = key.owner !== service.key && services.has(key.owner) ? key.owner : null;
        const optional = !routeTools.length && info.optional && !info.required;
        const keyRow = {...key, sharedFrom: shared, optional};
        service.keys.push(keyRow);
        service.routes.push(keyRoute(keyRow, routeTools, context));
      }
      for (const group of groups.values()) service.routes.push(otherRoute(group, context));
      service.routes.sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) || collator.compare(a.id, b.id));
      finishService(service, context);
    }
    for (const j of jobsAll) if (j.serviceKey && services.has(j.serviceKey)) services.get(j.serviceKey).jobs.push(j);
    for (const g of [...grants.active, ...grants.ended]) {
      const touched = new Set([...g.tools.map(id => toolViews.get(id)?.serviceKey), ...g.keys.map(name => serviceKeyOf(name))]);
      for (const key of touched) if (key && services.has(key)) services.get(key).grants.push(g);
    }
    for (const req of requests) for (const name of req.credentials) {
      const key = serviceKeyOf(name);
      if (services.has(key)) services.get(key).requests.push(req);
    }
    // In use: anything the owner set up, installed or started, or anything that needs the owner.
    const sessionNames = new Set(sessions.map(s => s?.name));
    for (const service of services.values()) {
      const toolIds = new Set(service.tools.map(v => v.id));
      service.inUse = service.keys.some(k => k.connection?.configured || k.connection?.sync_conflict)
        || service.tools.some(v => ['program', 'chrome', 'studio_server'].includes(v.route) && str(clisBy.get(exeOf(v.tool))?.path))
        || service.tools.some(v => v.custom) || (service.oauth && service.oauth.status !== 'missing')
        || Boolean(service.credits?.installed) || service.jobs.length > 0 || service.grants.length > 0 || service.requests.length > 0
        || service.tools.some(v => !v.enabled) || service.tools.some(v => v.route === 'recipe' && sessionNames.has(sessionOf(v.tool)))
        || service.routes.some(r => !HANDOFF_KINDS.has(r.kind) && r.state === 'ready' && r.kind !== 'key')
        // Something needs the owner, or a reviewed MCP configuration is bound (its Key may still be missing).
        || service.routes.some(r => ['attention', 'blocked'].includes(r.state))
        || service.tools.some(v => v.route === 'mcp' && str(v.tool.health?.state) && v.tool.health.state !== 'mcp_not_configured')
        // A Key name the owner declared (its inbox line says it still needs a Key).
        || arr(ext.credential_slots).some(name => typeof name === 'string' && service.keyNames.has(name));
      service.toolIds = toolIds;
      service.haystack = [service.key, service.name, ...service.tools.flatMap(v => [v.id, v.title, ...arr(v.tool.capabilities)])].join('\n').toLowerCase();
    }
    const list = [...services.values()].sort((a, b) => (b.inUse - a.inUse) || byName(a, b));
    const inbox = inboxItems({services, list, toolViews, connList, connBy, vault, clis, oauthRows, creditRows, jobsAll, overview, passkeys, ext, keyOf, now, custom});
    const enabledTools = [...toolViews.values()].filter(v => v.enabled);
    const agents = arr(overview.agents).map(agentView);
    const registered = agents.filter(a => a.installed);
    const firstRun = {
      show: !vault.backend || !registered.length,
      steps: [
        {id: 'vault', done: Boolean(vault.backend), backend: vault.backend || null},
        {id: 'agents', done: registered.length > 0, labels: registered.map(a => a.label)},
        {id: 'service', done: list.some(s => s.inUse), count: list.filter(s => s.inUse).length},
      ],
    };
    return {
      services: list, byKey: services, tools: toolViews, keys: keyIndex, inbox, requests, grants, agents,
      jobs: jobsAll.sort((a, b) => b.created - a.created),
      counts: {
        servicesReady: list.filter(s => s.state === 'ready').length,
        servicesAttention: list.filter(s => s.inUse && ['blocked', 'attention'].includes(s.state)).length,
        servicesSetup: list.filter(s => !s.inUse && s.routes.some(r => !HANDOFF_KINDS.has(r.kind))).length,
        servicesInUse: list.filter(s => s.inUse).length,
        toolsEnabled: enabledTools.length, toolsTotal: toolViews.size, toolsPaidEnabled: enabledTools.filter(v => v.paid).length,
        keysSaved: [...keyIndex.values()].filter(k => k.connection?.configured).length, keysTotal: keyIndex.size,
        liveRequests: requests.filter(r => r.live).length,
      },
      firstRun, vault, session, now,
    };
  }

  function keyRoute(key, routeTools, ctx) {
    const {service, now} = ctx, c = key.connection || {};
    const many = ctx.keyNames.length > 1;
    const title = key.optional ? '可选 Key · ' + key.name : many || key.sharedFrom ? 'API Key · ' + key.name : 'API Key';
    const chip = many ? 'Key · ' + key.name : 'API Key';
    const optionalExe = key.optional ? exeOf(service.tools.find(v => arr(v.tool.optional_credentials).includes(key.name))?.tool) : '';
    const sub = key.optional ? zh`可选。保存后 ${optionalExe} 会用这个 Key；不保存时使用 ${optionalExe} 自己的登录。`
      : ctx.kinds.has('chrome') || ctx.kinds.has('oauth') || service.credits ? '开发者 API Key，按用量计费，与网站订阅积分分开。' : '开发者 API Key。';
    const users = listTools(key.usedBy) || '相关工具';
    const add = dialog('添加 API Key', {d: 'key', mode: 'add', name: key.name}, {primary: true});
    const replace = (label, primary) => dialog(label, {d: 'key', mode: 'replace', name: key.name}, {primary});
    const test = dialog('联网测试', {d: 'verify', name: key.name});
    const remove = dialog('移除', {d: 'remove', name: key.name}, {danger: true});
    let body = [], actions = [], summary = '';
    const facts = [];
    const factList = () => {
      facts.push(['用于', key.usedBy.length ? key.usedBy.join('、') : '还没有工具使用它']);
      if (typeof c.configured_at === 'number') facts.push(['保存于', date(c.configured_at, now)]);
      facts.push(['到期', typeof c.expires_at === 'number' ? zh`${date(c.expires_at, now)}（还剩 ${daysLeft(c.expires_at, now)} 天）` : '没有填写']);
      const probe = ctx.history.get(key.name);
      facts.push(['联网测试', probe ? zh`${verifyResult(probe.status)}（${relative(probe.checked_at, now)}）${probe.credential_changed ? '；之后更换过 Key，这个结果不再适用' : ''}` : '还没测试过']);
      const send = ctx.peers.filter(p => !p?.revoked && arr(p?.send).includes(key.name)).map(p => str(p?.card?.name));
      const receive = ctx.peers.filter(p => !p?.revoked && arr(p?.receive).includes(key.name)).map(p => str(p?.card?.name));
      if (send.length || receive.length) facts.push(['同步', [send.length ? '会发给 ' + send.join('、') : '', receive.length ? '接收自 ' + receive.join('、') : ''].filter(Boolean).join('；')]);
      if (ctx.vault.backend === 'passphrase' && !ctx.session.unlocked) facts.push(['使用时', 'Key 锁定时，Agent 会打开授权窗口请你解锁。']);
      if (key.sharedFrom) facts.push(['共用', zh`与 ${ctx.services.get(key.sharedFrom)?.name || key.sharedFrom} 共用这个 Key`]);
    };
    if (key.why === 'setup') {
      body = [key.usedBy.length ? zh`还没有保存 API Key。保存后，${users} 就能使用。` : '还没有保存这个 Key。'];
      actions = [add];
      summary = key.usedBy.length ? zh`还没有 API Key，${users} 暂时不能使用。` : zh`还没有保存 ${key.name} 的 Key。`;
    } else if (key.why === 'ready') {
      factList(); actions = [test, replace('更换', false), remove];
    } else if (key.why === 'soon') {
      const n = daysLeft(c.expires_at, now);
      body = [zh`${n} 天后到期（${date(c.expires_at, now)}）。到期后 ${users} 会停止。`]; factList();
      actions = [replace('更换 API Key', true), test, remove];
      summary = zh`API Key 将在 ${n} 天后到期。`;
    } else if (key.why === 'expired') {
      body = [zh`已在 ${date(c.expires_at, now)} 过期，${users} 现在不能使用。只需更换这一个 Key。`];
      actions = [replace('更换 API Key', true), remove];
      summary = zh`API Key 已过期，${users} 现在不能使用。`;
    } else if (key.why === 'conflict') {
      body = ['这台电脑和其他设备上的这个 Key 不一致。为避免用错，相关调用已暂停。'];
      actions = [dialog('选择版本', {d: 'resolve', name: key.name}, {primary: true})];
      summary = zh`Key 在两台设备上不一致，${users} 已暂停。`;
    } else {
      body = ['系统钥匙串现在无法使用，已保存的 Key 没有丢失。不要重新设置保管方式。'];
      actions = [nav('查看解决方法', 'settings/keys', {primary: true})];
      summary = '无法读取已保存的 Key。';
    }
    if (c.connect_supported === false) {
      body.push('ATM 已经不认识这个 Key 名称（对应的工具可能已被移除）。');
      actions = c.configured ? [remove] : [];
    }
    return {kind: 'key', id: key.name, anchor: routeAnchor('key', key.name), title, chip, sub, state: key.state, word: key.word,
      summary, facts, steps: null, body, info: null, commands: [], actions, tools: routeTools, key};
  }

  function programCondition(exe, ctx, tools) {
    const row = ctx.clisBy.get(exe) || {};
    const states = tools.map(v => str(v.tool.health?.state));
    let state = str(row.state) || states.find(s => s.startsWith('executable_') || s === 'cli_not_configured') || 'configured_not_verified';
    return {row, state, path: str(row.path) || str(tools.map(v => v.tool.health?.binary?.path).find(Boolean)), detected: str(row.detected_path)};
  }

  function otherRoute(group, ctx) {
    const {service, site, now} = ctx, {kind, id, tools} = group;
    const enabled = tools.filter(v => v.enabled);
    let state = tools.length && !enabled.length ? 'off' : enabled.length ? worst(enabled.map(v => v.state)) : 'setup';
    const ids = listTools(tools.map(v => v.id));
    const route = {kind, id, anchor: routeAnchor(kind, id), title: KIND_TITLES[kind], chip: KIND_CHIPS[kind], sub: '', state, word: '',
      summary: '', facts: [], steps: null, body: [], info: null, commands: [], actions: [], tools, notes: []};
    // A command shows in its own box with a 复制 button; the route adds no second copy button for it.
    const cmd = (text, label = '') => route.commands.push({text, label});
    if (kind === 'chrome') {
      route.title = '你的 Chrome 登录 · ' + site.name; route.chip = '你的 Chrome';
      route.sub = zh`${tools.length} 个工具通过 OpenCLIApp 在你已登录的 Chrome 里操作 ${site.host || site.name}，用的是网站会员积分。登录保存在 Chrome 里，ATM 不保存密码。`;
      const exe = exeOf(tools[0]?.tool) || 'opencliapp', program = programCondition(exe, ctx, tools);
      const others = [...ctx.services.values()].filter(s => s.key !== service.key && s.tools.some(v => v.route === 'chrome' && exeOf(v.tool) === exe)).map(s => s.name);
      const steps = [{state: 'ok', text: zh`已安装 ${tools.length} 个 ${site.name} 工具`}];
      const bind = command(exe, program.path);
      let programOk = false;
      if (program.state === 'configured_not_verified' && program.path) {
        programOk = true;
        steps.push({state: 'ok', text: '已绑定 OpenCLIApp' + (others.length ? zh`（与 ${others.join('、')} 共用）` : ''), mono: program.path});
      } else if (program.state === 'cli_not_configured' && program.detected) {
        steps.push({state: 'todo', text: zh`在 ${program.detected} 找到了 OpenCLIApp，确认后即可使用。`, action: dialog('绑定', {d: 'setup', clis: [exe]})});
      } else if (program.state === 'cli_not_configured') {
        steps.push({state: 'todo', text: '还没绑定 OpenCLIApp。', note: 'OpenCLIApp 装在 .app 应用包里，不在 PATH 中，需要在终端绑定一次。程序一般在 OpenCLIApp.app/Contents/MacOS/ 目录下（在“访达”里右键 OpenCLIApp，选“显示包内容”）。',
          command: "atm cli bind opencliapp '<OpenCLIApp 程序的完整路径>'"});
      } else {
        const text = program.state === 'executable_changed' ? 'OpenCLIApp 已更新，需要你重新确认。' : program.state === 'executable_missing' ? '找不到之前绑定的 OpenCLIApp：' + program.path
          : program.state === 'executable_not_executable' ? 'OpenCLIApp 没有执行权限。' : program.state === 'executable_unreadable' ? '无法读取 OpenCLIApp。' : 'OpenCLIApp 已绑定，但没有记录程序指纹。';
        steps.push({state: 'todo', text, command: `atm cli bind opencliapp ${quote(program.path)}`});
      }
      const row = site.credits ? ctx.creditRows.find(r => r?.provider === site.credits) : null;
      const accountInstalled = site.account && ctx.toolViews.has(site.account);
      const fromSite = row && row.source === site.account, readsSite = row && row.next_source === site.account;
      // Another source (such as a CLI) reads this site's credits: the Chrome login is not checked from here.
      const reader = row && !readsSite && str(row.next_source) ? exeOf(ctx.toolViews.get(row.next_source)?.tool) : '';
      let login = false;
      if (fromSite && row.status === 'ok') steps.push({state: 'ok', text: zh`Chrome 已登录 ${site.name}（${relative(row.checked_at, now)}检查）`});
      else if (fromSite && row.status === 'error' && row.error?.code === 'login_required') {
        login = true;
        steps.push({state: 'todo', text: zh`上次检查时，Chrome 里没有登录 ${site.name}（${relative(row.checked_at, now)}）。登录后点“检查 Chrome 登录”。`});
      } else if (fromSite && row.status === 'error') steps.push({state: 'todo', text: zh`上次检查没有成功：${creditLabel(str(row.error?.code))}（${relative(row.checked_at, now)}）。`});
      else if (accountInstalled && reader) steps.push({state: 'none', text: zh`积分从 ${reader} 程序读取，不会检查 Chrome。Chrome 里是否已登录 ${site.name}，在 Agent 使用时确认${site.host ? '；可以先在 Chrome 里打开网站登录好' : ''}。`});
      else if (accountInstalled) steps.push({state: 'none', text: '还没检查过 Chrome 是否已登录。'});
      else steps.push({state: 'none', text: '登录状态只能在 Agent 使用时确认。'});
      route.steps = steps;
      const check = row && row.next_source === site.account && programOk;
      // Opening the website is always possible, so the login step never ends without a next step.
      if (site.host) route.open = {host: site.host, name: site.name};
      if (check) {
        route.check = {provider: site.credits, host: site.host, name: site.name};
        route.notes.push(zh`检查会让 Chrome 打开 ${site.name}，只读取登录状态和积分，不生成任何内容，并在记录里留下一条“读取额度”。`);
      }
      if (tools.some(v => v.paid)) route.notes.push('标着“可能扣费”的工具会消耗网站积分；每次扣费都要 Agent 明确声明。');
      if (login && state !== 'off' && severity(state) > severity('attention')) state = 'attention';
      route.state = state;
      if (state === 'off') route.word = '已停用';
      else if (state === 'setup') {
        route.word = '待设置';
        route.actions = [program.detected ? dialog('绑定', {d: 'setup', clis: [exe]}, {primary: true}) : {...routeAction('查看设置步骤', service.key, kind, id, {step: 2}), primary: true}];
        route.summary = '还没绑定 OpenCLIApp。';
      } else if (state === 'blocked') {
        route.word = '不能使用';  // The rebind command is in step 2, with its own 复制 button.
        route.summary = 'OpenCLIApp 已更新或不见了，需要你重新确认。';
      } else if (state === 'attention') {
        route.word = login ? '需要登录' : STATE_WORDS.attention;
        route.actions = check ? [{label: '检查 Chrome 登录', kind: 'credits', target: [site.credits], primary: true}] : [];
        route.summary = login ? zh`${site.name} 的 ${tools.length} 个工具需要你先在 Chrome 里登录。` : enabled.find(v => v.state === 'attention')?.sentence || '';
      } else route.word = '可以使用';
    } else if (kind === 'program' || kind === 'studio_server') {
      const exe = kind === 'program' ? id : exeOf(tools[0]?.tool), program = programCondition(exe, ctx, tools);
      const credits = ctx.creditRows.find(r => r?.source_kind === 'cli' && r.status === 'error' && r.error?.code === 'login_required'
        && tools.some(v => v.id === r.source));
      if (kind === 'studio_server') {
        route.title = '服务器上的 Tripo Studio'; route.chip = '服务器浏览器';
        route.sub = 'tripo.server.* · 在另一台服务器上长期运行 Tripo Studio 浏览器，用同一份网站订阅。';
        route.body = ['由你在服务器上安装和启动，登录在服务器的浏览器里完成。可以让 Agent 先运行：'];
        cmd('atm studio status');
        route.word = state === 'off' ? '已停用' : STATE_WORDS[state];
        route.summary = state === 'setup' ? '服务器上的 Tripo Studio 还没设置。' : enabled.find(v => v.state === state)?.sentence || '';
      } else {
        route.title = '本机程序 · ' + exe; route.chip = exe + ' 程序';
        route.sub = zh`${tools.length} 个工具会在这台电脑上运行 ${exe}。绑定只记录程序的位置和指纹，不会运行它。`;
        const bind = command(exe, program.path), path = program.path;
        if (state === 'off') route.word = '已停用';
        if (program.state === 'cli_not_configured' && program.detected) {
          route.word ||= '待设置'; route.body = [zh`在 ${program.detected} 找到了 ${exe}，确认后即可使用。`];
          route.actions = [dialog('绑定', {d: 'setup', clis: [exe]}, {primary: true})];
          route.summary = zh`在本机找到了 ${exe}，确认绑定后即可使用。`;
        } else if (program.state === 'cli_not_configured') {
          route.word ||= '待设置'; route.body = [zh`本机没有找到 ${exe}。先安装它；如果装好后它不在 PATH 里，在终端运行：`];
          cmd(command(exe));
          route.summary = zh`需要本机程序 ${exe}。`;
        } else if (program.state.startsWith('executable_')) {
          const table = {
            executable_changed: ['程序已更新', zh`${path} 的内容和你上次确认的不一样（可能刚升级）。确认是你安装的版本后，在终端重新绑定：`, zh`${exe} 已更新，需要你重新确认。`],
            executable_missing: ['程序不见了', zh`${path} 不存在，可能已卸载或移动。装好后在终端重新绑定：`, zh`找不到之前绑定的 ${exe}。`],
            executable_not_executable: ['不能运行', zh`${path} 没有执行权限。`, zh`${exe} 没有执行权限。`],
            executable_unreadable: ['无法读取', zh`无法读取 ${path}。`, zh`无法读取 ${exe}。`],
            executable_unpinned: ['需要重新绑定', zh`${exe} 已绑定，但没有记录程序指纹。在终端重新绑定一次：`, zh`${exe} 已绑定，但没有记录程序指纹。`],
          }[program.state] || ['不能使用', `${path}：${program.state}`, zh`${exe} 不能使用。`];
          route.word ||= table[0]; route.body = [table[1]]; cmd(bind);
          route.summary = table[2];
        } else if (credits) {
          if (state !== 'off' && severity(state) > severity('attention')) state = 'attention';
          route.word ||= '需要重新登录';
          route.body = [zh`${exe} 自己的登录已失效。` + (exe === 'higgsfield' ? '请在终端登录：' : zh`请用 ${exe} 自己的登录命令登录。`)];
          if (exe === 'higgsfield') cmd('higgsfield auth login');
          route.actions = credits.next_source && tools.some(v => v.id === credits.next_source) ? [{label: '检查登录', kind: 'credits', target: [credits.provider], primary: true}] : [];
          route.summary = zh`${exe} 自己的登录已失效。`;
        } else {
          route.word ||= '可以使用';
          if (path) route.facts.push(['程序', path], ['指纹', '已记录']);
          if (tools.some(v => v.tool.health?.cli_authentication === 'vendor_login_not_verified')) route.facts.push(['登录', zh`使用 ${exe} 自己的登录（ATM 不保存，也不检查）`]);
          for (const name of unique(tools.flatMap(v => arr(v.tool.optional_credentials)))) route.facts.push(['可选 Key', zh`${name}（${ctx.data?.connections?.connections?.find?.(c => c?.provider === name)?.configured ? '已保存' : '未保存'}）`]);
        }
      }
      route.state = state;
    } else if (kind === 'oauth') {
      const o = obj(service.oauth), status = str(o.status) || 'missing', svc = obj(o.service), backend = ctx.vault.backend;
      route.title = 'ATM 登录 · Higgsfield MCP'; route.chip = 'ATM 登录';
      route.sub = 'ATM 自己保存的 Higgsfield 订阅登录（ATM OAuth），供 Higgsfield MCP 工具使用；和 higgsfield 程序的登录、开发者 API Key 互不影响。';
      const table = {missing: ['setup', '尚未登录', '登录 Higgsfield', '还没有用 ATM 登录 Higgsfield。'], pending: ['attention', '等你在浏览器里确认', '刷新状态', '等你在浏览器里完成 Higgsfield 登录。'],
        ready: ['ready', '已登录', null, ''], refreshing: ['ready', '正在续期', null, ''],
        refresh_unknown: ['attention', '续期结果不确定，请重新登录', '重新登录', 'ATM 登录续期结果不确定，请重新登录。'],
        expired: ['blocked', '登录已过期', '重新登录', 'ATM 登录已过期，Higgsfield MCP 工具暂时不能使用。'],
        needs_login: ['blocked', '需要重新登录', '重新登录', '需要重新登录 Higgsfield，Higgsfield MCP 工具暂时不能使用。'],
        denied: ['blocked', '登录没有获批', '重新登录', 'ATM 登录没有获批。']};
      const [oState, word, primary, summary] = own(table, status) ? table[status] : ['attention', '状态：' + status, '重新登录', 'Higgsfield 的 ATM 登录状态：' + status + '。'];
      state = oState; route.word = word; route.summary = summary;
      if (state === 'ready' && o.keep_login && svc.status !== 'loaded') {
        state = 'attention'; route.word = '自动续期没有运行';
        route.summary = '自动续期没有运行，ATM 登录到期后需要重新登录。';
      }
      route.state = state;
      if (primary === '刷新状态') route.actions.push({label: '刷新状态', kind: 'refresh', primary: true});
      else if (primary) route.actions.push(dialog(primary, {d: 'oauth', keep: false}, {primary: true}));
      route.facts.push(['有效至', typeof o.expires_at === 'number' ? datetime(o.expires_at, now) : '登录后显示']);
      if (status === 'pending' && typeof o.login_deadline === 'number') route.facts.push(['登录期限', datetime(o.login_deadline, now) + ' 前完成']);
      route.facts.push(['自动续期', o.keep_login ? '已开启' : '未开启']);
      route.facts.push(['后台续期服务', say(OAUTH_SERVICE, str(svc.status) || 'not_installed', '{code}'), !own(OAUTH_SERVICE, str(svc.status) || 'not_installed')]);
      if (str(o.last_error)) route.facts.push(['最近一次续期失败', o.last_error, true]);
      if (!o.keep_login && backend !== 'keyring') route.facts.push(['自动续期', '自动续期需要用系统钥匙串保管 Key；你现在用的是 ATM 主密码。']);
      if (primary !== '刷新状态') route.actions.push({label: '刷新状态', kind: 'refresh'});
      if (!primary) route.actions.push(dialog('重新登录', {d: 'oauth', keep: Boolean(o.keep_login)}));
      if (o.keep_login) route.actions.push(dialog('停止自动续期', {d: 'stop-renew'}));
      else if (status === 'ready' && backend === 'keyring') route.actions.push(dialog('开启自动续期', {d: 'oauth', keep: true}));
    } else if (kind === 'mcp') {
      route.title = 'MCP 服务 · ' + id; route.chip = 'MCP';
      route.sub = zh`${tools.length} 个工具通过 MCP 服务 ${id} 运行。`;
      const codes = enabled.map(v => str(v.tool.health?.state));
      const bindCmd = `atm mcp bind ${id} --config '<配置文件路径>' --approve-config`;
      if (state === 'off') route.word = '已停用';
      if (codes.includes('mcp_not_configured')) {
        route.word ||= '待设置'; route.body = ['需要在终端绑定一次经过你审阅的 MCP 配置：']; cmd(bindCmd);
        route.summary = zh`MCP 服务 ${id} 还没设置。`;
      } else if (codes.includes('missing_credential')) {
        const name = str(enabled.find(v => v.tool.health?.state === 'missing_credential')?.tool.health.credential);
        // Bound but its Key is not saved: one Key to add, on the Key route above (no second 添加 API Key button).
        route.word ||= '缺少 Key'; route.body = [zh`MCP 已设置，还需要 Key：${name}。`];
        route.actions = [{...routeAction('到“API Key”里添加', service.key, 'key', name, {focus: 'action'}), quiet: true}];
        route.summary = zh`MCP 服务已设置，还缺少 Key：${name}。`;
      } else if (codes.some(c => c.startsWith('executable_'))) {
        const path = str(enabled.map(v => v.tool.health?.binary?.path).find(Boolean));
        route.word ||= codes.includes('executable_changed') ? '程序已更新' : '不能使用';
        route.body = [zh`MCP 服务的程序 ${path} 已变化，需要你重新确认：`]; cmd(bindCmd);
        route.summary = zh`MCP 服务 ${id} 的程序已变化，需要你重新确认。`;
      } else {
        route.word ||= state === 'ready' ? '可以使用' : STATE_WORDS[state];
        route.facts.push(['服务', id]);
        route.summary = enabled.find(v => v.state === state)?.sentence || '';
      }
    } else if (kind === 'recipe') {
      const toolId = tools[0]?.id || id, origins = unique(tools.flatMap(v => arr(v.tool.origins)));
      route.title = 'ATM 网页登录 · ' + id; route.chip = 'ATM 网页登录';
      route.sub = zh`ATM 用自己的浏览器登录 ${origins.length ? origins.join('、') : '这个网站'}，把登录加密保存在这台电脑上（不随 Key 同步）。登录只能在终端完成。`;
      const codes = enabled.map(v => str(v.tool.health?.state));
      if (state === 'off') route.word = '已停用';
      if (codes.includes('browser_dependency_missing')) {
        route.word ||= '待设置'; route.body = ['需要先安装 ATM 的网页组件（[web] 扩展）和它使用的 Chromium。']; route.summary = '需要安装 ATM 的网页组件。';
      } else if (codes.includes('browser_session_missing')) {
        route.word ||= '待设置'; route.body = ['还没有登录。在终端运行：']; cmd(`atm web login ${toolId}`);
        route.summary = '还没有用 ATM 登录这个网站。';
      } else if (codes.includes('browser_session_expired')) {
        route.word ||= '登录已过期'; route.body = ['登录已过期。在终端重新登录：']; cmd(`atm web login ${toolId} --replace`);
        route.summary = 'ATM 网页登录已过期。';
      } else if (codes.includes('browser_session_scope')) {
        route.word ||= '登录范围不符'; route.body = ['已保存的登录覆盖的网站和这个工具需要的不一致。在终端重新登录：']; cmd(`atm web login ${toolId} --replace`);
        route.summary = '已保存的登录不包含这个工具需要的网站。';
      } else {
        route.word ||= state === 'ready' ? '可以使用' : STATE_WORDS[state];
        const saved = ctx.sessions.find(s => s?.name === id);
        if (saved) {
          route.facts.push(['保存于', date(saved.saved_at, now)]);
          route.facts.push(['到期', saved.expired ? '已过期' : typeof saved.expires_at === 'number' ? date(saved.expires_at, now) : '没有设置到期']);
        }
        route.more = {label: '删除本机保存的登录：', text: `atm web remove-session ${id} --apply`};
      }
    } else if (kind === 'origin') {
      const provider = str(tools[0]?.tool.provider);
      route.title = '自建服务地址'; route.chip = '服务地址';
      route.sub = zh`${ids} 连接你自己运行的服务（例如本机的 ComfyUI），需要先设置地址。`;
      route.body = ['确认地址无误后，在终端运行：'];
      const text = `atm origin set ${provider} '<服务地址>' --approve-origin`;
      cmd(text);
      route.word = state === 'off' ? '已停用' : STATE_WORDS[state];
      if (state === 'setup') route.summary = '需要先设置服务地址。';
    } else if (kind === 'agent_browser') {
      route.sub = ids;
      const host = hostOf(tools.map(v => str(v.tool.url)).find(Boolean)) || zh`${service.name} 网站`;
      route.info = [zh`${ids} 不在 ATM 里登录。Claude Code 或 Codex 用到它时，会在它自己的浏览器里打开 ${host}；如果网站要求登录，请在那个浏览器窗口里登录。ATM 不保存这个登录，也不会提前检查。`,
        '任务会显示“等 Agent 的浏览器”，完成后由 Agent 把文件交回 ATM。'];
      if (tools.some(v => v.paid)) route.info.push(zh`在网站上的操作可能消耗你在 ${service.name} 的会员额度。`);
      const keyWorks = service.routes.some(r => r.kind === 'key' && ['ready', 'attention'].includes(r.state));
      if (ctx.keyNames.length && service.tools.some(v => v.route === 'key') && !keyWorks) route.info.push(zh`想让 Agent 不经过浏览器、直接调用 ${service.name}？在上面的“API Key”里保存 Key。`);
      if (ctx.kinds.has('chrome')) route.info.push('这和“你的 Chrome 登录”是同一个网站，但用的是 Agent 的浏览器，不是你的 Chrome。');
      route.word = state === 'off' ? '已停用' : '无需在 ATM 设置';
      route.handoffNote = ids;
    } else {
      const table = {desktop: ['无需在 ATM 设置', zh`由你或 Agent 在本机的 ${service.name} 桌面软件里操作；完成后由 Agent 把文件交回 ATM。ATM 不检查这个软件是否已安装。`],
        human: ['无需在 ATM 设置', zh`由一个人来完成（例如在 ${service.name} 上雇人或报价）。ATM 只记录任务状态。`],
        workflow: ['看各步骤', '这个流程由多个工具组成，每一步的工具都要各自可以使用。'], catalog: ['仅供参考', '目录条目，不能直接运行。']}[kind];
      route.title = {desktop: '交给桌面软件', human: '交给人工', workflow: '组合流程', catalog: '仅供参考'}[kind];
      route.chip = {desktop: '桌面软件', human: '人工', workflow: '组合流程', catalog: '仅供参考'}[kind];
      route.sub = ids; route.body = [table[1]]; route.word = state === 'off' ? '已停用' : table[0];
      route.handoffNote = ids;
    }
    if (!route.word) route.word = STATE_WORDS[route.state] || '';
    if (!route.summary && ['blocked', 'attention', 'setup'].includes(route.state)) route.summary = enabled.find(v => v.state === route.state)?.sentence || '';
    return route;
  }

  function finishService(service, ctx) {
    const routes = service.routes;
    const all = service.tools.length, disabled = service.tools.filter(v => !v.enabled).length;
    if (all && disabled === all) {
      service.state = 'off';
      service.lead = zh`你已停用全部 ${all} 个工具。`;
      service.primary = {label: '全部允许…', kind: 'bulk', target: {service: service.key, enable: true}, primary: true};
      return;
    }
    const states = routes.map(r => r.state);
    service.state = states.includes('blocked') && !states.includes('ready') ? 'blocked'
      : states.includes('blocked') || states.includes('attention') ? 'attention'
      : states.includes('ready') ? 'ready' : states.includes('setup') ? 'setup'
      : states.length && states.every(s => s === 'off') ? 'off' : 'handoff';
    const live = routes.filter(r => r.state !== 'off');
    const handoff = live.filter(r => HANDOFF_KINDS.has(r.kind));
    const ready = live.filter(r => r.state === 'ready');
    const count = rs => rs.reduce((n, r) => n + r.tools.filter(v => v.enabled).length, 0);
    const handoffNote = handoff.length ? unique(handoff.map(r => r.handoffNote)).join('、') + ' 不需要在 ATM 设置。' : '';
    const severe = ['blocked', 'attention'].map(s => live.find(r => r.state === s)).find(Boolean);
    const setup = live.filter(r => r.state === 'setup');
    if (severe) service.lead = stripStop(severe.summary || severe.word) + (ready.length ? '；其余方式可以使用。' : '。');
    else if (!live.length) service.lead = '还没有设置。';
    else if (live.every(r => r.state === 'handoff')) service.lead = '无需在 ATM 设置。Agent 会在它自己的浏览器或软件里完成，ATM 只记录结果。';
    else if (!setup.length) service.lead = zh`可以使用。Agent 可以通过 ${[...ready, ...handoff].map(r => r.title).join('、')} 使用 ${count([...ready, ...handoff])} 个工具。`;
    // The lead names the setup that unblocks tools (the header's fix), not a Key no tool reads yet.
    else if (!ready.length) service.lead = '还没有设置。' + ((setup.find(r => r.tools.some(v => v.enabled)) || setup[0]).summary || '') + handoffNote;
    else service.lead = zh`可以使用。Agent 可以通过 ${[...ready, ...handoff].map(r => r.title).join('、')} 使用 ${count([...ready, ...handoff])} 个工具；${setup.map(r => r.title).join('、')} 还没设置，用到时再设置。`;
    // One primary per intent. The header carries the fix of the most severe route (blocked > attention > setup, in route
    // order). A link to another route on this page stands for that route's own fix. A route fixed by a command (shown with
    // its own 复制 button) gets a header link that jumps to the command. Next to a working route, a setup is optional.
    const readsKey = r => r.kind === 'key' && service.tools.some(v => v.enabled && arr(r.key?.usedBy).includes(v.id));
    const eligible = routes.filter(r => r.tools.some(v => v.enabled) || (r.kind === 'key' && !service.tools.length) || readsKey(r) || r.kind === 'oauth');
    const firstOf = r => r.actions.find(a => a.primary) || r.actions[0] || null;
    const fixOf = r => {
      const a = firstOf(r), to = a?.kind === 'route' && a.target?.service === service.key ? routes.find(x => x.anchor === a.target.anchor) : null;
      if (to && to !== r && firstOf(to)) return firstOf(to);
      if (a) return a;
      const link = (r.commands.length || arr(r.steps).some(step => step.command)) && r.tools.find(v => v.enabled && v.state === r.state && v.fix?.kind === 'route')?.fix;
      return link ? {...link, target: {...link.target, focus: 'command'}} : null;
    };
    service.primary = null;
    for (const s of ['blocked', 'attention', 'setup']) {
      if (s === 'setup' && ready.length) break;
      const route = eligible.find(r => r.state === s && fixOf(r));
      if (route) { service.primary = {...fixOf(route), primary: true, quiet: false, route: route.anchor}; break; }
    }
    // With a header fix, it is the page's only filled button; an optional setup never outshines a working route.
    for (const r of routes) {
      const optional = r.state === 'setup' && routes.some(o => o !== r && ['ready', 'attention', 'blocked'].includes(o.state));
      r.actions = r.actions.map(a => a.primary && (optional || service.primary) ? {...a, primary: false} : a);
    }
  }

  function jobView(j, toolViews, services, creditRows, now) {
    const tool = toolViews.get(j.tool), code = str(j.status);
    const [word, group, state] = own(job, code) ? job[code] : [zh`其他状态（${code}）`, 'running', 'attention'];
    const refreshSources = new Set(creditRows.flatMap(r => arr(r?.sources)));
    const kind = j.kind === 'credits_refresh' || j.kind === 'tool' ? j.kind : refreshSources.has(j.tool) ? 'credits_refresh' : 'tool';
    const serviceKey = tool ? tool.serviceKey : null;
    const serviceName = serviceKey ? services.get(serviceKey)?.name || serviceKey : '服务';
    const created = typeof j.created === 'number' ? j.created : 0, updated = typeof j.updated === 'number' ? j.updated : created;
    return {id: j.id, tool: str(j.tool), title: tool ? tool.title : '', serviceKey, serviceName, brand: tool ? tool.tool.provider : str(j.tool).split('.')[0],
      status: code, word, group, state, needsYou: group === 'needsYou', kind, created, updated,
      day: day(created, now), time: time(created), full: fullDate(created), updatedText: datetime(updated, now), createdText: datetime(created, now),
      verification: verifyWord(j.verification), cost: cost(j.cost_usd, j.cost_status), files: Number(j.artifact_count) || 0,
      sentence: own(JOB_SENTENCE, code) ? fillZh(JOB_SENTENCE[code], {'服务': serviceName}) : ''};
  }

  function grantViews(access, now) {
    const clock = typeof access.clock === 'number' ? access.clock : now;
    const active = [], ended = [];
    for (const g of arr(access.grants)) {
      if (!str(g?.id)) continue;
      const kind = str(g.kind) || 'tools', keys = arr(g.credential_scope), tools = arr(g.tools);
      const live = !g.revoked && typeof g.expires_at === 'number' && g.expires_at > clock;
      const agentLabel = g.agent === 'claude' ? 'Claude Code' : g.agent === 'codex' ? 'Codex' : 'Claude Code / Codex';
      const view = {id: g.id, short: g.id.slice(0, 8), kind, active: live, keys, tools, workspace: str(g.workspace), agent: str(g.agent), agentLabel,
        revoked: Boolean(g.revoked), lines: [], time: ''};
      const ended_ = g.revoked ? '已撤销' : '已过期';
      if (kind === 'project_session') {
        view.title = zh`项目 ${basename(g.workspace)} · 由授权窗口批准`;
        view.lines = ['可用 Key：' + (keys.join('、') || '无'), '项目里运行的程序都能用这些 Key', '锁定 Key 后立即停止'];
        const left = (g.expires_at - clock) / 60;
        view.time = live ? (left < 60 ? zh`还剩 ${Math.max(1, Math.ceil(left))} 分钟` : zh`到 ${time(g.expires_at)}`) : ended_;
      } else if (kind === 'exec') {
        view.title = zh`命令授权 · ${basename(g.workspace)}`;
        const programs = unique(arr(g.exec_rules).map(rule => str(rule?.program) || str(arr(rule?.argv)[0])).map(p => basename(p)));
        view.lines = ['可用 Key：' + (keys.join('、') || '无'), '允许的程序：' + (programs.join('、') || '无')];
        view.time = live ? '有效至 ' + datetime(g.expires_at, now) : ended_;
      } else {
        view.title = zh`${agentLabel} · 受限授权`;
        view.lines = ['只能用：' + (tools.join('、') || '无'), '项目 ' + str(g.workspace), '可消耗额度：' + (g.allow_paid ? '是' : '否'),
          ...arr(g.permissions).map(p => say(PERMISSION, p, '{code}'))];
        view.time = live ? '有效至 ' + datetime(g.expires_at, now) : ended_;
      }
      (live ? active : ended).push(view);
    }
    return {active, ended};
  }

  function requestViews(access, connBy, services, now) {
    if (!Array.isArray(access.requests)) return [];
    return access.requests.filter(r => str(r?.id)).map(r => {
      const names = arr(r.credentials).filter(n => typeof n === 'string');
      const status = str(r.status), live = r.live === true;
      const statusText = status === 'starting' ? '正在打开授权窗口…' : !live ? '授权窗口已经关闭。请让 Agent 重新运行 atm start 再试。'
        : status === 'needs_unlock' ? '授权窗口已在浏览器里打开：在那里输入 ATM 主密码或用 Passkey 确认。'
        : status === 'needs_approval' ? 'Key 已解锁：在授权窗口里点“允许并继续”即可。' : '授权窗口已在浏览器里打开。';
      return {id: r.id, workspace: str(r.workspace), basename: basename(r.workspace), credentials: names, status, live,
        title: zh`有 Agent 请求在项目 ${basename(r.workspace)} 中使用 ${names.length} 个 Key`,
        chips: names.map(name => {
          const saved = Boolean(connBy.get(name)?.configured), service = services.get(serviceKeyOf(name));
          return {name, ready: saved, label: saved ? zh`${service?.name || name} · 已保存` : zh`${name} · 在授权窗口里填写`};
        }),
        statusText, timeText: zh`${relative(r.created_at, now)}发起 · ${Math.max(0, Math.ceil((r.expires_at - now) / 60))} 分钟后失效`};
    });
  }

  function agentView(a) {
    a = obj(a);
    const label = str(a.label) || str(a.agent), path = str(a.skill_path) || str(a.default_skill_path);
    const view = {agent: str(a.agent), label, path, installed: a.state === 'registered_not_host_verified', state: 'setup', word: '还没安装 ATM', detail: '', actions: []};
    if (a.state === 'registered_not_host_verified') {
      Object.assign(view, {state: 'ready', word: '已安装 ATM · 新开的会话会加载', detail: path,
        actions: [dialog('重新安装', {d: 'setup', agents: [a.agent]}), dialog('移除', {d: 'unregister', agent: a.agent, label}, {danger: true})]});
    } else if (a.state === 'registration_changed') {
      Object.assign(view, {state: 'attention', word: 'ATM 说明文件被改过', detail: '为安全起见，ATM 不会自动覆盖。查看后再决定是否替换。',
        actions: [dialog('查看并替换…', {d: 'setup', agents: [a.agent], replace: true}, {primary: true})], short: dialog('查看', {d: 'setup', agents: [a.agent], replace: true})});
    } else if (str(a.detected_executable)) {
      Object.assign(view, {detail: zh`已在本机找到 ${a.detected_executable}`, actions: [dialog('安装到 ' + label, {d: 'setup', agents: [a.agent]}, {primary: true})],
        short: dialog('安装', {d: 'setup', agents: [a.agent]})});
    } else {
      Object.assign(view, {detail: zh`本机没有找到 ${label}。可以先安装 ATM 说明文件，装好 ${label} 后生效。`,
        actions: [dialog('安装到 ' + label, {d: 'setup', agents: [a.agent]})], short: dialog('安装', {d: 'setup', agents: [a.agent]})});
    }
    return view;
  }

  // Something the owner set up, installed or started is broken or half-done. A never-set-up service is not.
  function inboxItems(ctx) {
    const {services, toolViews, connList, vault, clis, oauthRows, creditRows, jobsAll, overview, passkeys, ext, keyOf, now, custom} = ctx;
    const items = [], covered = new Set();
    const svc = key => services.get(key) || {key, name: key, brand: brandOf(key)};
    const push = (rule, subject, sev, serviceKey, title, detail, action, time = 0) => {
      const s = serviceKey ? svc(serviceKey) : null;
      items.push({id: rule + ':' + subject, rule, sev, serviceKey, serviceName: s?.name || '', provider: s?.provider || serviceKey || '', title, detail, action, time});
    };
    const toolsOf = name => listTools(keyOf(name).usedBy) || '相关工具';
    for (const c of connList) {
      const key = serviceKeyOf(c.provider), name = svc(key).name;
      if (c.configured && c.expired)
        push('key-expired', c.provider, 'bad', key, zh`${name} 的 API Key 已过期`, zh`${toolsOf(c.provider)} 现在不能使用。到期时间：${date(c.expires_at, now)}。`, dialog('更换 API Key', {d: 'key', mode: 'replace', name: c.provider}));
      if (c.sync_conflict)
        push('key-conflict', c.provider, 'bad', key, zh`${name} 的 Key 在两台设备上不一致`, zh`为避免用错 Key，${toolsOf(c.provider)} 已暂停。请选择保留哪个版本；不会按时间自动选择。`, dialog('选择版本', {d: 'resolve', name: c.provider}));
      if (c.configured && !c.expired && !c.sync_conflict && typeof c.expires_at === 'number' && c.expires_at - now <= 7 * 86400)
        push('key-soon', c.provider, 'warn', key, zh`${name} 的 API Key 将在 ${daysLeft(c.expires_at, now)} 天后到期`, zh`到期日：${date(c.expires_at, now)}。`, dialog('更换 API Key', {d: 'key', mode: 'replace', name: c.provider}));
    }
    if (['keyring_unavailable', 'keyring_key_missing', 'vault_corrupt'].includes(vault.state))
      push('vault', vault.state, 'bad', null, '无法打开 Key 保管库', '已保存的 Key 没有丢失。不要重新设置保管方式。', nav('查看', 'settings/keys'));
    const broken = {executable_changed: exe => zh`${exe} 程序已更新，需要你重新确认`, executable_missing: exe => zh`找不到 ${exe} 程序`,
      executable_not_executable: exe => zh`${exe} 不能运行`, executable_unreadable: exe => zh`${exe} 不能运行`};
    for (const row of clis) {
      if (!str(row?.path) || !own(broken, str(row.state))) continue;
      const users = [...toolViews.values()].filter(v => v.enabled && exeOf(v.tool) === row.name && ['program', 'chrome', 'studio_server'].includes(v.route));
      if (!users.length) continue;
      users.forEach(v => covered.add(v.id));
      const owners = unique(users.map(v => v.serviceKey)), first = users[0];
      const exe = row.name === 'opencliapp' ? 'OpenCLIApp' : row.name;
      const action = owners.length > 1 ? nav('查看确认方法', 'settings/programs') : routeAction('查看确认方法', first.serviceKey, first.route, first.routeId);
      push('program', row.name, 'bad', owners.length === 1 ? owners[0] : null, broken[row.state](exe), zh`用到它的 ${users.length} 个工具已暂停，直到你确认。`, action);
    }
    const sessionsHit = new Map();
    for (const v of toolViews.values()) {
      const code = v.tool.health?.state;
      if (!v.enabled || !['browser_session_expired', 'browser_session_scope'].includes(code)) continue;
      const gid = v.serviceKey + ':' + v.routeId + ':' + code;
      if (!sessionsHit.has(gid)) sessionsHit.set(gid, {v, code, ids: []});
      sessionsHit.get(gid).ids.push(v.id); covered.add(v.id);
    }
    for (const [gid, {v, code, ids}] of sessionsHit)
      push('session', gid, 'bad', v.serviceKey, zh`${svc(v.serviceKey).name} 的 ATM 网页登录${code === 'browser_session_expired' ? '已过期' : '范围不符'}`,
        zh`${listTools(ids)} 需要你在终端重新登录一次。`, routeAction('查看登录命令', v.serviceKey, v.route, v.routeId));
    for (const o of oauthRows) {
      const key = serviceKeyOf(o.provider), status = str(o.status), svcRow = obj(o.service);
      const words = {expired: ['bad', '已过期'], needs_login: ['bad', '需要重新登录'], denied: ['bad', '没有获批'], refresh_unknown: ['warn', '续期结果不确定']};
      if (own(words, status))
        push('oauth', status, words[status][0], key, zh`Higgsfield 的 ATM 登录${words[status][1]}`, 'Higgsfield MCP 工具暂时不能使用。', dialog('重新登录', {d: 'oauth', keep: false}));
      if (o.keep_login && svcRow.status !== 'loaded')
        push('renew', o.provider, 'warn', key, 'Higgsfield 自动续期没有运行', typeof o.expires_at === 'number' ? zh`ATM 登录将在 ${datetime(o.expires_at, now)} 到期，之后需要你重新登录。` : 'ATM 登录到期后需要你重新登录。', routeAction('查看', key, 'oauth', 'oauth'));
      if (status === 'pending')
        push('oauth-pending', o.provider, 'info', key, '等你在浏览器里完成 Higgsfield 登录', (typeof o.login_deadline === 'number' ? zh`${datetime(o.login_deadline, now)} 前有效。` : '') + '完成后点“刷新状态”。', {label: '刷新状态', kind: 'refresh'});
    }
    for (const row of creditRows) {
      if (!row?.installed || row.status !== 'error' || row.error?.code !== 'login_required') continue;
      const key = serviceKeyOf(row.brand || row.provider), site = siteOf(key, svc(key).name), source = toolViews.get(row.source);
      const website = row.source_kind !== 'cli';
      const exe = source ? exeOf(source.tool) : str(row.next_executable);
      const action = source ? routeAction('查看登录方法', key, source.route, source.routeId) : nav('查看登录方法', 'services/' + key);
      push('credits-login', row.provider, 'warn', key, zh`${str(row.label)} 需要重新登录`,
        website ? zh`Chrome 里没有登录 ${site.name}，读不到积分，相关工具也可能失败。` : zh`${exe} 程序自己的登录已失效，读不到积分。`, action);
    }
    const mcpHit = new Map();
    for (const v of toolViews.values()) {
      if (!v.enabled || v.route !== 'mcp' || v.tool.health?.state !== 'missing_credential') continue;
      const name = str(v.tool.health.credential), gid = v.routeId + ':' + name;
      if (!mcpHit.has(gid)) mcpHit.set(gid, {v, name, ids: []});
      mcpHit.get(gid).ids.push(v.id); covered.add(v.id);
    }
    for (const [gid, {v, name, ids}] of mcpHit)
      push('mcp-key', gid, 'warn', v.serviceKey, zh`${svc(v.serviceKey).name} 的 MCP 服务已设置，但缺少 Key：${name}`, zh`保存这个 Key 后，${listTools(ids)} 就能使用。`, dialog('添加 API Key', {d: 'key', mode: 'add', name}));
    const customHit = new Map();
    for (const v of toolViews.values()) {
      if (!v.enabled || !custom.has(v.id) || covered.has(v.id)) continue;
      if (!['cli_not_configured', 'mcp_not_configured', 'missing_credential', 'missing_origin', 'browser_session_missing'].includes(v.tool.health?.state)) continue;
      const gid = v.serviceKey + ':' + v.route + ':' + v.routeId;
      if (!customHit.has(gid)) customHit.set(gid, {v, ids: []});
      customHit.get(gid).ids.push(v.id);
    }
    for (const [gid, {v, ids}] of customHit) {
      const route = services.get(v.serviceKey)?.routes.find(r => r.kind === v.route && r.id === v.routeId);
      push('custom', gid, 'warn', v.serviceKey, zh`${svc(v.serviceKey).name} 有 ${ids.length} 个新装的工具还不能用`, route?.summary || v.sentence, routeAction('查看设置步骤', v.serviceKey, v.route, v.routeId));
    }
    for (const j of jobsAll) {
      if (j.kind !== 'tool') continue;
      if (j.status === 'submission_unknown')
        push('job-unknown', j.id, 'warn', j.serviceKey, zh`不确定 ${j.tool} 是否已提交`, zh`${j.time} · 为避免重复扣费，请先到 ${j.serviceName} 网站核对，不要让 Agent 重新提交。`, nav('查看记录', 'jobs', {job: j.id}), j.created);
      else if (['awaiting_confirmation', 'login_required', 'requires_human', 'blocked', 'download_failed', 'delivery_failed'].includes(j.status))
        push('job-needs', j.id, 'info', j.serviceKey, `${j.tool}：${j.word}`, j.sentence, nav('查看记录', 'jobs', {job: j.id}), j.created);
    }
    const agents = arr(overview.agents);
    for (const a of agents) if (a?.state === 'registration_changed')
      push('agent-changed', a.agent, 'warn', null, zh`${a.label} 里的 ATM 说明文件被改过`, '为安全起见，ATM 不会自动覆盖。', dialog('查看', {d: 'setup', agents: [a.agent], replace: true}));
    if (agents.some(a => a?.state === 'registered_not_host_verified'))
      for (const a of agents) if (a?.state === 'not_registered' && str(a.detected_executable))
        push('agent-missing', a.agent, 'info', null, zh`检测到 ${a.label}，还没安装 ATM`, zh`安装后，在 ${a.label} 的新会话里就能使用 ATM。`, dialog('安装', {d: 'setup', agents: [a.agent]}));
    if (passkeys?.state_error)
      push('passkey', 'state', 'warn', null, 'Passkey 记录校验失败', zh`ATM 主密码仍然可以解锁。错误代码：${str(passkeys.state_error.code)}`, nav('查看', 'settings/keys'));
    const saved = new Set(connList.filter(c => c.configured).map(c => c.provider));
    for (const name of arr(ext.credential_slots)) {
      if (typeof name !== 'string' || saved.has(name)) continue;
      const label = str(connList.find(c => c.provider === name)?.label) || name;
      push('slot', name, 'info', serviceKeyOf(name), zh`${label} 还没有填写 Key`, '你登记了这个 Key 名称，但还没有保存 Key。', dialog('填写 Key', {d: 'key', mode: 'add', name}));
    }
    const rank = {bad: 0, warn: 1, info: 2};
    return items.sort((a, b) => rank[a.sev] - rank[b.sev] || collator.compare(a.serviceName, b.serviceName) || b.time - a.time);
  }

  const T = Object.freeze({
    state: STATE_WORDS, job, jobSentence: JOB_SENTENCE, verify: VERIFY, verifyWord, cost, verifyResult: VERIFY_RESULT, verifyText: verifyResult,
    creditErrors: CREDIT_ERRORS, creditReasons: CREDIT_REASONS, creditLabel, creditTitle, vault: VAULT, backend: BACKEND, permission: PERMISSION, tag: TAG, oauthService: OAUTH_SERVICE, error: ERROR, errorText, knownError,
    kinds: KIND_TITLES, chips: KIND_CHIPS, kindOrder: KIND_ORDER, sites: SITES, date, time, datetime, fullDate, day, relative, listTools, quote, fill, zh, brandOf, slug,
  });
  W.ATM_MODEL = Object.freeze({derive, T, say, routeKindOf, toolReadiness, serviceKeyOf});
})();
