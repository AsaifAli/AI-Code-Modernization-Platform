from __future__ import annotations
import hashlib, json, os, re, time
from pathlib import Path
from typing import Any

CODE_EXTS={'.py','.js','.jsx','.ts','.tsx','.java','.go','.php','.cs','.rb','.rs','.kt','.swift'}
IGNORED={'.git','.venv','venv','node_modules','vendor','dist','build','target','__pycache__','.migration','.pytest_cache'}
SECRET_PATTERNS=[
 ('private_key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
 ('aws_access_key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
 ('generic_secret_assignment', re.compile(r'(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*["\'][^"\']{12,}["\']')),
]
DANGEROUS_PATTERNS=[
 ('python_shell', re.compile(r'(?m)\b(?:os\.system|subprocess\.(?:run|Popen|call)|eval|exec)\s*\(')),
 ('js_eval', re.compile(r'(?m)\beval\s*\(')),
 ('sql_string', re.compile(r'(?is)(?:select|insert|update|delete)\s+.{0,160}(?:from|into|where)\s+[^\n]*\+\s*[A-Za-z_]')),
]

def _files(root: Path):
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in CODE_EXTS and not any(x in IGNORED for x in p.relative_to(root).parts):
            yield p

def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def security_scan(root: str|Path, persist: bool=True) -> dict[str,Any]:
    root=Path(root).resolve(); findings=[]
    for p in _files(root):
        try: text=p.read_text(encoding='utf-8',errors='ignore')
        except Exception: continue
        rel=str(p.relative_to(root))
        for kind,pat in SECRET_PATTERNS:
            if pat.search(text): findings.append({'severity':'critical','category':'secret','rule':kind,'file':rel})
        for kind,pat in DANGEROUS_PATTERNS:
            if pat.search(text): findings.append({'severity':'high','category':'code-risk','rule':kind,'file':rel})
    critical=sum(x['severity']=='critical' for x in findings); high=sum(x['severity']=='high' for x in findings)
    status='blocked' if critical else ('review' if high else 'passed')
    result={'status':status,'critical':critical,'high':high,'findings':findings[:200],'methodology':'Deterministic pattern scan; findings require review and are not a substitute for SAST/dependency scanners.'}
    if persist:
        out=root/'.migration'; out.mkdir(exist_ok=True)
        (out/'security_review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (out/'security_review.md').write_text('# Security Review\n\n'+f"- Status: {status}\n- Critical: {critical}\n- High: {high}\n\n"+'\n'.join(f"- **{x['severity']}** `{x['rule']}` — `{x['file']}`" for x in findings)+'\n',encoding='utf-8')
    return result

def provenance_manifest(migration_name:str, source: str|Path|None, target: str|Path, quality:dict[str,Any], semantic:dict[str,Any], security:dict[str,Any], persist:bool=True)->dict[str,Any]:
    target=Path(target).resolve(); source=Path(source).resolve() if source else None
    target_files=[]
    for p in _files(target): target_files.append({'path':str(p.relative_to(target)),'sha256':_sha(p)})
    source_hashes=[]
    if source and source.exists():
        for p in _files(source): source_hashes.append({'path':str(p.relative_to(source)),'sha256':_sha(p)})
    manifest={'schema_version':'1.0','migration_name':migration_name,'created_at_epoch':time.time(),'tool_version':os.getenv('MIGRATION_PLATFORM_VERSION','dev'),'model_provider':os.getenv('MODEL_TYPE','unknown'),'model_id':os.getenv('OPENAI_MODEL_ID') or os.getenv('VLLM_CHAT_MODEL_ID') or os.getenv('GEMINI_LITELLM_MODEL','unknown'),'target_file_count':len(target_files),'source_file_count':len(source_hashes),'quality_status':quality.get('status'),'semantic_status':semantic.get('status'),'security_status':security.get('status'),'source_files':source_hashes,'target_files':target_files}
    if persist:
        out=target/'.migration'; out.mkdir(exist_ok=True); (out/'provenance_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

def traceability_matrix(semantic:dict[str,Any], persist_root:str|Path|None=None)->dict[str,Any]:
    matches=semantic.get('contract',{}).get('matched_symbols',[])
    matrix=[]
    for item in matches:
        matrix.append({'source':item.get('source'),'target':item.get('target'),'status':'verified' if item.get('arity_compatible', True) else 'arity_mismatch'})
    for item in semantic.get('contract',{}).get('missing_symbols',[]): matrix.append({'source':item,'target':None,'status':'missing'})
    result={'status':'available','source_symbol_count':semantic.get('contract',{}).get('source_symbols',0),'matched_count':semantic.get('contract',{}).get('matched',0),'unresolved':matrix}
    if persist_root:
        out=Path(persist_root)/'.migration'; out.mkdir(exist_ok=True); (out/'traceability_matrix.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
