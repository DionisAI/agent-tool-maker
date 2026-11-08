import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,readdirSync,readFileSync,writeFileSync,realpathSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';

const DATA=new URL('../src/agent_tool_maker/data/tripo_server/',import.meta.url);
const TMP=realpathSync(tmpdir());

// Both backends run the same packaged wrappers/runner around stub adapters that return a
// fixed probe row, so only each backend's own row shaping can make the outputs differ.
async function stubBundle(){
  const dir=mkdtempSync(join(TMP,'atm-tripo-runner-'));
  for(const name of readdirSync(DATA).filter(n=>n.endsWith('.mjs')&&n!=='runner.mjs')){
    const real=new URL(name,DATA).href,exports=await import(real);
    const stubs=Object.entries(exports).filter(([key,value])=>typeof value==='function'&&!/^[A-Z]/.test(key))
      .map(([key])=>key.startsWith('check')?`export const ${key}=()=>{};`:`export const ${key}=async()=>[{probe:${JSON.stringify(key)}}];`);
    writeFileSync(join(dir,name),`export * from ${JSON.stringify(real)};\n${stubs.join('\n')}\n`);
  }
  writeFileSync(join(dir,'registry.mjs'),"export const Strategy={UI:'ui',LOCAL:'local'};export function cli(command){globalThis.__tripoCommands.push(command);}");
  writeFileSync(join(dir,'errors.mjs'),'export class ArgumentError extends Error{};export class AuthRequiredError extends Error{};export class CommandExecutionError extends Error{};');
  writeFileSync(join(dir,'runner.mjs'),readFileSync(new URL('runner.mjs',DATA)));
  globalThis.__tripoCommands=[];
  for(const name of readdirSync(DATA).filter(n=>n.endsWith('.js'))){
    const source=readFileSync(new URL(name,DATA),'utf8').replace("'@jackwener/opencli/registry'","'./registry.mjs'").replace("'@jackwener/opencli/errors'","'./errors.mjs'");
    writeFileSync(join(dir,'wrapper-'+name.replace(/\.js$/,'.mjs')),source);
    await import(pathToFileURL(join(dir,'wrapper-'+name.replace(/\.js$/,'.mjs'))).href);
  }
  const commands=new Map(globalThis.__tripoCommands.map(command=>[command.name,command]));
  delete globalThis.__tripoCommands;
  return {dir,commands};
}

test('tripo.server returns the same rows as the tripo.studio OpenCLI wrapper for every operation',async()=>{
  const {dir,commands}=await stubBundle();
  try{
    const operations=Object.keys(JSON.parse(readFileSync(new URL('index.json',DATA),'utf8')));
    assert.equal(operations.length,31);
    for(const operation of operations){
      const command=commands.get(operation.replaceAll('_','-'));
      assert.ok(command,'OpenCLI wrapper for '+operation);
      const studio=await command.func({},{pin:'fixture'});
      const run=spawnSync(process.execPath,[join(dir,'runner.mjs')],{input:JSON.stringify({socket:join(dir,'unused.sock'),token:'fixture',operation,argv:['--pin','fixture']}),encoding:'utf8'});
      assert.equal(run.status,0,operation+': '+run.stdout);
      assert.deepEqual(JSON.parse(run.stdout),studio,operation);
    }
    // Wrappers with columns ['result'] wrap each row; the others return the adapter rows unchanged.
    assert.deepEqual(await commands.get('asset').func({},{pin:'fixture'}),[{result:{probe:'inspectAsset'}}]);
    assert.deepEqual(await commands.get('account').func({},{pin:'fixture'}),[{probe:'account'}]);
  }finally{rmSync(dir,{recursive:true,force:true});}
});
