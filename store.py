"""歷史紀錄：把每次分析的「統計結果」存到使用者指定的資料夾，並提供前後比對與預測回測。
隱私：只存統計數字、分數、預測與圖表，**不存聊天原文**（連「證據原文片段」也會移除），也不存逐則明細。"""
import os, sys, json, shutil, glob, math, datetime as dt, subprocess

APP = 'ChatRelationshipReport'
SCEN = ['疏遠／淡出', '普通朋友', '摯友（兄弟／姊妹／閨蜜）', '曖昧／交往初期', '情侶／伴侶']


def config_path():
    home = os.environ.get('CHATREL_HOME')
    if home: return os.path.join(home, 'config.json')
    if sys.platform.startswith('win'): base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin': base = os.path.expanduser('~/Library/Application Support')
    else: base = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    return os.path.join(base, APP, 'config.json')


def default_folder():
    home = os.environ.get('CHATREL_HOME')
    if home: return os.path.join(home, 'data')
    docs = os.path.join(os.path.expanduser('~'), 'Documents')
    return os.path.join(docs if os.path.isdir(docs) else os.path.expanduser('~'), APP)


def load_config():
    try: return json.load(open(config_path(), encoding='utf-8'))
    except Exception: return {}


def save_config(c):
    p = config_path(); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(c, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def runs_dir(folder=None):
    folder = folder or load_config().get('folder')
    return os.path.join(folder, 'runs') if folder else None


def set_folder(path):
    path = os.path.abspath(os.path.expanduser(path.strip()))
    os.makedirs(os.path.join(path, 'runs'), exist_ok=True)
    t = os.path.join(path, '.write_test')
    with open(t, 'w') as fh: fh.write('ok')
    os.remove(t)
    c = load_config(); c['folder'] = path; c.setdefault('auto_save', True); save_config(c)
    return path


def pick_folder_dialog():
    """呼叫系統的選資料夾視窗（不依賴 tkinter）。回傳路徑或 None。"""
    try:
        if sys.platform == 'darwin':
            r = subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "選擇要存放歷史紀錄的資料夾")'], capture_output=True, text=True, timeout=600)
            return r.stdout.strip() or None
        if sys.platform.startswith('win'):
            ps = ("Add-Type -AssemblyName System.Windows.Forms; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                  "$f=New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description='選擇要存放歷史紀錄的資料夾'; "
                  "if($f.ShowDialog() -eq 'OK'){Write-Output $f.SelectedPath}")
            r = subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', ps], capture_output=True, timeout=600, creationflags=0x08000000)
            return r.stdout.decode('utf-8', 'replace').strip() or None
        for cmd in (['zenity', '--file-selection', '--directory'], ['kdialog', '--getexistingdirectory']):
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=600); return r.stdout.strip() or None
    except Exception:
        return None
    return None


def pair_key(people):
    return '|'.join(sorted(str(p).strip().lower() for p in people))


def _weekly(csv_path):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
    import _lite as lt
    wd, wn = lt.weekly_counts(lt.load_csv(csv_path)); return {d.isoformat(): n for d, n in zip(wd, wn)}


