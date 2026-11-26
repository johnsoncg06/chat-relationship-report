"""對話情境：由使用者自己標註（聊天紀錄本身看不出「怎麼認識的、見面了沒、有沒有人剛失戀」）。

設計原則：
- 情境主要用來「改變怎麼解讀」，不是偷偷改分數。唯一改變計算的有兩處（見 apply），都在輸出的 adjustments 裡列明。
- 沒有任何情境的權重是用台灣資料校準的；這裡的提醒都是「可能」「不必解讀為」這類保守說法，等級一律是「未驗證」。
- 只收三個欄位，各自獨立，可組合使用；留空代表不指定。
"""

MET = {   # 認識管道
    'online_blind_date': '線上盲約／配對活動',
    'street': '搭訕',
    'matchmaking': '相親',
    'family': '家人介紹',
    'friend': '朋友介紹',
    'was_friend': '原本就是朋友',
    'new': '剛認識（同學、活動等自然認識）',
}
STAGE = {   # 見面進度
    'not_met_no_sns': '還沒見面，也沒交換其他社群帳號',
    'not_met_sns': '還沒見面，但已交換社群帳號',
    'met': '已經見面',
}
BREAKUP = {   # 感情狀態
    'none': '沒有人剛失戀',
    'one': '有一方剛失戀',
    'both': '兩方都剛失戀',
}

MET_NOTES = {
    'online_blind_date': '活動或配對情境的開頭互動，常被流程帶動（輪流發問、指定話題），先看「結構化對話」警示。分數只反映這段聊天，不代表活動結束後會不會續聊。',
    'street': '搭訕情境中一方先開口是常態，「主動對稱」不計入浪漫訊號。對方是否回應、回覆是否延續話題，比誰先開口更值得看。',
    'matchmaking': '相親情境初期語氣多半禮貌，情感詞少可能只是保持距離，不必解讀為沒興趣；浪漫訊號偏低要保守看待。',
    'family': '經家人介紹時，聊天頻率可能受到介紹人的期待或客套影響，不一定完全出於雙方自己的意願。',
    'friend': '經朋友介紹時，聊天頻率可能受到介紹人的期待或客套影響；同時要考慮共同朋友圈的互動不會出現在這份紀錄裡。',
    'was_friend': '原本就是朋友時，親密度基線本來就高，高分不等於有戀愛成分；比起絕對值，浪漫訊號隨時間的變化更有意義。',
    'new': '剛認識的聊天紀錄通常很短，容易被少數幾天的爆量主導，信心多半偏低。',
}
STAGE_NOTES = {
    'not_met_no_sns': '還沒見面、互動集中在單一管道時，頻率與回覆速度可能被放大；這份紀錄只能反映文字互動。',
    'not_met_sns': '已交換社群帳號，互動可能分散到 IG、通話等其他管道，只看這一份會低估；有 IG 匯出的話，可用「合併兩個平台的名字」一起分析。',
    'met': '已經見面後，線下相處不會出現在聊天紀錄裡，聊天量下降不一定是關係變淡，也可能是改成當面相處。',
}
BREAKUP_NOTES = {
    'one': '有一方剛失戀：研究（英語、Reddit 樣本）發現分手前後數個月語言與情緒表達會明顯改變，第一人稱用字與深夜互動可能反映當事人本身的狀態，不一定是這段新關係。語言類實驗指標在此情境不可靠，信心已下調一級。',
    'both': '兩方都剛失戀：互動可能含有互相安慰的成分，行為量不能直接當成戀愛訊號；語言類實驗指標在此情境不可靠，信心已下調一級。建議拉長觀察期。',
}
FORECAST_CAVEATS = {
    'breakup': '有人剛失戀：近期的行為可能受情緒影響，8 週落點的不確定性更大',
    'met': '已見面：聊天量走向只反映線上互動，線下相處看不到',
    'not_met': '尚未見面：預測只依文字互動，見面後的相處可能完全不同',
}


def normalize(met=None, stage=None, breakup=None):
    """只接受已知選項，未知或空白一律當作不指定。"""
    return {'met': met if met in MET else None, 'stage': stage if stage in STAGE else None,
            'breakup': breakup if breakup in ('one', 'both') else None}


def describe(ctx, is_group=False):
    """回傳要放進評分輸出的 context 區塊；完全沒指定則回傳 None。群組不套用。"""
    if is_group or not any(ctx.values()):
        return None
    notes, adj, fc = [], [], []
    if ctx['met']: notes.append(MET_NOTES[ctx['met']])
    if ctx['stage']:
        notes.append(STAGE_NOTES[ctx['stage']])
        fc.append(FORECAST_CAVEATS['met' if ctx['stage'] == 'met' else 'not_met'])
    if ctx['breakup']:
        notes.append(BREAKUP_NOTES[ctx['breakup']])
        fc.append(FORECAST_CAVEATS['breakup'])
        adj.append('信心下調一級（高→中、中→低）；語言類實驗指標標示為不可靠')
    if ctx['met'] == 'street': adj.append('浪漫訊號不計「主動對稱」（權重 10 → 0，其餘重新正規化）')
    labels = [x for x in (MET.get(ctx['met']), STAGE.get(ctx['stage']), BREAKUP.get(ctx['breakup'])) if x]
    return {'met': ctx['met'], 'stage': ctx['stage'], 'breakup': ctx['breakup'], 'labels': labels, 'notes': notes,
            'adjustments': adj, 'forecast_caveats': fc, 'evidence_level': '未驗證',
            'note': '情境由使用者標註，主要影響解讀提醒；沒有任何情境的權重經台灣資料校準。'}


def lower_confidence(conf, ctx):
    if ctx.get('breakup'): return {'高': '中', '中': '低'}.get(conf, conf)
    return conf


def romantic_weights(base, ctx):
    """搭訕：一方先開口是常態，主動對稱不計入。其餘情境不改權重。"""
    w = dict(base)
    if ctx.get('met') == 'street': w['主動對稱'] = 0
    return w
