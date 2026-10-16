// Synthetic frame headers/payloads are structure fixtures, not decoded audio.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtempSync,writeFileSync,readFileSync,existsSync,symlinkSync} from 'node:fs';
import {join} from 'node:path';
import {inspectAudioFile,audioFormHash,uploadAudioReference,AUDIO_PANEL} from '../examples/opencli/xyq-web/audio.mjs';
import {runBoundAudioUpload} from '../examples/opencli/xyq-web/audio-upload-bound.mjs';

const sha=b=>createHash('sha256').update(b).digest('hex');
const scope={project_id:'1',canvas_id:'2',node_id:'3'};
function frame({version=3,rateIndex=0,bitrate=9,mono=true,padding=0,crc=false}={}){
  const rate=[44100,48000,32000][rateIndex]/(version===3?1:version===2?2:4);
  const kbps=(version===3?[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]:[0,8,16,24,32,40,48,56,64,80,96,112,128,144,160])[bitrate];
  const b=Buffer.alloc(Math.floor((version===3?144000:72000)*kbps/rate)+padding);
  b.writeUInt32BE((0xffe00000|(version<<19)|(1<<17)|((crc?0:1)<<16)|(bitrate<<12)|(rateIndex<<10)|(padding<<9)|((mono?3:0)<<6))>>>0);
  return b;
}
function tag(major=4,body=Buffer.from('FAKE_PRIVATE_TAG')){
  const h=Buffer.alloc(10);h.write('ID3');h[3]=major;
  for(let n=body.length,i=9;i>=6;i--,n>>>=7)h[i]=n&127;
  return Buffer.concat([h,body]);
}
function fixture(bytes=Buffer.concat([frame(),frame({padding:1})])){
  const root=mkdtempSync('/private/tmp/atm-xyq-mp3-unit-'),file=join(root,'FAKE_PRIVATE.mp3');writeFileSync(file,bytes,{mode:0o600});
  const form={kind:'ready',...scope,model:'Seed Audio 1.0',sample_rate:'44.1kHz',prompt:'',prompt_tree:null,prompt_references:0,references:[],files:[{kind:'audio',multiple:true,accept:null,files:[]},{kind:'image',multiple:true,accept:'.png',files:[]}],layers:0,submit_busy:false,submit_enabled:false,association:'unique_audio_node_only'};
  const calls=[],s={mutate:null,fail:false};
  const attach=files=>{
    assert.deepEqual(files,[file]);
    assert(existsSync(join(root,'.atm/xyq-audio-uploads/once.intent.json')));
    assert(existsSync(join(root,'.atm/xyq-audio-uploads/active.lock')));
    if(s.fail)throw Error('FAKE_PRIVATE_ERROR');
    form.references.push({type:'audio',name:'FAKE_PRIVATE.mp3',id:'FAKE_PRIVATE-NEW',valid:true});if(s.mutate)s.mutate();return{};
  };
  const backend={evaluate:async fn=>{calls.push(fn.name);return fn.name==='readAudioUploadTargetDOM'?{kind:'ready'}:structuredClone(form);},cdp:async(method,args)=>{
    calls.push(method);
    if(method==='DOM.getDocument')return{root:{nodeId:1}};
    if(method==='DOM.querySelector')return{nodeId:2};
    assert.equal(method,'DOM.setFileInputFiles');return attach(args.files);
  },setFileInput:async(files,selector)=>{calls.push('setFileInput');assert.equal(selector,AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]');return attach(files);}};
  return{root,file,form,calls,s,backend,args:()=>({expected_form_sha256:audioFormHash(form),file,file_sha256:sha(bytes),request_key:'once',confirm:true,purpose:'audio_reference'})};
}
test('MPEG 1/2/2.5, three rates, mono/stereo and CRC frame headers are bounded',()=>{
  for(const version of [3,2,0])for(const rateIndex of [0,1,2])for(const mono of [true,false]){
    const x=fixture(Buffer.concat([frame({version,rateIndex,mono,crc:true}),frame({version,rateIndex,mono,padding:1})]));
    const out=inspectAudioFile(x.file,x.root,x.args().file_sha256),rate=[44100,48000,32000][rateIndex]/(version===3?1:version===2?2:4);
    assert.equal(out.format,'mp3');assert.equal(out.sample_rate,rate);assert.equal(out.channels,mono?1:2);
    assert.equal(out.duration_seconds,2*(version===3?1152:576)/rate);assert.equal(out.decoder_verified,false);
    assert.equal(out.duration_basis,'encoded_frame_samples');assert(!JSON.stringify(out).includes('TAG'));
  }
});
test('CBR/VBR and ID3v2.2/2.3/2.4 + ID3v1 do not output metadata',()=>{
  for(const major of [2,3,4]){
    const tail=Buffer.alloc(128);tail.write('TAGFAKE_PRIVATE_TAG');
    const x=fixture(Buffer.concat([tag(major),frame({bitrate:9}),frame({bitrate:10,padding:1}),tail]));
    const out=inspectAudioFile(x.file,x.root,x.args().file_sha256);assert.equal(out.duration_seconds,2304/44100);assert(!JSON.stringify(out).includes('FAKE_PRIVATE_TAG'));
  }
});
test('a valid MP3 SHA mismatch is rejected before constructing a browser',async()=>{
  const x=fixture();await assert.rejects(runBoundAudioUpload({},scope,{...x.args(),file_sha256:'0'.repeat(64)},x.root,()=>assert.fail('browser')),e=>e.code==='input_changed');assert.equal(x.calls.length,0);
});
test('project ownership, symlinks and extension spoofing remain intake errors',()=>{
  const x=fixture(),other=mkdtempSync('/private/tmp/atm-xyq-mp3-outside-');
  assert.throws(()=>inspectAudioFile(x.file,other),e=>e.code==='invalid_audio_file');
  const link=join(x.root,'linked.mp3');symlinkSync(x.file,link);assert.throws(()=>inspectAudioFile(link,x.root),e=>e.code==='unsafe_path');
  const wav=join(x.root,'not-a-wav.wav');writeFileSync(wav,readFileSync(x.file));assert.throws(()=>inspectAudioFile(wav,x.root),e=>e.code==='invalid_audio_file');
  writeFileSync(x.file,Buffer.from('RIFF'+'.'.repeat(100)));assert.throws(()=>inspectAudioFile(x.file,x.root),e=>e.code==='invalid_audio_file');
});
for(const [name,make] of [
  ['partial frame',()=>frame().subarray(0,-1)],
  ['trailing partial header',()=>Buffer.concat([frame(),Buffer.from([255])])],
  ['leading junk',()=>Buffer.concat([Buffer.from('junk'),frame()])],
  ['trailing junk',()=>Buffer.concat([frame(),Buffer.from('junk')])],
  ['free bitrate',()=>{const b=frame();b[2]&=15;return b;}],
  ['reserved bitrate',()=>{const b=frame();b[2]|=240;return b;}],
  ['reserved rate',()=>{const b=frame();b[2]|=12;return b;}],
  ['reserved version',()=>{const b=frame();b[1]=(b[1]&231)|8;return b;}],
  ['wrong layer',()=>{const b=frame();b[1]=(b[1]&249)|4;return b;}],
  ['reserved emphasis',()=>{const b=frame();b[3]|=2;return b;}],
  ['changing rate',()=>Buffer.concat([frame(),frame({rateIndex:1})])],
  ['changing channels',()=>Buffer.concat([frame(),frame({mono:false})])],
  ['ID3 invalid version',()=>Buffer.concat([tag(5),frame()])],
  ['ID3 reserved flags',()=>{const b=tag();b[5]=1;return Buffer.concat([b,frame()]);}],
  ['ID3 revision reserved',()=>{const b=tag();b[4]=255;return Buffer.concat([b,frame()]);}],
  ['ID3 invalid syncsafe size',()=>{const b=tag();b[6]=128;return Buffer.concat([b,frame()]);}],
  ['ID3 excessive size',()=>{const b=tag();b[6]=127;return Buffer.concat([b,frame()]);}],
  ['ID3 footer flag',()=>{const b=tag();b[5]=16;return Buffer.concat([b,frame()]);}],
  ['ID3 no frames',()=>tag(4,Buffer.alloc(64))],
  ['nonascii ID3 lookalike',()=>{const b=tag();b[0]|=128;return Buffer.concat([b,frame()]);}],
  ['nonascii ID3v1 lookalike',()=>{const b=Buffer.alloc(128);b.write('TAG');b[0]|=128;return Buffer.concat([frame(),b]);}],
  ['duration > 120 seconds',()=>Buffer.concat(Array.from({length:4600},()=>frame()))],
  ['size > 20 MiB',()=>Buffer.alloc(20*1024*1024+1)],
])test('MP3 rejects '+name+' with zero browser calls',async()=>{
  const x=fixture(make());await assert.rejects(runBoundAudioUpload({},scope,x.args(),x.root,()=>assert.fail('browser')),e=>e.code==='invalid_audio_file');assert.equal(x.calls.length,0);assert(!existsSync(join(x.root,'.atm')));
});
for(const bound of [false,true])test('MP3 '+(bound?'bound':'default')+' append preserves original content and historical reuse',async()=>{
  const x=fixture(Buffer.concat([tag(),frame(),frame()]));x.form.prompt='FAKE_PRIVATE_PROMPT';x.form.prompt_tree=['P','FAKE_PRIVATE_PROMPT',['SPAN','FAKE_TOKEN']];x.form.prompt_references=1;
  x.form.references=[{type:'audio',name:'OLD.wav',id:'OLD_AUDIO',valid:true},{type:'image',name:'OLD.png',id:'OLD_IMAGE',valid:true}];
  const old=structuredClone(x.form),args={...x.args(),mode:'append'};
  const run=()=>bound?runBoundAudioUpload({},scope,args,x.root,async()=>x.backend):uploadAudioReference(x.backend,scope,args,x.root);
  const out=(await run())[0].result;assert.equal(out.file_format,'mp3');assert.equal(out.duration_basis,'encoded_frame_samples');assert.equal(out.decoder_verified,false);
  assert.equal(out.voice_effect_verified,false);assert.equal(out.persistence_verified,false);assert.equal(out.generation_submitted,false);assert.equal(out.references_preserved,true);
  assert.deepEqual(x.form.prompt_tree,old.prompt_tree);assert.equal(x.form.prompt,old.prompt);assert.equal(x.form.prompt_references,1);assert.deepEqual(x.form.references.slice(0,2),old.references);
  assert.equal(x.calls.filter(c=>c===(bound?'setFileInput':'DOM.setFileInputFiles')).length,1);if(bound)assert(!x.calls.includes('DOM.setFileInputFiles'));assert(!JSON.stringify(out).includes('FAKE_PRIVATE'));
  const n=x.calls.length,reused=(await run())[0].result;assert.equal(reused.reused,true);assert.equal(reused.current_form_verified,false);assert.equal(x.calls.length,n);
  const receipt=JSON.parse(readFileSync(join(x.root,'.atm/xyq-audio-uploads/once.result.json')));
  assert.equal(receipt.fingerprint,sha(JSON.stringify([scope,args.expected_form_sha256,args.file,args.file_sha256,args.purpose,'append-v1'])));
});
test('MP3 file changed during one input retains unknown intent and no second input',async()=>{
  const x=fixture(),args=x.args();x.s.mutate=()=>writeFileSync(x.file,Buffer.alloc(100));
  await assert.rejects(runBoundAudioUpload({},scope,args,x.root,async()=>x.backend),e=>e.code==='input_changed'&&e.outcome_uncertain);
  assert(existsSync(join(x.root,'.atm/xyq-audio-uploads/active.lock')));
  writeFileSync(x.file,Buffer.concat([frame(),frame({padding:1})]));
  await assert.rejects(runBoundAudioUpload({},scope,args,x.root,async()=>x.backend),e=>e.code==='upload_unknown');assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);assert(!x.calls.includes('DOM.setFileInputFiles'));
});
