#!/usr/bin/env python3
# 🚬食少支煙系統：落單模組

import json


def record_items(r):
    """取得一張訂單內的煙款項目，兼容舊格式。"""
    if isinstance(r.get("items"), list):
        return r["items"]
    if r.get("name") or r.get("brand"):
        return [{k: r.get(k, "") for k in (
            "type_id", "brand", "name", "price", "code", "image", "quantity", "unit"
        )}]
    return []


def page(handler, helpers):
    """輸出落單頁面。"""
    load_json = helpers["load_json"]
    esc = helpers["esc"]
    record_file = helpers["RECORD_FILE"]
    clients_file = helpers["CLIENTS_FILE"]
    sellers_file = helpers["SELLERS_FILE"]

    records = load_json(record_file, [])
    clients = load_json(clients_file, [])
    sellers = load_json(sellers_file, [])
    active_records = [r for r in records if not r.get("completed", False)]
    order_numbers = {str(r.get('id')): i for i, r in enumerate(records, 1)}
    opts = ''
    for r in active_records:
        total = 0.0
        for it in record_items(r):
            try: price = float(str(it.get('price', 0)).replace(',', ''))
            except Exception: price = 0.0
            try: qty = float(str(it.get('quantity', 0)).replace(',', ''))
            except Exception: qty = 0.0
            total += price * qty
        items_summary = '、'.join(str(it.get('name') or it.get('brand') or '—') for it in record_items(r)) or '—'
        updated = str(r.get('updated_at') or r.get('created_at') or '')[:16]
        opts += f'<option value="{esc(r.get("id"))}">#{order_numbers.get(str(r.get("id")), "")} · {esc(r.get("client_name"))} · {esc(items_summary)} · ${total:,.2f} · {esc(updated)}</option>'
    seller_opts = ''.join(
        f'<option value="{esc(s.get("id"))}">{esc(s.get("name"))} · {esc(s.get("phone"))}</option>'
        for s in sellers
    )
    records_json = json.dumps(active_records, ensure_ascii=False)
    clients_json = json.dumps(clients, ensure_ascii=False)
    sellers_json = json.dumps(sellers, ensure_ascii=False)

    return f'''<section class="skullframe"><h1>📦 落單</h1>
<section class="panel">
<label class="small">選擇訂煙 Order</label>
<select id="orderSelect"><option value="">請選擇一張訂煙 Order</option>{opts}</select>
<textarea id="orderText" class="ordertext" style="margin-top:12px" placeholder="選擇後會顯示煙款及數量"></textarea>
<label class="small" style="margin-top:12px">選擇賣煙者</label>
<select id="sellerSelect"><option value="">請選擇賣煙者</option>{seller_opts}</select>
<div class="actions" style="justify-content:flex-end;margin-top:10px"><button class="btn gold" onclick="copyOrder()">📋 複製到剪貼簿</button><button class="btn green" onclick="waOrder()">💬 WhatsApp</button></div>
</section>
<section class="panel"><h2>☠️ 訂煙資料</h2><div class="meta">每張 Order 可包含多款煙，會一次過產生 WhatsApp 訊息。</div></section>
</section>
<script>
const records={records_json};
const clients={clients_json};
const sellers={sellers_json};
const sel=document.getElementById('orderSelect'), sellerSel=document.getElementById('sellerSelect'), ta=document.getElementById('orderText');
function items(r){{return Array.isArray(r.items)?r.items:[r]}}
function selected(){{return records.find(x=>x.id===sel.value)}}
function makeText(){{
 const r=selected();
 if(!r)return '';
 const c=clients.find(x=>x.id===r.client_id);
 const its=items(r);
 const lines=its.map(x=>`${{x.brand || ''}} ${{x.name || ''}} x ${{x.quantity || 0}}`);
 const parts=its.map(x=>{{const price=Number(x.price)||0;const qty=Number(x.quantity)||0;return qty===1?`$${{price.toLocaleString('en-US')}}`:`(${{'$'+price.toLocaleString('en-US')}} x ${{qty}})`}});
 const total=its.reduce((sum,x)=>sum+(Number(x.price)||0)*(Number(x.quantity)||0),0);
 const address=c&&c.address?c.address:'';
 let text=lines.join('\\n')+`\\n${{parts.join(' + ')}} = ${{total.toLocaleString('en-US')}}\\n有冇貨？`;
 if(address)text+=`如有貨，送去：\\n${{address}}`;
 return text;
}}
sel.addEventListener('change',()=>ta.value=makeText());
async function copyOrder(){{const t=ta.value;if(!t)return;await navigator.clipboard.writeText(t);alert('已複製到剪貼簿')}}
function waOrder(){{
 const r=selected();
 if(!r){{alert('請先選擇一張訂煙 Order');return;}}
 const s=sellers.find(x=>x.id===sellerSel.value);
 if(!s){{alert('請先選擇賣煙者');return;}}
 const t=ta.value||makeText();
 navigator.clipboard.writeText(t).catch(()=>{{}});
 const digits=String(s.phone||'').replace(/\\D/g,'');
 if(digits)window.open('https://wa.me/'+digits+'?text='+encodeURIComponent(t),'_blank');
 else window.open('https://wa.me/?text='+encodeURIComponent(t),'_blank');
}}
</script>'''
