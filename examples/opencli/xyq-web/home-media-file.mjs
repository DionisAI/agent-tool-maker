// Bounded local intake integrity, not a codec decoder or provider-limit claim.
import {createHash} from 'node:crypto';
import {lstatSync,openSync,closeSync,fstatSync,readFileSync,constants} from 'node:fs';
import {isAbsolute,resolve,relative,dirname,basename,extname} from 'node:path';
import {XyqError} from './core.mjs';
import {inspectAudioFile} from './audio.mjs';
const fail=(code,message)=>{throw new XyqError(code,message);};
export function homeUploadSafePath(path,directory=false){
  if(typeof path!=='string'||!isAbsolute(path)||resolve(path)!==path||path==='/'||/[\x00-\x1f]/.test(path))fail('unsafe_path','Use a canonical project path.');
  for(let p=path;;p=dirname(p)){
    let st;try{st=lstatSync(p);}catch{fail('unsafe_path','The project path is missing.');}
    if(st.isSymbolicLink()||(p===path&&!directory?(!st.isFile()||st.nlink!==1):!st.isDirectory()))fail('unsafe_path','Use regular single-link project files and directories.');
    if(dirname(p)===p)break;
  }
}
export const HOME_MEDIA_TYPES={'.png':['image_reference','image/png'],'.jpg':['image_reference','image/jpeg'],'.jpeg':['image_reference','image/jpeg'],
  '.webp':['image_reference','image/webp'],'.gif':['image_reference','image/gif'],'.bmp':['image_reference','image/bmp'],
  '.wav':['audio_reference','audio/wav'],'.mp3':['audio_reference','audio/mpeg'],'.mp4':['video_reference','video/mp4'],'.mov':['video_reference','video/quicktime']};
