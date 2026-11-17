import os, time, uuid


def page(handler, h):
    data = h['load_json'](h['TYPES_FILE'], [])
    csrf = handler.session['csrf']
    edit_id = handler.query.get('edit', [''])[0]
    edit = next((x for x in data if x.get('id') == edit_id), None)
    groups = {}
    for x in data:
        groups.setdefault(x.get('brand', '未分類'), []).append(x)

    cards = ''
    for brand, items in groups.items():
        inner = ''
        for x in items:
            img = f'<img class="thumb" src="/uploads/cigarette/{h["esc"](os.path.basename(x["image"]))}">' if x.get('image') else ''
            inner += f'''<div class="card">{img}<h3>{h['esc'](x.get('name'))}</h3><div class="price">${h['esc'](x.get('price'))}</div><div class="meta">品牌：{h['esc'](x.get('brand'))}<br>代碼：{h['esc'](x.get('code')) or '—'}</div><div class="actions" style="margin-top:12px"><a class="btn gold" href="/?page=types&edit={h['esc'](x.get('id'))}">✏️</a><form method="post" action="/types" onsubmit="return confirm('確定刪除呢款煙？')"><input type="hidden" name="csrf" value="{h['esc'](csrf)}"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="{h['esc'](x.get('id'))}"><button class="btn danger">🗑️</button></form></div></div>'''
        cards += f'<section class="panel"><h2>🚬 {h["esc"](brand)}</h2><div class="cards">{inner}</div></section>'
    if not cards:
        cards = '<div class="empty">🚬 暫時無資料</div>'

    form_title = '✏️ 修改煙款' if edit else '➕ 新增煙款'
    action = 'edit' if edit else 'add'
    edit_hidden = f'<input type="hidden" name="id" value="{h["esc"](edit.get("id"))}">' if edit else ''
    current_image = os.path.basename(edit.get('image', '')) if edit and edit.get('image') else ''
    cigarette_dir = h.get('CIGARETTE_UPLOAD_DIR', h['UPLOAD_DIR'])
    cigarette_files = sorted(x.name for x in cigarette_dir.iterdir() if x.is_file() and x.suffix.lower() in {'.jpg','.jpeg','.png','.gif','.webp','.bmp'})
    if cigarette_files:
        image_options = '<option value="">Choose file</option>' + ''.join(f'<option value="{h["esc"](n)}" {"selected" if n==current_image else ""}>{h["esc"](n)}</option>' for n in cigarette_files)
        existing_picker = f'<select name="existing_image">{image_options}</select>'
    else:
        existing_picker = '<div class="smallmuted">Choose file</div>'
    image_note = '<div class="smallmuted">如不重新上載相片，會保留原有相片。</div>' if edit else ''
    file_input = f"""<div><label class="small">已有香煙相片</label>{existing_picker}<label class="small" style="margin-top:10px">上載新相片</label><div class="filepicker"><input id="cig_image" type="file" name="image" accept="image/*" onchange="document.getElementById('cigFileName').textContent=this.files.length?this.files[0].name:'Choose file'"><label for="cig_image" class="btn gray filepicklabel"><span id="cigFileName">Choose file</span></label></div></div>"""
    cancel = '<a class="btn gray" href="/?page=types">取消</a>' if edit else ''
    form = f'''<section class="panel"><h2>{form_title}</h2><form method="post" action="/types" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{h['esc'](csrf)}"><input type="hidden" name="action" value="{action}">{edit_hidden}<div class="formgrid"><input name="brand" placeholder="煙的品牌" value="{h['esc'](edit.get('brand') if edit else '')}" required><input name="name" placeholder="煙的名稱" value="{h['esc'](edit.get('name') if edit else '')}" required><input name="price" placeholder="價錢" value="{h['esc'](edit.get('price') if edit else '')}" required><input name="code" placeholder="代碼（如有）" value="{h['esc'](edit.get('code') if edit else '')}">{file_input}</div>{image_note}<div class="actions" style="margin-top:12px"><button class="btn gold">💾 儲存</button>{cancel}</div></form></section>'''
    return f'<section class="skullframe"><h1>🚬 煙款</h1>{cards}{form}</section>'


def handle_post(handler, data, h):
    arr = h['load_json'](h['TYPES_FILE'], [])
    action = str(data.get('action', 'add')).strip()
    if action == 'delete':
        rid = str(data.get('id', ''))
        arr = [x for x in arr if x.get('id') != rid]
        h['save_json'](h['TYPES_FILE'], arr)
        h['redirect'](handler, '/?page=types')
        return True

    image = ''
    if isinstance(data.get('image'), tuple) and data['image'][0]:
        image = h['save_cigarette_upload'](data['image'])
    else:
        existing = os.path.basename(str(data.get('existing_image','')).strip())
        cigarette_dir = h.get('CIGARETTE_UPLOAD_DIR', h['UPLOAD_DIR'])
        if existing and (cigarette_dir / existing).is_file():
            image = existing
    rid = str(data.get('id', ''))
    if action == 'edit':
        obj = next((x for x in arr if x.get('id') == rid), None)
        if obj:
            obj.update({'brand': str(data.get('brand', '')).strip(), 'name': str(data.get('name', '')).strip(), 'price': str(data.get('price', '')).strip(), 'code': str(data.get('code', '')).strip()})
            if image:
                obj['image'] = image
    else:
        arr.append({'id': uuid.uuid4().hex, 'brand': str(data.get('brand', '')).strip(), 'name': str(data.get('name', '')).strip(), 'price': str(data.get('price', '')).strip(), 'code': str(data.get('code', '')).strip(), 'image': image, 'created_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    h['save_json'](h['TYPES_FILE'], arr)
    h['redirect'](handler, '/?page=types')
    return True
