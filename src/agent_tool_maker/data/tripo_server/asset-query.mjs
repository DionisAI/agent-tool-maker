// Visible asset-grid contracts, independent of the older Model-only adapter pins.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { ORIGIN, StudioError, unwrap, pollDOM, readAccountDOM } from './core.mjs';

export const QUERY_FILES = ['core.mjs', 'asset-query.mjs', 'asset-query.js'];
export const MODEL_CARD = 'main div.group.rounded-5[class~="aspect-3/4"]';
export const IMAGE_CARD = 'main div.group.rounded-5.aspect-square';
export const IMAGE_DIALOG = '[role="dialog"]:has(img[alt="preview"])';
const UUID = '[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}';
const fail = (code, message) => { throw new StudioError(code, message); };
export function queryDigest() {
  const hash = createHash('sha256');
  for (const name of QUERY_FILES) hash.update(name+'\0').update(readFileSync(new URL(name, import.meta.url))).update('\0');
  return hash.digest('hex');
}
export function checkQueryPin(pin) {
  if (!/^[a-f0-9]{64}$/.test(pin || '') || pin !== queryDigest()) fail('definition_changed', 'Review and rebuild the asset query adapter.');
}
export function queryScope(args) {
  const {category, ownership, filter} = args;
  if (category === 'Model' && ['My Assets','Collected'].includes(ownership) &&
      (ownership === 'Collected' ? filter === 'All' : ['All','Smart Mesh','Untextured','Textured','Rigged'].includes(filter)))
    return {asset_type: category, ownership, filter: ownership === 'Collected' ? null : filter};
  if (category === 'Image' && ownership === 'Image Assets' && ['All','multi-views'].includes(filter))
    return {asset_type:category, ownership, filter};
  fail('invalid_argument', 'Use the observed category/ownership/filter combination; Collected has no filter controls.');
}
export function queryBounds(args) {
  const limit = Number(args.limit), pages = Number(args.pages);
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000 || !Number.isInteger(pages) || pages < 1 || pages > 50)
    fail('invalid_argument', 'limit 1-1000 and pages 1-50 are required.');
  return {limit,pages};
}