def save_run(out_dir, result, label='', project=None):
    """out_dir：pipeline 的輸出資料夾。回傳 run id；未設定資料夾時回傳 None。"""
    rd = runs_dir()
    if not rd: return None
    now = dt.datetime.now(); rid = now.strftime('%Y%m%d-%H%M%S')
    dst = os.path.join(rd, rid); os.makedirs(dst, exist_ok=True)
    st = json.load(open(os.path.join(out_dir, 'stats.json'), encoding='utf-8')); sc = json.load(open(os.path.join(out_dir, 'score.json'), encoding='utf-8'))
    st.pop('evidence', None); sc.pop('evidence', None)
    json.dump(st, open(os.path.join(dst, 'stats.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(sc, open(os.path.join(dst, 'score.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    fc = result.get('forecast')
    if fc: json.dump(fc, open(os.path.join(dst, 'forecast.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cdir = os.path.join(out_dir, 'charts')
    if os.path.isdir(cdir): shutil.copytree(cdir, os.path.join(dst, 'charts'), dirs_exist_ok=True)
    csvp = os.path.join(out_dir, 'messages.csv')
    meta = {'id': rid, 'saved_at': now.isoformat(timespec='seconds'), 'label': label, 'actual_status': None, 'people': list(st['people']), 'key': pair_key(st['people']),
            'is_group': bool(st.get('is_group')), 'span': st.get('span'), 'total': st.get('total'), 'closeness': sc['closeness'], 'romantic': sc['romantic_signal'],
            'band': sc['band'], 'profile': sc.get('profile', 'base'), 'context': {k: (sc.get('context') or {}).get(k) for k in ('met', 'stage', 'breakup')}, 'trend': sc['trend'], 'confidence': sc['confidence'], 'has_forecast': bool(fc),
            'project': _resolve_project(project, pair_key(st['people'])),
            'weekly': _weekly(csvp) if os.path.isfile(csvp) else {}}
    json.dump(meta, open(os.path.join(dst, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return rid


# ---------------- 對象（專案） ----------------
# 一個「對象」= 一個專案，把同一個人的多次分析放在一起；專案清單存在儲存資料夾的 projects.json。
def _pj_path():
    f = load_config().get('folder'); return os.path.join(f, 'projects.json') if f else None


def _pj_load():
    p = _pj_path()
    try: return json.load(open(p, encoding='utf-8')) if p and os.path.isfile(p) else []
    except Exception: return []


def _pj_save(lst):
    p = _pj_path()
    if not p: raise ValueError('還沒有選儲存資料夾')
    json.dump(lst, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def _resolve_project(project, key):
    """明確指定就用指定的；沒指定時，若已有專案收過同一組參與者的紀錄就自動歸到那個專案，否則不分組。"""
    ids = {x['id'] for x in _pj_load()}
    if project in ids: return project
    if project: return None
    for m in list_runs():
        if m.get('key') == key and m.get('project') in ids: return m['project']
    return None


def create_project(name, color=None):
    name = (name or '').strip()[:40]
    if not name: raise ValueError('請輸入對象名稱')
    lst = _pj_load()
    if any(x['name'] == name for x in lst): raise ValueError('已經有同名的對象')
    pid = 'p' + dt.datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]
    lst.append({'id': pid, 'name': name, 'created': dt.datetime.now().isoformat(timespec='seconds')}); _pj_save(lst); return pid


def rename_project(pid, name):
    name = (name or '').strip()[:40]; lst = _pj_load()
    if not name or any(x['name'] == name and x['id'] != pid for x in lst): return False
    for x in lst:
        if x['id'] == pid: x['name'] = name; _pj_save(lst); return True
    return False


def delete_project(pid, delete_runs=False):
    """刪除對象；預設只解除分組，紀錄保留（變成「未分組」）。"""
    lst = _pj_load()
    if not any(x['id'] == pid for x in lst): return False
    _pj_save([x for x in lst if x['id'] != pid])
    for m in list_runs():
        if m.get('project') == pid:
            if delete_runs: delete_run(m['id'])
            else: assign_run(m['id'], None)
    return True


def assign_run(rid, pid):
    m, d = _meta(rid)
    if not m: return False
    if pid and pid not in {x['id'] for x in _pj_load()}: return False
    m['project'] = pid or None
    json.dump(m, open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1); return True


def _digest(rid):
    """從一筆紀錄抽出跨對象比較用的預測摘要（只讀已存的檔案，不重算）。"""
    m, d = _meta(rid)
    try: fc = json.load(open(os.path.join(d, 'forecast.json'), encoding='utf-8'))
    except Exception: fc = None
    wk = m.get('weekly') or {}; out = {'weekly': wk, 'mode': None}
    if not fc: return out
    if fc.get('mode') == 'early':
        e = fc.get('early') or {}; pj = e.get('projection') or {}
        out.update(mode='early', risk=e.get('risk_label'), fade=pj.get('fade_risk_7d'), horizon='未來 1 週', recent=pj.get('recent_7d_msgs_per_day'),
                   next_p50=(pj.get('next_7d_msgs_per_day') or {}).get('p50'), unit='則/日', cool=e.get('cool_signals'), warm=e.get('warm_signals'))
        return out
    sc = fc.get('scenarios') or {}; top = max(sc, key=lambda k: sc[k]['point']) if sc else None
    fm = fc.get('forecast_msgs_per_week') or {}; ds = sorted(wk)
    fut = []
    if ds:
        last = dt.date.fromisoformat(ds[-1])
        for h in range(int(fc.get('horizon_weeks') or 0)):
            v = fm.get(f'+{h + 1}w')
            if v: fut.append({'date': (last + dt.timedelta(weeks=h + 1)).isoformat(), 'p10': v['p10'], 'p50': v['p50'], 'p90': v['p90']})
    out.update(mode='full', fade=fc.get('fade_risk_4wk'), horizon='未來 %s 週' % fc.get('horizon_weeks'), top=top, top_pct=(sc[top]['point'] if top else None),
               scenarios={k: v['point'] for k, v in sc.items()}, future=fut, recent=fc.get('recent_4wk_msgs_per_week'), next_p50=(fut[-1]['p50'] if fut else None), unit='則/週',
               slope=fc.get('trend_slope_pct_per_week'))
    return out


def projects_overview():
    """每個對象：全部紀錄的摘要 + 最新一筆的預測摘要；另附未分組的紀錄。"""
    runs = list_runs(); lst = _pj_load(); ids = {x['id'] for x in lst}; out = []
    for p in lst:
        rs = sorted([r for r in runs if r.get('project') == p['id']], key=lambda r: r['saved_at'])
        item = {'id': p['id'], 'name': p['name'], 'n': len(rs), 'runs': rs}
        if rs:
            last = rs[-1]; item['latest'] = dict(last, **{'digest': _digest(last['id'])})
        out.append(item)
    return {'projects': out, 'unassigned': [r for r in runs if r.get('project') not in ids]}


# ---------------- 個人檔案：從「你這一側」的行為看自己的感情經營 ----------------
# 全部是啟發式、未驗證；只描述聊天裡看得到的行為，不是性格或道德評價。需要每次分析都填「你的名字」才知道哪一側是你。
def _lin(x, bad, good):
    if x is None: return None
    return max(0.0, min(1.0, (x - bad) / (good - bad)))


def _mine(rid):
    m, d = _meta(rid)
    if not m: return None
    try:
        st = json.load(open(os.path.join(d, 'stats.json'), encoding='utf-8')); sc = json.load(open(os.path.join(d, 'score.json'), encoding='utf-8'))
    except Exception: return None
    me = st.get('me'); ppl = list(st.get('people') or {})
    if st.get('is_group') or len(ppl) != 2 or me not in ppl: return None
    ot = next(p for p in ppl if p != me); comp = {}
    lat = st.get('reply_latency_min_median') or {}
    if st.get('reply_latency_reliable', True) and lat.get(me) is not None: comp['回覆及時'] = (_lin(lat[me], 120, 5), 30)
    ini = st.get('initiations') or {}; tot = sum(ini.values())
    if tot >= 10: comp['主動平衡'] = (1 - abs(ini.get(me, 0) / tot - .5) / .5, 20)
    b = (st.get('bids_by_sender') or {}).get(ot) or {}
    if b.get('sent', 0) >= 10: comp['回應對方'] = (b.get('answered_within_30min', 0) / b['sent'], 30)
    al = st.get('avg_len_chars') or {}
    if al.get(ot): comp['表達投入'] = (min(1.0, (al.get(me) or 0) / al[ot]), 20)
    comp = {k: v for k, v in comp.items() if v[0] is not None}
    if len(comp) < 2: return None
    w = sum(v[1] for v in comp.values()); score = round(100 * sum(v[0] * v[1] for v in comp.values()) / w)
    wk = m.get('weekly') or {}; vals = [wk[k] for k in sorted(wk)]
    peak = max((sum(vals[i:i + 4]) / len(vals[i:i + 4]) for i in range(0, max(1, len(vals) - 3))), default=0) if vals else 0
    last4 = sum(vals[-4:]) / len(vals[-4:]) if vals else 0
    span = st.get('span') or [None, None]
    return {'id': rid, 'project': m.get('project') or 'k:' + m.get('key', ''), 'end': str(span[1])[:10], 'start': str(span[0])[:10], 'closeness': sc['closeness'], 'romantic': sc['romantic_signal'],
            'score': score, 'comps': {k: round(100 * v[0]) for k, v in comp.items()}, 'weeks': len(vals), 'last4': round(last4, 1), 'peak4': round(peak, 1),
            'ratio': round(last4 / peak, 2) if peak else None, 'people': ppl, 'saved_at': m['saved_at']}


def personal_profile():
    runs = list_runs(); names = {x['id']: x['name'] for x in _pj_load()}
    mine = [r for r in (_mine(m['id']) for m in runs) if r]; skipped = len(runs) - len(mine)
    for r in mine: r['name'] = names.get(r['project']) or ' × '.join(r['people'])
    mine.sort(key=lambda r: (r['end'], r['saved_at']))
    out = {'n_runs': len(runs), 'n_used': len(mine), 'skipped': skipped, 'runs': mine}
    if not mine: out['archetype'] = None; return out
    # 整體經營分：每個時間點，取各對象「到那天為止最新一筆」的平均（避免某對象紀錄多就被放大）
    latest = {}; overall = []
    for r in mine:
        latest[r['project']] = r['score']; overall.append({'date': r['end'], 'score': round(sum(latest.values()) / len(latest), 1), 'n': len(latest)})
    out['overall'] = overall
    if len(overall) >= 3:
        xs = [dt.date.fromisoformat(o['date']).toordinal() for o in overall]; ys = [o['score'] for o in overall]; mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        den = sum((x - mx) ** 2 for x in xs)
        sl = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den * 30 if den else 0
        out['slope_per_30d'] = round(sl, 2); out['slope_label'] = '進步中' if sl >= 2 else '退步中' if sl <= -2 else '大致持平'
    byp = {}
    for r in mine: byp.setdefault(r['project'], []).append(r)
    prog = []
    for pid, rs in byp.items():
        a, b = rs[0], rs[-1]; days = (dt.date.fromisoformat(b['end']) - dt.date.fromisoformat(a['end'])).days if len(rs) > 1 else 0
        prog.append({'project': pid, 'name': b['name'], 'n': len(rs), 'days': days, 'score_first': a['score'], 'score_last': b['score'], 'closeness_first': a['closeness'], 'closeness_last': b['closeness'], 'last': b})
    out['progress'] = prog
    lastend = max(r['end'] for r in mine); cur = [p['last'] for p in prog]
    active = [r for r in cur if r['last4'] >= 15 and r['romantic'] >= 45 and (dt.date.fromisoformat(lastend) - dt.date.fromisoformat(r['end'])).days <= 45]
    old = [r for r in cur if r['weeks'] >= 4 and r['ratio'] is not None]; faded = [r for r in old if r['ratio'] < .3]
    avg = round(sum(r['score'] for r in cur) / len(cur)); ev = [f'你這一側的經營分平均 {avg}（共 {len(cur)} 段關係）', f'目前同時「有在聊且浪漫訊號偏高」的關係：{len(active)} 段']
    if old: ev.append(f'有 4 週以上資料的 {len(old)} 段裡，{len(faded)} 段最近 4 週的量掉到高峰的 3 成以下')
    comps = {}
    for r in cur:
        for k, v in r['comps'].items(): comps.setdefault(k, []).append(v)
    cav = {k: round(sum(v) / len(v)) for k, v in comps.items()}
    if cav: ev.append('各項平均：' + '、'.join(f'{k} {v}' for k, v in cav.items()))
    tot_w = sum(r['weeks'] for r in cur)
    if len(cur) < 2 and tot_w < 4: lab, tag = '資料不足', '至少要有 1 段 4 週以上的聊天，才有辦法描述。'
    elif len(active) >= 3: lab, tag = '多線並進型（海王風，玩笑向）', '同時有好幾段投入度不低的聊天。純看聊天量看不出對方是否知情、是不是真的都在曖昧。'
    elif len(old) >= 2 and len(faded) / len(old) >= .5: lab, tag = '快燃快熄型', '開頭熱度高，之後容易整段淡下去；可以回頭看是不是每次都在同一個階段掉下來。'
    elif len(active) <= 1 and avg >= 60 and (not old or len(faded) / len(old) < .5): lab, tag = '純愛戰士', '目前投入集中在一段關係，回應與經營分數也不低。'
    elif avg < 45: lab, tag = '慢熱觀望型', '回覆、回應或主動度偏保守，不一定是壞事，但容易讓對方抓不到你的興趣。'
    else: lab, tag = '穩定經營型', '沒有特別極端的傾向，回覆與互動大致平衡。'
    out['archetype'] = {'label': lab, 'tagline': tag, 'evidence': ev, 'avg_score': avg, 'active': len(active), 'components': cav}
    return out


def _meta(rid):
    rd = runs_dir()
    if not rd or not rid or os.sep in rid or rid.startswith('.'): return None, None
    p = os.path.join(rd, rid, 'meta.json')
    try: return json.load(open(p, encoding='utf-8')), os.path.join(rd, rid)
    except Exception: return None, None


def list_runs():
    rd = runs_dir(); out = []
    if not rd or not os.path.isdir(rd): return out
    for p in sorted(glob.glob(os.path.join(rd, '*', 'meta.json'))):
        try: m = json.load(open(p, encoding='utf-8'))
        except Exception: continue
        m.pop('weekly', None); out.append(m)
    return out


def load_run(rid):
    m, d = _meta(rid)
    if not m: return None
    ld = lambda n: json.load(open(os.path.join(d, n), encoding='utf-8')) if os.path.isfile(os.path.join(d, n)) else None
    imgs = sorted(os.path.basename(f) for f in glob.glob(os.path.join(d, 'charts', '*.svg')))
    return {'stats': ld('stats.json'), 'score': ld('score.json'), 'forecast': ld('forecast.json'), 'images': imgs, 'notes': ['這是已儲存的歷史紀錄（不含聊天原文與證據片段）。'], 'run_id': rid, 'meta': {k: v for k, v in m.items() if k != 'weekly'}}


def run_image(rid, name):
    m, d = _meta(rid)
    if not m: return None
    p = os.path.join(d, 'charts', os.path.basename(name)); return p if os.path.isfile(p) else None


def update_run(rid, label=None, actual_status=None, clear_status=False):
    m, d = _meta(rid)
    if not m: return False
    if label is not None: m['label'] = str(label)[:80]
    if clear_status: m['actual_status'] = None
    elif actual_status is not None:
        if actual_status not in SCEN: return False
        m['actual_status'] = actual_status
    json.dump(m, open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1); return True


def delete_run(rid):
    m, d = _meta(rid)
    if not m: return False
    shutil.rmtree(d, ignore_errors=True); return True


# ---------------- 前後比對 ----------------
def _g(d, *ks):
    for k in ks:
        if not isinstance(d, dict): return None
        d = d.get(k)
    return d


def compare(a_id, b_id):
    A, B = load_run(a_id), load_run(b_id)
    if not A or not B: return None
    ma, mb = A['meta'], B['meta']
    if ma['saved_at'] > mb['saved_at']: A, B, ma, mb = B, A, mb, ma
    rows = []
    def add(name, va, vb, unit='', better=None, digits=1):
        if va is None or vb is None: return
        try: dlt = round(vb - va, digits)
        except TypeError: dlt = None
        rows.append({'name': name, 'a': va, 'b': vb, 'delta': dlt, 'unit': unit})
    sa, sb, ta, tb = A['score'], B['score'], A['stats'], B['stats']
    add('親密度', sa['closeness'], sb['closeness'], '', digits=0); add('浪漫訊號', sa['romantic_signal'], sb['romantic_signal'], '', digits=0)
    for k in (sa.get('dimensions') or {}):
        add('維度：' + k, (sa.get('dimensions') or {}).get(k), (sb.get('dimensions') or {}).get(k), '', digits=0)
    add('總訊息數', ta.get('total'), tb.get('total'), '則', digits=0)
    ci_a, ci_b = ta.get('closeness_inputs') or {}, tb.get('closeness_inputs') or {}
    add('活躍日比例', ci_a.get('active_day_ratio'), ci_b.get('active_day_ratio'), '', digits=3)
    add('活躍日平均訊息', ci_a.get('msgs_per_active_day'), ci_b.get('msgs_per_active_day'), '則', digits=1)
    add('晚安日占比', ci_a.get('goodnight_day_ratio'), ci_b.get('goodnight_day_ratio'), '', digits=3)
    add('最長沉默', ci_a.get('longest_silence_days'), ci_b.get('longest_silence_days'), '天', digits=0)
    la, lb = ta.get('reply_latency_min_median') or {}, tb.get('reply_latency_min_median') or {}
    for p in la:
        if p in lb: add('回覆中位數：' + p, la[p], lb[p], '分', digits=1)
    notes = []
    if sa['band'] != sb['band']: notes.append(f"關係區間：「{sa['band']}」→「{sb['band']}」")
    if sa['trend'] != sb['trend']: notes.append(f"趨勢：{sa['trend']} → {sb['trend']}")
    if sa['confidence'] != sb['confidence']: notes.append(f"信心：{sa['confidence']} → {sb['confidence']}")
    if ma['key'] != mb['key']: notes.append('注意：兩次紀錄的參與者名字不同，可能不是同一段關係，比較僅供參考。')
    if sa['confidence'] == '低' or sb['confidence'] == '低': notes.append('其中一次信心為「低」，分數差異可能只是資料量或單日爆量造成，不一定代表關係變化。')
    if sa.get('profile', 'base') != sb.get('profile', 'base'):
        # 舊紀錄（沒有 profile 欄位）是用 base 權重算的；兩次權重不同時，分數差有一部分是算法造成的
        ca, cb = (sa.get('closeness_by_profile') or {}), (sb.get('closeness_by_profile') or {})
        notes.append(f"注意：兩次使用不同的權重設定（{sa.get('profile', 'base')} → {sb.get('profile', 'base')}），親密度差異可能含算法差異；同一權重下的比較請看 closeness_by_profile。")
    ca_, cb_ = (ma.get('context') or {}), (mb.get('context') or {})
    if ca_ != cb_ and (any(ca_.values()) or any(cb_.values())):
        notes.append('兩次紀錄標註的對話情境不同（例如見面進度或感情狀態），差異可能來自情境變化，不一定是關係本身。')
    ds = abs((sb['closeness'] - sa['closeness']))
    if ds < 5 and ma['key'] == mb['key']: notes.append('親密度變化在 5 分以內，約在分數本身的不確定範圍內，不要過度解讀。')
    return {'a': ma, 'b': mb, 'rows': rows, 'notes': notes}


# ---------------- 預測回測 ----------------
def _week_end(d): return d + dt.timedelta(days=(6 - d.weekday()))


def backtest():
    """用歷次紀錄檢驗：較早那次的預測，和較晚那次實際發生的每週訊息量相比。"""
    rd = runs_dir()
    if not rd: return {'volume': None, 'scenario': None}
    metas = []
    for p in sorted(glob.glob(os.path.join(rd, '*', 'meta.json'))):
        try:
            m = json.load(open(p, encoding='utf-8')); fp = os.path.join(os.path.dirname(p), 'forecast.json')
            m['_fc'] = json.load(open(fp, encoding='utf-8')) if os.path.isfile(fp) else None; metas.append(m)
        except Exception: pass
    metas.sort(key=lambda m: m['saved_at'])
    pts = []   # 每個「預測週」一筆
    for i, A in enumerate(metas):
        fc = A.get('_fc')
        if not fc or 'forecast_msgs_per_week' not in fc or not A.get('weekly') or A['is_group']: continue   # 早期模式的預測沒有每週量
        weeks = sorted(A['weekly']); last = dt.date.fromisoformat(weeks[-1]); fcw = fc['forecast_msgs_per_week']
        recent = fc.get('recent_4wk_msgs_per_week')
        for B in metas[i + 1:]:
            if B['key'] != A['key'] or not B.get('weekly'): continue
            bspan_end = dt.date.fromisoformat(str((B.get('span') or ['', ''])[1])[:10]) if B.get('span') else None
            for h in range(1, 9):
                wk = (last + dt.timedelta(weeks=h)).isoformat(); f = fcw.get(f'+{h}w')
                if not f or wk not in B['weekly'] or bspan_end is None or dt.date.fromisoformat(wk) > bspan_end: continue   # 只算已完整結束的週
                act = B['weekly'][wk]
                pts.append({'from': A['id'], 'to': B['id'], 'week': wk, 'h': h, 'p10': f['p10'], 'p50': f['p50'], 'p90': f['p90'], 'actual': act, 'naive': recent})
            break   # 每份預測只和「之後第一份同一對象的紀錄」比，避免同一週被重複計算
    vol = None
    if pts:
        n = len(pts); inb = sum(1 for p in pts if p['p10'] <= p['actual'] <= p['p90'])
        mape = sum(abs(p['p50'] - p['actual']) / max(p['actual'], 1) for p in pts) / n
        nv = [p for p in pts if p['naive'] is not None]
        mape_n = sum(abs(p['naive'] - p['actual']) / max(p['actual'], 1) for p in nv) / len(nv) if nv else None
        vol = {'n_weeks': n, 'coverage_pct': round(100 * inb / n, 1), 'nominal_pct': 80, 'mape_pct': round(100 * mape, 1),
               'naive_mape_pct': round(100 * mape_n, 1) if mape_n is not None else None, 'points': pts[-60:],
               'verdict': _verdict(n, inb / n, mape, mape_n)}
    # 情境：需要使用者在「較晚的紀錄」標註實際狀態
    sc = []
    for i, A in enumerate(metas):
        fc = A.get('_fc')
        if not fc or 'scenarios' not in fc: continue
        for B in metas[i + 1:]:
            if B['key'] != A['key'] or not B.get('actual_status'): continue
            gap = (dt.datetime.fromisoformat(B['saved_at']) - dt.datetime.fromisoformat(A['saved_at'])).days
            if gap < 42: continue   # 預測期是 8 週；至少隔 6 週才有比較意義
            pr = fc['scenarios'].get(B['actual_status'], {}).get('point')
            top = max(fc['scenarios'], key=lambda k: fc['scenarios'][k]['point'])
            sc.append({'from': A['id'], 'to': B['id'], 'days': gap, 'predicted_top': top, 'actual': B['actual_status'], 'prob_on_actual': pr, 'hit': top == B['actual_status']}); break
    scen = None
    if sc: scen = {'n': len(sc), 'hit_rate_pct': round(100 * sum(1 for s in sc if s['hit']) / len(sc), 1), 'rows': sc[-30:]}
    return {'volume': vol, 'scenario': scen}


def _verdict(n, cov, mape, mape_n):
    if n < 12: return '樣本還很少（不到 12 個預測週），先不要下結論。'
    t = []
    t.append('80% 區間實際涵蓋率 %.0f%%，' % (100 * cov) + ('接近預期。' if 0.7 <= cov <= 0.9 else '偏低：區間可能太窄，預測比看起來更不確定。' if cov < 0.7 else '偏高：區間可能太寬。'))
    if mape_n is not None: t.append('中位數預測誤差 %.0f%%，' % (100 * mape) + ('優於' if mape < mape_n else '沒有優於') + '「直接沿用近 4 週平均」的簡單做法（%.0f%%）。' % (100 * mape_n))
    return ''.join(t)
