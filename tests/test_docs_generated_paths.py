"""Docs cite generated/ only for tracked bundles or explicitly marked local build outputs.

Rule: each repo-root `generated/...` or `./generated/...` path (literal part up to `{`, `<`,
backtick, space or CJK text) must be a tracked file or a directory of tracked files, or its
paragraph must say 本机构建输出. Blank lines, headings, top-level list items and table rows
start a new paragraph, so one marker does not cover a whole list or section. A document
with such local citations must also link the rebuild recipe. Tracked files come from the git
index in a checkout; a clean export (no git top-level here) has exactly the tracked files on disk.
"""
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
CITE=re.compile(r'(?<![A-Za-z0-9_./-])(?:\./)?(generated/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)')
BLOCK=re.compile(r'(?:#|[-*+] |\d+\. |\|)')
LOCAL='本机构建输出'
RECIPE='从源码重建并安装27项'
RUNTIME='docs/XYQ_MEDIA_RUNTIME_CONTRACT.md'
SKIP={'.git','generated','node_modules','build','.atm','.venv','venv'}

def repo_files():
    """Tracked files: the git index in a checkout, else the files of a clean export on disk."""
    try:
        top=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=ROOT,capture_output=True,text=True)
        if not top.returncode and Path(top.stdout.strip()).resolve()==ROOT:
            files=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,text=True,check=True)
            return {f for f in files.stdout.split('\0') if f}
    except (FileNotFoundError,subprocess.CalledProcessError):
        pass
    assert not (ROOT/'.git').exists(),'a git checkout must list its index'
    return {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and
            (not SKIP.intersection(p.relative_to(ROOT).parts) or p.relative_to(ROOT).parts[0]=='generated')}

def documents(files):
    return [ROOT/f for f in sorted(files) if f.endswith('.md') and not f.startswith(('generated/','tests/fixtures/'))]

def paragraphs(text):
    out,gap=[],True
    for n,line in enumerate(text.splitlines(),1):
        if not line.strip():gap=True;continue
        if gap or BLOCK.match(line):out.append([n,line])
        else:out[-1][1]+='\n'+line
        gap=line.startswith('#')
    return out

def citations(para):
    return [(para.count('\n',0,m.start()),m.group(1).rstrip('.')) for m in CITE.finditer(para)]

def tracked(files):
    names={PurePosixPath(f) for f in files if f.startswith('generated/')}
    return {str(p) for f in names for p in (f,*f.parents)}

def links_recipe(doc,text):
    target=('' if doc==ROOT/RUNTIME else '(?:'+re.escape(Path(RUNTIME).name)+'|'+re.escape(RUNTIME)+')')
    return re.search(r'\]\('+target+'#'+RECIPE+r'\)',text) is not None

def test_paragraph_split_and_citation_literal_prefix():
    text='a `generated/x/{a,b}/`\nb 本机构建输出\n\n- generated/y/<op>/\n- 目录generated/z/。src/generated/q\n## h\nsee generated/w.\n\nrun ./generated/v/tool.py'
    assert [(n,citations(t)) for n,t in paragraphs(text)]==[(1,[(0,'generated/x')]),(4,[(0,'generated/y')]),(5,[(0,'generated/z')]),(6,[]),(7,[(0,'generated/w')]),(9,[(0,'generated/v/tool.py')])]
    runtime=ROOT/RUNTIME;other=ROOT/'docs/XYQ_X.md'
    assert links_recipe(runtime,'[r](#'+RECIPE+')') and not links_recipe(other,'[r](#'+RECIPE+')')
    assert links_recipe(other,'[r](XYQ_MEDIA_RUNTIME_CONTRACT.md#'+RECIPE+')') and not links_recipe(other,'see #'+RECIPE)
    assert LOCAL in paragraphs(text)[0][1]

def test_generated_citations_are_tracked_or_marked_local():
    files=repo_files();index=tracked(files);bad=[];unlinked=[]
    assert {'generated/tripo-studio','generated/tripo-studio-delivery-stage-r4'}<=index
    for doc in documents(files):
        text=doc.read_text(encoding='utf-8');local=False
        for start,para in paragraphs(text):
            for line,cite in citations(para):
                if cite in index:continue
                local=True
                if LOCAL not in para:bad.append(f'{doc.relative_to(ROOT)}:{start+line}: {cite}')
        if local and not links_recipe(doc,text):unlinked.append(str(doc.relative_to(ROOT)))
    assert not bad,'untracked generated/ paths need 本机构建输出 in the same paragraph:\n'+'\n'.join(bad)
    assert not unlinked,'documents citing local generated/ outputs must link the rebuild recipe: '+', '.join(unlinked)
    assert f'## {RECIPE}\n' in (ROOT/RUNTIME).read_text(encoding='utf-8')
