import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';

const root=new URL('../src/agent_tool_maker/data/web/',import.meta.url);
const data=readFileSync(new URL('brand-data.js',root),'utf8');
const code=readFileSync(new URL('brands.js',root),'utf8');
const context=vm.createContext({window:{}});
vm.runInContext(data,context);vm.runInContext(code,context);
const get=context.window.ATM_BRANDS.get;

test('core tools and clients have bundled image bytes',()=>{
  for(const key of ['higgsfield','tripo','fal','comfyui','canva','claude','codex','1password']) {
    assert.match(get(key).src,/^data:image\/svg\+xml;base64,/);
    assert.ok(Buffer.from(get(key).src.split(',')[1],'base64').toString().includes('<path'));
  }
});
test('aliases share images without losing provider identity',()=>{
  for(const [alias,key] of Object.entries({ffprobe:'ffmpeg',cloudflare_dns:'cloudflare',gh:'github',google_oauth:'google',shopify_cli:'shopify',youtube_data:'youtube'})) {
    assert.equal(get(alias).key,key);assert.equal(get(alias).src,get(key).src);
  }
});
test('generic studio/local only map reviewed Tripo namespaces',()=>{
  assert.equal(get('studio','tripo.studio.account').key,'tripo');
  assert.equal(get('local','tripo.server.login').key,'tripo');
  assert.equal(get('studio','other.studio.account').src,null);
  assert.equal(get('acme','tripo.studio.fake').src,null);
  assert.equal(get('studio','tripo.studioevil.fake').src,null);
});
test('unknown and URL-like providers use text, never remote image URLs',()=>{
  for(const key of ['acme','https://evil.test/logo.svg','__proto__','constructor','toString','<img src=x onerror=alert(1)>']) {
    const value=get(key);assert.equal(value.src,null);assert.ok(value.initials.length<=2);
  }
  assert.equal(get('custom-tool').initials,'CT');
  assert.equal(get('xyq').name,'小云雀');
});
test('lookup is case normalized and Unicode initials are bounded',()=>{
  assert.equal(get(' Tripo ').key,'tripo');
  assert.equal(get('蓝色工具').initials,'蓝色');
  assert.equal(get(null).name,'自定义工具');
});
test('registry and result are immutable',()=>{
  assert.ok(Object.isFrozen(context.window.ATM_BRAND_DATA));
  assert.ok(Object.isFrozen(context.window.ATM_BRAND_DATA.tripo));
  assert.ok(Object.isFrozen(get('tripo')));
});
test('all icons match provenance digests; no dynamic remote URLs',async()=>{
  const {createHash}=await import('node:crypto');
  const sources=JSON.parse(readFileSync(new URL('brand-sources.json',root),'utf8'));
  const icons=context.window.ATM_BRAND_DATA;
  assert.equal(Object.keys(icons).length,55);
  assert.deepEqual(Object.keys(icons).sort(),Object.keys(sources).sort());
  for(const [key,icon] of Object.entries(icons)) {
    const bytes=Buffer.from(icon.src.split(',')[1],'base64');
    assert.equal(createHash('sha256').update(bytes).digest('hex'),sources[key].bundled_svg_sha256);
    assert.doesNotMatch(bytes.toString(),/<script|<foreignObject|onload=|href=|url\(/i);
    assert.ok(bytes.length<120000);
  }
  assert.ok(Buffer.byteLength(data)<100000);
});
test('missing bundle raises a clear startup error',()=>{
  assert.throws(()=>vm.runInNewContext(code,{window:{}}),/brand assets are missing/);
});
