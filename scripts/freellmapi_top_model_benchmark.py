#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from urllib import request, error

DB=Path('<USER_HOME>/AppData/Local/Temp/freellmapi/server/data/freeapi.db')
BASE='http://127.0.0.1:3001/v1'
OUT=Path('<USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT/docs/research/FREELLMAPI_TOP_MODEL_BENCHMARK_2026-06-07.json')
MODELS=[
 'llama-3.3-70b-versatile',
 'meta-llama/llama-4-scout-17b-16e-instruct',
 'codestral-latest',
 'mistral-medium-latest',
 '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
 'mistral-large-latest',
 'gemini-2.5-flash-lite',
 'openai/gpt-oss-120b:free',
 'auto',
]
TESTS=[
 ('strict_exact','Reply exactly and only: OK-731',lambda s: s.strip()=='OK-731',32),
 ('json','Return only compact JSON with keys answer and count. answer must be "blue" and count must be 4.',lambda s: _json_check(s),80),
 ('code','Write one Python function only: def add_even(nums): return the sum of even integers in nums. No prose.',lambda s: 'def add_even' in s and 'return' in s and 'sum' in s and 'even' not in s.lower()[:20],120),
]

def _json_check(s):
    try:
        obj=json.loads(s.strip().strip('`'))
        return obj.get('answer')=='blue' and obj.get('count')==4
    except Exception:
        return False

def key():
    c=sqlite3.connect(str(DB)); return c.execute("select value from settings where key='unified_api_key'").fetchone()[0]

def call(k,model,prompt,max_tokens):
    data=json.dumps({'model':model,'messages':[{'role':'user','content':prompt}],'temperature':0,'max_tokens':max_tokens}).encode()
    req=request.Request(BASE+'/chat/completions',data=data,headers={'Authorization':'Bearer '+k,'Content-Type':'application/json'},method='POST')
    t=time.perf_counter()
    try:
        with request.urlopen(req,timeout=60) as r:
            j=json.loads(r.read().decode())
            content=(j.get('choices') or [{}])[0].get('message',{}).get('content','') or ''
            return {'ok':True,'status':r.status,'latency_ms':round((time.perf_counter()-t)*1000),'content':content.strip(),'routed_via':j.get('_routed_via'),'usage':j.get('usage')}
    except error.HTTPError as e:
        return {'ok':False,'status':e.code,'latency_ms':round((time.perf_counter()-t)*1000),'error':e.read().decode(errors='replace')[:500]}
    except Exception as e:
        return {'ok':False,'status':None,'latency_ms':round((time.perf_counter()-t)*1000),'error':repr(e)}

def main():
    k=key(); rows=[]
    for m in MODELS:
        print('TEST',m,flush=True)
        tests=[]
        for name,prompt,check,max_tokens in TESTS:
            r=call(k,m,prompt,max_tokens); r['test']=name; r['passed']=bool(r.get('ok') and check(r.get('content','')))
            print(json.dumps({'model':m,'test':name,'passed':r['passed'],'ok':r.get('ok'),'ms':r.get('latency_ms'),'route':r.get('routed_via'),'content':(r.get('content') or r.get('error') or '')[:120]},ensure_ascii=False),flush=True)
            tests.append(r); time.sleep(.4)
        ok=sum(t.get('ok') for t in tests); passed=sum(t.get('passed') for t in tests); lat=[t['latency_ms'] for t in tests if t.get('ok')]
        avg=round(sum(lat)/len(lat)) if lat else None
        score=passed*1000+ok*100-(avg or 99999)/100
        rows.append({'model':m,'tests':tests,'summary':{'ok':ok,'passed':passed,'avg_latency_ms':avg,'score':score}})
    rows.sort(key=lambda x:x['summary']['score'], reverse=True)
    OUT.write_text(json.dumps({'generated_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'ranked':rows},indent=2,ensure_ascii=False),encoding='utf-8')
    print('\nRANK')
    for i,r in enumerate(rows,1): print(i,r['model'],r['summary'])
    print('Saved:',OUT)
if __name__=='__main__': main()
