import json, time, uuid, copy


def normalize_items(r):
    if isinstance(r.get('items'), list):
        return r['items']
    if r.get('name') or r.get('brand'):
        return [{k: r.get(k, '') for k in ('type_id','brand','name','price','code','image','quantity','unit')}]
    return []


def page(handler, h):
    types = h['load_json'](h['TYPES_FILE'], [])
    clients = h['load_json'](h['CLIENTS_FILE'], [])
    records = h['load_json'](h['RECORD_FILE'], [])
    csrf = handler.session['csrf']
    order_numbers = {str(r.get('id')): i for i, r in enumerate(records, 1)}
    q = (handler.query.get('q', [''])[0]).strip().lower()
    status = (handler.query.get('status', ['all'])[0]).strip().lower()
    sort_key = (handler.query.get('sort', ['order'])[0]).strip().lower()
    sort_dir = (handler.query.get('dir', ['asc'])[0]).strip().lower()
    if sort_key not in {'order', 'customer', 'cigarettes', 'updated', 'actions'}: sort_key = 'order'
    if sort_dir not in {'asc', 'desc'}: sort_dir = 'asc'
    if q:
        records = [r for r in records if q in json.dumps(r, ensure_ascii=False).lower()]
    if status == 'completed':
        records = [r for r in records if r.get('completed', False)]
    elif status == 'pending':
        records = [r for r in records if not r.get('completed', False)]

    edit_id = handler.query.get('edit', [''])[0]
    edit = next((r for r in records if r.get('id') == edit_id), None)

    # ♻️ 再訂只建立暫存草稿，不會寫入 record.json；直到使用者按「💾 儲存 Order」才真正新增。
    reorder_draft = handler.session.get('reorder_draft') if hasattr(handler, 'session') else None
    if not edit and isinstance(reorder_draft, dict):
        edit = reorder_draft
        edit_id = ''
    client_opts = ''.join(
        f'<option value="{h["esc"](x.get("id"))}" {"selected" if edit and edit.get("client_id") == x.get("id") else ""}>{h["esc"](x.get("name"))}</option>'
        for x in clients
    )

    edit_items = normalize_items(edit) if edit else []
    initial_rows = ''.join(item_row(i, types, item, h) for i, item in enumerate(edit_items)) if edit_items else item_row(0, types, None, h)
    type_json = json.dumps(types, ensure_ascii=False).replace('</', '<\\/')

    def sort_value(r):
        if sort_key == 'customer':
            return str(r.get('client_name') or '').lower()
        if sort_key == 'cigarettes':
            return ' '.join(str(x.get('name') or x.get('brand') or '') for x in normalize_items(r)).lower()
        if sort_key == 'updated':
            return str(r.get('updated_at') or r.get('created_at') or '')
        if sort_key == 'actions':
            return 1 if r.get('completed', False) else 0
        return order_numbers.get(str(r.get('id')), 0)
    records.sort(key=sort_value, reverse=(sort_dir == 'desc'))

    def sort_link(key, label, mobile_label=None):
        direction = 'desc' if sort_key == key and sort_dir == 'asc' else 'asc'
        params = {'page':'record', 'q': handler.query.get('q',[''])[0], 'status':status, 'sort':key, 'dir':direction}
        query = '&'.join('%s=%s' % (k, __import__('urllib.parse').parse.quote(str(v))) for k,v in params.items() if v != '')
        arrow = ' ▲' if sort_key == key and sort_dir == 'asc' else (' ▼' if sort_key == key else '')
        m = mobile_label or label
        return '<a class="record-sort" href="/?%s"><span class="desktop-label">%s%s</span><span class="mobile-label">%s%s</span></a>' % (query, label, arrow, m, arrow)

    rows = ''
    csrf_html = h['esc'](csrf)
    for r in records:
        items = normalize_items(r)
        item_lines = []
        total_amount = 0.0
        for it in items:
            try: price = float(str(it.get('price', 0)).replace(',', ''))
            except Exception: price = 0.0
            try: qty = float(str(it.get('quantity', 0)).replace(',', ''))
            except Exception: qty = 0.0
            total_amount += price * qty
            qty_text = str(it.get('quantity', '0'))
            unit = str(it.get('unit', '條'))
            if unit == '條煙': unit = '條'
            elif unit == '包煙': unit = '包'
            # Show brand before cigarette name, e.g. "Brand · Name".
            # Older records may lack a saved brand, so look it up by type_id.
            type_info = next((t for t in types if str(t.get('id', '')) == str(it.get('type_id', ''))), {})
            brand = str(it.get('brand') or type_info.get('brand') or '').strip()
            name = str(it.get('name') or type_info.get('name') or '').strip()
            cigarette_label = (brand + ' · ' + name).strip(' ·') or '—'
            # Display the cigarette photo immediately after the item description.
            image_name = str(it.get('image') or type_info.get('image') or '').strip()
            image_html = ''
            if image_name:
                image_file = __import__('os').path.basename(image_name)
                image_html = '<div class="record-cigarette-image" style="margin:5px 0 9px"><img src="/uploads/cigarette/%s" alt="%s" loading="lazy" style="display:block;max-width:150px;max-height:120px;width:auto;height:auto;object-fit:contain;border-radius:8px;border:1px solid rgba(220,190,120,.45)"></div>' % (
                    h['esc'](image_file), h['esc'](cigarette_label))
            item_lines.append('<div><b>%s</b> × %s %s · $%s</div>%s' % (
                h['esc'](cigarette_label), h['esc'](qty_text), h['esc'](unit), f'{price:,.2f}', image_html))
        smoke = ''.join(item_lines) or '<span class="smallmuted">—</span>'
        total_text = f'${total_amount:,.2f}'
        rid_html = h['esc'](r.get('id'))
        confirm_attr = 'onsubmit="return confirm(\"確定刪除呢張訂煙 Order？\")"'
        edit_link = '<a class="btn gold" href="/?page=record&edit=%s" title="修改">✏️</a>' % rid_html
        delete_form = '<form method="post" action="/record" %s><input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="%s"><button class="btn danger" title="刪除">🗑️</button></form>' % (confirm_attr, csrf_html, rid_html)
        if r.get('completed', False):
            final_form = '<form method="post" action="/record"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="reorder"><input type="hidden" name="id" value="%s"><button class="btn green" title="再訂">♻️</button></form>' % (csrf_html, rid_html)
        else:
            final_form = '<form method="post" action="/record"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="complete"><input type="hidden" name="id" value="%s"><button class="btn green" title="完成">✅</button></form>' % (csrf_html, rid_html)
        action_html = '<div class="actions record-actions">%s%s%s</div>' % (edit_link, delete_form, final_form)
        updated = str(r.get('updated_at') or r.get('created_at') or '')[:16]
        rows += '<tr><td>%s</td><td>%s</td><td>%s<div class="smallmuted" style="margin-top:6px"><b>%s</b></div></td><td>%s</td><td>%s</td></tr>' % (
            order_numbers.get(str(r.get('id')), ''), h['esc'](r.get('client_name')), smoke, h['esc'](total_text), h['esc'](updated), action_html)

    is_edit = bool(edit and edit_id)
    form_title = '✏️ 修改訂煙 Order' if is_edit else '📝 新增訂煙 Order'
    form_action = 'edit' if is_edit else 'add'
    edit_id_html = f'<input type="hidden" name="id" value="{h["esc"](edit.get("id"))}">' if is_edit else ''

    return f'''<section class="skullframe"><h1>📋 訂煙記錄</h1>
    <style>
    @media (max-width: 600px) {{
      .record-mobile-table {{ width:100% !important; min-width:0 !important; table-layout:fixed !important; }}
      .record-mobile-table thead {{ display:none !important; }}
      .record-mobile-table,
      .record-mobile-table tbody,
      .record-mobile-table tbody tr,
      .record-mobile-table tbody td {{ display:block !important; width:100% !important; }}
      .record-mobile-table tbody tr {{ box-sizing:border-box; margin:0 0 12px; padding:10px; border:1px solid rgba(220,190,120,.45); border-radius:12px; background:rgba(0,0,0,.10); }}
      .record-mobile-table tbody td {{ box-sizing:border-box; padding:5px 0 !important; border:0 !important; overflow-wrap:anywhere; }}
      .record-mobile-table tbody tr {{ display:flex !important; flex-direction:column; }}
      .record-mobile-table tbody td:nth-child(1) {{ display:block !important; order:2; font-size:.9em; opacity:.85; }}
      .record-mobile-table tbody td:nth-child(2),
      .record-mobile-table tbody td:nth-child(4) {{ display:none !important; }}
      .record-mobile-table tbody td:nth-child(3) {{ display:block !important; order:1; }}
      .record-mobile-table tbody td:nth-child(5) {{ display:block !important; order:3; padding-top:9px !important; margin-top:6px; border-top:1px solid rgba(220,190,120,.3) !important; }}
      .record-mobile-table tbody td:nth-child(5) .record-actions {{ display:flex; flex-wrap:wrap; gap:8px; }}
      .record-mobile-table tbody td:nth-child(5) form {{ display:inline-flex; margin:0; }}
      .record-mobile-table tbody td:nth-child(3) .record-cigarette-image img {{ max-width:100% !important; max-height:140px !important; }}
      .tablewrap {{ overflow-x:hidden !important; }}
      .record-mobile-table .empty {{ display:block !important; }}
    }}
    </style>
    <section class="panel tablewrap">
      <div style="padding:0 0 14px 0">
        <form method="get" id="recordSearchForm">
          <input type="hidden" name="page" value="record">
          <input type="hidden" name="sort" value="{h['esc'](sort_key)}">
          <input type="hidden" name="dir" value="{h['esc'](sort_dir)}">
          <div class="formgrid">
            <div><input id="recordSearchInput" name="q" value="{h['esc'](handler.query.get('q',[''])[0])}" placeholder="搜尋煙名稱、價錢、代碼、數量、訂煙者稱呼、電話 / WhatsApp" autocomplete="off"></div>
            <div><select id="recordStatusFilter" name="status"><option value="all" {"selected" if status == "all" else ""}>全部</option><option value="pending" {"selected" if status == "pending" else ""}>未完成</option><option value="completed" {"selected" if status == "completed" else ""}>✅完成</option></select></div>
          </div>
        </form>
      </div>
      <table class="record-mobile-table"><thead><tr><th>{sort_link('order','訂單號碼','訂單')}</th><th>{sort_link('customer','訂煙者')}</th><th>{sort_link('cigarettes','煙款')}</th><th>{sort_link('updated','最後修改時間','日期')}</th><th>{sort_link('actions','操作') }</th></tr></thead><tbody>{rows or '<tr><td colspan="5" class="empty">暫時無資料</td></tr>'}</tbody></table>
    </section>
    <section class="panel"><h2>{form_title}</h2><form method="post" action="/record" id="orderForm"><input type="hidden" name="csrf" value="{h['esc'](csrf)}"><input type="hidden" name="action" value="{form_action}">{edit_id_html}<div class="formgrid"><div><label class="small">訂煙者資料</label><select name="client_id" required><option value="">選擇訂煙者</option>{client_opts}</select></div></div><div style="margin-top:14px"><label class="small">煙款（同一張 Order 可加入多款煙）</label><div id="itemRows">{initial_rows}</div><button type="button" id="addItemBtn" class="btn gray" style="margin-top:10px">➕ 增加另一款煙</button></div><div class="actions" style="margin-top:16px"><button class="btn gray" type="button" id="cancelOrderBtn">取消</button><button class="btn gold" type="submit">💾 儲存 Order</button></div></form></section>
    <script>
    const recordSearchForm = document.getElementById('recordSearchForm');
    const recordSearchInput = document.getElementById('recordSearchInput');
    const recordStatusFilter = document.getElementById('recordStatusFilter');
    let recordSearchTimer;
    function submitRecordSearch() {{ if (recordSearchForm) recordSearchForm.submit(); }}
    if (recordSearchInput) recordSearchInput.addEventListener('input', function() {{ clearTimeout(recordSearchTimer); recordSearchTimer = setTimeout(submitRecordSearch, 250); }});
    if (recordStatusFilter) recordStatusFilter.addEventListener('change', submitRecordSearch);

    const smokeTypes = {type_json};
    let rowCount = {len(edit_items) if edit_items else 1};
    const itemRows = document.getElementById('itemRows');

    function escJsHtml(value) {{
        return String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }}

    function typeOptions(selected) {{
        let html = '<option value="">選擇煙款</option>';
        smokeTypes.forEach(function(t) {{
            const isSelected = String(t.id) === String(selected || '') ? ' selected' : '';
            html += '<option value="' + escJsHtml(t.id) + '"' + isSelected + '>' +
                    escJsHtml(t.brand) + ' · ' + escJsHtml(t.name) + ' · $' + escJsHtml(t.price) + ' · ' + escJsHtml(t.code || '—') + '</option>';
        }});
        return html;
    }}

    function preview(id, target) {{
        const t = smokeTypes.find(function(x) {{ return String(x.id) === String(id); }});
        if (!t) {{
            target.innerHTML = '<span class="smallmuted">選擇煙款後顯示完整資料及相片</span>';
            return;
        }}
        const image = t.image ? '<img class="cigthumb" src="/uploads/cigarette/' + encodeURIComponent(String(t.image).split('/').pop()) + '" alt="">' : '<span class="smallmuted">無相片</span>';
        target.innerHTML = image +
            '<div style="display:inline-block;vertical-align:middle;line-height:1.7">' +
            '<b>品牌：' + escJsHtml(t.brand) + '</b><br>' +
            '名稱：' + escJsHtml(t.name) + '<br>' +
            '價錢：$' + escJsHtml(t.price) + '<br>' +
            '代碼：' + escJsHtml(t.code || '—') +
            '</div>';
    }}

    function bindRow(row) {{
        const select = row.querySelector('select[name^="type_id_"]');
        const previewBox = row.querySelector('.item-preview');
        if (select && previewBox) {{
            select.addEventListener('change', function() {{ preview(select.value, previewBox); }});
            if (select.value) preview(select.value, previewBox);
        }}
        const removeBtn = row.querySelector('.remove-item-btn');
        if (removeBtn) removeBtn.addEventListener('click', function() {{ row.remove(); }});
    }}

    function addItemRow(selected, qty, unit) {{
        const i = rowCount++;
        selected = selected || '';
        qty = String(qty || '1');
        unit = unit || '條';
        const row = document.createElement('div');
        row.className = 'panel order-item-row';
        row.id = 'item-' + i;
        let qtyOptions = '';
        for (let n = 1; n <= 9; n++) qtyOptions += '<option value="' + n + '"' + (String(n) === qty ? ' selected' : '') + '>' + n + '</option>';
        row.innerHTML =
            '<div class="formgrid">' +
              '<div><select name="type_id_' + i + '" required>' + typeOptions(selected) + '</select>' +
              '<div class="notice item-preview" style="margin-top:8px"><span class="smallmuted">選擇煙款後顯示完整資料及相片</span></div></div>' +
              '<div><div style="display:flex;gap:8px"><select name="quantity_' + i + '">' + qtyOptions + '</select>' +
              '<select name="unit_' + i + '"><option' + (unit === '條' ? ' selected' : '') + '>條</option><option' + (unit === '包' ? ' selected' : '') + '>包</option></select></div></div>' +
              '<div class="actions"><button type="button" class="btn danger remove-item-btn">🗑️</button></div>' +
            '</div>';
        itemRows.appendChild(row);
        bindRow(row);
    }}

    document.querySelectorAll('.order-item-row').forEach(bindRow);
    document.getElementById('addItemBtn').addEventListener('click', function() {{ addItemRow(); }});
    document.getElementById('cancelOrderBtn').addEventListener('click', async function() {{
        const form = document.getElementById('orderForm');
        const fd = new FormData();
        fd.append('csrf', form.querySelector('input[name=csrf]').value);
        fd.append('action', 'cancel');
        try {{ await fetch('/record', {{method:'POST', body:fd, credentials:'same-origin'}}); }} catch (e) {{}}
        form.reset();
        itemRows.innerHTML = '';
        rowCount = 0;
        addItemRow();
        window.scrollTo({{top:0, behavior:'smooth'}});
    }});
    </script></section>'''


