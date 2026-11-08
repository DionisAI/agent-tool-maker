'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const fragment = new URLSearchParams(location.hash.slice(1));
  const token = fragment.get('token') || sessionStorage.getItem('atm-window-token') || '';
  if (token) sessionStorage.setItem('atm-window-token', token);
  history.replaceState(null, '', location.pathname);
  let view;
  function showError(message) { $('error').textContent = message; $('error').hidden = false; }
  async function api(path, body) {
    const headers = {Authorization: 'Bearer ' + token};
    const options = {headers, cache: 'no-store'};
    if (body !== undefined) { headers['Content-Type'] = 'application/json'; options.method = 'POST'; options.body = JSON.stringify(body); }
    const response = await fetch(path, options); const data = await response.json();
    if (!response.ok) throw new Error(data.error ? data.error.code + ': ' + data.error.message : '本机请求失败');
    return data;
  }
  function field(parent, id, label, autocomplete) {
    const l = document.createElement('label'); l.htmlFor = id; l.textContent = label;
    const i = document.createElement('input'); i.id = id; i.type = 'password'; i.autocomplete = autocomplete; i.required = true;
    parent.append(l, i); return i;
  }
  function done(data) {
    $('request').hidden = true; $('success').hidden = false;
    $('remaining').textContent = '本次剩余约 ' + Math.max(0, Math.ceil(data.seconds_remaining / 60)) + ' 分钟。';
  }
  async function load() {
    if (!token) throw new Error('请让 Agent 使用 ATM 打开本地授权窗口。不要在聊天里发送密码或复制会话令牌。');
    view = await api('/api/desktop'); $('loading').hidden = true;
    if (view.status === 'ready') { done(view.session); return; }
    if (['denied','expired','locked'].includes(view.status)) throw new Error('这次请求已经结束。');
    $('request').hidden = false; $('workspace').textContent = view.plan.workspace;
    $('keys').replaceChildren();
    for (const name of view.plan.credentials) { const x = document.createElement('span'); x.className='tag'; x.textContent=name; $('keys').append(x); }
    $('passwords').replaceChildren(); $('missing').replaceChildren();
    if (!view.session.unlocked && view.backend === 'passphrase') {
      field($('passwords'), 'passphrase', view.initialized ? 'ATM 主密码' : '设置 ATM 主密码（至少 12 个字符）', view.initialized ? 'current-password' : 'new-password');
      if (!view.initialized) field($('passwords'), 'confirm-password', '再输入一次新密码', 'new-password');
    }
    if (view.session.unlocked) { $('title').textContent='允许这个项目继续？'; $('subtitle').textContent='ATM 已经解锁；本次只确认新增的项目或 Key 范围，不再询问密码。'; $('approve').textContent='允许并继续'; }
    if (!view.session.unlocked && view.backend !== 'passphrase') $('subtitle').textContent='使用系统凭证库解锁；操作系统可能请求一次确认。';
    if(view.passkeys?.state_error)showError(view.passkeys.state_error.code+': 本机 Passkey 记录校验失败，现有主密码入口保留。');
    for (const c of view.connections) if (c.state==='missing_credential') field($('missing'), 'key-'+c.name, c.name + ' 的 API Key（仅此连接尚未配置）', 'off');
    const credentials=view.passkeys?.credentials.filter(c=>!c.disabled) || [];
    if (!view.session.unlocked && view.passkeys?.available && credentials.length && window.ATM_PASSKEY?.supported()) {
      const select=document.createElement('select');select.id='passkey-select';select.setAttribute('aria-label','解锁 Passkey');
      for(const c of credentials){const option=document.createElement('option');option.value=c.id;option.textContent=c.label;select.append(option);}
      const button=document.createElement('button');button.id='passkey-approve';button.type='button';button.textContent='用 Passkey 解锁并继续';
      $('passwords').append(select,button);
      button.addEventListener('click',async()=>{
        if (!Array.from($('missing').querySelectorAll('input')).every(input=>input.reportValidity()))return;
        button.disabled=true;$('approve').disabled=true;$('error').hidden=true;
        let body={approved_sha256:view.approved_sha256,consent:true,credentials:{}};
        for(const c of view.connections)if($('key-'+c.name))body.credentials[c.name]=$('key-'+c.name).value;
        document.querySelectorAll('input[type=password]').forEach(input=>{input.value='';});
        try{
          body.passkey=await window.ATM_PASSKEY.authenticate(api,'/api/desktop/passkey/begin',{
            approved_sha256:view.approved_sha256,consent:true,credential_id:select.value},'/api/desktop/passkey/cancel');
          const result=await api('/api/desktop/approve',body);body=null;$('passwords').replaceChildren();$('missing').replaceChildren();done(result);
        }catch(error){body=null;showError(error.message);}
        finally{button.disabled=false;$('approve').disabled=false;}
      });
    }
  }
  $('approval').addEventListener('submit', async event => {
    event.preventDefault(); $('error').hidden=true; $('approve').disabled=true;
    let body = {approved_sha256:view.approved_sha256, consent:true, credentials:{}};
    if ($('passphrase')) body.passphrase = $('passphrase').value;
    if ($('confirm-password')) body.confirm_password = $('confirm-password').value;
    for (const c of view.connections) if ($('key-'+c.name)) body.credentials[c.name] = $('key-'+c.name).value;
    // Clear DOM fields before awaiting a network response; never persist secrets.
    document.querySelectorAll('input[type=password]').forEach(input => {input.value='';});
    try { const data=await api('/api/desktop/approve',body); body=null; $('passwords').replaceChildren(); $('missing').replaceChildren(); done(data); }
    catch(e) { body=null; showError(e.message); }
    finally { $('approve').disabled=false; }
  });
  $('cancel').addEventListener('click', async () => { try {await api('/api/desktop/cancel',{}); $('request').hidden=true; showError('已拒绝，Agent 不会取得使用权限。');} catch(e){showError(e.message);} });
  $('lock').addEventListener('click', async () => { try {await api('/api/desktop/lock',{}); $('success').hidden=true; showError('已锁定。新的调用需要再次解锁。');} catch(e){showError(e.message);} });
  load().catch(e => { $('loading').hidden=true; showError(e.message); });
})();
