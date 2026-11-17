import time, uuid, urllib.parse


def page(handler, h):
    data = h['load_json'](h['CLIENTS_FILE'], [])
    csrf = handler.session['csrf']
    edit_id = handler.query.get('edit', [''])[0]
    edit = next((x for x in data if x.get('id') == edit_id), None)
    form_title = '✏️ 修改訂煙者' if edit else '➕ 新增訂煙者'
    action = 'edit' if edit else 'add'
    form = f'''<section class="panel"><h2>{form_title}</h2><form method="post" action="/clients"><input type="hidden" name="csrf" value="{h['esc'](csrf)}"><input type="hidden" name="action" value="{action}">{f'<input type="hidden" name="id" value="{h["esc"](edit.get("id"))}">' if edit else ''}<div class="formgrid"><input name="name" placeholder="訂煙者稱呼" value="{h['esc'](edit.get('name') if edit else '')}" required><input name="address" placeholder="送貨地點" value="{h['esc'](edit.get('address') if edit else '')}" required><input name="phone" placeholder="電話 / WhatsApp" value="{h['esc'](edit.get('phone') if edit else '')}" required><textarea name="whatsapp_content" placeholder="WhatsApp 內容" rows="3" style="grid-column:1/-1">{h['esc'](edit.get('whatsapp_content') if edit else '有煙食喇')}</textarea></div><div class="actions" style="margin-top:12px"><button class="btn gold">💾 儲存</button>{'<a class="btn gray" href="/?page=clients">取消</a>' if edit else ''}</div></form></section>'''
    cards = ''
    for x in data:
        digits = ''.join(ch for ch in str(x.get('phone','')) if ch.isdigit())
        wa = f'https://wa.me/{digits}?text={urllib.parse.quote(str(x.get('whatsapp_content') or '有煙食喇'))}' if digits else 'https://wa.me/?text='+urllib.parse.quote(str(x.get('whatsapp_content') or '有煙食喇'))
        cards += f'''<div class="card"><h3>👤 {h['esc'](x.get('name'))}</h3><div class="meta">送貨地點：{h['esc'](x.get('address'))}<br>電話 / WhatsApp：{h['esc'](x.get('phone'))}<br>WhatsApp 內容：{h['esc'](x.get('whatsapp_content') or '有煙食喇')}</div><div class="actions" style="margin-top:12px"><a class="btn green" href="{wa}" target="_blank">💬 WhatsApp</a><a class="btn gold" href="/?page=clients&edit={h['esc'](x.get('id'))}">✏️</a><form method="post" action="/clients" onsubmit="return confirm('確定刪除呢位訂煙者？')"><input type="hidden" name="csrf" value="{h['esc'](csrf)}"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="{h['esc'](x.get('id'))}"><button class="btn danger">🗑️</button></form></div></div>'''
    return f'<section class="skullframe"><h1>👤 訂煙者</h1>{"<div class=\"empty\">👤 暫時無資料</div>" if not cards else "<div class=\"cards\">"+cards+"</div>"}{form}</section>'


def handle_post(handler, data, h):
    arr = h['load_json'](h['CLIENTS_FILE'], [])
    action = str(data.get('action', 'add')).strip()
    rid = str(data.get('id', ''))
    if action == 'delete':
        arr = [x for x in arr if x.get('id') != rid]
    elif action == 'edit':
        obj = next((x for x in arr if x.get('id') == rid), None)
        if obj:
            obj.update({'name': str(data.get('name','')).strip(), 'address': str(data.get('address','')).strip(), 'phone': str(data.get('phone','')).strip(), 'whatsapp_content': str(data.get('whatsapp_content','')).strip() or '有煙食喇'})
    else:
        arr.append({'id': uuid.uuid4().hex, 'name': str(data.get('name','')).strip(), 'address': str(data.get('address','')).strip(), 'phone': str(data.get('phone','')).strip(), 'whatsapp_content': str(data.get('whatsapp_content','')).strip() or '有煙食喇', 'created_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    h['save_json'](h['CLIENTS_FILE'], arr)
    h['redirect'](handler, '/?page=clients')
    return True
