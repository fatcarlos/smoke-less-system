#!/usr/bin/env python3
# 🚬食少支煙系統：賣煙者模組

import time
import uuid
import urllib.parse


def page(handler, h):
    data = h['load_json'](h['SELLERS_FILE'], [])
    csrf = handler.session['csrf']
    edit_id = handler.query.get('edit', [''])[0]
    edit = next((x for x in data if x.get('id') == edit_id), None)
    form_title = '✏️ 修改賣煙者' if edit else '➕ 新增賣煙者'
    action = 'edit' if edit else 'add'
    rating = int(edit.get('rating', 5) or 5) if edit else 5
    rating = max(1, min(5, rating))
    rating_options = ''.join(
        f'<option value="{i}" {"selected" if rating == i else ""}>{"⭐" * i}</option>'
        for i in range(1, 6)
    )
    form = f'''<section class="panel"><h2>{form_title}</h2><form method="post" action="/seller">
<input type="hidden" name="csrf" value="{h['esc'](csrf)}">
<input type="hidden" name="action" value="{action}">
{f'<input type="hidden" name="id" value="{h["esc"](edit.get("id"))}">' if edit else ''}
<div class="formgrid">
<input name="name" placeholder="賣煙者稱呼" value="{h['esc'](edit.get('name') if edit else '')}" required>
<input name="phone" placeholder="電話 / WhatsApp" value="{h['esc'](edit.get('phone') if edit else '')}" required>
<select name="rating" aria-label="評價">{rating_options}</select>
<textarea name="comment" placeholder="評語" rows="3" style="grid-column:1/-1">{h['esc'](edit.get('comment') if edit else '')}</textarea>
</div>
<div class="actions" style="margin-top:12px"><button class="btn gold">💾 儲存</button>{'<a class="btn gray" href="/?page=seller">取消</a>' if edit else ''}</div>
</form></section>'''

    cards = ''
    for x in data:
        digits = ''.join(ch for ch in str(x.get('phone', '')) if ch.isdigit())
        wa = f'https://wa.me/{digits}' if digits else 'https://wa.me/'
        try:
            r = max(1, min(5, int(x.get('rating', 5) or 5)))
        except (ValueError, TypeError):
            r = 5
        stars = '⭐' * r + '☆' * (5 - r)
        cards += f'''<div class="card"><h3>🚬 {h['esc'](x.get('name'))}</h3>
<div class="meta">電話 / WhatsApp：{h['esc'](x.get('phone'))}<br>評價：<span style="font-size:20px">{stars}</span><br>評語：{h['esc'](x.get('comment')) or '—'}</div>
<div class="actions" style="margin-top:12px"><a class="btn green" href="{wa}" target="_blank">💬 WhatsApp</a><a class="btn gold" href="/?page=seller&edit={h['esc'](x.get('id'))}">✏️</a>
<form method="post" action="/seller" onsubmit="return confirm('確定刪除呢位賣煙者？')"><input type="hidden" name="csrf" value="{h['esc'](csrf)}"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="{h['esc'](x.get('id'))}"><button class="btn danger">🗑️</button></form></div></div>'''

    return f'<section class="skullframe"><h1>🚬 賣煙者</h1>{"<div class=\"empty\">🚬 暫時無資料</div>" if not cards else "<div class=\"cards\">" + cards + "</div>"}{form}</section>'


def handle_post(handler, data, h):
    arr = h['load_json'](h['SELLERS_FILE'], [])
    action = str(data.get('action', 'add')).strip()
    rid = str(data.get('id', '')).strip()
    if action == 'delete':
        arr = [x for x in arr if x.get('id') != rid]
    elif action == 'edit':
        obj = next((x for x in arr if x.get('id') == rid), None)
        if obj:
            try:
                rating = max(1, min(5, int(data.get('rating', 5))))
            except (ValueError, TypeError):
                rating = 5
            obj.update({
                'name': str(data.get('name', '')).strip(),
                'phone': str(data.get('phone', '')).strip(),
                'rating': rating,
                'comment': str(data.get('comment', '')).strip(),
            })
    else:
        try:
            rating = max(1, min(5, int(data.get('rating', 5))))
        except (ValueError, TypeError):
            rating = 5
        arr.append({
            'id': uuid.uuid4().hex,
            'name': str(data.get('name', '')).strip(),
            'phone': str(data.get('phone', '')).strip(),
            'rating': rating,
            'comment': str(data.get('comment', '')).strip(),
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        })
    h['save_json'](h['SELLERS_FILE'], arr)
    h['redirect'](handler, '/?page=seller')
    return True
