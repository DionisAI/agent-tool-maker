"""Install the built wheel away from source. Reuses available dependencies, no network."""
from pathlib import Path
import json,os,subprocess,sys,time,venv,tempfile,sysconfig
ROOT=Path(__file__).resolve().parents[1];work=Path(tempfile.mkdtemp(prefix='atm-wheel-smoke-'))
envdir=work/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=True).create(envdir)
# Parent is itself a venv; base system-site-packages would omit its dependencies.
shared=Path(sysconfig.get_paths()['purelib'])
local_site=envdir/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))/'site-packages'
(local_site/'reused-dependencies.pth').write_text(str(shared)+'\n')
py=envdir/'bin/python';atm=envdir/'bin/atm';atr=envdir/'bin/atr';wheel=next((ROOT/'dist').glob('*.whl'))
env=dict(os.environ);env.pop('PYTHONPATH',None);env.pop('ATM_HOME',None);env.pop('ATR_HOME',None)
def call(cmd):return subprocess.check_output([str(x) for x in cmd],cwd=work,env=env,stderr=subprocess.STDOUT,timeout=90).decode()
call([py,'-m','pip','install','--no-deps','--ignore-installed',wheel])
mod=call([py,'-c','import agent_tool_maker; print(agent_tool_maker.__file__)']).strip()
assert mod.startswith(str(envdir)) and '/src/' not in mod
base=[atm,'--home',work/'state']
records=[]
def cli(args,expected=None):
    result=json.loads(call(base+args))
    if expected:
        for k,v in expected.items():assert result[k]==v,(k,result)
    records.append({'command':['atm',*map(str,args)],'success':True})
    return result
assert call([atm,'--version']).strip()=='0.2.0'
assert call([atr,'--version']).strip()=='0.2.0'
cli(['init'],{'tools':157});cli(['stats'],{'actions':157});r=cli(['roadmap']);assert len(r['records'])==66
cli(['skill','export','--destination',work/'skills'])
manifest=work/'resize.json';cli(['make','scaffold','my.resize','--from','imagemagick.resize','--out',manifest])
r=cli(['make','validate',manifest]);cli(['make','install',manifest,'--approve',r['sha256']])
cli(['describe','my.resize'])
r=json.loads(call([atm,'demo','--out',work/'fixture-demo']));assert r['live_provider_calls']==0 and r['completed_jobs']==3
report={'wheel':wheel.name,'installed_module':mod,'reused_system_dependencies':True,'dependency_source':str(shared),'fresh_network_dependency_resolution':False,
        'atm_version':'0.2.0','atr_alias_version':'0.2.0','commands':records,'synthetic_media_demo':r,'result':'passed'}
(ROOT/'reports/release-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'result':'passed','module':mod,'commands':len(records)+3}))