export function inspectHomeMediaFile(file,workspace,expected,purpose){
  homeUploadSafePath(workspace,true);homeUploadSafePath(file);
  const rel=relative(workspace,file),extension=extname(file).toLowerCase(),type=HOME_MEDIA_TYPES[extension];
  if(!rel||rel.startsWith('..')||isAbsolute(rel)||!type||type[0]!==purpose||typeof expected!=='string'||!/^[a-f0-9]{64}$/.test(expected))fail('invalid_media_file','Bind an approved project-owned image, video or audio file and SHA.');
  const name=basename(file);if(name.length>255||name!==name.trim()||/[\x00-\x1f]/.test(name))fail('invalid_media_file','Use a bounded regular media filename.');
  let fd,bytes,st;
  try{
    fd=openSync(file,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);st=fstatSync(fd);
    if(!st.isFile()||st.nlink!==1||st.size<12||st.size>200*1024*1024)fail('invalid_media_file','Local intake bounds are 12 bytes to 200 MiB; provider limits are separate.');
    bytes=readFileSync(fd);const last=fstatSync(fd);
    if(bytes.length!==st.size||last.size!==st.size||last.mtimeMs!==st.mtimeMs||last.ctimeMs!==st.ctimeMs)fail('input_changed','Approved media changed during its local read.');
    const hash=createHash('sha256').update(bytes).digest('hex');if(hash!==expected)fail('input_changed','Media bytes differ from the approved SHA.');
  }catch(e){if(e instanceof XyqError)throw e;fail('file_read_failed','The approved media read failed.');}finally{if(fd!==undefined)closeSync(fd);}
  let dimensions=null,audio=null;
  if(purpose==='audio_reference'){
    audio=inspectAudioFile(file,workspace,expected);
    if(audio.size!==bytes.length)fail('input_changed','The approved audio changed between integrity checks.');
  }else if(extension==='.png'){
    if(bytes.length<57||!bytes.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex'))||bytes.readUInt32BE(8)!==13||bytes.toString('ascii',12,16)!=='IHDR')fail('invalid_media_file','Expected a bounded PNG header.');
    dimensions=[bytes.readUInt32BE(16),bytes.readUInt32BE(20)];let offset=8,idat=false,end=false;
    while(offset+12<=bytes.length){const size=bytes.readUInt32BE(offset),tag=bytes.toString('ascii',offset+4,offset+8);if(offset+12+size>bytes.length||!/^[A-Za-z]{4}$/.test(tag))fail('invalid_media_file','PNG chunk boundaries changed.');
      if(tag==='IDAT'&&size>0)idat=true;offset+=size+12;if(tag==='IEND'){end=size===0&&offset===bytes.length;break;}}
    if(!idat||!end)fail('invalid_media_file','Expected PNG data and a final IEND chunk.');
  }else if(extension==='.jpg'||extension==='.jpeg'){
    if(bytes.length<20||bytes.readUInt16BE(0)!==0xffd8||bytes.readUInt16BE(bytes.length-2)!==0xffd9)fail('invalid_media_file','Expected JPEG start and end markers.');
    let offset=2,sos=false;
    while(offset+4<bytes.length){if(bytes[offset++]!==255)fail('invalid_media_file','JPEG marker boundaries changed.');while(bytes[offset]===255)offset++;const tag=bytes[offset++];
      if([0,0xd8,0xd9].includes(tag)||offset+2>bytes.length)fail('invalid_media_file','JPEG header is malformed.');
      const size=bytes.readUInt16BE(offset);if(size<2||offset+size>bytes.length-2)fail('invalid_media_file','JPEG segment is incomplete.');
      if([0xc0,0xc1,0xc2].includes(tag)){if(size<8)fail('invalid_media_file','JPEG frame header is incomplete.');dimensions=[bytes.readUInt16BE(offset+5),bytes.readUInt16BE(offset+3)];}
      if(tag===0xda){sos=true;break;}offset+=size;}
    if(!dimensions||!sos)fail('invalid_media_file','Expected a JPEG frame and scan header.');
  }else if(extension==='.webp'){
    if(bytes.length<30||bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WEBP'||bytes.readUInt32LE(4)+8!==bytes.length)fail('invalid_media_file','Expected a complete WebP RIFF envelope.');
    let offset=12,frame=false;while(offset+8<=bytes.length){const n=bytes.readUInt32LE(offset+4),tag=bytes.toString('ascii',offset,offset+4);if(offset+8+n+(n%2)>bytes.length)fail('invalid_media_file','WebP chunk exceeds its envelope.');if(['VP8 ','VP8L','ANMF'].includes(tag)&&n>0)frame=true;offset+=8+n+n%2;}
    if(offset!==bytes.length||!frame)fail('invalid_media_file','Expected WebP image frame data.');
  }else if(extension==='.gif'){
    if(bytes.length<14||!['GIF87a','GIF89a'].includes(bytes.toString('ascii',0,6))||bytes.at(-1)!==0x3b)fail('invalid_media_file','Expected a bounded GIF envelope.');dimensions=[bytes.readUInt16LE(6),bytes.readUInt16LE(8)];
  }else if(extension==='.bmp'){
    if(bytes.length<54||bytes.toString('ascii',0,2)!=='BM'||bytes.readUInt32LE(2)!==bytes.length||bytes.readUInt32LE(14)<40||bytes.readUInt32LE(10)>=bytes.length)fail('invalid_media_file','Expected a bounded BMP envelope.');dimensions=[bytes.readInt32LE(18),Math.abs(bytes.readInt32LE(22))];
  }else{
    let offset=0,ftyp=false,moov=false,mdat=false;
    while(offset+8<=bytes.length){let size=bytes.readUInt32BE(offset),header=8;const tag=bytes.toString('ascii',offset+4,offset+8);
      if(size===1){if(offset+16>bytes.length)fail('invalid_media_file','Video extended-size box is incomplete.');const big=bytes.readBigUInt64BE(offset+8);if(big>BigInt(Number.MAX_SAFE_INTEGER))fail('invalid_media_file','Video box exceeds local bounds.');size=Number(big);header=16;}
      if(size===0)size=bytes.length-offset;
      if(size<header||offset+size>bytes.length)fail('invalid_media_file','Video box boundaries changed.');
      if(tag==='ftyp'&&size>=16)ftyp=true;if(tag==='moov'&&size>header)moov=true;if(tag==='mdat'&&size>header)mdat=true;offset+=size;
    }
    if(offset!==bytes.length||!moov||!mdat||(extension==='.mp4'&&!ftyp))fail('invalid_media_file','Expected bounded MP4/MOV metadata and media envelopes.');
  }
  if(dimensions&&dimensions.some(n=>!Number.isInteger(n)||n<1||n>32768))fail('invalid_media_file','Image dimensions exceed local intake bounds.');
  homeUploadSafePath(file);
  return{sha256:expected,size:bytes.length,name,extension,purpose,mime:type[1],duration_seconds:audio?.duration_seconds??null,
    duration_basis:audio?.duration_basis??(audio?'pcm_samples':null),decoder_verified:false,provider_limits_verified:false};
}
