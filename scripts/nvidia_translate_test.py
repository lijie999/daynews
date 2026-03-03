#!/usr/bin/env python3
import os
import json
import urllib.request

API_KEY=os.environ.get('NVIDIA_API_KEY')
if not API_KEY:
  raise SystemExit('missing NVIDIA_API_KEY')

url='https://integrate.api.nvidia.com/v1/chat/completions'
body={
  'model': 'meta/llama-3.1-8b-instruct',
  'messages': [
    {'role':'system','content':'Translate to Simplified Chinese, keep tickers/acronyms.'},
    {'role':'user','content':'Nvidia is now cheaper than the S&P 500, according to one key metric.'}
  ],
  'temperature': 0.2,
  'max_tokens': 200,
}
req=urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers={
  'Authorization': f'Bearer {API_KEY}',
  'Content-Type':'application/json',
})
try:
  with urllib.request.urlopen(req, timeout=30) as resp:
    data=resp.read().decode('utf-8')
    obj=json.loads(data)
    print(obj['choices'][0]['message']['content'].strip())
except Exception as e:
  print('ERROR',e)