// These browser functions are serialized: DOM only, no captured module state.
export function readQueryNavigationDOM() {
  const visible = e => { const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 && getComputedStyle(e).display!=='none' && getComputedStyle(e).visibility!=='hidden'; };
  const dialogs = [...document.querySelectorAll('[role="dialog"]')].filter(visible);
  return {origin:location.origin, path:location.pathname, dialog_open:dialogs.length>0,
    site_error:/Something went wrong|Please try again later/.test(document.querySelector('main')?.innerText || ''),
    links:[...document.querySelectorAll('header a[href]')].filter(visible).filter(a=>a.innerText.trim()==='Assets').map(a=>a.getAttribute('href'))};
}
export function readQueryChoiceDOM(label) {
  const main=document.querySelector('main');
  if (location.origin!=='https://studio.tripo3d.ai' || location.pathname!=='/assets') return {kind:'pending'};
  const buttons=[...main?.querySelectorAll('button') || []];
  const matches=buttons.map((b,nth)=>{
    const r=b.getBoundingClientRect();if (b.innerText.trim()!==label || r.width<=0 || r.height<=0) return null;
    const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
    return {nth,state:b.getAttribute('data-state'),pointer_ready:hit===b || !!hit && b.contains(hit)};
  }).filter(Boolean);
  if (!matches.length) return {kind:'pending'};
  if (matches.length!==1 || !['active','inactive'].includes(matches[0].state)) return {kind:'collection_scope_changed'};
  return {kind:'ready',...matches[0]};
}
export function readQueryDOM(scope) {
  if (location.origin!=='https://studio.tripo3d.ai' || location.pathname!=='/assets') return {kind:'origin_mismatch'};
  const main=document.querySelector('main');
  if (!main) return {kind:'pending'};
  if (/Something went wrong|Please try again later/.test(main.innerText || '')) return {kind:'site_error'};
  const visible=e=>{const r=e.getBoundingClientRect();return r.width>0 && r.height>0 && getComputedStyle(e).display!=='none' && getComputedStyle(e).visibility!=='hidden';};
  if ([...document.querySelectorAll('[role="dialog"]')].some(visible)) return {kind:'dialog_open'};
  const buttons=[...main.querySelectorAll('button')].filter(visible);
  const labels=[scope.asset_type,...(scope.asset_type==='Model'?[scope.ownership]:[]),...(scope.filter?[scope.filter]:[])];
  for (const label of labels) {
    const found=buttons.filter(b=>b.innerText.trim()===label);
    if (found.length!==1 || !['active','inactive'].includes(found[0].getAttribute('data-state'))) return {kind:'collection_scope_changed'};
    if (found[0].getAttribute('data-state')!=='active') return {kind:'collection_scope_mismatch'};
  }
  if (scope.asset_type==='Image' && !/Image Assets/.test(main.innerText || '')) return {kind:'collection_scope_changed'};
  if (scope.ownership==='Collected' && buttons.some(b=>['All','Smart Mesh','Untextured','Textured','Rigged'].includes(b.innerText.trim()))) return {kind:'collection_scope_changed'};
  const selector=scope.asset_type==='Model'?'div.group.rounded-5[class~="aspect-3/4"]':'div.group.rounded-5.aspect-square';
  const all=[...main.querySelectorAll(selector)];
  const outer=[...main.querySelectorAll('div.group.rounded-5')].filter(c=>visible(c) && !c.parentElement?.closest('div.group.rounded-5'));
  if (outer.length!==all.filter(visible).length) return {kind:'collection_card_contract_changed'};
  const cards=[];
  for (let nth=0;nth<all.length;nth++) {
    const card=all[nth];if (!visible(card)) continue;
    const images=[];
    for (const img of card.querySelectorAll('img')) {
      let url;try {url=new URL(img.getAttribute('src'),location.origin);} catch {return {kind:'thumbnail_contract_changed'};}
      if (url.protocol!=='https:') return {kind:'thumbnail_contract_changed'};
      // Deliberately discard signed query strings and never return the source URL.
      images.push({host:url.host,path:url.pathname,title:img.getAttribute('alt')?.trim() || null});
    }
    if (!images.length) return {kind:'pending'};
    cards.push({nth,images});
  }
  // No observed empty-state contract: missing cards are not success [].
  if (!cards.length) return {kind:'pending'};
  const footer=main.querySelector('div.min-h-10');
  if (!footer) return {kind:'collection_footer_changed'};
  let scroll=main;
  while (scroll.parentElement && !(scroll.scrollHeight>scroll.clientHeight+5 && /auto|scroll/.test(getComputedStyle(scroll).overflowY))) scroll=scroll.parentElement;
  return {kind:'ready',cards,scope_verified:true,rendered_cards:cards.length,
    at_end:scroll.scrollTop+scroll.clientHeight>=scroll.scrollHeight-5,
    loading:!!footer.querySelector('[class*="loading"],[class*="animate-spin"]'),
    footer_text_present:!!footer.innerText.trim()};
}