def item_row(i, types, item, h):
    selected = item.get('type_id', '') if item else ''
    qty = item.get('quantity', '1') if item else '1'
    unit = item.get('unit', '條') if item else '條'
    if unit == '條煙': unit = '條'
    elif unit == '包煙': unit = '包'
    opts = '<option value="">選擇煙款</option>' + ''.join(
        f'<option value="{h["esc"](t.get("id"))}" {"selected" if t.get("id") == selected else ""}>{h["esc"](t.get("brand"))} · {h["esc"](t.get("name"))} · ${h["esc"](t.get("price"))} · {h["esc"](t.get("code")) or "—"}</option>'
        for t in types
    )
    qtyopts = ''.join(f'<option value="{n}" {"selected" if str(n) == str(qty) else ""}>{n}</option>' for n in range(1, 10))
    return f'''<div class="panel order-item-row" id="item-{i}"><div class="formgrid"><div><select name="type_id_{i}" required>{opts}</select><div class="notice item-preview" style="margin-top:8px"><span class="smallmuted">選擇煙款後顯示完整資料及相片</span></div></div><div><div style="display:flex;gap:8px"><select name="quantity_{i}">{qtyopts}</select><select name="unit_{i}"><option {'selected' if unit == '條' else ''}>條</option><option {'selected' if unit == '包' else ''}>包</option></select></div></div><div class="actions"><button type="button" class="btn danger remove-item-btn">🗑️</button></div></div></div>'''


