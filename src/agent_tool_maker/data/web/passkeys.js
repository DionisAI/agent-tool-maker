'use strict';
// Ephemeral WebAuthn/PRF transport. No provider secrets or PRF output in storage/logs.
(() => {
  const encode = buffer => btoa(String.fromCharCode(...new Uint8Array(buffer))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
  const decode = text => Uint8Array.from(atob(text.replaceAll('-','+').replaceAll('_','/') + '='.repeat((4-text.length%4)%4)), c=>c.charCodeAt(0));
  function options(raw) {
    const value = structuredClone(raw);
    value.challenge = decode(value.challenge);
    if (value.user) value.user.id = decode(value.user.id);
    for (const key of ['allowCredentials','excludeCredentials']) for (const c of value[key] || []) c.id = decode(c.id);
    if (value.extensions?.prf?.eval) value.extensions.prf.eval.first = decode(value.extensions.prf.eval.first);
    return value;
  }
  function serialize(credential) {
    if (!credential) throw new Error('passkey_cancelled: 本次验证已结束，请重新点击。');
    const response = {clientDataJSON:encode(credential.response.clientDataJSON)};
    for (const key of ['attestationObject','authenticatorData','signature','userHandle']) {
      if (credential.response[key] != null) response[key] = encode(credential.response[key]);
    }
    return {id:credential.id,rawId:encode(credential.rawId),type:credential.type,response,clientExtensionResults:{}};
  }
  const bufferLength = Object.getOwnPropertyDescriptor(ArrayBuffer.prototype,'byteLength').get;
  function prfBytes(value) {
    if (value == null) throw new Error('passkey_prf_missing: 当前浏览器或 Passkey 未返回 PRF；请选择主密码入口。');
    const invalid = () => new Error('passkey_prf_invalid: PRF 返回值不是完整的 32 字节；ATM 尚未保存绑定。');
    // Some 1Password extension versions return a plain byte Array (FS-5593).
    // Validate before conversion: do not truncate, coerce or fill sparse bytes.
    if (Array.isArray(value)) {
      if (value.length !== 32) throw invalid();
      for (let i=0;i<32;i++) if (!Number.isInteger(value[i]) || value[i]<0 || value[i]>255) throw invalid();
      return Uint8Array.from(value);
    }
    if (ArrayBuffer.isView(value)) {
      if (value.byteLength !== 32) throw invalid();
      return new Uint8Array(value.buffer,value.byteOffset,value.byteLength);
    }
    let length;
    try { length=bufferLength.call(value); } catch { throw invalid(); }
    if (length !== 32) throw invalid();
    return new Uint8Array(value);
  }
  async function get(step) {
    const credential = await navigator.credentials.get({publicKey:options(step.publicKey)});
    const prf = prfBytes(credential?.getClientExtensionResults()?.prf?.results?.first);
    return {ceremony_id:step.ceremony_id,credential:serialize(credential),prf_first:encode(prf)};
  }
  const supported = () => Boolean(window.isSecureContext && window.PublicKeyCredential && navigator.credentials?.get && location.hostname === 'localhost');
  function diagnostic(error) {
    if (error?.name === 'NotAllowedError' || error?.name === 'AbortError') return new Error('passkey_cancelled: 验证已取消或超时，原授权期限保持原样。');
    if (error instanceof Error && !['SecurityError','NotSupportedError','InvalidStateError','TypeError'].includes(error.name)) return error;
    return new Error('passkey_browser_' + (error?.name || 'error') + ': 浏览器验证未完成，请使用主密码或检查 Passkey / PRF 支持。');
  }
  async function cancelled(api, path, error) {
    if (error?.gated) throw error;  // The console session ended; its gate says why and no bearer is left to cancel with.
    try { await api(path,{}); }
    catch { throw new Error('passkey_cancel_cleanup_failed: 本机连接已中断；临时验证状态将于三分钟内过期。'); }
    throw diagnostic(error);
  }
  async function register(api, passphrase, label) {
    try {
      const step = await api('/api/passkeys/register/begin',{label,...(passphrase ? {passphrase} : {})});
      passphrase = null;
      const credential = await navigator.credentials.create({publicKey:options(step.publicKey)});
      if (credential?.getClientExtensionResults()?.prf?.enabled !== true) throw new Error('passkey_prf_missing: 新凭证未启用 PRF，ATM 尚未保存绑定；已创建的 1Password 项目请在 1Password 中核对。');
      const binding = await api('/api/passkeys/register/verify',{ceremony_id:step.ceremony_id,credential:serialize(credential)});
      let proof = await get(binding);
      try { return await api('/api/passkeys/register/finish',proof); }
      finally { proof = null; }
    } catch (error) { passphrase=null; return cancelled(api,'/api/passkeys/cancel',error); }
  }
  async function authenticate(api, path, body, cancelPath) {
    try { return await get(await api(path,body)); }
    catch (error) { return cancelled(api,cancelPath,error); }
  }
  window.ATM_PASSKEY = Object.freeze({supported,register,authenticate});
})();