export function imageIdentity(image) {
  if (!image || image.host!=='tripo-data.rg1.data.tripo3d.com') fail('thumbnail_contract_changed', 'Unexpected image thumbnail host.');
  let match=image.path?.match(new RegExp('^/generate-image/\\d{8}/('+UUID+')/image(?:_(\\d+))?\\.png$'));
  if (match) {
    const index=match[2]===undefined?null:Number(match[2]);
    if (index!==null && (!Number.isSafeInteger(index) || index<0 || index>99)) fail('thumbnail_contract_changed','Unexpected generated image index.');
    return {asset_type:'image',image_task_id:match[1],image_index:index,card_id:'image:'+match[1]+':'+(index===null?'single':index)};
  }
  match=image.path?.match(new RegExp('^/tripo-studio/\\d{8}/('+UUID+')/multiview_([0-3])_('+UUID+')\\.jpeg$'));
  if (match && match[1]===match[3]) return {asset_type:'multiview',image_task_id:match[1],view_index:Number(match[2]),card_id:'multiview:'+match[1]};
  fail('thumbnail_contract_changed','Unexpected image thumbnail path; review the visible card.');
}
export function parseQueryCards(raw,scope) {
  if (!Array.isArray(raw) || !raw.length) fail('bridge_protocol','Expected observed asset cards.');
  const seen=new Set();
  return raw.map(card=>{
    let item;
    if (scope.asset_type==='Model') {
      if (card.images?.length!==1) fail('collection_card_identity_changed','Expected one model thumbnail per outer card.');
      const image=card.images[0], match=image.path?.match(new RegExp('^/tripo-studio/\\d{8}/('+UUID+')/studio_(?:mesh|mesh_gray|part|wireframe)\\.webp$'));
      if (image.host!=='tripo-data-public.rg1.data.tripo3d.com' || !match || !image.title || image.title.length>1000) fail('thumbnail_contract_changed','Unexpected model thumbnail contract.');
      item={card_id:'model:'+match[1],asset_type:'model',preview_task_id:match[1],title:image.title,task_status:null};
    } else {
      if (!Array.isArray(card.images) || !card.images.length) fail('collection_card_identity_changed','Expected image thumbnails.');
      const images=card.images.map(imageIdentity),first=images[0];
      if (images.some(i=>i.card_id!==first.card_id)) fail('collection_card_identity_changed','Mixed task/image identities in one outer card.');
      if (first.asset_type==='image') {
        if (images.length!==1 || scope.filter==='multi-views') fail('collection_card_identity_changed','Unexpected single image in this card/filter.');
        item=first;
      } else {
        const indices=images.map(i=>i.view_index).sort();
        if (indices.join(',')!=='0,1,2,3') fail('collection_card_identity_changed','Expected the four distinct observed multiview images.');
        item={card_id:first.card_id,asset_type:'multiview',image_task_id:first.image_task_id,view_indices:indices};
      }
    }
    if (!Number.isInteger(card.nth) || card.nth<0 || seen.has(item.card_id)) fail('collection_card_identity_changed','Duplicate or ambiguous outer card identity.');
    seen.add(item.card_id);return item;
  });
}
async function navigateQuery(page) {
  let nav=unwrap(await page.evaluate(readQueryNavigationDOM));
  if (nav?.dialog_open) fail('dialog_open','An existing visible dialog is preserved; close it locally before a new query.');
  if (nav?.origin!==ORIGIN) {await page.goto(ORIGIN+'/');await pollDOM(page,readAccountDOM);nav=unwrap(await page.evaluate(readQueryNavigationDOM));}
  if (nav?.site_error) fail('site_error','Tripo displays an error; no asset operation was submitted.');
  if (nav?.path!=='/assets') {
    if (nav?.links?.length!==1 || nav.links[0]!=='/assets') fail('layout_changed','Expected the observed Assets navigation link.');
    await page.click('header a[href="/assets"]');
  }
  await pollDOM(page,readAccountDOM);
}
async function selectScope(page,scope) {
  for (const label of [scope.asset_type,...(scope.asset_type==='Model'?[scope.ownership]:[]),...(scope.filter?[scope.filter]:[])]) {
    const choice=await pollDOM({evaluate:()=>page.evaluate(readQueryChoiceDOM,label)},readQueryChoiceDOM);
    if (choice.state!=='active') {
      const target=await prepareQueryChoice(page,label,choice);
      await page.click('main button',{nth:target.nth});
    }
    const selected=await pollDOM({evaluate:async()=>{const value=unwrap(await page.evaluate(readQueryChoiceDOM,label));return value?.kind==='ready' && value.state!=='active'?{kind:'pending'}:value;}},readQueryChoiceDOM);
    if (selected.state!=='active') fail('collection_scope_mismatch','Requested asset scope was not selected.');
  }
}
async function prepareQueryChoice(page,label,choice=null) {
  choice ||= await pollDOM({evaluate:()=>page.evaluate(readQueryChoiceDOM,label)},readQueryChoiceDOM);
  if (!choice.pointer_ready) {
    // Real Studio's nested scroll viewport leaves sticky category tabs at y=0,
    // underneath the fixed header. CDP scrollIntoView alone considers them
    // visible and clicks the logo. Focus + Home is the observed UI repair.
    await page.focus('main button',{nth:choice.nth});
    await page.pressKey('Home');
    const waitPointer=timeout=>pollDOM({evaluate:async()=>{
      const value=unwrap(await page.evaluate(readQueryChoiceDOM,label));
      return value?.kind==='ready' && !value.pointer_ready?{kind:'pending'}:value;
    }},readQueryChoiceDOM,{timeout,pause:100});
    try {choice=await waitPointer(800);} catch (error) {
      if (!(error instanceof StudioError) || error.code!=='page_not_ready') throw error;
      if (typeof page.cdp!=='function') fail('control_obscured','Asset scope control remains covered; no click was sent.');
      // SDK 1.8.6 sends key only (virtual code defaults to zero). Complete
      // the documented UI key event; never scroll by executing page JS.
      for (const type of ['rawKeyDown','keyUp']) await page.cdp('Input.dispatchKeyEvent',{type,key:'Home',code:'Home',windowsVirtualKeyCode:36});
      try {choice=await waitPointer(2000);} catch (next) {
        if (!(next instanceof StudioError) || next.code!=='page_not_ready') throw next;
        fail('control_obscured','Asset scope control remains covered; no click was sent.');
      }
    }
  }
  return choice;
}
export async function queryAssets(page,args,{quietMs=4000,pause=250}={}) {
  const scope=queryScope(args),{limit,pages}=queryBounds(args);
  await navigateQuery(page);await selectScope(page,scope);
  const read=()=>pollDOM({evaluate:()=>page.evaluate(readQueryDOM,scope)},readQueryDOM);
  const found=new Map();let data,stop='page_limit',rounds=0;
  // Let scope transitions settle before collecting, including any observed loading indicator.
  let signature='',stableUntil=Date.now()+quietMs;
  const settleDeadline=Date.now()+Math.max(15000,quietMs*3);
  do {
    data=await read();const items=parseQueryCards(data.cards,scope),next=JSON.stringify(items);
    if (next!==signature || data.loading) {signature=next;stableUntil=Date.now()+quietMs;}
    if (!data.loading && Date.now()>=stableUntil) break;
    if (Date.now()>=settleDeadline) fail('page_not_ready','Asset scope remains loading or changing.');
    await new Promise(resolve=>setTimeout(resolve,pause));
  } while (true);
  for (;rounds<pages;rounds++) {
    for (const item of parseQueryCards(data.cards,scope)) found.set(item.card_id,item);
    if (found.size>=limit) {stop='item_limit';break;}
    const count=found.size;await page.scrollTo('main div.min-h-10');const end=Date.now()+quietMs;
    do {
      data=await read();for (const item of parseQueryCards(data.cards,scope)) found.set(item.card_id,item);
      if (found.size>count || Date.now()>=end) break;
      await new Promise(resolve=>setTimeout(resolve,pause));
    } while (true);
    if (found.size>=limit) {stop='item_limit';break;}
    if (found.size===count && data.at_end && !data.loading) {stop='quiet_scroll_end_no_authoritative_total';break;}
    if (found.size===count && data.loading) fail('page_not_ready','Asset pagination remains loading.');
  }
  const items=[...found.values()].slice(0,limit);
  return [{status:'partial',assets:items,returned_count:items.length,pages_scanned:Math.min(rounds+1,pages),scope,
    coverage:'automatic_visible_scroll_scan',all_assets:false,site_wide_coverage:false,authoritative_total:null,
    coverage_evidence:{scope_verified:true,rendered_cards:data.rendered_cards,at_scroll_end:data.at_end,loading:data.loading,
      explicit_ui_end:false,end_marker_contract_observed:false},stop_reason:stop,secrets_returned:false,paid_submitted:false}];
}

