// Observed test canvas inventory; not node editing, rendering or generation.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,FILES,pollDOM} from './core.mjs';
export const CANVAS_FILES=[...FILES,'canvas.mjs','canvas.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
export function canvasDigest(){const h=createHash('sha256');for(const n of CANVAS_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkCanvasPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==canvasDigest())throw new XyqError('definition_changed','Review the XYQ canvas reader bundle.');}
export function canvasScope(args){if(!args||typeof args.project_id!=='string'||typeof args.canvas_id!=='string'||!/^\d{1,20}$/.test(args.project_id)||!/^\d{1,20}$/.test(args.canvas_id))throw new XyqError('invalid_argument','Use exact observed project_id and canvas_id.');return{project_id:args.project_id,canvas_id:args.canvas_id};}
export function readCanvasDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const url=new URL(location.href),project=url.searchParams.get('projectId'),canvas=url.searchParams.get('canvasId');
  if(project!==scope.project_id||canvas!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const roots=Array.from(document.querySelectorAll('[data-testid="rf__wrapper"][role="application"]')).filter(visible);
  const tops=Array.from(document.querySelectorAll('[aria-label="画布顶部操作区"]')).filter(visible);
  if(!roots.length||!tops.length)return{kind:'pending'};
  if(roots.length!==1||tops.length!==1||!roots[0].querySelector('.react-flow__nodes'))return{kind:'layout_changed'};
  const titles=Array.from(tops[0].querySelectorAll('h1')).filter(visible);
  const amounts=Array.from(tops[0].querySelectorAll('button[aria-label^="积分余额 "]')).filter(visible);
  if(titles.length!==1||amounts.length!==1)return{kind:'layout_changed'};
  const amount=amounts[0].getAttribute('aria-label').slice(5).trim();
  if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(amount)||Number(amount.replaceAll(',',''))>Number.MAX_SAFE_INTEGER)return{kind:'layout_changed'};
  const es=Array.from(roots[0].querySelectorAll('.react-flow__node'));
  const nodes=es.map(e=>{const types=Array.from(e.classList).filter(c=>c.startsWith('react-flow__node-biz/'));
    // Selected and freshly loaded nodes use the same editor class, but only the
    // selected node is contenteditable=true. Read both; never activate for reading.
    const editors=Array.from(e.querySelectorAll('.xyq-text-node-editor[contenteditable]'));
    return{node_id:e.getAttribute('data-id'),type:types.length===1?types[0].slice('react-flow__node-biz/'.length):null,
      visible:visible(e),text:editors.length===1?(editors[0].innerText||'').replace(/\r\n/g,'\n').trim():null,
      text_editors:editors.length,text_editable:editors.length===1?editors[0].getAttribute('contenteditable')==='true':null,
      position_style:e.style.transform||null,width:e.style.width||null,height:e.style.height||null};});
  if(nodes.length>2000||new Set(nodes.map(e=>e.node_id)).size!==nodes.length||nodes.some(e=>!/^\d{1,20}$/.test(e.node_id||'')||!e.type||e.type.length>64||e.text_editors>1||e.text?.length>100000))return{kind:'layout_changed'};
  const toolbar=Array.from(document.querySelectorAll('[aria-label="Canvas viewport toolbar"]')).filter(visible);
  if(toolbar.length!==1)return{kind:'layout_changed'};
  const controls=Array.from(toolbar[0].querySelectorAll('button')).filter(visible).map(e=>({label:e.getAttribute('aria-label')||(e.innerText||'').trim(),pressed:e.getAttribute('aria-pressed'),disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'}));
  return{kind:'ready',project_id:project,canvas_id:canvas,title:titles[0].innerText,credits:Number(amount.replaceAll(',','')),nodes,
    edge_elements:roots[0].querySelectorAll('.react-flow__edge').length,saving:Array.from(document.querySelectorAll('[aria-label="画布保存中"]')).some(visible),controls};
}
export async function inspectCanvas(page,args){
  const scope=canvasScope(args),d=await pollDOM({evaluate:()=>page.evaluate(readCanvasDOM,scope)},readCanvasDOM);
  const {title,nodes,kind,...rest}=d;
  return[{result:{...rest,status:'ready',project_title_sha256:sha(title),nodes:nodes.map(({text,...n})=>({...n,text_characters:text?.length??null,text_sha256:text===null?null:sha(text)})),
    snapshot_sha256:sha(JSON.stringify([scope,title,nodes])),coverage:'current_canvas_dom',all_project_assets:false,persistence_verified:false,
    source:'visible_dom',secrets_returned:false,paid_submitted:false,upload_started:false}}];
}