def handle_post(handler, data, h):
    records = h['load_json'](h['RECORD_FILE'], [])
    clients = h['load_json'](h['CLIENTS_FILE'], [])
    types = h['load_json'](h['TYPES_FILE'], [])
    action = str(data.get('action', 'add')).strip()
    rid = str(data.get('id', ''))
    if action == 'cancel':
        if hasattr(handler, 'session'):
            handler.session.pop('reorder_draft', None)
        h['redirect'](handler, '/?page=record')
        return True
    if action == 'delete':
        records = [r for r in records if r.get('id') != rid]
        h['save_json'](h['RECORD_FILE'], records)
        h['redirect'](handler, '/?page=record')
        return True
    if action == 'complete':
        r = next((x for x in records if x.get('id') == rid), None)
        if r and not r.get('completed', False):
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            r['completed'] = True
            r['completed_at'] = now
            r['updated_at'] = now
            h['save_json'](h['RECORD_FILE'], records)
        h['redirect'](handler, '/?page=record')
        return True
    if action == 'reorder':
        r = next((x for x in records if x.get('id') == rid), None)
        if r and r.get('completed', False):
            # 只放入 session 暫存，絕不寫入 record.json。
            new_order = copy.deepcopy(r)
            new_order['id'] = ''
            new_order.pop('completed', None)
            new_order.pop('completed_at', None)
            new_order.pop('created_at', None)
            new_order.pop('updated_at', None)
            if hasattr(handler, 'session'):
                handler.session['reorder_draft'] = new_order
        h['redirect'](handler, '/?page=record')
        return True
    client = next((x for x in clients if x.get('id') == data.get('client_id')), None)
    if not client:
        h['redirect'](handler, '/?page=record')
        return True
    keys = []
    for k in data:
        if k.startswith('type_id_'):
            try:
                keys.append(int(k.rsplit('_', 1)[1]))
            except ValueError:
                pass
    items = []
    for i in sorted(set(keys)):
        tid = data.get(f'type_id_{i}')
        t = next((x for x in types if x.get('id') == tid), None)
        if not t:
            continue
        items.append({
            'type_id': t['id'], 'brand': t.get('brand', ''), 'name': t.get('name', ''),
            'price': t.get('price', ''), 'code': t.get('code', ''), 'image': t.get('image', ''),
            'quantity': data.get(f'quantity_{i}', '1'), 'unit': ('條' if data.get(f'unit_{i}', '條') == '條煙' else '包' if data.get(f'unit_{i}', '條') == '包煙' else data.get(f'unit_{i}', '條'))
        })
    if not items:
        h['redirect'](handler, '/?page=record')
        return True
    if action == 'edit':
        r = next((x for x in records if x.get('id') == rid), None)
        if r:
            r.update({'client_id': client['id'], 'client_name': client['name'], 'client_phone': client.get('phone', ''), 'items': items, 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')})
            for k in ('brand', 'name', 'price', 'code', 'image', 'quantity', 'unit', 'type_id'):
                r.pop(k, None)
    else:
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        records.append({'id': uuid.uuid4().hex, 'client_id': client['id'], 'client_name': client['name'], 'client_phone': client.get('phone', ''), 'items': items, 'created_at': now, 'updated_at': now})
    if hasattr(handler, 'session'):
        handler.session.pop('reorder_draft', None)
    h['save_json'](h['RECORD_FILE'], records)
    h['redirect'](handler, '/?page=record')
    return True
