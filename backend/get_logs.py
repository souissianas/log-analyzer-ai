import httpx, json
r = httpx.get('http://localhost:8000/logs')
print('Status:', r.status_code)
try:
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))
except Exception:
    print(r.text)
