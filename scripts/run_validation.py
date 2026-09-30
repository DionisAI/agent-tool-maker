from pathlib import Path
import os,sys,subprocess,json,time
root=Path(__file__).resolve().parents[1]
report=root/'reports';report.mkdir(exist_ok=True)
start=time.time()
cmd=[sys.executable,'-m','pytest','-q','--cov=agent_tool_maker','--cov-report=term-missing','--cov-report=xml:reports/coverage.xml','--junitxml=reports/junit.xml','--json-report','--json-report-file=reports/pytest.json','--durations=10']
with (report/'test-output.txt').open('w') as out:
 result=subprocess.run(cmd,cwd=root,stdout=out,stderr=subprocess.STDOUT)
(report/'test-exit-code.txt').write_text(str(result.returncode))
(report/'validation-run.json').write_text(json.dumps({'command':cmd,'exit_code':result.returncode,'wall_seconds':time.time()-start},indent=2))
