import test from 'node:test';
import assert from 'node:assert/strict';
import {readdirSync,readFileSync} from 'node:fs';

// Load every reviewed OpenCLI loader with a recording registry, so the declared access is read
// from the real registrations rather than from a source pattern. Modules are cached, so load once.
const DIR=new URL('../examples/opencli/xyq-web/',import.meta.url);
const asModule=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
async function load(){
  const key='__atmXyqAccessFixture';globalThis[key]=[];
  const registry=asModule(`export const Strategy={LOCAL:'local',UI:'ui'};export function cli(value){globalThis.${key}.push(value);}`);
  const errors=asModule('export class ArgumentError extends Error{};export class AuthRequiredError extends Error{};export class CommandExecutionError extends Error{};');
  try{
    for(const name of readdirSync(DIR).filter(n=>n.endsWith('.js')).sort()){
      const source=readFileSync(new URL(name,DIR),'utf8')
        .replace("'@jackwener/opencli/registry'",JSON.stringify(registry))
        .replace("'@jackwener/opencli/errors'",JSON.stringify(errors))
        .replace(/'\.\/([a-z-]+\.mjs)'/g,(_,file)=>JSON.stringify(new URL(file,DIR).href));
      await import(asModule(source));
    }
    return globalThis[key];
  }finally{delete globalThis[key];}
}
let loaded;const registrations=()=>loaded||=load();
const dash=operation=>operation.replaceAll('_','-');

test('audio choice discovery opens and closes menus, so every loader declares it a write',async()=>{
  const commands=await registrations(),web=commands.filter(c=>c.site==='xyq-web');
  for(const name of ['audio-choices','audio-choices-bound','mode-choices','mode-choices-bound','form-choices','form-choices-bound'])
    assert.equal(web.find(c=>c.name===name)?.access,'write',name);
});
test('each xyq-web counterpart of a media runtime operation declares the same access',async()=>{
  const commands=await registrations(),web=commands.filter(c=>c.site==='xyq-web'),media=commands.filter(c=>c.site==='xyq-media');
  assert.equal(media.length,20);
  for(const command of media){
    const twins=web.filter(c=>[command.name,command.name+'-bound',command.name+'-home-bound'].includes(c.name));
    assert(twins.length>0,command.name);
    for(const twin of twins)assert.equal(twin.access,command.access,twin.name+' vs xyq-media '+command.name);
  }
  assert.equal(media.find(c=>c.name===dash('audio_choices')).access,'write');
});