export function readImagePreviewDOM() {
  if (location.origin!=='https://studio.tripo3d.ai') return {kind:'origin_mismatch'};
  const dialogs=[...document.querySelectorAll('[role="dialog"]:has(img[alt="preview"])')].filter(d=>{const r=d.getBoundingClientRect();return r.width>0 && r.height>0;});
  if (!dialogs.length) return {kind:'pending'};
  if (dialogs.length!==1) return {kind:'layout_changed'};
  const dialog=dialogs[0],imgs=[...dialog.querySelectorAll('img[alt="preview"]')];
  if (imgs.length!==1) return {kind:'layout_changed'};
  let url;try {url=new URL(imgs[0].getAttribute('src'),location.origin);} catch {return {kind:'layout_changed'};}
  if (url.protocol!=='https:') return {kind:'thumbnail_contract_changed'};
  const fields={};
  for (const label of ['Generation Model','Image dimensions']) {
    const labels=[...dialog.querySelectorAll('span')].filter(e=>e.innerText.trim()===label);
    if (labels.length>1) return {kind:'layout_changed'};
    if (labels.length) {
      const value=labels[0].nextElementSibling?.innerText?.trim();
      if (!value || value.length>100) return {kind:'layout_changed'};
      fields[label]=value;
    }
  }
  const actions=[...dialog.querySelectorAll('button')].map(b=>({label:b.innerText.trim(),enabled:!b.disabled})).filter(b=>['Generate HD Model','Generate Smart Mesh'].includes(b.label));
  if (actions.length!==2 || !fields['Image dimensions']) return {kind:'layout_changed'};
  if (dialog.querySelectorAll('button.rounded-full.bg-gray-3').length!==1) return {kind:'layout_changed'};
  return {kind:'ready',image:{host:url.host,path:url.pathname},fields,actions};
}
export function parsePreviewTarget(args) {
  const card=args.card,view=Number(args.view);
  if (!new RegExp('^(?:image:'+UUID+':(?:single|[0-9]|[1-9][0-9])|multiview:'+UUID+')$').test(card || '') ||
      !Number.isInteger(view) || view<0 || view>3 || card.startsWith('image:') && view!==0)
    fail('invalid_argument','Use an image/multiview card_id from assets-query; view 0-3 applies only to multiview.');
  return {card,view};
}
export function readPreviewCloseDOM() {
  if (location.origin!=='https://studio.tripo3d.ai' || location.pathname!=='/assets') return {kind:'origin_mismatch'};
  const dialogs=[...document.querySelectorAll('[role="dialog"]')].filter(d=>{const r=d.getBoundingClientRect();return r.width>0 && r.height>0 && getComputedStyle(d).display!=='none' && getComputedStyle(d).visibility!=='hidden';});
  if (dialogs.some(d=>d.querySelector('img[alt="preview"]'))) return {kind:'pending'};
  if (!dialogs.length) return {kind:'ready',creator_popover:false};
  if (dialogs.length===1 && dialogs[0].classList.contains('creator-growth-header-popover') && dialogs[0].getAttribute('data-state')==='open')
    return {kind:'ready',creator_popover:true};
  return {kind:'dialog_open'};
}
export async function previewImage(page,args,options={}) {
  const {card,view}=parsePreviewTarget(args),scope=queryScope({category:'Image',ownership:'Image Assets',filter:'All'});
  await queryAssets(page,{category:'Image',ownership:'Image Assets',filter:'All',limit:1000,pages:50},options);
  const data=await pollDOM({evaluate:()=>page.evaluate(readQueryDOM,scope)},readQueryDOM);
  const items=parseQueryCards(data.cards,scope),index=items.findIndex(i=>i.card_id===card);
  if (index<0) fail('asset_not_visible','Requested image card is not in the rendered grid.');
  const raw=data.cards[index],imgIndex=raw.images.findIndex(i=>{const identity=imageIdentity(i);return identity.card_id===card && (identity.asset_type==='image' || identity.view_index===view);});
  if (imgIndex<0) fail('asset_mismatch','Requested multiview image is absent.');
  // The validated path identifies this image without signed URL parameters or
  // positional assumptions about nested wrappers / multiview display order.
  await page.click(IMAGE_CARD+' img[src*="'+raw.images[imgIndex].path+'"]');
  const detail=await pollDOM(page,readImagePreviewDOM),identity=imageIdentity(detail.image);
  if (identity.card_id!==card || identity.asset_type==='multiview' && identity.view_index!==view) fail('asset_mismatch','Preview does not match the exact requested image.');
  await page.click(IMAGE_DIALOG+' button.rounded-full.bg-gray-3');
  const closed=await pollDOM(page,readPreviewCloseDOM);
  const allTab=await prepareQueryChoice(page,'All');
  // Move away from the header after closing the overlay: Escape alone leaves
  // the cursor on Creator and its hover timer can reopen the popover later.
  await page.hover('main button',{nth:allTab.nth});
  // The close button's cursor position can open this observed header hover
  // popover. Initial dialogs were rejected above; dismiss only this new known
  // incidental popover, never an existing draft/consent or unknown dialog.
  const afterHover=await pollDOM(page,readPreviewCloseDOM);
  if (afterHover.creator_popover) {
    await page.pressKey('Escape');
    await pollDOM({evaluate:async()=>{const state=unwrap(await page.evaluate(readPreviewCloseDOM));return state?.kind==='ready' && state.creator_popover?{kind:'pending'}:state;}},readPreviewCloseDOM);
  }
  return [{status:'ready',...identity,generation_model:detail.fields['Generation Model'] || null,
    aspect_ratio:detail.fields['Image dimensions'],available_actions:detail.actions,
    preview_verified:true,preview_closed:true,incidental_creator_popover_dismissed:closed.creator_popover || afterHover.creator_popover,
    model_completed:false,secrets_returned:false,paid_submitted:false}];
}
