"""Build finite reviewed actions. This is NOT a vendor-wide compatibility claim."""
import argparse
import json
from pathlib import Path
if __name__=='__main__':argparse.ArgumentParser(description='Regenerate src/agent_tool_maker/data/catalog-v02.json in place; takes no options.').parse_args()
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'src/agent_tool_maker/data'
research=json.loads((DATA/'research.json').read_text())
SOURCES={r['id']:r['source_urls'] for r in research['records']}
rows=[]
S={'type':'string','minLength':1,'maxLength':20000}
ID={'type':'string','pattern':r'^[A-Za-z0-9][A-Za-z0-9_.:~@-]{0,199}$'}
N={'type':'integer','minimum':1,'maximum':100}
OBJ={'type':'object'}
URL={'type':'string','pattern':r'^https://[^\s]+$','maxLength':4096}
FILE={'type':'string','minLength':1,'maxLength':2048}
def schema(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def add(id,provider,title,caps,props,example,adapter,**kw):
 row=dict(id=id,provider=provider,title=title,capabilities=caps.split(),schema=schema(props),example=example,
          adapter=adapter,implementation='native' if adapter in ['rest','command'] else adapter,paid=False,permissions=[],
          sources=SOURCES.get(provider,[]),checked_on='2026-09-29',verification='contract_tests_not_vendor_live',**kw)
 rows.append(row);return row
def cli(id,p,title,exe,args,props={},example={},caps='inspect',out='text',perms=(),paid=False,files=(),**extra):
 row=add(id,p,title,caps,props,example,'command',executable=exe)
 row.update(permissions=list(perms),paid=paid)
 row['command']={'argv':args,'output':out,'outputs':list(files),'timeout':120,**extra}
 return row
def api(id,p,title,origin,path,props={},example={},caps='search',method='GET',body=None,query=None,auth='bearer',credential=None,perms=(),paid=False,**extra):
 row=add(id,p,title,caps,props,example,'rest')
 row.update(permissions=list(perms),paid=paid)
 if auth!='none':row['credential']=credential or p
 req={'path':path,'method':method,'auth':auth,**extra}
 if origin: req['origin']=origin
 else:req['origin_setting']=True
 if body is not None:req['body']=body
 if query is not None:req['query']=query
 row['request']=req
 return row
def arg(n):return {'input':n}
def file(n):return {'file':n}
def output(n):return {'output':n}
def jarg(n):return {'json':n}
def directory(n):return {'dir':n}
W=['external_write'];C=['execute_code'];P=['external_write','production','execute_code']
# Information and social discovery: keep site invocations finite, not an unrestricted CLI pass-through.
cli('opencli.list','opencli','OpenCLI command registry','opencli',['list','-f','json'],out='json',caps='search social')
cli('opencli.doctor','opencli','OpenCLI browser connection diagnostics','opencli',['doctor'],caps='inspect social')
cli('opencli.hackernews_top','opencli','Hacker News top stories','opencli',['hackernews','top','--limit',arg('limit'),'-f','json'],{'limit':N},{'limit':5},out='json',caps='search social')
for site,title in [('bilibili','Bilibili'),('zhihu','Zhihu')]:
 cli(f'opencli.{site}_hot','opencli',title+' trending discussions','opencli',[site,'hot','--limit',arg('limit'),'-f','json'],{'limit':N},{'limit':5},out='json',caps='search social')
cli('opencli.browser_state','opencli','Read an existing browser session state','opencli',['browser',arg('session'),'state'],{'session':ID},{'session':'work'},caps='inspect browser')
api('apify.run','apify','Start a selected Apify Actor','https://api.apify.com','/v2/acts/{actor}/runs',{'actor':ID,'input':OBJ},{'actor':'user~actor','input':{'query':'test'}},method='POST',body='$input',perms=W,paid=True,caps='scrape search')
api('apify.run_status','apify','Read existing Actor run','https://api.apify.com','/v2/actor-runs/{run_id}',{'run_id':ID},{'run_id':'run123'},caps='inspect scrape')
api('apify.dataset_items','apify','Retrieve one bounded dataset page','https://api.apify.com','/v2/datasets/{dataset_id}/items',{'dataset_id':ID,'limit':N,'offset':{'type':'integer','minimum':0}},{'dataset_id':'data123','limit':20,'offset':0},query={'limit':'$limit','offset':'$offset','clean':True},caps='scrape')
api('dataforseo.search_volume','dataforseo','Keyword search-volume request','https://api.dataforseo.com','/v3/keywords_data/google_ads/search_volume/live',{'keywords':{'type':'array','items':S,'minItems':1,'maxItems':100},'location_code':{'type':'integer'},'language_code':ID},{'keywords':['3d design'],'location_code':2840,'language_code':'en'},method='POST',body=[{'keywords':'$keywords','location_code':'$location_code','language_code':'$language_code'}],auth='basic',paid=True)
api('youtube.search','youtube_data','Search YouTube metadata (OAuth bearer)','https://www.googleapis.com','/youtube/v3/search',{'query':S,'limit':N},{'query':'product feedback','limit':10},query={'part':'snippet','q':'$query','maxResults':'$limit','type':'video'},credential='google_oauth',caps='search social')
api('youtube.comments','youtube_data','Read one page of YouTube comment threads','https://www.googleapis.com','/youtube/v3/commentThreads',{'video_id':ID,'limit':N},{'video_id':'video123','limit':20},query={'part':'snippet','videoId':'$video_id','maxResults':'$limit'},credential='google_oauth',caps='search social')
# Reviewed social reads: preserve signed content URLs, use the installed site's login session.
cli('opencli.xiaohongshu_search','opencli','小红书 search notes','opencli',['xiaohongshu','search',arg('query'),'--limit',arg('limit'),'-f','json'],{'query':S,'limit':N},{'query':'通勤穿搭','limit':10},caps='search social',out='json')
cli('opencli.xiaohongshu_note','opencli','小红书 read signed note URL','opencli',['xiaohongshu','note',arg('url'),'-f','json'],{'url':URL},{'url':'https://www.xiaohongshu.com/search_result/example?xsec_token=replace-locally'},caps='search social',out='json')
cli('opencli.xiaohongshu_comments','opencli','小红书 comments and replies','opencli',['xiaohongshu','comments',arg('url'),'--with-replies','--limit',arg('limit'),'-f','json'],{'url':URL,'limit':N},{'url':'https://www.xiaohongshu.com/search_result/example?xsec_token=replace-locally','limit':20},caps='search social',out='json')
cli('opencli.twitter_search','opencli','X/Twitter live search','opencli',['twitter','search',arg('query'),'--filter','live','-f','json'],{'query':S},{'query':'need better product design tools'},caps='search social',out='json')
cli('opencli.reddit_read','opencli','Read Reddit thread and bounded replies','opencli',['reddit','read',arg('post_id'),'--depth','2','-f','json'],{'post_id':ID},{'post_id':'1abc123'},caps='search social',out='json')
cli('opencli.upwork_search','upwork','Read Upwork search via existing OpenCLI browser login','opencli',['upwork','search',arg('query'),'-f','json'],{'query':S},{'query':'clothing design'},caps='search outsourcing',out='json')
cli('opencli.upwork_detail','upwork','Read Upwork job details without applying or hiring','opencli',['upwork','detail',arg('job_id'),'-f','json'],{'job_id':S},{'job_id':'~022000000000000000000'},caps='search outsourcing',out='json')

# Office/project operations reuse the user's authenticated CLI where appropriate.
for id,sub,params in [('drive_files',['drive','files','list'],{'pageSize':20}),('gmail_messages',['gmail','users','messages','list'],{'userId':'me','maxResults':20}),('calendar_events',['calendar','events','list'],{'calendarId':'primary','maxResults':20})]:
 cli('gws.'+id,'gws','Google Workspace '+id,'gws',sub+['--params',jarg('params')],{'params':OBJ},{'params':params},caps='office search',out='json')
api('notion.search','notion','Search connected Notion workspace','https://api.notion.com','/v1/search',{'query':S},{'query':'requirements'},method='POST',body={'query':'$query','page_size':20},headers={'Notion-Version':'2025-09-03'},caps='office search')
api('notion.create_page','notion','Create a Notion page','https://api.notion.com','/v1/pages',{'page':OBJ},{'page':{'parent':{'page_id':'replace-me'},'properties':{'title':{'title':[{'text':{'content':'Plan'}}]}}}},method='POST',body='$page',headers={'Notion-Version':'2025-09-03'},perms=W,caps='office planning')
api('linear.issues','linear','Read Linear issues','https://api.linear.app','/graphql',{}, {},method='POST',body={'query':'query { issues(first: 20) { nodes { id title url } pageInfo { hasNextPage endCursor } } }'},auth='header:Authorization',caps='planning search')
api('linear.create_issue','linear','Create a Linear issue','https://api.linear.app','/graphql',{'team_id':ID,'title':S,'description':S},{'team_id':'team123','title':'Review prototype','description':'Acceptance criteria'},method='POST',body={'query':'mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id title url } } }','variables':{'input':{'teamId':'$team_id','title':'$title','description':'$description'}}},auth='header:Authorization',perms=W,caps='planning')
api('typeform.forms','typeform','List Typeform forms','https://api.typeform.com','/forms',caps='forms search')
api('typeform.responses','typeform','Read Typeform responses','https://api.typeform.com','/forms/{form_id}/responses',{'form_id':ID},{'form_id':'form123'},query={'page_size':100},caps='forms search')
api('typeform.create','typeform','Create a Typeform survey','https://api.typeform.com','/forms',{'form':OBJ},{'form':{'title':'User research','fields':[]}},method='POST',body='$form',perms=W,caps='forms')
cli('pandoc.to_markdown','pandoc','Convert a local document to Markdown','pandoc',['--sandbox',file('path'),'-t','gfm','-o',output('document.md')],{'path':FILE},{'path':'source.html'},caps='document',files=['document.md'])
# Fixed DOCX conversion uses no filters or Lua. Some Pandoc builds cannot render DOCX in
# --sandbox because of default-data access. Require execute_code rather than promise isolation.
cli('pandoc.to_docx','pandoc','Convert local Markdown to DOCX','pandoc',[file('path'),'-o',output('document.docx')],{'path':FILE},{'path':'source.md'},caps='document',files=['document.docx'],perms=C)
api('freelancer.active_projects','freelancer','Search active Freelancer projects','https://www.freelancer.com','/api/projects/0.1/projects/active/',{'query':S},{'query':'3d clothing'},query={'query':'$query','limit':20},auth='header:freelancer-oauth-v1',caps='search outsourcing')
api('figma.file','figma','Read a Figma file tree','https://api.figma.com','/v1/files/{file_key}',{'file_key':ID},{'file_key':'file123'},auth='header:X-Figma-Token',caps='design')
# Media and local generation
api('comfyui.queue','comfyui','Read explicitly configured local ComfyUI queue',None,'/queue',auth='none',local=True,caps='image inspect')
api('comfyui.submit','comfyui','Submit an approved local ComfyUI workflow',None,'/prompt',{'prompt':OBJ},{'prompt':{'1':{'class_type':'KSampler','inputs':{}}}},auth='none',method='POST',body={'prompt':'$prompt'},local=True,perms=C,paid=True,caps='image')
api('comfyui.history','comfyui','Get completed ComfyUI history',None,'/history/{prompt_id}',{'prompt_id':ID},{'prompt_id':'prompt123'},auth='none',local=True,caps='inspect image')
api('pexels.photos','pexels','Search Pexels stock photos','https://api.pexels.com','/v1/search',{'query':S,'page':{'type':'integer','minimum':1}},{'query':'fabric','page':1},query={'query':'$query','per_page':20,'page':'$page'},auth='header:Authorization',caps='stock image')
api('pexels.videos','pexels','Search Pexels stock video','https://api.pexels.com','/videos/search',{'query':S},{'query':'fabric'},query={'query':'$query','per_page':20},auth='header:Authorization',caps='stock video')
cli('imagemagick.resize','imagemagick','Resize a local raster image','magick',[file('path'),'-resize',arg('geometry'),output('resized.png')],{'path':FILE,'geometry':{'type':'string','pattern':r'^[1-9][0-9]{0,4}x[1-9][0-9]{0,4}>?$'}},{'path':'image.png','geometry':'640x640>'},caps='image_edit',files=['resized.png'])
cli('imagemagick.webp','imagemagick','Convert a raster image to WebP','magick',[file('path'),'-quality',arg('quality'),output('image.webp')],{'path':FILE,'quality':N},{'path':'image.png','quality':80},caps='image_edit',files=['image.webp'])
cli('ffmpeg.trim','ffmpeg','Trim a local video or audio clip','ffmpeg',['-nostdin','-v','error','-protocol_whitelist','file,pipe','-ss',arg('start'),'-i',file('path'),'-t',arg('duration'),'-y',output('clip.mp4')],{'path':FILE,'start':{'type':'number','minimum':0},'duration':{'type':'number','exclusiveMinimum':0,'maximum':600}},{'path':'video.mp4','start':0,'duration':3},caps='video_edit',files=['clip.mp4'])
cli('ffmpeg.thumbnail','ffmpeg','Extract a video thumbnail','ffmpeg',['-nostdin','-v','error','-protocol_whitelist','file,pipe','-ss',arg('at'),'-i',file('path'),'-frames:v','1','-y',output('thumbnail.png')],{'path':FILE,'at':{'type':'number','minimum':0}},{'path':'video.mp4','at':0},caps='video_edit image',files=['thumbnail.png'])
cli('remotion.compositions','remotion','Inspect a trusted Remotion project','remotion',['compositions',file('entry')],{'entry':FILE},{'entry':'src/index.ts'},caps='video inspect',perms=C)
cli('remotion.render','remotion','Render an existing Remotion composition','remotion',['render',file('entry'),arg('composition'),output('render.mp4'),'--props',jarg('props')],{'entry':FILE,'composition':ID,'props':OBJ},{'entry':'src/index.ts','composition':'Main','props':{}},caps='video_edit video',perms=C,files=['render.mp4'],timeout=900)
cli('whisper.transcribe','whisper_cpp','Transcribe local WAV with whisper.cpp','whisper-cli',['-m',file('model'),'-f',file('audio'),'-l',arg('language'),'-otxt','-oj','-of',output('transcript')],{'model':FILE,'audio':FILE,'language':ID},{'model':'models/ggml.bin','audio':'tone.wav','language':'auto'},caps='transcribe',files=['transcript.txt','transcript.json'],timeout=900)
cli('blender.inspect','blender','Inspect a blend project without auto-run scripts','blender',['--background','--disable-autoexec',file('project'),'--python',{'script':'blender_inspect.py'},'--',output('scene.json')],{'project':FILE},{'project':'scene.blend'},caps='3d inspect',files=['scene.json'],timeout=300)
cli('blender.render','blender','Render one frame of an approved blend project','blender',['--background','--disable-autoexec',file('project'),'--python',{'script':'blender_render.py'},'--',output('render.png')],{'project':FILE},{'project':'scene.blend'},caps='3d image',perms=C,files=['render.png'],timeout=900)
cli('gltf.inspect','gltf_transform','Inspect glTF/GLB structure','gltf-transform',['inspect',file('path')],{'path':FILE},{'path':'model.glb'},caps='3d inspect')
cli('gltf.optimize','gltf_transform','Optimize a GLB for web delivery','gltf-transform',['optimize',file('path'),output('optimized.glb')],{'path':FILE},{'path':'model.glb'},caps='3d',files=['optimized.glb'],timeout=300)
cli('kicad.drc','kicad','Run PCB design-rule checks','kicad-cli',['pcb','drc','--format','json','--output',output('drc.json'),'--exit-code-violations',file('board')],{'board':FILE},{'board':'board.kicad_pcb'},caps='hardware inspect',files=['drc.json'])
cli('kicad.gerbers','kicad','Export PCB Gerber files','kicad-cli',['pcb','export','gerbers','--output',output('gerbers'),file('board')],{'board':FILE},{'board':'board.kicad_pcb'},caps='hardware',timeout=300)
# Development / deployment. Project code execution is explicitly gated.
for id,args,props,example in [
 ('repo',['repo','view',arg('repo'),'--json','name,url,defaultBranchRef'],{'repo':S},{'repo':'owner/repo'}),
 ('issues',['issue','list','--repo',arg('repo'),'--json','number,title,state,url'],{'repo':S},{'repo':'owner/repo'}),
 ('runs',['run','list','--repo',arg('repo'),'--json','databaseId,status,conclusion,url'],{'repo':S},{'repo':'owner/repo'}),
 ('pr_checks',['pr','checks',arg('number'),'--repo',arg('repo'),'--json','name,state,link'],{'repo':S,'number':N},{'repo':'owner/repo','number':1})]:
 cli('github.'+id,'github_cli','GitHub '+id,'gh',args,props,example,caps='development inspect',out='json')
cli('github.create_issue','github_cli','Create GitHub issue','gh',['issue','create','--repo',arg('repo'),'--title',arg('title'),'--body-file',file('body')],{'repo':S,'title':S,'body':FILE},{'repo':'owner/repo','title':'Fix layout','body':'issue.md'},caps='development planning',perms=W)
cli('docker.ps','docker','Inspect Docker containers','docker',['ps','--format','json'],caps='development inspect')
cli('docker.build','docker','Build an approved Docker project','docker',['build','-t',arg('tag'),directory('project')],{'tag':ID,'project':FILE},{'tag':'atm-demo:local','project':'.'},caps='development',perms=C,timeout=900)
cli('playwright.test','playwright','Run existing trusted Playwright tests','playwright',['test','--reporter=json'],caps='debug inspect',perms=C,out='json',timeout=900)
cli('wrangler.deployments','cloudflare_wrangler','Read Worker deployment history','wrangler',['deployments','list','--name',arg('name'),'--json'],{'name':ID},{'name':'atm-demo'},caps='deploy inspect',out='json',credential_env={'CLOUDFLARE_API_TOKEN':'cloudflare'})
cli('wrangler.build','cloudflare_wrangler','Build Worker without deployment','wrangler',['deploy','--dry-run','--outdir',output('bundle')],caps='deploy development',perms=C,timeout=300,credential_env={'CLOUDFLARE_API_TOKEN':'cloudflare'})
cli('wrangler.preview','cloudflare_wrangler','Create Worker preview deployment (requires compatible Wrangler)','wrangler',['preview','--name',arg('name'),'--json'],{'name':ID},{'name':'atm-preview'},caps='deploy',perms=W+C,paid=True,out='json',timeout=300,credential_env={'CLOUDFLARE_API_TOKEN':'cloudflare'})
cli('wrangler.deploy','cloudflare_wrangler','Deploy Worker to named environment','wrangler',['deploy','--env',arg('environment')],{'environment':ID},{'environment':'production'},caps='deploy',perms=P,paid=True,timeout=300,credential_env={'CLOUDFLARE_API_TOKEN':'cloudflare'})
cli('wrangler.d1_list','cloudflare_wrangler','List D1 databases','wrangler',['d1','list','--json'],out='json',caps='database inspect',credential_env={'CLOUDFLARE_API_TOKEN':'cloudflare'})
cli('wrangler.d1_local','cloudflare_wrangler','Execute reviewed local D1 SQL','wrangler',['d1','execute',arg('database'),'--local','--file',file('sql'),'--json'],{'database':ID,'sql':FILE},{'database':'DB','sql':'schema.sql'},caps='database',perms=C,out='json')
cli('cloudflared.tunnels','cloudflared','List named Cloudflare tunnels','cloudflared',['tunnel','list','--output','json'],out='json',caps='deploy inspect')
api('cloudflare.dns_list','cloudflare_dns','Read Cloudflare DNS records','https://api.cloudflare.com','/client/v4/zones/{zone_id}/dns_records',{'zone_id':ID},{'zone_id':'zone123'},credential='cloudflare',caps='dns inspect')
api('cloudflare.dns_create','cloudflare_dns','Create a Cloudflare DNS record','https://api.cloudflare.com','/client/v4/zones/{zone_id}/dns_records',{'zone_id':ID,'type':{'enum':['A','AAAA','CNAME','TXT']},'name':S,'content':S,'ttl':{'type':'integer','minimum':1},'proxied':{'type':'boolean'}},{'zone_id':'zone123','type':'CNAME','name':'demo.example.com','content':'example.workers.dev','ttl':1,'proxied':False},method='POST',body={k:'$'+k for k in ['type','name','content','ttl','proxied']},credential='cloudflare',perms=['external_write','production'],caps='dns deploy')
cli('vercel.list','vercel','List Vercel deployments','vercel',['ls'],caps='deploy inspect')
cli('vercel.preview','vercel','Deploy Vercel preview','vercel',['deploy','--yes'],caps='deploy',perms=W+C,paid=True,timeout=600)
cli('vercel.production','vercel','Deploy Vercel production','vercel',['deploy','--prod','--yes'],caps='deploy',perms=P,paid=True,timeout=600)
cli('supabase.projects','supabase','List Supabase projects','supabase',['projects','list','--output','json'],caps='database inspect',out='json',credential_env={'SUPABASE_ACCESS_TOKEN':'supabase'})
cli('supabase.migrations','supabase','List linked Supabase migrations','supabase',['migration','list'],caps='database inspect',credential_env={'SUPABASE_ACCESS_TOKEN':'supabase'})
cli('supabase.db_push','supabase','Apply linked remote database migrations','supabase',['db','push','--yes'],caps='database deploy',perms=P,paid=True,timeout=600,credential_env={'SUPABASE_ACCESS_TOKEN':'supabase'})
cli('supabase.function_deploy','supabase','Deploy one Supabase function','supabase',['functions','deploy',arg('name')],{'name':ID},{'name':'hello'},caps='deploy',perms=P,paid=True,timeout=300,credential_env={'SUPABASE_ACCESS_TOKEN':'supabase'})
cli('eas.build_list','expo_eas','List Expo EAS builds','eas',['build:list','--json','--non-interactive'],caps='app inspect',out='json',credential_env={'EXPO_TOKEN':'expo'})
cli('eas.build','expo_eas','Submit an Expo build, without waiting','eas',['build','--platform',arg('platform'),'--profile',arg('profile'),'--non-interactive','--no-wait','--json'],{'platform':{'enum':['android','ios','all']},'profile':ID},{'platform':'android','profile':'preview'},caps='app deploy',perms=W+C,paid=True,out='json',timeout=300,credential_env={'EXPO_TOKEN':'expo'})
cli('godot.export','godot','Export an existing Godot project','godot',['--headless','--path',directory('project'),'--export-release',arg('preset'),output('game.zip')],{'project':FILE,'preset':S},{'project':'.','preset':'Web'},caps='game deploy',perms=C,files=['game.zip'],timeout=600)
cli('butler.status','itch_butler','Read itch.io channel status','butler',['status',arg('target')],{'target':S},{'target':'user/game:web'},caps='game inspect')
cli('butler.push','itch_butler','Upload a game archive to itch.io','butler',['push',file('archive'),arg('target')],{'archive':FILE,'target':S},{'archive':'game.zip','target':'user/game:web'},caps='game deploy',perms=W,timeout=600)
# Distribution / customer operations
cli('buffer.channels','buffer','List connected Buffer channels','buffer',['channels','list','--output','json'],out='json',caps='social inspect')
cli('buffer.posts','buffer','Read posts for a specific channel','buffer',['posts','list','--channel-id',arg('channel_id'),'--output','json'],{'channel_id':ID},{'channel_id':'channel123'},out='json',caps='social inspect')
cli('buffer.schedule','buffer','Add a post to a channel queue','buffer',['posts','create','--channel-id',arg('channel_id'),'--scheduling-type','automatic','--mode','addToQueue','--text',arg('text'),'--output','json'],{'channel_id':ID,'text':S},{'channel_id':'channel123','text':'Approved product announcement'},out='json',caps='social publish',perms=W,paid=True)
cli('buffer.schema','buffer','Read post creation schema from installed Buffer version','buffer',['schema','describe','posts','create'],caps='social inspect',out='json')
api('postiz.integrations','postiz','Read Postiz connected channels',None,'/public/v1/integrations',auth='header:Authorization',caps='social inspect')
api('postiz.posts','postiz','Read Postiz scheduled posts',None,'/public/v1/posts',{'startDate':S,'endDate':S},{'startDate':'2026-09-01T00:00:00Z','endDate':'2026-09-30T23:59:59Z'},query={'startDate':'$startDate','endDate':'$endDate'},auth='header:Authorization',caps='social inspect')
cli('wordpress.posts','wordpress','List WordPress posts','wp',['post','list','--format=json'],out='json',caps='publish inspect',perms=C)
cli('wordpress.draft','wordpress','Create WordPress draft from local content','wp',['post','create',file('content'),'--post_status=draft','--post_title='+ '$TITLE','--porcelain'],{'content':FILE,'title':S},{'content':'post.md','title':'Product update'},caps='publish',perms=W+C)
# Replace flag=value interpolation with separate option/value tokens, supported by WP-CLI.
rows[-1]['command']['argv']=['post','create',file('content'),'--post_status=draft','--post_title',arg('title'),'--porcelain']
api('ghost.posts','ghost','List Ghost posts',None,'/ghost/api/admin/posts/',auth='ghost',query={'limit':20},caps='publish inspect')
api('ghost.draft','ghost','Create a Ghost draft',None,'/ghost/api/admin/posts/',{'title':S,'html':S},{'title':'Launch','html':'<p>New product</p>'},auth='ghost',method='POST',query={'source':'html'},body={'posts':[{'title':'$title','html':'$html','status':'draft'}]},perms=W,caps='publish')
api('stripe.products','stripe','List Stripe products','https://api.stripe.com','/v1/products',query={'limit':20},caps='payments inspect')
api('stripe.checkout_test','stripe','Create a Stripe test checkout session','https://api.stripe.com','/v1/checkout/sessions',{'price_id':ID,'success_url':URL,'cancel_url':URL},{'price_id':'price_test','success_url':'https://example.com/ok','cancel_url':'https://example.com/cancel'},method='POST',body={'mode':'payment','line_items[0][price]':'$price_id','line_items[0][quantity]':1,'success_url':'$success_url','cancel_url':'$cancel_url'},form=True,perms=W,caps='payments',idempotency_header='Idempotency-Key',test_key_only=True)
cli('stripe.events','stripe','List Stripe events in CLI','stripe',['events','list','--limit','10'],caps='payments inspect',out='json')
cli('shopify.theme_list','shopify_cli','List Shopify themes','shopify',['theme','list','--store',arg('store'),'--json'],{'store':{'type':'string','pattern':r'^[a-z0-9-]+\.myshopify\.com$'}},{'store':'example.myshopify.com'},caps='commerce inspect',out='json')
api('shopify.products','shopify_admin','Read Shopify product records',None,'/admin/api/2026-07/graphql.json',auth='header:X-Shopify-Access-Token',method='POST',body={'query':'query { products(first: 20) { nodes { id title status } pageInfo { hasNextPage endCursor } } }'},host_suffix='.myshopify.com',caps='commerce inspect')
api('shopify.product_draft','shopify_admin','Create a Shopify product draft',None,'/admin/api/2026-07/graphql.json',{'title':S},{'title':'Sample product'},auth='header:X-Shopify-Access-Token',method='POST',body={'query':'mutation($product: ProductCreateInput!) { productCreate(product: $product) { product { id title status } userErrors { field message } } }','variables':{'product':{'title':'$title','status':'DRAFT'}}},host_suffix='.myshopify.com',perms=W,caps='commerce')
api('printful.products','printful','Read Printful product catalog','https://api.printful.com','/products',caps='commerce search')
api('printful.order_draft','printful','Create an unconfirmed Printful order','https://api.printful.com','/orders',{'recipient':OBJ,'items':{'type':'array','items':OBJ,'minItems':1,'maxItems':20}},{'recipient':{'name':'Test Recipient','address1':'Example street','city':'Test','country_code':'US','zip':'10001'},'items':[{'sync_variant_id':123,'quantity':1}]},method='POST',query={'confirm':'false'},body={'recipient':'$recipient','items':'$items'},perms=W,caps='commerce fulfillment')
api('resend.send','resend','Send an explicitly approved email','https://api.resend.com','/emails',{'from':S,'to':{'type':'array','items':S,'minItems':1,'maxItems':20},'subject':S,'text':S},{'from':'team@example.com','to':['user@example.com'],'subject':'Delivery','text':'Approved message'},method='POST',body={k:'$'+k for k in ['from','to','subject','text']},perms=W,paid=True,caps='email',idempotency_header='Idempotency-Key')
api('hubspot.contacts','hubspot','Read one page of HubSpot contacts','https://api.hubapi.com','/crm/v3/objects/contacts',query={'limit':20,'properties':'email,firstname,lastname'},caps='crm search')
api('slack.history','slack','Read authorized channel history','https://slack.com','/api/conversations.history',{'channel':ID},{'channel':'C123'},query={'channel':'$channel','limit':20},caps='office search')
api('slack.send','slack','Send an approved Slack message','https://slack.com','/api/chat.postMessage',{'channel':ID,'text':S},{'channel':'C123','text':'Build ready for review'},method='POST',body={'channel':'$channel','text':'$text'},perms=W,caps='notify')
api('telegram.me','telegram','Inspect the configured Telegram bot','https://api.telegram.org','/bot__TOKEN__/getMe',auth='telegram',caps='notify inspect')
api('telegram.send','telegram','Send an approved message to a chat','https://api.telegram.org','/bot__TOKEN__/sendMessage',{'chat_id':S,'text':S},{'chat_id':'12345','text':'Task completed'},method='POST',body={'chat_id':'$chat_id','text':'$text'},auth='telegram',perms=W,caps='notify')
api('posthog.query','posthog','Run a project analytics query',None,'/api/projects/{project_id}/query/',{'project_id':ID,'query':OBJ},{'project_id':'123','query':{'kind':'HogQLQuery','query':'select event, count() from events group by event limit 10'}},method='POST',body={'query':'$query'},caps='analytics',paid=True)
api('sentry.issues','sentry','Read Sentry project issues','https://sentry.io','/api/0/projects/{organization}/{project}/issues/',{'organization':ID,'project':ID},{'organization':'my-org','project':'web'},query={'query':'is:unresolved'},caps='debug analytics')
api('search_console.sites','search_console','List authorized Search Console sites','https://www.googleapis.com','/webmasters/v3/sites',credential='google_oauth',caps='analytics inspect')
api('youtube.analytics','youtube_analytics','Read authorized channel analytics','https://youtubeanalytics.googleapis.com','/v2/reports',{'start_date':S,'end_date':S},{'start_date':'2026-09-01','end_date':'2026-09-28'},query={'ids':'channel==MINE','startDate':'$start_date','endDate':'$end_date','metrics':'views,estimatedMinutesWatched','dimensions':'day'},credential='google_oauth',caps='analytics')
api('n8n.workflows','n8n','Read configured n8n workflow page',None,'/api/v1/workflows',auth='header:X-N8N-API-KEY',query={'limit':20},caps='automation inspect')
api('n8n.activate','n8n','Activate an existing n8n workflow',None,'/api/v1/workflows/{workflow_id}/activate',{'workflow_id':ID},{'workflow_id':'123'},method='POST',body={},auth='header:X-N8N-API-KEY',perms=P,paid=True,caps='automation')
# Explicit handoffs; no desktop mouse clicks, hiring, purchases or OAuth secretly performed.
for provider,title,url,kind,notes in [
 ('marvelous_designer','Marvelous Designer garment workflow','https://developer.marvelousdesigner.com/','desktop','Use the installed licensed application and its version-matched Python API. Save the editable project and export assets. Do not treat a 3D garment as a tested physical pattern.'),
 ('clo','CLO garment and BOM workflow','https://developer.clo3d.com/','desktop','Use the installed licensed CLO application. Return project, export and BOM; physical fitting remains a separate acceptance task.'),
 ('freecad','FreeCAD parametric engineering handoff','https://www.freecad.org/','desktop','Use the installed application/Python console. Preserve FCStd and exports; manufacturability requires separate review.'),
 ('photopea','Photopea layered source editing','https://www.photopea.com/','desktop','Use the host browser and scripting API with a reviewed script. Return layered source and flattened exports.'),
 ('upwork','Upwork quotation and expert handoff','https://www.upwork.com/','human','Prepare brief and candidates. Do not hire or pay without separate approval. API onboarding and site access are not assumed.'),
 ('fiverr','Fiverr expert handoff','https://www.fiverr.com/','human','Prepare deliverables, budget and acceptance criteria. Await selected provider and explicit purchase approval.'),
 ('freelancer','Freelancer expert handoff','https://www.freelancer.com/','human','Compare quotations. Hiring, milestones, payment and final acceptance are separate approvals.'),
 ('tally','Tally survey and webhook setup','https://tally.so/','browser','Create or open a survey in host browser. Configure webhook at a user-controlled endpoint. No public inbound server is started by ATM.'),
 ('google_trends','Google Trends browser research','https://trends.google.com/trends/','browser','Read trend data in host browser. API alpha requires separate approval; do not invent access.'),
 ('tiktok_posting','TikTok publishing approval','https://www.tiktok.com/','browser','Use an approved app/account. Do not assume public posting permission or bypass unaudited-client visibility limits.'),
 ('google_ads','Google Ads review and reporting handoff','https://ads.google.com/','browser','Review reports or prepare drafts. Do not activate campaigns or change spend without campaign-specific approval.')]:
 row=add(provider+'.handoff',provider,title,'handoff '+('design' if kind=='desktop' else 'outsourcing' if kind=='human' else 'research'),{'task':S},{'task':'Prepare a reviewed deliverable'},kind,url=url,instructions=[notes])
 row['implementation']='handoff';row['verification']='handoff_contract_only';row['extensions']=['.json','.md','.png','.glb','.mp4','.txt']
 if kind=='browser':row['paid']=False
# MCP client entry pairs; actual server tool names are discovered, never invented.
for p,caps in [('figma','design'),('notion','office planning'),('linear','planning'),('playwright','browser debug'),('chrome_devtools','debug browser'),('posthog','analytics'),('sentry','debug analytics')]:
 for action in ['tools','batch']:
  props={} if action=='tools' else {'calls':{'type':'array','minItems':1,'maxItems':12,'items':{'type':'object','required':['name','arguments'],'additionalProperties':False,'properties':{'name':ID,'arguments':OBJ}}}}
  row=add(p+'.mcp_'+action,p,p+' MCP '+action,caps,props,{} if action=='tools' else {'calls':[{'name':'use-discovered-tool-name','arguments':{}}]},'mcp',server=p,mcp_operation=action)
  row['implementation']='bridge';row['verification']='generic_mcp_protocol_not_vendor_live'
  if action=='batch':row['permissions']=W+C;row['paid']=True
# Extra vault credentials for CLI-only setups are advertised without becoming executable actions.
for row in rows:
 row.setdefault('notes','Finite action only; pagination, OAuth renewal and vendor-wide feature coverage are not implied.')
# Persist deterministic registry.
assert len({r['id'] for r in rows})==len(rows)
(DATA/'catalog-v02.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print('New catalog actions:',len(rows))
