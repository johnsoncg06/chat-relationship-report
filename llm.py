"""問答功能：使用者自帶 Anthropic API Key，對「已算好的統計結果」提問。
隱私：只送統計數字、分數、預測、提醒（已移除證據原文片段，名字換成代號）；**不送聊天原文**。
數字一律來自程式，模型只負責解讀；不確定或資料沒有的，請它直說。"""
import os, json, re, urllib.request, urllib.error, urllib.parse

DEFAULT_MODEL = 'claude-sonnet-5-5'
MODELS = {'anthropic': ['claude-sonnet-5-5', 'claude-haiku-5-5', 'claude-opus-5-5'],
          'gemini': ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash-lite']}   # Gemini 型號更新快：介面也允許自行輸入
DEFAULT = {'anthropic': 'claude-sonnet-5-5', 'gemini': 'gemini-2.5-flash'}
LABEL = {'anthropic': 'Anthropic（Claude）', 'gemini': 'Google（Gemini）'}
FILES = ('stats.json', 'score.json', 'forecast.json', 'alerts.json', 'monthly.json')
SYSTEM = ('你是「CRR」聊天關係分析的解讀助手。使用者會問關於他們聊天紀錄分析結果的問題。\n'
          '規則：1) 只根據下方「分析結果 JSON」回答，數字必須與 JSON 一致，不可自己推算或編造；'
          '2) JSON 沒有的資訊（例如對話內容、對方想法）要明說「資料裡看不到」；'
          '3) 這是行為統計的推論，不是診斷，也不能判斷對方的真實感情；信心為低或資料量少時要提醒；'
          '4) 啟發式、未驗證的部分（權重、門檻）要標示「未驗證」；5) 用繁體中文，簡潔、具體，建議要可執行。')


def api_base():
    return (os.environ.get('CHATREL_API_BASE') or 'https://api.anthropic.com').rstrip('/')


def gemini_base():
    return (os.environ.get('CHATREL_GEMINI_BASE') or 'https://generativelanguage.googleapis.com').rstrip('/')


def detect(key):
    """由 Key 開頭判斷是哪一家；認不出來回傳 None。"""
    if re.match(r'^sk-[\w-]{20,}$', key or ''): return 'anthropic'
    if re.match(r'^AIza[\w-]{30,}$', key or ''): return 'gemini'
    return None


def _strip(o):
    if isinstance(o, dict): return {k: _strip(v) for k, v in o.items() if k not in ('evidence_text', 'quotes', 'examples')}
    if isinstance(o, list): return [_strip(v) for v in o]
    return o


def build_context(out_dir):
    """讀 pipeline 輸出的 JSON，移除證據原文、把名字換成代號，回傳 (json 字串, 名字對照)。"""
    ctx = {}
    for fn in FILES:
        p = os.path.join(out_dir, fn)
        if os.path.isfile(p):
            try: ctx[fn[:-5]] = _strip(json.load(open(p, encoding='utf-8')))
            except Exception: pass
    if 'stats' not in ctx or 'score' not in ctx: return None
    ctx['stats'].pop('evidence', None); ctx['score'].pop('evidence', None)
    me = ctx['stats'].get('me'); people = list((ctx['stats'].get('people') or {}).keys())
    mp = {}
    for n in people:
        mp[n] = '我' if n == me else ('對方' if len(people) == 2 else f'P{len(mp) + 1}')
    s = json.dumps(ctx, ensure_ascii=False, separators=(',', ':'))
    for n in sorted(mp, key=len, reverse=True):
        if len(n) >= 2: s = s.replace(n, mp[n])
    return s, mp


def _history(history, question):
    msgs = []
    for h in (history or [])[-8:]:
        if h.get('role') in ('user', 'assistant') and str(h.get('content', '')).strip(): msgs.append({'role': h['role'], 'content': str(h['content'])[:4000]})
    msgs.append({'role': 'user', 'content': question[:2000]})
    while msgs and msgs[0]['role'] != 'user': msgs.pop(0)
    return msgs


def _post(url, headers, body, timeout, errs):
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='POST', headers=dict(headers, **{'content-type': 'application/json'}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read().decode('utf-8')).get('error', {}).get('message', '')
        except Exception: msg = ''
        raise RuntimeError(f'API 錯誤 {e.code}：{errs.get(e.code) or msg[:150]}')
    except urllib.error.URLError as e:
        raise RuntimeError('連不到 API（請檢查網路）：' + str(e.reason)[:100])


def ask(provider, key, model, ctx_json, question, history=None, timeout=90):
    msgs = _history(history, question)
    if provider == 'gemini':
        body = {'systemInstruction': {'parts': [{'text': SYSTEM + '\n\n分析結果 JSON：\n' + ctx_json}]},
                'contents': [{'role': 'user' if m['role'] == 'user' else 'model', 'parts': [{'text': m['content']}]} for m in msgs],
                'generationConfig': {'maxOutputTokens': 2048}}
        d = _post(f"{gemini_base()}/v1beta/models/{urllib.parse.quote(model or DEFAULT['gemini'], safe='-._')}:generateContent", {'x-goog-api-key': key}, body, timeout,
                  {400: '請求被拒（Key 無效或型號不對）', 403: '這把 Key 沒有權限或未啟用', 404: '找不到這個模型，請換一個', 429: '請求太頻繁或額度用完'})
        cands = d.get('candidates') or []
        if not cands: raise RuntimeError('Gemini 沒有回覆（可能被安全機制擋下），請換個問法')
        txt = ''.join(p.get('text', '') for p in (cands[0].get('content') or {}).get('parts', [])).strip()
        if not txt: raise RuntimeError('Gemini 回覆是空的，請換個問法或換型號')
        u = d.get('usageMetadata') or {}
        return txt, {'input_tokens': u.get('promptTokenCount'), 'output_tokens': u.get('candidatesTokenCount')}
    body = {'model': model or DEFAULT['anthropic'], 'max_tokens': 1200,
            'system': [{'type': 'text', 'text': SYSTEM}, {'type': 'text', 'text': '分析結果 JSON：\n' + ctx_json, 'cache_control': {'type': 'ephemeral'}}],
            'messages': msgs}
    d = _post(api_base() + '/v1/messages', {'x-api-key': key, 'anthropic-version': '2023-06-01'}, body, timeout,
              {401: 'API Key 不正確或已失效', 403: '這把 Key 沒有權限', 404: '找不到這個模型，請換一個', 429: '請求太頻繁或額度用完', 529: '服務忙碌，稍後再試'})
    return ''.join(b.get('text', '') for b in d.get('content', []) if b.get('type') == 'text').strip(), d.get('usage', {})


def mask(key):
    return (key[:7] + '…' + key[-4:]) if key and len(key) > 14 else ('已設定' if key else '')
