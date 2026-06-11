#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from urllib import request, error
DB=Path('C:/Users/Davi/AppData/Local/Temp/freellmapi/server/data/freeapi.db')
BASE='http://127.0.0.1:3001/v1'
OUT=Path('C:/Users/Davi/Desktop/Projects/L2-ATLAS-PROJECT/docs/research/FREELLMAPI_OPENCODE_KILO_BENCHMARK_2026-06-07.json')
MODELS=[
 'deepseek-v4-flash-free','minimax-m3-free','nemotron-3-ultra-free','big-pickle','nemotron-3-super-free','mimo-v2.5-free',
 'poolside/laguna-m.1:free','poolside/laguna-xs.2:free','nvidia/nemotron-3-super-120b-a12b:free','stepfun/step-3.7-flash:free'
]
TESTS=[
 ('exact','Reply exactly and only: ZEN_KILO_OK',lambda s:s.strip()=='ZEN_KILO_OK',32),
 ('reason','A task starts at 09:15 and takes 2h 35m. Reply only HH:MM final time.',lambda s:'11:50' in s,48),
 ('code','Return only JavaScript code for function twice(x) that returns x*2. No markdown.',lambda s:'function twice' in s and 'return' in s and '```' not in s,96),
]
def key():
 c=sqlite3.connect(str(DB)); return c.execute("select value from settings where key='unified_api_key'").fetchone()[0]
def call(k,m,p,mt):
 data=json.dumps({'model':m,'messages':[{'role':'user','content':p}],'temperature':0,'max_tokens':mt}).encode()
 req=request.Request(BASE+'/chat/completions',data=data,headers={'Authorization':'Bearer '+k,'Content-Type':'application/json'},method='POST')
 t=time.perf_counter()
 try:
  with request.urlopen(req,timeout=70) as r:
   j=json.loads(r.read().decode())
   content=(j.get('choices') or [{}])[0].get('message',{}).get('content','') or ''
   return {'ok':True,'status':r.status,'latency_ms':round((time.perf_counter()-t)*1000),'content':content.strip(),'routed_via':j.get('_routed_via'),'usage':j.get('usage')}
 except error.HTTPError as e:
  return {'ok':False,'status':e.code,'latency_ms':round((time.perf_counter()-t)*1000),'error':e.read().decode(errors='replace')[:800]}
 except Exception as e:
  return {'ok':False,'status':None,'latency_ms':round((time.perf_counter()-t)*1000),'error':repr(e)}
def main():
 k=key(); rows=[]
 for m in MODELS:
  print('TEST',m,flush=True); tests=[]
  for name,prompt,check,mt in TESTS:
   r=call(k,m,prompt,mt); r['test']=name; r['passed']=bool(r.get('ok') and check(r.get('content','')))
   route=r.get('routed_via') or {}
   requested_family = 'opencode' if m in MODELS[:6] else 'kilo'
   r['routed_requested_family']=route.get('platform')==requested_family
   print(json.dumps({'model':m,'test':name,'ok':r.get('ok'),'passed':r['passed'],'ms':r.get('latency_ms'),'route':route,'same_family':r['routed_requested_family'],'content':(r.get('content') or r.get('error') or '')[:160]},ensure_ascii=False),flush=True)
   tests.append(r); time.sleep(.5)
  ok=sum(t.get('ok') for t in tests); passed=sum(t.get('passed') for t in tests); same=sum(t.get('routed_requested_family') for t in tests); lat=[t['latency_ms'] for t in tests if t.get('ok')]
  avg=round(sum(lat)/len(lat)) if lat else None
  score=passed*1000+ok*100+same*50-(avg or 99999)/100
  rows.append({'model':m,'intended_platform':'opencode' if m in MODELS[:6] else 'kilo','tests':tests,'summary':{'ok':ok,'passed':passed,'same_family':same,'avg_latency_ms':avg,'score':score}})
 rows.sort(key=lambda x:x['summary']['score'], reverse=True)
 OUT.write_text(json.dumps({'generated_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'ranked':rows},indent=2,ensure_ascii=False),encoding='utf-8')
 print('\nRANK')
 for i,r in enumerate(rows,1): print(i,r['model'],r['intended_platform'],r['summary'])
 print('Saved:',OUT)
if __name__=='__main__': main()
