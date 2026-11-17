#!/usr/bin/env python3
import base64, contextvars, hashlib, hmac, html, json, mimetypes, os, random, re, secrets, struct, time, urllib.parse, uuid
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cigarette_types
import clients as clients_module
import record as record_module
import order as order_module
import seller as seller_module

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROFILE_UPLOAD_DIR = UPLOAD_DIR / "profile"
CIGARETTE_UPLOAD_DIR = UPLOAD_DIR / "cigarette"
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CIGARETTE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = BASE_DIR / "config.json"
TYPES_FILE = BASE_DIR / "types.json"
CLIENTS_FILE = BASE_DIR / "clients.json"
RECORD_FILE = BASE_DIR / "record.json"
SELLERS_FILE = BASE_DIR / "seller.json"
REMEMBER_FILE = BASE_DIR / ".remember_tokens.json"
SESSION_SECRET_FILE = BASE_DIR / ".session_secret"
DEFAULT_LOGIN = "smoker"
DEFAULT_PASSWORD = "smokekills"
DEFAULT_ADMIN_PASSWORD = "dontsmoke"
PORT_DEFAULT = 6667


def detect_raspberry_pi4():
    """Detect Raspberry Pi 4 from the server host's device-tree model."""
    for model_path in (Path("/proc/device-tree/model"), Path("/sys/firmware/devicetree/base/model")):
        try:
            model = model_path.read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore").lower()
            if "raspberry pi 4" in model:
                return True
        except OSError:
            continue
    return False


IS_RASPBERRY_PI4 = detect_raspberry_pi4()
LOGOUT_MESSAGES = [
    "香港政府忠告市民吸煙危害健康",
    "食少支煙啦屌你味道！",
    "人到40要保養下，少煙酒呀🤣",
    "要量入為出，食10條買返16條🤣",
    "行萬里路，唔好食萬寶路，因為唔夠氣🤣",
]
UPLOAD_DIR.mkdir(exist_ok=True)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        save_json(path, default)
        return default


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# 中英文介面設定：所有固定 UI 文字集中保存於 config.json，方便日後自行修改。
DEFAULT_UI_TEXT = {
    "食少支煙系統": "Smoke Less System", "主頁": "Home", "設定": "Settings", "煙款": "Cigarettes",
    "訂煙者": "Customers", "賣煙者": "Sellers", "訂煙記錄": "Order Records", "落單": "Place Order",
    "功能選單": "Menu", "登出": "Logout", "切換夜間模式": "Toggle dark mode", "登入": "Login",
    "登入名稱": "Username", "密碼": "Password", "記住我（只限此裝置及此 Browser，永久至登出）": "Remember me (this device and browser only, until logout)",
    "香港政府忠告市民吸煙危害健康": "Hong Kong Government advises that smoking is hazardous to health",
    "食少支煙啦屌你味道！": "Smoke less, for fuck's sake!",
    "人到40要保養下，少煙酒呀🤣": "When you reach 40, take care of yourself — less smoking and drinking 🤣",
    "要量入為出，食10條買返16條🤣": "Live within your means — smoke 10 packs and buy 16 🤣",
    "行萬里路，唔好食萬寶路，因為唔夠氣🤣": "Travel far and wide, but don't smoke Marlboro — you'll run out of breath 🤣",
    "🚬 登入": "🚬 Login", "雙重認證": "Two-Factor Authentication", "請輸入 Authenticator App 顯示的 6 位數字": "Enter the 6-digit code shown in your Authenticator app",
    "6位數字": "6 digits", "☠️ 驗證登入": "☠️ Verify & Login", "登入頁面已失效，請重新整理。": "The login page has expired. Please refresh.",
    "登入名稱或密碼錯誤。": "Incorrect username or password.", "2FA 驗證失敗。": "2FA verification failed.",
    "2FA 驗證工作階段已失效，請重新登入。": "The 2FA session has expired. Please log in again.",
    "主頁": "Home", "墨西哥亡靈節主題 · 訂煙、記錄、落單集中管理": "Day of the Dead theme · Manage cigarettes, records and orders in one place",
    "管理品牌、名稱、價錢、代碼及相片。": "Manage brands, names, prices, codes and photos.", "管理訂煙者及 WhatsApp 聯絡資料。": "Manage customers and WhatsApp contact details.",
    "建立每一行獨立訂煙 Order。": "Create individual cigarette orders.", "按煙款選擇後產生落單 WhatsApp 訊息。": "Generate a WhatsApp order message from selected cigarettes.",
    "🚬 煙款": "🚬 Cigarettes", "👤 訂煙者": "👤 Customers", "🚬 賣煙者": "🚬 Sellers", "📋 訂煙記錄": "📋 Order Records", "📦 落單": "📦 Place Order",
    "更變背景": "Change Background", "背景顏色預覽": "Background color preview", "背景類型": "Background type", "顏色": "Color", "相片": "Photo",
    "常用顏色": "Common colors", "亡靈黑": "Day-of-the-Dead Black", "深紅": "Dark Red", "墨綠": "Dark Green", "深藍": "Dark Blue", "咖啡": "Coffee", "紫黑": "Purple Black",
    "已上載相片": "Uploaded photos", "上載新相片": "Upload new photo", "顯示方式": "Display mode", "選擇檔案": "Choose file", "Choose file": "Choose file",
    "填滿": "Fill", "適合": "Fit", "置中": "Center", "拉伸": "Stretch", "平鋪": "Tile", "💀 儲存背景": "💀 Save Background",
    "🌙 夜間模式": "🌙 Dark Mode", "☀️ 關閉夜間模式": "☀️ Turn Off Dark Mode", "🌙 開啟夜間模式": "🌙 Turn On Dark Mode", "按一下即時切換，不使用 checkbox。": "Click to switch instantly; no checkbox is used.",
    "🌍 中英文切換": "🌍 Language", "中文": "Chinese", "English": "English", "目前語言": "Current language", "中英文": "Chinese / English", "切換語言": "Switch language",
    "🪟 透明化顯示比例": "🪟 Transparency", "系統透明化：": "System transparency: ", "5% 最透明　　100% 不透明": "5% most transparent　　100% opaque", "💾 儲存透明度": "💾 Save Transparency",
    "🔐 更改登入名和密碼": "🔐 Change Username and Password", "目前登入名": "Current username", "目前密碼": "Current password", "新登入名": "New username", "新密碼": "New password", "儲存新登入資料": "Save New Login Details",
    "☠️ 更改 admin 密碼": "☠️ Change admin Password", "目前 admin 密碼": "Current admin password", "新 admin 密碼": "New admin password", "更新 admin 密碼": "Update admin Password",
    "📱 雙重認證（2FA / TOTP）": "📱 Two-Factor Authentication (2FA / TOTP)", "啟用雙重認證（TOTP）": "Enable two-factor authentication (TOTP)", "💾 儲存2FA開關": "💾 Save 2FA setting", "👁️ 顯示/隱藏 QR Code": "👁️ Show/Hide QR Code", "重新產生後舊 Code 即刻失效，確定？": "Regenerating will immediately invalidate the old code. Continue?", "♻️ 重新產生金鑰（舊 Code 即刻失效）": "♻️ Regenerate Key (old code expires immediately)",
    "Secret：": "Secret: ", "尚未產生 2FA 金鑰。": "No 2FA key has been generated yet.", "輸入 admin 密碼後顯示 QR Code": "Enter the admin password to show the QR Code", "🔐 驗證並顯示 QR Code": "🔐 Verify and Show QR Code", "QR code library unavailable. Run:": "QR code library unavailable. Run:",
    "⚙️ 系統設定": "⚙️ System Settings", "錯誤": "Error", "設定錯誤": "Settings Error", "CSRF 驗證失敗，請重新整理頁面。": "CSRF verification failed. Please refresh the page.", "目前登入名稱或密碼錯誤。": "Current username or password is incorrect.", "目前 admin 密碼錯誤。": "Current admin password is incorrect.", "admin 密碼錯誤。": "Incorrect admin password.",
    "煙的品牌": "Cigarette brand", "煙的名稱": "Cigarette name", "價錢": "Price", "代碼（如有）": "Code (optional)", "已有香煙相片": "Existing cigarette photo", "上載新相片": "Upload new photo", "如不重新上載相片，會保留原有相片。": "If you do not upload a new photo, the existing photo will be kept.",
    "取消": "Cancel", "💾 儲存": "💾 Save", "✏️ 修改": "✏️ Edit", "🗑️ 刪除": "🗑️ Delete", "🚬 暫時無資料": "🚬 No data yet", "確定刪除呢款煙？": "Delete this cigarette?",
    "訂煙者稱呼": "Customer name", "送貨地點": "Delivery address", "電話 / WhatsApp": "Phone / WhatsApp", "WhatsApp 內容": "WhatsApp content", "有煙食喇": "Cigarettes are available", "確定刪除呢位訂煙者？": "Delete this customer?",
    "賣煙者稱呼": "Seller name", "評價": "Rating", "評語": "Comment", "確定刪除呢位賣煙者？": "Delete this seller?", "🚬 暫時無資料": "🚬 No data yet",
    "搜尋煙名稱、價錢、代碼、數量、訂煙者稱呼、電話 / WhatsApp": "Search cigarette name, price, code, quantity, customer name, phone / WhatsApp", "🔎 搜尋": "🔎 Search", "訂煙者資料": "Customer details", "選擇訂煙者": "Select customer", "煙款（同一張 Order 可加入多款煙）": "Cigarettes (multiple types can be added to one order)", "➕ 增加另一款煙": "➕ Add another type", "💾 儲存 Order": "💾 Save Order", "訂煙者": "Customer", "煙款": "Cigarettes", "時間": "Time", "操作": "Actions", "確定刪除呢張訂煙 Order？": "Delete this cigarette order?", "暫時無資料": "No data yet", "選擇煙款": "Select cigarette", "選擇煙款後顯示完整資料及相片": "Full details and photo will appear after selecting a cigarette", "品牌：": "Brand: ", "名稱：": "Name: ", "價錢：": "Price: ", "無相片": "No photo", "移除": "Remove", "條": "stick(s)", "包": "pack(s)", "條煙": "stick(s)", "包煙": "pack(s)",
    "選擇訂煙 Order": "Select cigarette order", "請選擇一張訂煙 Order": "Please select a cigarette order", "選擇後會顯示煙款及數量": "Cigarettes and quantities will appear after selection", "預設會按 Browser 語言自動切換；手動選擇後會記住此 Browser 的設定。": "By default, the interface follows your browser language; after manual selection, the setting is remembered for this browser.", "最後修改時間": "Last modified time", "最後修改時間：": "Last modified time: ", "選擇賣煙者": "Select seller", "請選擇賣煙者": "Please select a seller", "📋 複製到剪貼簿": "📋 Copy to Clipboard", "☠️ 訂煙資料": "☠️ Order Details", "每張 Order 可包含多款煙，會一次過產生 WhatsApp 訊息。": "Each order can contain multiple cigarette types and generates one WhatsApp message.", "有冇貨？如有貨，送去：": "Is it available? If so, please deliver to:",
    "Choose file": "Choose file", "儲存": "Save", "修改": "Edit", "刪除": "Delete", "電話 / WhatsApp：": "Phone / WhatsApp: ", "送貨地點：": "Delivery address: ", "評價：": "Rating: ", "評語：": "Comment: ", "WhatsApp 內容：": "WhatsApp content: ", "煙款：": "Cigarettes: ", "總數：": "Total: ",
    "確定？": "Continue?", "有冇貨？": "Is it available?", "如有貨，送去：": "If available, please deliver to:", "賣煙者：": "Seller: ", "訂煙：": "Order: ",
    "💬 WhatsApp": "💬 WhatsApp", "⚠️": "⚠️",
}

# Additional fixed UI phrases used by the individual modules.
DEFAULT_UI_TEXT.update({'管理賣煙者、電話、評價及評語。': 'Manage sellers, phone numbers, ratings and comments.', '新增煙款': 'Add Cigarette', '修改煙款': 'Edit Cigarette', '新增訂煙者': 'Add Customer', '修改訂煙者': 'Edit Customer', '新增賣煙者': 'Add Seller', '修改賣煙者': 'Edit Seller', '新增訂煙 Order': 'Add Cigarette Order', '修改訂煙 Order': 'Edit Cigarette Order', '品牌：': 'Brand: ', '代碼：': 'Code: ', '只接受圖片檔案。': 'Only image files are accepted.', '未分類': 'Uncategorized', '電話 / WhatsApp：': 'Phone / WhatsApp: ', '評價：': 'Rating: ', '評語：': 'Comment: ', '總數：': 'Total: ', '訂煙者資料': 'Customer details', '選擇訂煙者': 'Select customer', '煙款（同一張 Order 可加入多款煙）': 'Cigarettes (multiple types can be added to one order)', '選擇煙款': 'Select cigarette', '選擇煙款後顯示完整資料及相片': 'Full details and photo will appear after selecting a cigarette', '無相片': 'No photo', '移除': 'Remove', '選擇訂煙 Order': 'Select cigarette order', '請選擇一張訂煙 Order': 'Please select a cigarette order', '選擇後會顯示煙款及數量': 'Cigarettes and quantities will appear after selection', '選擇賣煙者': 'Select seller', '請選擇賣煙者': 'Please select a seller', '已複製到剪貼簿': 'Copied to clipboard', '請先選擇一張訂煙 Order': 'Please select a cigarette order first', '請先選擇賣煙者': 'Please select a seller first', '建立每一行獨立訂煙 Order。': 'Create individual cigarette orders.', '按煙款選擇後產生落單 WhatsApp 訊息。': 'Generate a WhatsApp order message from selected cigarettes.', '煙款：': 'Cigarettes: ', '送貨地點：': 'Delivery address: ', 'WhatsApp 內容：': 'WhatsApp content: ', '賣煙者：': 'Seller: ', '訂煙：': 'Order: '})
DEFAULT_UI_TEXT.update({'完成': 'Complete', '再訂': 'Reorder'})


# Explicit mixed-language/legacy labels that may already exist in older config.json versions.
DEFAULT_UI_TEXT.update({
    "管理Sellers、電話、Rating及Comment。": "Manage sellers, phone numbers, ratings and comments.",
    "🚬 Sellers": "🚬 Sellers",
    "➕新增Cigarettes": "➕ Add Cigarettes",
    "➕ 新增Cigarettes": "➕ Add Cigarettes",
    "➕新增Customer": "➕ Add Customer",
    "➕ 新增Customer": "➕ Add Customer",
    "➕新增Sellers": "➕ Add Sellers",
    "➕ 新增Sellers": "➕ Add Sellers",
    "📝 新增訂煙 Order": "📝 Add Cigarette Order",
    "Copyright ©️洗錢多過賺錢既垃圾系統2026": "Copyright ©️A shitty system that launders more money than it earns 2026",
})

DEFAULT_UI_TEXT.update({'✏️ 修改煙款': '✏️ Edit Cigarette', '➕ 新增煙款': '➕ Add Cigarette', '✏️ 修改訂煙者': '✏️ Edit Customer', '➕ 新增訂煙者': '➕ Add Customer', '✏️ 修改賣煙者': '✏️ Edit Seller', '➕ 新增賣煙者': '➕ Add Seller', '✏️ 修改訂煙 Order': '✏️ Edit Cigarette Order', '📝 新增訂煙 Order': '📝 Add Cigarette Order', '🚬 食少支煙系統': '🚬 Smoke Less System'})

# Browser language is detected per request. Chinese browsers use the existing
# Traditional Chinese UI; all other browser languages use English.
REQUEST_LANGUAGE = contextvars.ContextVar("request_language", default=None)

SUPPORTED_LANGUAGES = ("zh-Hant", "en", "th", "ja", "ko", "ru", "es")
LANGUAGE_NAMES = {"zh-Hant":"繁體中文","en":"English","th":"ไทย","ja":"日本語","ko":"한국어","ru":"Русский","es":"Español"}

def detect_browser_language(accept_language):
    raw = str(accept_language or "").strip()
    if not raw: return "en"
    choices=[]
    for pos,item in enumerate(raw.split(",")):
        parts=[x.strip() for x in item.split(";")]; lang=parts[0].lower()
        if not lang: continue
        q=1.0
        for param in parts[1:]:
            if param.lower().startswith("q="):
                try: q=float(param.split("=",1)[1])
                except (ValueError,TypeError): q=0.0
        choices.append((-q,pos,lang))
    choices.sort()
    mapping=[("zh","zh-Hant"),("en","en"),("th","th"),("ja","ja"),("ko","ko"),("ru","ru"),("es","es")]
    for _,_,lang in choices:
        if lang=="*": continue
        for prefix,code in mapping:
            if lang==prefix or lang.startswith(prefix+"-"): return code
    return "en"

MULTI_UI_TEXT = {
'Copyright ©️洗錢多過賺錢既垃圾系統2026': {'th':'ลิขสิทธิ์ ©️ ระบบห่วยๆ ที่ฟอกเงินมากกว่าหาเงิน 2026','ja':'Copyright ©️ 稼ぐよりマネーロンダリングするクソシステム 2026','ko':'Copyright ©️ 돈 버는 것보다 돈세탁을 더 많이 하는 쓰레기 시스템 2026','ru':'Copyright ©️ Система-отстой, которая отмывает больше денег, чем зарабатывает, 2026','es':'Copyright ©️ Sistema basura que blanquea más dinero del que gana 2026'},'食少支煙系統': {'th':'ระบบสูบบุหรี่น้อยลง','ja':'禁煙・減煙システム','ko':'담배 줄이기 시스템','ru':'Система «Курить меньше»','es':'Sistema Fumar Menos'},'主頁': {'th':'หน้าหลัก','ja':'ホーム','ko':'홈','ru':'Главная','es':'Inicio'},'設定': {'th':'การตั้งค่า','ja':'設定','ko':'설정','ru':'Настройки','es':'Configuración'},'煙款': {'th':'บุหรี่','ja':'たばこ','ko':'담배','ru':'Сигареты','es':'Cigarrillos'},'訂煙者': {'th':'ลูกค้า','ja':'顧客','ko':'고객','ru':'Клиенты','es':'Clientes'},'賣煙者': {'th':'ผู้ขาย','ja':'販売者','ko':'판매자','ru':'Продавцы','es':'Vendedores'},'訂煙記錄': {'th':'ประวัติการสั่งซื้อ','ja':'注文履歴','ko':'주문 기록','ru':'История заказов','es':'Historial de pedidos'},'落單': {'th':'สั่งซื้อ','ja':'注文する','ko':'주문하기','ru':'Оформить заказ','es':'Hacer pedido'},'功能選單': {'th':'เมนู','ja':'メニュー','ko':'메뉴','ru':'Меню','es':'Menú'},'登出': {'th':'ออกจากระบบ','ja':'ログアウト','ko':'로그아웃','ru':'Выйти','es':'Cerrar sesión'},'登入': {'th':'เข้าสู่ระบบ','ja':'ログイン','ko':'로그인','ru':'Войти','es':'Iniciar sesión'},'登入名稱': {'th':'ชื่อผู้ใช้','ja':'ユーザー名','ko':'사용자 이름','ru':'Имя пользователя','es':'Nombre de usuario'},'密碼': {'th':'รหัสผ่าน','ja':'パスワード','ko':'비밀번호','ru':'Пароль','es':'Contraseña'},'雙重認證': {'th':'การยืนยันตัวตนสองขั้นตอน','ja':'二要素認証','ko':'2단계 인증','ru':'Двухфакторная аутентификация','es':'Autenticación de dos factores'},'6位數字': {'th':'6 หลัก','ja':'6桁','ko':'6자리','ru':'6 цифр','es':'6 dígitos'},'☠️ 驗證登入': {'th':'☠️ ยืนยันและเข้าสู่ระบบ','ja':'☠️ 認証してログイン','ko':'☠️ 인증 및 로그인','ru':'☠️ Проверить и войти','es':'☠️ Verificar e iniciar sesión'},'🚬 煙款': {'th':'🚬 บุหรี่','ja':'🚬 たばこ','ko':'🚬 담배','ru':'🚬 Сигареты','es':'🚬 Cigarrillos'},'👤 訂煙者': {'th':'👤 ลูกค้า','ja':'👤 顧客','ko':'👤 고객','ru':'👤 Клиенты','es':'👤 Clientes'},'🚬 賣煙者': {'th':'🚬 ผู้ขาย','ja':'🚬 販売者','ko':'🚬 판매자','ru':'🚬 Продавцы','es':'🚬 Vendedores'},'📋 訂煙記錄': {'th':'📋 ประวัติการสั่งซื้อ','ja':'📋 注文履歴','ko':'📋 주문 기록','ru':'📋 История заказов','es':'📋 Historial de pedidos'},'📦 落單': {'th':'📦 สั่งซื้อ','ja':'📦 注文する','ko':'📦 주문하기','ru':'📦 Оформить заказ','es':'📦 Hacer pedido'},'更變背景': {'th':'เปลี่ยนพื้นหลัง','ja':'背景を変更','ko':'배경 변경','ru':'Изменить фон','es':'Cambiar fondo'},'背景類型': {'th':'ประเภทพื้นหลัง','ja':'背景タイプ','ko':'배경 유형','ru':'Тип фона','es':'Tipo de fondo'},'顏色': {'th':'สี','ja':'色','ko':'색상','ru':'Цвет','es':'Color'},'相片': {'th':'รูปภาพ','ja':'写真','ko':'사진','ru':'Фото','es':'Foto'},'常用顏色': {'th':'สีที่ใช้บ่อย','ja':'よく使う色','ko':'자주 사용하는 색상','ru':'Популярные цвета','es':'Colores habituales'},'亡靈黑': {'th':'ดำวันแห่งความตาย','ja':'死者の日ブラック','ko':'망자의 날 블랙','ru':'Чёрный День мёртвых','es':'Negro del Día de Muertos'},'深紅': {'th':'แดงเข้ม','ja':'ダークレッド','ko':'진한 빨강','ru':'Тёмно-красный','es':'Rojo oscuro'},'墨綠': {'th':'เขียวเข้ม','ja':'ダークグリーン','ko':'진한 녹색','ru':'Тёмно-зелёный','es':'Verde oscuro'},'深藍': {'th':'น้ำเงินเข้ม','ja':'ダークブルー','ko':'진한 파랑','ru':'Тёмно-синий','es':'Azul oscuro'},'咖啡': {'th':'กาแฟ','ja':'コーヒー','ko':'커피','ru':'Кофейный','es':'Café'},'紫黑': {'th':'ม่วงดำ','ja':'パープルブラック','ko':'보라색 블랙','ru':'Фиолетово-чёрный','es':'Morado negro'},'已上載相片': {'th':'รูปภาพที่อัปโหลด','ja':'アップロード済みの写真','ko':'업로드된 사진','ru':'Загруженные фото','es':'Fotos subidas'},'上載新相片': {'th':'อัปโหลดรูปใหม่','ja':'新しい写真をアップロード','ko':'새 사진 업로드','ru':'Загрузить новое фото','es':'Subir nueva foto'},'顯示方式': {'th':'โหมดการแสดงผล','ja':'表示モード','ko':'표시 방식','ru':'Режим отображения','es':'Modo de visualización'},'選擇檔案': {'th':'เลือกไฟล์','ja':'ファイルを選択','ko':'파일 선택','ru':'Выбрать файл','es':'Elegir archivo'},'填滿': {'th':'เต็มพื้นที่','ja':'塗りつぶし','ko':'채우기','ru':'Заполнить','es':'Rellenar'},'適合': {'th':'พอดี','ja':'フィット','ko':'맞춤','ru':'По размеру','es':'Ajustar'},'置中': {'th':'จัดกึ่งกลาง','ja':'中央','ko':'가운데','ru':'По центру','es':'Centrar'},'拉伸': {'th':'ยืด','ja':'引き伸ばし','ko':'늘이기','ru':'Растянуть','es':'Estirar'},'平鋪': {'th':'เรียงซ้ำ','ja':'タイル','ko':'바둑판식','ru':'Мозаика','es':'Mosaico'},'🌙 夜間模式': {'th':'🌙 โหมดกลางคืน','ja':'🌙 ダークモード','ko':'🌙 다크 모드','ru':'🌙 Тёмный режим','es':'🌙 Modo oscuro'},'☀️ 關閉夜間模式': {'th':'☀️ ปิดโหมดกลางคืน','ja':'☀️ ダークモードをオフ','ko':'☀️ 다크 모드 끄기','ru':'☀️ Выключить тёмный режим','es':'☀️ Desactivar modo oscuro'},'🌙 開啟夜間模式': {'th':'🌙 เปิดโหมดกลางคืน','ja':'🌙 ダークモードをオン','ko':'🌙 다크 모드 켜기','ru':'🌙 Включить тёмный режим','es':'🌙 Activar modo oscuro'},'🌍 中英文切換': {'th':'🌍 ภาษา','ja':'🌍 言語','ko':'🌍 언어','ru':'🌍 Язык','es':'🌍 Idioma'},'中文': {'th':'ภาษาจีน','ja':'中国語','ko':'중국어','ru':'Китайский','es':'Chino'},'目前語言': {'th':'ภาษาปัจจุบัน','ja':'現在の言語','ko':'현재 언어','ru':'Текущий язык','es':'Idioma actual'},'切換語言': {'th':'เปลี่ยนภาษา','ja':'言語を変更','ko':'언어 변경','ru':'Сменить язык','es':'Cambiar idioma'},'取消': {'th':'ยกเลิก','ja':'キャンセル','ko':'취소','ru':'Отмена','es':'Cancelar'},'💾 儲存': {'th':'💾 บันทึก','ja':'💾 保存','ko':'💾 저장','ru':'💾 Сохранить','es':'💾 Guardar'},'✏️ 修改': {'th':'✏️ แก้ไข','ja':'✏️ 編集','ko':'✏️ 수정','ru':'✏️ Изменить','es':'✏️ Editar'},'🗑️ 刪除': {'th':'🗑️ ลบ','ja':'🗑️ 削除','ko':'🗑️ 삭제','ru':'🗑️ Удалить','es':'🗑️ Eliminar'},'煙的品牌': {'th':'แบรนด์บุหรี่','ja':'たばこのブランド','ko':'담배 브랜드','ru':'Бренд сигарет','es':'Marca de cigarrillos'},'煙的名稱': {'th':'ชื่อบุหรี่','ja':'たばこの名前','ko':'담배 이름','ru':'Название сигареты','es':'Nombre del cigarrillo'},'價錢': {'th':'ราคา','ja':'価格','ko':'가격','ru':'Цена','es':'Precio'},'代碼（如有）': {'th':'รหัส (ถ้ามี)','ja':'コード（任意）','ko':'코드(선택)','ru':'Код (необязательно)','es':'Código (opcional)'},'已有香煙相片': {'th':'รูปบุหรี่ที่มีอยู่','ja':'既存の写真','ko':'기존 담배 사진','ru':'Существующее фото','es':'Foto existente'},'訂煙者稱呼': {'th':'ชื่อลูกค้า','ja':'顧客名','ko':'고객 이름','ru':'Имя клиента','es':'Nombre del cliente'},'送貨地點': {'th':'ที่อยู่จัดส่ง','ja':'配送先','ko':'배송 주소','ru':'Адрес доставки','es':'Dirección de entrega'},'電話 / WhatsApp': {'th':'โทรศัพท์ / WhatsApp','ja':'電話 / WhatsApp','ko':'전화 / WhatsApp','ru':'Телефон / WhatsApp','es':'Teléfono / WhatsApp'},'WhatsApp 內容': {'th':'ข้อความ WhatsApp','ja':'WhatsApp メッセージ','ko':'WhatsApp 내용','ru':'Сообщение WhatsApp','es':'Contenido de WhatsApp'},'賣煙者稱呼': {'th':'ชื่อผู้ขาย','ja':'販売者名','ko':'판매자 이름','ru':'Имя продавца','es':'Nombre del vendedor'},'評價': {'th':'คะแนน','ja':'評価','ko':'평가','ru':'Оценка','es':'Valoración'},'評語': {'th':'ความคิดเห็น','ja':'コメント','ko':'의견','ru':'Комментарий','es':'Comentario'},'🔎 搜尋': {'th':'🔎 ค้นหา','ja':'🔎 検索','ko':'🔎 검색','ru':'🔎 Поиск','es':'🔎 Buscar'},'選擇訂煙者': {'th':'เลือกลูกค้า','ja':'顧客を選択','ko':'고객 선택','ru':'Выберите клиента','es':'Seleccionar cliente'},'選擇煙款': {'th':'เลือกบุหรี่','ja':'たばこを選択','ko':'담배 선택','ru':'Выберите сигарету','es':'Seleccionar cigarrillo'},'➕ 增加另一款煙': {'th':'➕ เพิ่มบุหรี่อีกชนิด','ja':'➕ 別のたばこを追加','ko':'➕ 다른 담배 추가','ru':'➕ Добавить ещё один вид','es':'➕ Añadir otro tipo'},'💾 儲存 Order': {'th':'💾 บันทึกคำสั่งซื้อ','ja':'💾 注文を保存','ko':'💾 주문 저장','ru':'💾 Сохранить заказ','es':'💾 Guardar pedido'},'時間': {'th':'เวลา','ja':'日時','ko':'시간','ru':'Время','es':'Hora'},'操作': {'th':'การดำเนินการ','ja':'操作','ko':'작업','ru':'Действия','es':'Acciones'},'品牌：': {'th':'แบรนด์: ','ja':'ブランド: ','ko':'브랜드: ','ru':'Бренд: ','es':'Marca: '},'名稱：': {'th':'ชื่อ: ','ja':'名称: ','ko':'이름: ','ru':'Название: ','es':'Nombre: '},'價錢：': {'th':'ราคา: ','ja':'価格: ','ko':'가격: ','ru':'Цена: ','es':'Precio: '},'無相片': {'th':'ไม่มีรูปภาพ','ja':'写真なし','ko':'사진 없음','ru':'Нет фото','es':'Sin foto'},'移除': {'th':'ลบออก','ja':'削除','ko':'제거','ru':'Удалить','es':'Quitar'},'條': {'th':'มวน','ja':'本','ko':'개비','ru':'шт.','es':'unidad(es)'},'包': {'th':'ซอง','ja':'箱','ko':'갑','ru':'пач.','es':'paquete(s)'},'選擇訂煙 Order': {'th':'เลือกคำสั่งซื้อ','ja':'注文を選択','ko':'주문 선택','ru':'Выберите заказ','es':'Seleccionar pedido'},'請選擇一張訂煙 Order': {'th':'โปรดเลือกคำสั่งซื้อ','ja':'注文を選択してください','ko':'주문을 선택하세요','ru':'Выберите заказ','es':'Selecciona un pedido'},'選擇賣煙者': {'th':'เลือกผู้ขาย','ja':'販売者を選択','ko':'판매자 선택','ru':'Выберите продавца','es':'Seleccionar vendedor'},'請選擇賣煙者': {'th':'โปรดเลือกผู้ขาย','ja':'販売者を選択してください','ko':'판매자를 선택하세요','ru':'Выберите продавца','es':'Selecciona un vendedor'},'📋 複製到剪貼簿': {'th':'📋 คัดลอกไปยังคลิปบอร์ด','ja':'📋 クリップボードにコピー','ko':'📋 클립보드에 복사','ru':'📋 Копировать в буфер','es':'📋 Copiar al portapapeles'},'☠️ 訂煙資料': {'th':'☠️ รายละเอียดคำสั่งซื้อ','ja':'☠️ 注文詳細','ko':'☠️ 주문 정보','ru':'☠️ Данные заказа','es':'☠️ Detalles del pedido'},'💬 WhatsApp': {'th':'💬 WhatsApp','ja':'💬 WhatsApp','ko':'💬 WhatsApp','ru':'💬 WhatsApp','es':'💬 WhatsApp'},'完成': {'th':'เสร็จสิ้น','ja':'完了','ko':'완료','ru':'Завершить','es':'Completar'},'再訂': {'th':'สั่งซ้ำ','ja':'再注文','ko':'재주문','ru':'Повторить заказ','es':'Repetir pedido'},'新增煙款': {'th':'เพิ่มบุหรี่','ja':'たばこを追加','ko':'담배 추가','ru':'Добавить сигарету','es':'Añadir cigarrillo'},'修改煙款': {'th':'แก้ไขบุหรี่','ja':'たばこを編集','ko':'담배 수정','ru':'Изменить сигарету','es':'Editar cigarrillo'},'新增訂煙者': {'th':'เพิ่มลูกค้า','ja':'顧客を追加','ko':'고객 추가','ru':'Добавить клиента','es':'Añadir cliente'},'修改訂煙者': {'th':'แก้ไขลูกค้า','ja':'顧客を編集','ko':'고객 수정','ru':'Изменить клиента','es':'Editar cliente'},'新增賣煙者': {'th':'เพิ่มผู้ขาย','ja':'販売者を追加','ko':'판매자 추가','ru':'Добавить продавца','es':'Añadir vendedor'},'修改賣煙者': {'th':'แก้ไขผู้ขาย','ja':'販売者を編集','ko':'판매자 수정','ru':'Изменить продавца','es':'Editar vendedor'},'📝 新增訂煙 Order': {'th':'📝 เพิ่มคำสั่งซื้อ','ja':'📝 新しい注文','ko':'📝 새 주문','ru':'📝 Новый заказ','es':'📝 Nuevo pedido'},'✏️ 修改訂煙 Order': {'th':'✏️ แก้ไขคำสั่งซื้อ','ja':'✏️ 注文を編集','ko':'✏️ 주문 수정','ru':'✏️ Изменить заказ','es':'✏️ Editar pedido'},'🚬 暫時無資料': {'th':'🚬 ยังไม่มีข้อมูล','ja':'🚬 データはまだありません','ko':'🚬 아직 데이터가 없습니다','ru':'🚬 Пока нет данных','es':'🚬 Aún no hay datos'},'暫時無資料': {'th':'ยังไม่มีข้อมูล','ja':'データはまだありません','ko':'아직 데이터가 없습니다','ru':'Пока нет данных','es':'Aún no hay datos'},}


# Deep multilingual coverage for all fixed UI labels and messages.
DEEP_MULTI_UI_TEXT = {
    '儲存': {'th': 'บันทึก', 'ja': '保存', 'ko': '저장', 'ru': 'Сохранить', 'es': 'Guardar'},
    '條煙': {'th': 'มวน', 'ja': '本', 'ko': '개비', 'ru': 'шт.', 'es': 'cigarrillos'},
    '包煙': {'th': 'ซอง', 'ja': '箱', 'ko': '갑', 'ru': 'пачка', 'es': 'paquete'},
    '⚠️': {'th': '⚠️', 'ja': '⚠️', 'ko': '⚠️', 'ru': '⚠️', 'es': '⚠️'},
    '錯誤': {'th': 'ข้อผิดพลาด', 'ja': 'エラー', 'ko': '오류', 'ru': 'Ошибка', 'es': 'Error'},
    '刪除': {'th': 'ลบ', 'ja': '削除', 'ko': '삭제', 'ru': 'Удалить', 'es': 'Eliminar'},
    '修改': {'th': 'แก้ไข', 'ja': '編集', 'ko': '수정', 'ru': 'Изменить', 'es': 'Editar'},
    '中英文': {'th': 'จีน / อังกฤษ', 'ja': '中国語 / 英語', 'ko': '중국어 / 영어', 'ru': 'Китайский / английский', 'es': 'Chino / inglés'},
    '評價：': {'th': 'คะแนน: ', 'ja': '評価: ', 'ko': '평가: ', 'ru': 'Оценка: ', 'es': 'Valoración: '},
    '訂煙：': {'th': 'คำสั่งซื้อ: ', 'ja': '注文: ', 'ko': '주문: ', 'ru': 'Заказ: ', 'es': 'Pedido: '},
    '新密碼': {'th': 'รหัสผ่านใหม่', 'ja': '新しいパスワード', 'ko': '새 비밀번호', 'ru': 'Новый пароль', 'es': 'Nueva contraseña'},
    '煙款：': {'th': 'บุหรี่: ', 'ja': 'たばこ: ', 'ko': '담배: ', 'ru': 'Сигареты: ', 'es': 'Cigarrillos: '},
    '評語：': {'th': 'ความคิดเห็น: ', 'ja': 'コメント: ', 'ko': '의견: ', 'ru': 'Комментарий: ', 'es': 'Comentario: '},
    '總數：': {'th': 'รวม: ', 'ja': '合計: ', 'ko': '총 수량: ', 'ru': 'Всего: ', 'es': 'Total: '},
    '確定？': {'th': 'ยืนยันหรือไม่?', 'ja': '続行しますか？', 'ko': '계속하시겠습니까?', 'ru': 'Продолжить?', 'es': '¿Continuar?'},
    '目前密碼': {'th': 'รหัสผ่านปัจจุบัน', 'ja': '現在のパスワード', 'ko': '현재 비밀번호', 'ru': 'Текущий пароль', 'es': 'Contraseña actual'},
    '有冇貨？': {'th': 'มีสินค้าไหม?', 'ja': '在庫がありますか？', 'ko': '재고가 있나요?', 'ru': 'Есть в наличии?', 'es': '¿Hay disponibilidad?'},
    '設定錯誤': {'th': 'ข้อผิดพลาดในการตั้งค่า', 'ja': '設定エラー', 'ko': '설정 오류', 'ru': 'Ошибка настроек', 'es': 'Error de configuración'},
    '🚬 登入': {'th': '🚬 เข้าสู่ระบบ', 'ja': '🚬 ログイン', 'ko': '🚬 로그인', 'ru': '🚬 Войти', 'es': '🚬 Iniciar sesión'},
    '賣煙者：': {'th': 'ผู้ขาย: ', 'ja': '販売者: ', 'ko': '판매자: ', 'ru': 'Продавец: ', 'es': 'Vendedor: '},
    '有煙食喇': {'th': 'มีบุหรี่แล้ว', 'ja': 'たばこがあります', 'ko': '담배가 있습니다', 'ru': 'Сигареты в наличии', 'es': 'Hay cigarrillos'},
    '新登入名': {'th': 'ชื่อผู้ใช้ใหม่', 'ja': '新しいユーザー名', 'ko': '새 사용자 이름', 'ru': 'Новое имя пользователя', 'es': 'Nuevo nombre de usuario'},
    '目前登入名': {'th': 'ชื่อผู้ใช้ปัจจุบัน', 'ja': '現在のユーザー名', 'ko': '현재 사용자 이름', 'ru': 'Текущее имя пользователя', 'es': 'Nombre de usuario actual'},
    '送貨地點：': {'th': 'ที่อยู่จัดส่ง: ', 'ja': '配送先: ', 'ko': '배송 주소: ', 'ru': 'Адрес доставки: ', 'es': 'Dirección de entrega: '},
    '訂煙者資料': {'th': 'ข้อมูลลูกค้า', 'ja': '顧客情報', 'ko': '고객 정보', 'ru': 'Данные клиента', 'es': 'Datos del cliente'},
    '切換夜間模式': {'th': 'สลับโหมดกลางคืน', 'ja': 'ダークモード切替', 'ko': '다크 모드 전환', 'ru': 'Переключить тёмный режим', 'es': 'Cambiar modo oscuro'},
    '背景顏色預覽': {'th': 'ตัวอย่างสีพื้นหลัง', 'ja': '背景色プレビュー', 'ko': '배경색 미리보기', 'ru': 'Предпросмотр цвета фона', 'es': 'Vista previa del color de fondo'},
    '系統透明化：': {'th': 'ความโปร่งใสของระบบ: ', 'ja': 'システム透明度: ', 'ko': '시스템 투명도: ', 'ru': 'Прозрачность системы: ', 'es': 'Transparencia del sistema: '},
    '💀 儲存背景': {'th': '💀 บันทึกพื้นหลัง', 'ja': '💀 背景を保存', 'ko': '💀 배경 저장', 'ru': '💀 Сохранить фон', 'es': '💀 Guardar fondo'},
    '最後修改時間': {'th': 'เวลาที่แก้ไขล่าสุด', 'ja': '最終更新日時', 'ko': '마지막 수정 시간', 'ru': 'Время последнего изменения', 'es': 'Última modificación'},
    '最後修改時間：': {'th': 'เวลาที่แก้ไขล่าสุด: ', 'ja': '最終更新日時: ', 'ko': '마지막 수정 시간: ', 'ru': 'Время последнего изменения: ', 'es': 'Última modificación: '},
    '如有貨，送去：': {'th': 'ถ้ามีสินค้า กรุณาส่งไปที่:', 'ja': '在庫があれば配送先:', 'ko': '재고가 있으면 배송지:', 'ru': 'Если есть в наличии, доставить:', 'es': 'Si está disponible, entregar en:'},
    'English': {'th': 'ภาษาอังกฤษ', 'ja': '英語', 'ko': '영어', 'ru': 'Английский', 'es': 'Inglés'},
    '⚙️ 系統設定': {'th': '⚙️ การตั้งค่าระบบ', 'ja': '⚙️ システム設定', 'ko': '⚙️ 시스템 설정', 'ru': '⚙️ Системные настройки', 'es': '⚙️ Configuración del sistema'},
    '💾 儲存透明度': {'th': '💾 บันทึกความโปร่งใส', 'ja': '💾 透明度を保存', 'ko': '💾 투명도 저장', 'ru': '💾 Сохранить прозрачность', 'es': '💾 Guardar transparencia'},
    'Secret：': {'th': 'Secret: ', 'ja': 'シークレット: ', 'ko': '시크릿: ', 'ru': 'Секрет: ', 'es': 'Secreto: '},
    '儲存新登入資料': {'th': 'บันทึกข้อมูลเข้าสู่ระบบใหม่', 'ja': '新しいログイン情報を保存', 'ko': '새 로그인 정보 저장', 'ru': 'Сохранить новые данные входа', 'es': 'Guardar nuevos datos de inicio de sesión'},
    '確定刪除呢款煙？': {'th': 'ยืนยันการลบบุหรี่นี้หรือไม่?', 'ja': 'このたばこを削除しますか？', 'ko': '이 담배를 삭제하시겠습니까?', 'ru': 'Удалить эту сигарету?', 'es': '¿Eliminar este cigarrillo?'},
    '💾 儲存2FA開關': {'th': '💾 บันทึกการตั้งค่า 2FA', 'ja': '💾 2FA設定を保存', 'ko': '💾 2FA 설정 저장', 'ru': '💾 Сохранить настройку 2FA', 'es': '💾 Guardar configuración 2FA'},
    '2FA 驗證失敗。': {'th': 'การยืนยัน 2FA ล้มเหลว', 'ja': '2FA認証に失敗しました。', 'ko': '2FA 인증에 실패했습니다.', 'ru': 'Ошибка проверки 2FA.', 'es': 'Falló la verificación 2FA.'},
    '🪟 透明化顯示比例': {'th': '🪟 ความโปร่งใส', 'ja': '🪟 ความโปร่งใส', 'ko': '🪟 투명도', 'ru': '🪟 Прозрачность', 'es': '🪟 Transparencia'},
    '新 admin 密碼': {'th': 'รหัสผ่าน admin ใหม่', 'ja': '新しいadminパスワード', 'ko': '새 admin 비밀번호', 'ru': 'Новый пароль admin', 'es': 'Nueva contraseña de admin'},
    '確定刪除呢位賣煙者？': {'th': 'ยืนยันการลบผู้ขายรายนี้หรือไม่?', 'ja': 'この販売者を削除しますか？', 'ko': '이 판매자를 삭제하시겠습니까?', 'ru': 'Удалить этого продавца?', 'es': '¿Eliminar este vendedor?'},
    '食少支煙啦屌你味道！': {'th': 'สูบบุหรี่ให้น้อยลงเถอะโว้ย!', 'ja': 'タバコを少し減らそうぜ！', 'ko': '담배 좀 줄이세요!', 'ru': 'Кури поменьше, чёрт возьми!', 'es': '¡Fuma menos, joder!'},
    '登入名稱或密碼錯誤。': {'th': 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'ja': 'ユーザー名またはパスワードが正しくありません。', 'ko': '사용자 이름 또는 비밀번호가 올바르지 않습니다.', 'ru': 'Неверное имя пользователя или пароль.', 'es': 'Nombre de usuario o contraseña incorrectos.'},
    '🔐 更改登入名和密碼': {'th': '🔐 เปลี่ยนชื่อผู้ใช้และรหัสผ่าน', 'ja': '🔐 ユーザー名とパスワードを変更', 'ko': '🔐 사용자 이름 및 비밀번호 변경', 'ru': '🔐 Изменить имя пользователя и пароль', 'es': '🔐 Cambiar nombre de usuario y contraseña'},
    '確定刪除呢位訂煙者？': {'th': 'ยืนยันการลบลูกค้ารายนี้หรือไม่?', 'ja': 'この顧客を削除しますか？', 'ko': '이 고객을 삭제하시겠습니까?', 'ru': 'Удалить этого клиента?', 'es': '¿Eliminar este cliente?'},
    'admin 密碼錯誤。': {'th': 'รหัสผ่าน admin ไม่ถูกต้อง', 'ja': 'adminパスワードが正しくありません。', 'ko': 'admin 비밀번호가 올바르지 않습니다.', 'ru': 'Неверный пароль admin.', 'es': 'Contraseña de admin incorrecta.'},
    '有冇貨？如有貨，送去：': {'th': 'มีสินค้าไหม? ถ้ามี กรุณาส่งไปที่:', 'ja': '在庫がありますか？あれば配送先:', 'ko': '재고가 있나요? 있다면 배송지:', 'ru': 'Есть в наличии? Если да, доставить:', 'es': '¿Hay disponibilidad? Si la hay, entregar a:'},
    '選擇後會顯示煙款及數量': {'th': 'เลือกแล้วจะแสดงชนิดและจำนวนบุหรี่', 'ja': '選択するとたばこの種類と数量が表示されます', 'ko': '선택하면 담배 종류와 수량이 표시됩니다', 'ru': 'После выбора отобразятся сигареты и количество', 'es': 'Después de seleccionar se mostrarán los cigarrillos y cantidades'},
    '目前 admin 密碼': {'th': 'รหัสผ่าน admin ปัจจุบัน', 'ja': '現在のadminパスワード', 'ko': '현재 admin 비밀번호', 'ru': 'Текущий пароль admin', 'es': 'Contraseña de admin actual'},
    '更新 admin 密碼': {'th': 'อัปเดตรหัสผ่าน admin', 'ja': 'adminパスワードを更新', 'ko': 'admin 비밀번호 업데이트', 'ru': 'Обновить пароль admin', 'es': 'Actualizar contraseña de admin'},
    'Choose file': {'th': 'เลือกไฟล์', 'ja': 'ファイルを選択', 'ko': '파일 선택', 'ru': 'Выбрать файл', 'es': 'Elegir archivo'},
    '尚未產生 2FA 金鑰。': {'th': 'ยังไม่ได้สร้างคีย์ 2FA', 'ja': '2FAキーはまだ生成されていません。', 'ko': '아직 2FA 키가 생성되지 않았습니다.', 'ru': 'Ключ 2FA ещё не создан.', 'es': 'Aún no se ha generado la clave 2FA.'},
    'WhatsApp 內容：': {'th': 'ข้อความ WhatsApp: ', 'ja': 'WhatsAppメッセージ: ', 'ko': 'WhatsApp 내용: ', 'ru': 'Сообщение WhatsApp: ', 'es': 'Contenido de WhatsApp: '},
    '目前登入名稱或密碼錯誤。': {'th': 'ชื่อผู้ใช้หรือรหัสผ่านปัจจุบันไม่ถูกต้อง', 'ja': '現在のユーザー名またはパスワードが正しくありません。', 'ko': '현재 사용자 이름 또는 비밀번호가 올바르지 않습니다.', 'ru': 'Текущее имя пользователя или пароль неверны.', 'es': 'El nombre de usuario o contraseña actuales son incorrectos.'},
    '啟用雙重認證（TOTP）': {'th': 'เปิดใช้งานการยืนยันสองขั้นตอน (TOTP)', 'ja': '二要素認証（TOTP）を有効にする', 'ko': '2단계 인증(TOTP) 활성화', 'ru': 'Включить двухфакторную аутентификацию (TOTP)', 'es': 'Activar autenticación de dos factores (TOTP)'},
    '電話 / WhatsApp：': {'th': 'โทรศัพท์ / WhatsApp: ', 'ja': '電話 / WhatsApp: ', 'ko': '전화 / WhatsApp: ', 'ru': 'Телефон / WhatsApp: ', 'es': 'Teléfono / WhatsApp: '},
    '選擇煙款後顯示完整資料及相片': {'th': 'หลังเลือกบุหรี่จะแสดงข้อมูลและรูปภาพทั้งหมด', 'ja': 'たばこを選択すると詳細情報と写真が表示されます', 'ko': '담배를 선택하면 전체 정보와 사진이 표시됩니다', 'ru': 'После выбора отобразятся подробности и фото', 'es': 'Después de seleccionar se mostrarán los detalles y la foto'},
    '登入頁面已失效，請重新整理頁面。': {'th': 'หน้าล็อกอินหมดอายุ กรุณาโหลดหน้าใหม่', 'ja': 'ログインページの有効期限が切れました。更新してください。', 'ko': '로그인 페이지가 만료되었습니다. 새로고침하세요.', 'ru': 'Страница входа устарела. Обновите страницу.', 'es': 'La página de inicio de sesión ha caducado. Actualiza la página.'},
    '人到40要保養下，少煙酒呀🤣': {'th': 'อายุ 40 แล้วดูแลตัวเองหน่อย ลดบุหรี่และเหล้านะ 🤣', 'ja': '40歳になったら体を大切に。タバコとお酒はほどほどに🤣', 'ko': '40살이면 몸 좀 챙기고 담배와 술을 줄이세요 🤣', 'ru': 'После 40 береги здоровье, поменьше сигарет и алкоголя 🤣', 'es': 'A los 40 cuídate, menos tabaco y alcohol 🤣'},
    '☠️ 更改 admin 密碼': {'th': '☠️ เปลี่ยนรหัสผ่าน admin', 'ja': '☠️ adminパスワードを変更', 'ko': '☠️ admin 비밀번호 변경', 'ru': '☠️ Изменить пароль admin', 'es': '☠️ Cambiar contraseña de admin'},
    '香港政府忠告市民吸煙危害健康': {'th': 'รัฐบาลฮ่องกงเตือนประชาชนว่าการสูบบุหรี่เป็นอันตรายต่อสุขภาพ', 'ja': '香港政府は喫煙が健康に有害であると市民に注意喚起しています', 'ko': '홍콩 정부는 흡연이 건강에 해롭다고 시민에게 경고합니다', 'ru': 'Правительство Гонконга предупреждает: курение опасно для здоровья', 'es': 'El Gobierno de Hong Kong advierte que fumar es perjudicial para la salud'},
    '目前 admin 密碼錯誤。': {'th': 'รหัสผ่าน admin ปัจจุบันไม่ถูกต้อง', 'ja': '現在のadminパスワードが正しくありません。', 'ko': '현재 admin 비밀번호가 올바르지 않습니다.', 'ru': 'Текущий пароль admin неверен.', 'es': 'La contraseña de admin actual es incorrecta.'},
    '🔐 驗證並顯示 QR Code': {'th': '🔐 ยืนยันและแสดง QR Code', 'ja': '🔐 認証してQRコードを表示', 'ko': '🔐 인증 후 QR 코드 표시', 'ru': '🔐 Проверить и показать QR-код', 'es': '🔐 Verificar y mostrar código QR'},
    '確定刪除呢張訂煙 Order？': {'th': 'ยืนยันการลบคำสั่งซื้อนี้หรือไม่?', 'ja': 'この注文を削除しますか？', 'ko': '이 주문을 삭제하시겠습니까?', 'ru': 'Удалить этот заказ?', 'es': '¿Eliminar este pedido?'},
    '5% 最透明\u3000\u3000100% 不透明': {'th': '5% โปร่งใสที่สุด\u3000\u3000100% ทึบแสง', 'ja': '5%が最も透明\u3000\u3000100%が不透明', 'ko': '5% 가장 투명\u3000\u3000100% 불투명', 'ru': '5% — максимум прозрачности\u3000\u3000100% — непрозрачно', 'es': '5% más transparente\u3000\u3000100% opaco'},
    '要量入為出，食10條買返16條🤣': {'th': 'ใช้เงินอย่างมีสติ สูบ 10 ซองแต่ซื้อกลับ 16 ซอง 🤣', 'ja': '収入に合わせて生活しよう。10箱吸って16箱買う🤣', 'ko': '수입에 맞게 살자. 10갑 피우고 16갑 사기 🤣', 'ru': 'Живи по средствам: выкури 10 пачек, а купи 16 🤣', 'es': 'Vive según tus posibilidades: fuma 10 paquetes y compra 16 🤣'},
    '👁️ 顯示/隱藏 QR Code': {'th': '👁️ แสดง/ซ่อน QR Code', 'ja': '👁️ QRコードを表示/非表示', 'ko': '👁️ QR 코드 표시/숨기기', 'ru': '👁️ Показать/скрыть QR-код', 'es': '👁️ Mostrar/ocultar código QR'},
    '建立每一行獨立訂煙 Order。': {'th': 'สร้างคำสั่งซื้อแยกสำหรับแต่ละรายการ', 'ja': '各行ごとに個別の注文を作成します。', 'ko': '각 행마다 개별 주문을 생성합니다.', 'ru': 'Создайте отдельный заказ для каждой строки.', 'es': 'Crear un pedido independiente para cada línea.'},
    '管理品牌、名稱、價錢、代碼及相片。': {'th': 'จัดการแบรนด์ ชื่อ ราคา รหัส และรูปภาพ', 'ja': 'ブランド、名前、価格、コード、写真を管理します。', 'ko': '브랜드, 이름, 가격, 코드 및 사진을 관리합니다.', 'ru': 'Управление брендами, названиями, ценами, кодами и фото.', 'es': 'Gestiona marcas, nombres, precios, códigos y fotos.'},
    '如不重新上載相片，會保留原有相片。': {'th': 'หากไม่อัปโหลดรูปใหม่ จะเก็บรูปเดิมไว้', 'ja': '新しい写真をアップロードしない場合、既存の写真を保持します。', 'ko': '새 사진을 업로드하지 않으면 기존 사진을 유지합니다.', 'ru': 'Если новое фото не загружать, сохранится старое.', 'es': 'Si no subes una foto nueva, se conservará la existente.'},
    '行萬里路，唔好食萬寶路，因為唔夠氣🤣': {'th': 'เดินทางให้ไกล แต่อย่าสูบ Marlboro เพราะหายใจไม่พอ 🤣', 'ja': '遠くまで旅しよう。でもマルボロは吸わないで、息が続かないから🤣', 'ko': '멀리 여행하되 말보로는 피우지 마세요. 숨이 찹니다 🤣', 'ru': 'Путешествуй далеко, но не кури Marlboro — дыхания не хватит 🤣', 'es': 'Viaja lejos, pero no fumes Marlboro: te faltará el aire 🤣'},
    '📱 雙重認證（2FA / TOTP）': {'th': '📱 การยืนยันสองขั้นตอน (2FA / TOTP)', 'ja': '📱 二要素認証（2FA / TOTP）', 'ko': '📱 2단계 인증(2FA / TOTP)', 'ru': '📱 Двухфакторная аутентификация (2FA / TOTP)', 'es': '📱 Autenticación de dos factores (2FA / TOTP)'},
    'CSRF 驗證失敗，請重新整理頁面。': {'th': 'การตรวจสอบ CSRF ล้มเหลว กรุณาโหลดหน้าใหม่', 'ja': 'CSRF検証に失敗しました。ページを更新してください。', 'ko': 'CSRF 검증에 실패했습니다. 페이지를 새로고침하세요.', 'ru': 'Проверка CSRF не удалась. Обновите страницу.', 'es': 'La verificación CSRF falló. Actualiza la página.'},
    '重新產生後舊 Code 即刻失效，確定？': {'th': 'การสร้างใหม่จะทำให้โค้ดเดิมใช้ไม่ได้ทันที ดำเนินการต่อหรือไม่?', 'ja': '再生成すると古いコードは無効になります。続行しますか？', 'ko': '재생성하면 기존 코드가 즉시 무효화됩니다. 계속하시겠습니까?', 'ru': 'После генерации старый код сразу станет недействительным. Продолжить?', 'es': 'Regenerar invalidará inmediatamente el código anterior. ¿Continuar?'},
    '煙款（同一張 Order 可加入多款煙）': {'th': 'บุหรี่ (หนึ่งคำสั่งซื้อสามารถมีหลายชนิด)', 'ja': 'たばこ（1件の注文に複数種類を追加できます）', 'ko': '담배(한 주문에 여러 종류 추가 가능)', 'ru': 'Сигареты (в одном заказе можно добавить несколько видов)', 'es': 'Cigarrillos (se pueden añadir varios tipos a un pedido)'},
    '2FA 驗證工作階段已失效，請重新登入。': {'th': 'เซสชันยืนยัน 2FA หมดอายุ กรุณาเข้าสู่ระบบใหม่', 'ja': '2FA認証セッションの有効期限が切れました。再度ログインしてください。', 'ko': '2FA 인증 세션이 만료되었습니다. 다시 로그인하세요.', 'ru': 'Сеанс проверки 2FA истёк. Войдите снова.', 'es': 'La sesión de verificación 2FA ha caducado. Inicia sesión de nuevo.'},
    '按一下即時切換，不使用 checkbox。': {'th': 'คลิกเพื่อสลับทันที ไม่ใช้ checkbox', 'ja': 'クリックすると即時切り替え。チェックボックスは使用しません。', 'ko': '클릭하면 즉시 전환되며 체크박스를 사용하지 않습니다.', 'ru': 'Нажмите для мгновенного переключения; флажок не используется.', 'es': 'Haz clic para cambiar al instante; no se usa casilla.'},
    '管理訂煙者及 WhatsApp 聯絡資料。': {'th': 'จัดการลูกค้าและข้อมูลติดต่อ WhatsApp', 'ja': '顧客とWhatsApp連絡先を管理します。', 'ko': '고객 및 WhatsApp 연락처를 관리합니다.', 'ru': 'Управление клиентами и контактами WhatsApp.', 'es': 'Gestiona clientes y datos de contacto de WhatsApp.'},
    '♻️ 重新產生金鑰（舊 Code 即刻失效）': {'th': '♻️ สร้างคีย์ใหม่ (โค้ดเดิมใช้ไม่ได้ทันที)', 'ja': '♻️ キーを再生成（旧コードは直ちに無効）', 'ko': '♻️ 키 재생성(기존 코드 즉시 무효화)', 'ru': '♻️ Создать новый ключ (старый код сразу недействителен)', 'es': '♻️ Regenerar clave (el código anterior caduca de inmediato)'},
    '輸入 admin 密碼後顯示 QR Code': {'th': 'ป้อนรหัสผ่าน admin เพื่อแสดง QR Code', 'ja': 'adminパスワードを入力してQRコードを表示', 'ko': 'admin 비밀번호를 입력하면 QR 코드가 표시됩니다', 'ru': 'Введите пароль admin, чтобы показать QR-код', 'es': 'Introduce la contraseña de admin para mostrar el código QR'},
    '按煙款選擇後產生落單 WhatsApp 訊息。': {'th': 'เลือกบุหรี่แล้วสร้างข้อความสั่งซื้อ WhatsApp', 'ja': 'たばこを選択してWhatsApp注文メッセージを作成します。', 'ko': '담배를 선택해 WhatsApp 주문 메시지를 생성합니다.', 'ru': 'Создайте сообщение WhatsApp для заказа после выбора сигарет.', 'es': 'Genera un mensaje de pedido de WhatsApp al seleccionar cigarrillos.'},
    '墨西哥亡靈節主題 · 訂煙、記錄、落單集中管理': {'th': 'ธีมวันแห่งความตายเม็กซิโก · จัดการบุหรี่ ประวัติ และคำสั่งซื้อในที่เดียว', 'ja': 'メキシコの死者の日テーマ · たばこ・履歴・注文を一元管理', 'ko': '멕시코 망자의 날 테마 · 담배, 기록, 주문을 한곳에서 관리', 'ru': 'Тема мексиканского Дня мёртвых · сигареты, история и заказы в одном месте', 'es': 'Tema del Día de Muertos mexicano · gestiona cigarrillos, registros y pedidos en un solo lugar'},
    '記住我（只限此裝置及此 Browser，永久至登出）': {'th': 'จดจำฉัน (เฉพาะอุปกรณ์และเบราว์เซอร์นี้ จนกว่าจะออกจากระบบ)', 'ja': 'ログイン状態を記憶（この端末・ブラウザのみ、ログアウトまで）', 'ko': '기억하기(이 기기 및 브라우저에서만, 로그아웃할 때까지)', 'ru': 'Запомнить меня (только это устройство и браузер, до выхода)', 'es': 'Recordarme (solo este dispositivo y navegador, hasta cerrar sesión)'},
    '請輸入 Authenticator App 顯示的 6 位數字': {'th': 'ป้อนรหัส 6 หลักจากแอป Authenticator', 'ja': 'Authenticatorアプリに表示された6桁のコードを入力してください', 'ko': 'Authenticator 앱에 표시된 6자리 코드를 입력하세요', 'ru': 'Введите 6-значный код из приложения Authenticator', 'es': 'Introduce los 6 dígitos mostrados en la aplicación Authenticator'},
    'QR code library unavailable. Run:': {'th': 'ไม่มีไลบรารี QR code กรุณารัน:', 'ja': 'QRコードライブラリがありません。実行:', 'ko': 'QR 코드 라이브러리를 사용할 수 없습니다. 실행:', 'ru': 'Библиотека QR-кодов недоступна. Выполните:', 'es': 'Biblioteca de códigos QR no disponible. Ejecuta:'},
    '搜尋煙名稱、價錢、代碼、數量、訂煙者稱呼、電話 / WhatsApp': {'th': 'ค้นหาชื่อบุหรี่ ราคา รหัส จำนวน ชื่อลูกค้า โทรศัพท์ / WhatsApp', 'ja': 'たばこの名前、価格、コード、数量、顧客名、電話 / WhatsAppを検索', 'ko': '담배 이름, 가격, 코드, 수량, 고객 이름, 전화 / WhatsApp 검색', 'ru': 'Поиск по названию, цене, коду, количеству, клиенту, телефону / WhatsApp', 'es': 'Buscar nombre, precio, código, cantidad, cliente, teléfono / WhatsApp'},
    '每張 Order 可包含多款煙，會一次過產生 WhatsApp 訊息。': {'th': 'แต่ละคำสั่งซื้อมีบุหรี่หลายชนิดได้ และสร้างข้อความ WhatsApp ครั้งเดียว', 'ja': '1件の注文に複数のたばこを含め、WhatsAppメッセージを一度に作成できます。', 'ko': '각 주문에 여러 담배를 포함하고 WhatsApp 메시지를 한 번에 생성합니다.', 'ru': 'Каждый заказ может содержать несколько видов сигарет, сообщение WhatsApp создаётся сразу.', 'es': 'Cada pedido puede incluir varios tipos de cigarrillos y generar un mensaje de WhatsApp.'},
    '預設會按 Browser 語言自動切換；手動選擇後會記住此 Browser 的設定。': {'th': 'ระบบจะเปลี่ยนตามภาษาของเบราว์เซอร์โดยอัตโนมัติ และจะจำภาษาที่เลือกไว้ในเบราว์เซอร์นี้', 'ja': 'デフォルトではブラウザ言語に合わせて切り替わり、手動選択後はこのブラウザに保存されます。', 'ko': '기본적으로 브라우저 언어를 따르며 수동 선택 후 이 브라우저에 저장됩니다.', 'ru': 'По умолчанию используется язык браузера; после ручного выбора настройка сохраняется в этом браузере.', 'es': 'Por defecto se usa el idioma del navegador; tras elegirlo manualmente se guarda en este navegador.'},
    '語言 / Language': {'th': 'ภาษา / Language', 'ja': '言語 / Language', 'ko': '언어 / Language', 'ru': 'Язык / Language', 'es': 'Idioma / Language'},
    'Browser 自動': {'th': 'อัตโนมัติตามเบราว์เซอร์', 'ja': 'ブラウザ自動', 'ko': '브라우저 자동', 'ru': 'Авто по браузеру', 'es': 'Automático del navegador'},
    '繁體中文': {'th': 'ภาษาจีนตัวเต็ม', 'ja': '繁体中国語', 'ko': '번체 중국어', 'ru': 'Традиционный китайский', 'es': 'Chino tradicional'},
    '目前語言：': {'th': 'ภาษาปัจจุบัน: ', 'ja': '現在の言語: ', 'ko': '현재 언어: ', 'ru': 'Текущий язык: ', 'es': 'Idioma actual: '},
    '輸出落單頁面。': {'th': 'ส่งออกหน้าสั่งซื้อ', 'ja': '注文ページを出力します。', 'ko': '주문 페이지를 출력합니다.', 'ru': 'Открыть страницу заказа.', 'es': 'Mostrar página de pedido.'},
    '完了': {'th': 'เสร็จสิ้น', 'ja': '完了', 'ko': '완료', 'ru': 'Готово', 'es': 'Completado'},
    '再注文': {'th': 'สั่งซื้ออีกครั้ง', 'ja': '再注文', 'ko': '재주문', 'ru': 'Повторить заказ', 'es': 'Volver a pedir'},
}
THEME_UI_TEXT = {
    '主題和特效模式': {'th':'โหมดธีมและเอฟเฟกต์','ja':'テーマとエフェクト','ko':'테마 및 효과 모드','ru':'Режим тем и эффектов','es':'Modo de temas y efectos'},
    '日間和夜間模式': {'th':'โหมดกลางวันและกลางคืน','ja':'昼夜モード','ko':'주간 및 야간 모드','ru':'Дневной и ночной режим','es':'Modo día y noche'},
    '💀 墨西哥亡靈節主題': {'th':'💀 ธีมวันแห่งความตายเม็กซิโก','ja':'💀 メキシコ死者の日テーマ','ko':'💀 멕시코 망자의 날 테마','ru':'💀 Тема мексиканского Дня мёртвых','es':'💀 Tema del Día de Muertos'},
    '💃 Disco 主題': {'th':'💃 ธีมดิสโก้','ja':'💃 ディスコテーマ','ko':'💃 디스코 테마','ru':'💃 Диско-тема','es':'💃 Tema disco'},
    '💎 Liquid Glass 主題': {'th':'💎 ธีม Liquid Glass','ja':'💎 Liquid Glassテーマ','ko':'💎 Liquid Glass 테마','ru':'💎 Тема Liquid Glass','es':'💎 Tema Liquid Glass'},
    '🐱 可愛貓狗花草主題': {'th':'🐱 ธีมแมวหมาน่ารักและดอกไม้','ja':'🐱 かわいい猫犬と花のテーマ','ko':'🐱 귀여운 고양이 강아지 꽃 테마','ru':'🐱 Тема милых котиков, собак и цветов','es':'🐱 Tema de gatos, perros y flores'},
    'Browser 自動偵測': {'th':'ตรวจจับอัตโนมัติจากเบราว์เซอร์','ja':'ブラウザ自動検出','ko':'브라우저 자동 감지','ru':'Автоопределение браузера','es':'Detección automática del navegador'},
}
MULTI_UI_TEXT.update(THEME_UI_TEXT)
# Register deep-only labels so ensure_i18n persists their translations in config.json.
DEFAULT_UI_TEXT.update({k: k for k in {**DEEP_MULTI_UI_TEXT, **THEME_UI_TEXT} if k not in DEFAULT_UI_TEXT})

def ensure_i18n(c):
    changed = False
    if c.get("language") not in SUPPORTED_LANGUAGES:
        c["language"] = "zh-Hant"; changed = True
    ui = c.get("ui_text")
    if not isinstance(ui, dict):
        ui = {}; c["ui_text"] = ui; changed = True
    for zh, en in DEFAULT_UI_TEXT.items():
        if zh not in ui or not isinstance(ui.get(zh), dict):
            ui[zh] = {"zh-Hant": zh, "en": en, **MULTI_UI_TEXT.get(zh, {})}; changed = True
        else:
            if "zh-Hant" not in ui[zh]: ui[zh]["zh-Hant"] = zh; changed = True
            if "en" not in ui[zh]: ui[zh]["en"] = en; changed = True
            for _lang, _txt in MULTI_UI_TEXT.get(zh, {}).items():
                if _lang not in ui[zh]: ui[zh][_lang] = _txt; changed = True
    # One-time translation migration: older config.json files may contain only
    # partial English translations from the previous multilingual release.
    if c.get("ui_text_version", 0) < 5:
        for _key, _en in DEFAULT_UI_TEXT.items():
            _item = c["ui_text"].setdefault(_key, {"zh-Hant": _key, "en": _en})
            if not isinstance(_item, dict):
                _item = {"zh-Hant": _key, "en": _en}; c["ui_text"][_key] = _item
            _item["zh-Hant"] = _key
            _item["en"] = _en
            for _lang, _txt in MULTI_UI_TEXT.get(_key, {}).items():
                _item[_lang] = _txt
        c["ui_text_version"] = 5
        changed = True
    if changed: save_json(CONFIG_FILE, c)
    return c

def config():
    c = load_json(CONFIG_FILE, {})
    changed = False
    defaults = {
        "username": DEFAULT_LOGIN, "password": DEFAULT_PASSWORD,
        "admin_password": DEFAULT_ADMIN_PASSWORD,
        "background": {"type": "color", "value": "#120808", "mode": "fill"},
        "dark_mode": True, "theme": "dayofdead", "transparency": 50, "totp": {"enabled": False, "secret": ""}
    }
    for k, v in defaults.items():
        if k not in c:
            c[k] = v; changed = True
    if "totp" not in c or not isinstance(c["totp"], dict):
        c["totp"] = defaults["totp"]; changed = True
    if changed: save_json(CONFIG_FILE, c)
    c = ensure_i18n(c)
    request_lang = REQUEST_LANGUAGE.get()
    if request_lang in SUPPORTED_LANGUAGES:
        c["language"] = request_lang
    return c

def localize_html(value, c=None):
    c = c or config()
    lang = c.get("language", "zh-Hant")
    if lang == "zh-Hant": return str(value)
    ui = c.get("ui_text", {})
    out = str(value)
    pairs=[]
    for zh,item in ui.items():
        if isinstance(item,dict):
            target=item.get(lang) or item.get("en",zh)
            if zh != target: pairs.append((zh,target))
    if pairs:
        pattern=re.compile("|".join(re.escape(zh) for zh,_ in sorted(pairs,key=lambda x:len(x[0]),reverse=True)))
        lookup=dict(pairs)
        out=pattern.sub(lambda m: lookup[m.group(0)], out)
    return out

def t(text, c=None):
    return localize_html(text, c)


def session_secret():
    if not SESSION_SECRET_FILE.exists():
        SESSION_SECRET_FILE.write_text(secrets.token_hex(32), encoding="ascii")
        try: os.chmod(SESSION_SECRET_FILE, 0o600)
        except OSError: pass
    return SESSION_SECRET_FILE.read_text(encoding="ascii").strip()

SECRET = session_secret()
SESSIONS = {}

def remember_store():
    return load_json(REMEMBER_FILE, {})

def make_remember_token(username):
    raw=secrets.token_urlsafe(48)
    data=remember_store(); data[hashlib.sha256(raw.encode()).hexdigest()]={"user":username,"created":time.time()}; save_json(REMEMBER_FILE,data)
    return raw + "." + sign(raw)

def valid_remember_token(value):
    try:
        raw,sig=value.rsplit(".",1)
        if not hmac.compare_digest(sig,sign(raw)): return None
        data=remember_store().get(hashlib.sha256(raw.encode()).hexdigest())
        return data.get("user") if data else None
    except Exception: return None

def revoke_remember_token(value):
    try:
        raw,sig=value.rsplit(".",1)
        if not hmac.compare_digest(sig,sign(raw)): return
        data=remember_store(); data.pop(hashlib.sha256(raw.encode()).hexdigest(),None); save_json(REMEMBER_FILE,data)
    except Exception: pass
LOCK = __import__('threading').RLock()


def sign(value):
    return hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session(username, remember=False):
    sid = secrets.token_urlsafe(32)
    with LOCK: SESSIONS[sid] = {"user": username, "created": time.time(), "remember": remember, "csrf": secrets.token_urlsafe(24)}
    return sid


def totp_code(secret, for_time=None):
    if not secret: return ""
    try: key = base64.b32decode(secret.upper() + "=" * ((8-len(secret)%8)%8))
    except Exception: return ""
    counter = int((for_time or time.time()) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    n = struct.unpack(">I", digest[offset:offset+4])[0] & 0x7fffffff
    return f"{n % 1000000:06d}"


def valid_totp(code, secret):
    code = str(code).strip()
    return bool(re.fullmatch(r"\d{6}", code)) and any(hmac.compare_digest(code, totp_code(secret, time.time()+i*30)) for i in (-1,0,1))


def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def qr_svg(data):
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
        import io
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=4)
        qr.add_data(data); qr.make(fit=True)
        out = io.BytesIO(); qr.make_image(image_factory=SvgPathImage).save(out)
        return out.getvalue().decode("utf-8")
    except Exception as e:
        return f'<div class="notice danger">QR code library unavailable. Run: <code>python3 -m pip install -r requirements.txt</code><br>{html.escape(str(e))}</div>'


def esc(v): return html.escape(str(v or ""), quote=True)

def nav_active(page, current): return "active" if page == current else ""


THEMES = ('dayofdead','disco','liquidglass','cute')
THEME_LABEL_KEYS = {'dayofdead':'💀 墨西哥亡靈節主題','disco':'💃 Disco 主題','liquidglass':'💎 Liquid Glass 主題','cute':'🐱 可愛貓狗花草主題'}
def theme_name(c):
    value=c.get('theme','dayofdead')
    return value if value in THEMES else 'dayofdead'
def theme_css():
    return 'body.theme-disco{--accent:#ff4fd8;--red:#7b4dff;background:radial-gradient(circle at 20% 15%,#ff3cac33,transparent 28%),radial-gradient(circle at 80% 30%,#00e5ff2b,transparent 25%),linear-gradient(135deg,#09051a99,#1a083099 45%,#061c2d99),url("https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=2400&q=85") center/cover fixed!important}body.theme-disco:after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:transparent;animation:discoBg 8s ease-in-out infinite alternate}\nbody.theme-disco:before{background:radial-gradient(circle at 30% 30%,#ff00cc2b,transparent 18%),radial-gradient(circle at 70% 60%,#00ffff25,transparent 20%),linear-gradient(#08001866,#00000088)}\n.guest.theme-disco .loginbox{position:fixed!important;left:50%!important;right:auto!important;top:auto!important;bottom:30px!important;transform:translateX(-50%)!important;width:min(300px,calc(100vw - 24px))!important;max-width:300px!important;min-width:0!important;margin:0!important;padding:0!important;z-index:5!important}.guest.theme-disco .loginbox .skullframe{position:relative!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;transform:none!important;width:100%!important;max-width:none!important;margin:0!important;box-sizing:border-box!important}\n.theme-disco .loginbox,.theme-liquidglass .loginbox,.theme-cute .loginbox{position:fixed!important;left:50%!important;bottom:30px!important;transform:translateX(-50%)!important;width:min(300px,calc(100vw - 24px))!important;max-width:300px!important;margin:0!important;z-index:5!important}.theme-disco .mainnav{background:#0c0720dd;border-bottom-color:#ff4fd8}.theme-disco .skullframe,.theme-disco .panel,.theme-disco .card{border-color:#8b55ff;background:linear-gradient(145deg,#1a0d38e8,#09051ce8);box-shadow:0 0 28px #ff2bd122,0 14px 45px #0008}.theme-disco .btn{background:linear-gradient(135deg,#6d22b8,#d62aa9);border-color:#ff66dc}.theme-disco .btn.gold{background:linear-gradient(135deg,#00a6b8,#00e5ff);border-color:#6fffff}.theme-disco .loginbox .skullframe{animation:discoPulse 1.8s ease-in-out infinite}\n@keyframes discoBg{from{filter:hue-rotate(0deg)}to{filter:hue-rotate(35deg)}}@keyframes discoPulse{50%{box-shadow:0 0 30px #ff4fd866,0 0 55px #00e5ff22}}\nbody.theme-liquidglass{--accent:#4aa8ff;--red:#ff5f7a;color:#172033!important;background:url("https://static.dezeen.com/uploads/2025/01/apple-park-foster-partners-21st-century-architecture_dezeen_2364_col_9.jpg") center/cover fixed!important;overflow-x:hidden}body.theme-liquidglass:before{display:none!important}body.theme-liquidglass:after{display:none!important}.theme-liquidglass .mainnav{background:linear-gradient(135deg,#ffffffb8,#ffffff72)!important;border-bottom:1px solid #ffffffb5;box-shadow:0 10px 35px #52718c30,0 1px 0 #fff;backdrop-filter:blur(24px) saturate(170%);-webkit-backdrop-filter:blur(24px) saturate(170%)}.theme-liquidglass .skullframe,.theme-liquidglass .panel,.theme-liquidglass .card{background:linear-gradient(135deg,#ffffffb8,#ffffff70)!important;border:1px solid #ffffffb8;color:#172033;box-shadow:0 18px 45px #46627d2b,0 2px 0 #ffffffcc inset,0 -1px 0 #ffffff55 inset;backdrop-filter:blur(24px) saturate(165%);-webkit-backdrop-filter:blur(24px) saturate(165%)}.theme-liquidglass .hero p,.theme-liquidglass .meta,.theme-liquidglass .smallmuted{color:#4c5c70}.theme-liquidglass input,.theme-liquidglass select,.theme-liquidglass textarea{background:#ffffff88!important;color:#172033;border:1px solid #ffffffb8;box-shadow:0 2px 10px #506b8220 inset,0 1px 0 #fff8;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}.theme-liquidglass input:focus,.theme-liquidglass select:focus,.theme-liquidglass textarea:focus{border-color:#55adff;box-shadow:0 0 0 3px #55adff28,0 2px 10px #506b8220 inset}.theme-liquidglass .btn{background:linear-gradient(135deg,#ffffffc9,#e8f0f8a8)!important;color:#172033;border:1px solid #ffffffc9;box-shadow:0 8px 22px #46627d26,0 1px 0 #fff inset;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}.theme-liquidglass .btn:hover{transform:translateY(-1px);box-shadow:0 12px 28px #46627d33,0 1px 0 #fff inset}.theme-liquidglass .btn.gold{background:linear-gradient(135deg,#4baeff,#716cff)!important;color:#fff;border-color:#ffffff88;box-shadow:0 10px 26px #478cff45,0 1px 0 #ffffff66 inset}.theme-liquidglass .iconbtn{background:#ffffff8f;color:#172033;border:1px solid #ffffffb8;box-shadow:0 7px 18px #46627d20;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}.theme-liquidglass .skullframe:before,.theme-liquidglass .skullframe:after{opacity:.035}.theme-liquidglass .loginbox .skullframe{box-shadow:0 24px 60px #46627d35,0 2px 0 #fff inset;animation:glassPulse 4s ease-in-out infinite}.theme-liquidglass .theme-picker{background:#ffffffb8;border-color:#ffffffc9;box-shadow:0 20px 60px #46627d3d;backdrop-filter:blur(28px) saturate(170%);-webkit-backdrop-filter:blur(28px) saturate(170%)}.theme-liquidglass .theme-choice{background:#ffffff75;color:#172033;border-color:#ffffff9e}.theme-liquidglass .theme-choice:hover{background:#ffffffb0;border-color:#55adff}.theme-liquidglass .theme-choice.current{outline:2px solid #55adff88}@keyframes liquidFloat{from{transform:translate3d(-1%, -1%,0) scale(1)}to{transform:translate3d(1%,1%,0) scale(1.04)}}@keyframes glassPulse{50%{box-shadow:0 28px 68px #46627d3d,0 2px 0 #fff inset,0 0 35px #8ccfff22}}\nbody.theme-cute{--accent:#ff6fae;--red:#ff7b8f;color:#4a2f3a!important;background:radial-gradient(circle at 12% 20%,#fff6a8 0 4%,transparent 5%),radial-gradient(circle at 88% 15%,#b8f2d0 0 5%,transparent 6%),radial-gradient(circle at 20% 80%,#cfe8ff 0 5%,transparent 6%),linear-gradient(135deg,#fff1f799,#eefaf499 50%,#fff9e899),url("https://images.unsplash.com/photo-1495360010541-f48722b34f7d?auto=format&fit=crop&w=2400&q=85") center/cover fixed!important}body.theme-cute:before{background:radial-gradient(circle at 75% 70%,#ffb7d833,transparent 24%),linear-gradient(#ffffff22,#ffd8e822)}.theme-cute .mainnav{background:#fff9f2cc;border-bottom:2px solid #f2b6cb;box-shadow:0 8px 25px #b86b8b22}.theme-cute .skullframe,.theme-cute .panel,.theme-cute .card{background:#ffffffaa;border-color:#f2bfd2;color:#4a2f3a;box-shadow:0 12px 28px #b86b8b1f;backdrop-filter:blur(12px);border-radius:22px}.theme-cute input,.theme-cute select,.theme-cute textarea{background:#ffffffbb;color:#4a2f3a;border-color:#efbed0}.theme-cute .btn{background:linear-gradient(135deg,#ff9fc5,#ffc3d9);color:#5a2e42;border-color:#f48eb4}.theme-cute .btn.gold{background:linear-gradient(135deg,#ffd66b,#ffb7d1);color:#5a3821;border-color:#f0b76d}.theme-cute .iconbtn{background:#fff7faaa;color:#5a3c4a;border-color:#f0bfd1}.theme-cute .loginbox .skullframe{animation:cuteFloat 3s ease-in-out infinite}\n@keyframes cuteFloat{50%{transform:translateY(-3px)}}\nbody.dark.theme-liquidglass{--accent:#7fc5ff;--red:#ff7188;color:#edf5ff!important;background:#07101b url("https://static.dezeen.com/uploads/2025/01/apple-park-foster-partners-21st-century-architecture_dezeen_2364_col_9.jpg") center/cover fixed!important}body.dark.theme-liquidglass:after{display:block!important;content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(rgba(3,10,20,.52),rgba(3,10,20,.68)),radial-gradient(circle at 25% 15%,#4baeff22,transparent 30%),radial-gradient(circle at 80% 70%,#8d6cff1c,transparent 35%)}body.dark.theme-liquidglass .mainnav{background:linear-gradient(135deg,#172b40cc,#0b1828b8)!important;border-bottom-color:#7fc5ff66;box-shadow:0 10px 35px #0008,0 1px 0 #ffffff22}body.dark.theme-liquidglass .skullframe,body.dark.theme-liquidglass .panel,body.dark.theme-liquidglass .card{background:linear-gradient(135deg,#1b3047c7,#0c1b2bc2)!important;border-color:#a9d9ff55;color:#edf5ff;box-shadow:0 18px 45px #0009,0 2px 0 #ffffff18 inset,0 -1px 0 #ffffff0d inset}body.dark.theme-liquidglass .hero p,body.dark.theme-liquidglass .meta,body.dark.theme-liquidglass .smallmuted{color:#b8cbe0}body.dark.theme-liquidglass input,body.dark.theme-liquidglass select,body.dark.theme-liquidglass textarea{background:#0e2032b8!important;color:#edf5ff;border-color:#9bd5ff55;box-shadow:0 2px 10px #0005 inset,0 1px 0 #fff1}body.dark.theme-liquidglass input:focus,body.dark.theme-liquidglass select:focus,body.dark.theme-liquidglass textarea:focus{border-color:#7fc5ff;box-shadow:0 0 0 3px #55adff28,0 2px 10px #0005 inset}body.dark.theme-liquidglass .btn{background:linear-gradient(135deg,#203b54dd,#10263bdd)!important;color:#edf5ff;border-color:#a9d9ff55;box-shadow:0 8px 22px #0007,0 1px 0 #fff2 inset}body.dark.theme-liquidglass .btn.gold{background:linear-gradient(135deg,#2586c9,#6357d8)!important;color:#fff;border-color:#bde5ff66}body.dark.theme-liquidglass .iconbtn{background:#183047bb;color:#edf5ff;border-color:#a9d9ff55}body.dark.theme-liquidglass .theme-picker{background:#102237ed;border-color:#a9d9ff55}body.dark.theme-liquidglass .theme-choice{background:#193149cc;color:#edf5ff;border-color:#a9d9ff44}\nbody.dark.theme-cute{--accent:#ff9fc5;--red:#ff8099;color:#ffeef5!important;background:radial-gradient(circle at 12% 20%,#fff6a82b 0 4%,transparent 5%),radial-gradient(circle at 88% 15%,#7ce3b044 0 5%,transparent 6%),radial-gradient(circle at 20% 80%,#80c7ff30 0 5%,transparent 6%),linear-gradient(135deg,#211522d9,#10241fd9 50%,#211b13d9),url("https://images.unsplash.com/photo-1495360010541-f48722b34f7d?auto=format&fit=crop&w=2400&q=85") center/cover fixed!important}body.dark.theme-cute:before{background:radial-gradient(circle at 75% 70%,#ff7fb733,transparent 24%),linear-gradient(#130b18aa,#06140faa)}body.dark.theme-cute .mainnav{background:#241a28d9;border-bottom-color:#f29abd66;box-shadow:0 8px 25px #0008}body.dark.theme-cute .skullframe,body.dark.theme-cute .panel,body.dark.theme-cute .card{background:#211923d4;border-color:#f0a5c955;color:#ffeef5;box-shadow:0 12px 28px #0007,0 1px 0 #ffffff12 inset}body.dark.theme-cute input,body.dark.theme-cute select,body.dark.theme-cute textarea{background:#17111cbf;color:#ffeef5;border-color:#f0a5c955}body.dark.theme-cute .btn{background:linear-gradient(135deg,#a94d78,#713e78);color:#fff0f7;border-color:#f49abe88}body.dark.theme-cute .btn.gold{background:linear-gradient(135deg,#c9933e,#a85d85);color:#fff7e8;border-color:#f6c56e88}body.dark.theme-cute .iconbtn{background:#2b1e2fbb;color:#ffeef5;border-color:#f0a5c955}body.dark.theme-cute .theme-picker{background:#211725ed;border-color:#f0a5c955}body.dark.theme-cute .theme-choice{background:#2a1d31cc;color:#ffeef5;border-color:#f0a5c944}.theme-picker-overlay{display:none;position:fixed;inset:0;z-index:1100;align-items:center;justify-content:center;background:#0009;backdrop-filter:blur(5px);padding:10px}.theme-picker-overlay.open{display:flex}.theme-picker{width:max-content;max-width:calc(100vw - 14px);padding:4px;border:1px solid #f5c54277;border-radius:11px;background:#180a0af5;box-shadow:0 18px 50px #0009;overflow:hidden}.theme-picker-grid{display:grid;grid-template-columns:repeat(4,auto);gap:3px}.theme-choice{display:flex;align-items:center;justify-content:center;gap:4px;padding:7px 8px;border:1px solid #6e282866;border-radius:7px;background:#241010;color:#fff;text-decoration:none;font-size:10px;line-height:1.1;white-space:nowrap}.theme-choice:hover{background:#3a1515;border-color:#f5c542}.theme-choice.current{outline:1px solid #f5c542}.theme-choice .theme-icon{font-size:15px}.theme-settings-row{display:flex;align-items:stretch;gap:7px;flex-wrap:wrap}\n@media(max-width:520px){.theme-picker-grid{grid-template-columns:repeat(2,1fr)}.theme-choice{min-width:130px}}\n'

def bg_image_url(c):
    """Return a versioned background-image URL for safe browser caching."""
    bg = c.get("background", {})
    if bg.get("type") != "image" or not bg.get("value"):
        return ""
    name = os.path.basename(str(bg.get("value", "")))
    fp = PROFILE_UPLOAD_DIR / name
    try:
        st = fp.stat()
        version = f"{st.st_mtime_ns}-{st.st_size}"
    except OSError:
        version = "0"
    return "/uploads/profile/" + urllib.parse.quote(name) + "?v=" + urllib.parse.quote(version)


def bg_css(c):
    bg = c.get("background", {})
    if bg.get("type") == "image" and bg.get("value"):
        url = bg_image_url(c)
        mode = bg.get("mode", "fill")
        if mode in ("fill", "Cover"): size = "cover"
        elif mode in ("fit", "Contain"): size = "contain"
        elif mode == "stretch": size = "100% 100%"
        elif mode == "tile": size = "auto"
        elif mode == "Span": size = "100% auto"
        elif mode in ("Mirror", "Reflect"): size = "50% 100%"
        else: size = "auto"
        repeat = "repeat" if mode in ("tile", "Mirror", "Reflect") else "no-repeat"
        pos = "center"
        return f"background-image:url('{url}');background-size:{size};background-position:{pos};background-repeat:{repeat};background-attachment:fixed;"
    return f"background:{esc(bg.get('value','#120808'))};"


def layout(title, body, page="home", user=None, extra_head="", flash=""):
    c = config(); dark = bool(c.get("dark_mode", True)); active_theme = theme_name(c); ui_opacity = max(0.05, min(1.0, int(c.get("transparency",50))/100))
    flash_html = f'<div class="flash">{esc(flash)}</div>' if flash else ''
    bg_preload = ''
    bg_url = bg_image_url(c)
    if bg_url:
        bg_preload = f'<link rel="preload" as="image" href="{esc(bg_url)}" fetchpriority="high">'
    nav = '' if not user else f'''
      <nav class="mainnav">
        <a class="brand" href="/?page=home"><span class="brand-emoji">🚬</span> <span class="brand-text">{esc(t("食少支煙系統", c))}</span></a>
        <details class="navmenu"><summary class="iconbtn" title="{esc(t("功能選單", c))}">🚬</summary><div class="navdropdown"><a href="/?page=clients">{esc(t("👤 訂煙者", c))}</a><a href="/?page=types">{esc(t("🚬 煙款", c))}</a><a class="record-glow-card" href="/?page=record">{esc(t("📋 訂煙記錄", c))}</a><a href="/?page=seller">{esc(t("🚬 賣煙者", c))}</a><a href="/?page=order">{esc(t("📦 落單", c))}</a></div></details>
        <div class="navright"><a href="/?page=settings" class="iconbtn" title="{esc(t("設定", c))}">⚙️</a>{'' if IS_RASPBERRY_PI4 else f'<a href="/logout" class="iconbtn logout" title="{esc(t("登出", c))}">🚪</a>'}</div>
      </nav>'''
    return f'''<!doctype html><html lang="{c.get('language','en')}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{bg_preload}<title>{esc(title)} · 🚬食少支煙系統</title><style>
:root{{--accent:#f5c542;--red:#d94343;--ink:#170d0d;--paper:#251313;--muted:#d9c9a7;--line:#7b2020;--shadow:0 14px 45px rgba(0,0,0,.5)}}*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif;color:#f7f1df}}body{{{bg_css(c)}background-color:#120808;background-attachment:fixed}}body:before{{content:"";position:fixed;inset:0;background:radial-gradient(circle at 15% 20%,rgba(221,50,50,.13),transparent 28%),linear-gradient(rgba(12,4,4,.58),rgba(12,4,4,.7));pointer-events:none;z-index:-1}}a{{color:inherit;text-decoration:none}}button,.btn,input,select,textarea{{font:inherit}}button,.btn{{cursor:pointer}}.mainnav{{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:8px;padding:10px 12px;background:rgba(18,8,8,.92);backdrop-filter:blur(12px);border-bottom:2px solid #7b2020;box-shadow:var(--shadow);flex-wrap:nowrap;white-space:nowrap;overflow:visible}}.brand{{display:flex;align-items:center;gap:3px;min-width:0;flex:1 1 auto;font-weight:900;font-size:20px;line-height:1;white-space:nowrap;overflow:visible}}.brand-text{{display:inline-block;white-space:nowrap;transform-origin:left center}}.brand-emoji{{flex:0 0 auto}}.lang-en .brand{{font-size:20px}}.brand span{{color:var(--accent)}}.navtabs{{display:flex;gap:8px;flex:1;justify-content:center;flex-wrap:wrap}}.navtabs a,.iconbtn{{padding:9px 14px;border:1px solid #6e2828;border-radius:14px;background:#241010;transition:.2s}}.navtabs a:hover,.navtabs .active,.iconbtn:hover{{transform:translateY(-2px);background:#3a1515;border-color:var(--accent);box-shadow:0 0 18px rgba(245,197,66,.18)}}.navright{{display:flex;gap:4px;flex:0 0 auto;align-items:center}}.navmenu{{flex:0 0 auto}}.iconbtn{{font-size:21px;display:inline-flex;align-items:center;justify-content:center;min-width:42px;height:42px;padding:7px 9px}}.logout:hover{{border-color:#ff5555!important}}.wrap{{position:relative;z-index:1;max-width:1500px;margin:25px auto;padding:0 18px 80px}}.skullframe{{position:relative;border:2px solid #8c2424;border-radius:24px;padding:24px;background:linear-gradient(145deg,rgba(42,16,16,.93),rgba(20,9,9,.9));box-shadow:var(--shadow),inset 0 0 0 1px rgba(245,197,66,.14);overflow:hidden}}.skullframe:before{{content:"🚬  ☠️  💀  ☠️  🚬  💀  ☠️  🚬";position:absolute;top:5px;left:20px;right:20px;color:#f5c542;letter-spacing:8px;text-align:center;font-size:14px;opacity:.7}}.skullframe:after{{content:"💀  🚬  ☠️  💀  🚬  ☠️  💀  🚬";position:absolute;bottom:5px;left:20px;right:20px;color:#f5c542;letter-spacing:8px;text-align:center;font-size:14px;opacity:.7}}h1,h2,h3{{margin-top:0}}.hero{{text-align:center;padding:38px 15px}}.hero h1{{font-size:clamp(32px,6vw,70px);margin:10px 0;text-shadow:0 0 22px rgba(245,197,66,.22)}}.hero p{{color:var(--muted)}}.formgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}label.small{{display:block;color:#d7c49b;font-size:13px;margin-bottom:5px}}input,select,textarea{{width:100%;border:1px solid #713333;background:#130909;color:#fff;padding:11px 12px;border-radius:12px;outline:none}}input:focus,select:focus,textarea:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(245,197,66,.1)}}.btn{{border:1px solid #9a3232;background:linear-gradient(135deg,#5b1717,#8b2525);color:white;border-radius:12px;padding:10px 16px;transition:.2s;box-shadow:0 7px 18px rgba(0,0,0,.25)}}.btn:hover{{transform:translateY(-2px);filter:brightness(1.12)}}.btn.gold{{background:linear-gradient(135deg,#7b5a13,#c89a25);color:#160d06;border-color:#e5be52}}.btn.green{{background:linear-gradient(135deg,#145b3b,#218c59);border-color:#5de0a2}}.btn.gray{{background:#302020;border-color:#684646}}.btn.danger{{background:#641616}}.actions{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}.panel{{background:rgba(25,11,11,.9);border:1px solid #5d2929;border-radius:18px;padding:18px;margin-bottom:18px}}.panel h2{{color:var(--accent)}}.notice{{padding:13px;border-radius:12px;background:#201010;border:1px solid #654040;margin:10px 0}}.danger{{border-color:#9d3030}}.flash{{margin:10px auto;padding:12px 16px;border:1px solid #b98c29;background:#33280d;border-radius:12px;max-width:1000px;color:#ffe9a3}}.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}}.card{{border:1px solid #653333;border-radius:16px;padding:14px;background:rgba(27,12,12,.92);transition:.2s}}.card:hover{{transform:translateY(-3px);border-color:#b37b2c}}.record-glow-card{{border:2px solid #f5c542;box-shadow:0 0 8px rgba(245,197,66,.45),0 0 22px rgba(245,197,66,.22),inset 0 0 12px rgba(245,197,66,.08);animation:recordGlowDark 2.4s ease-in-out infinite}}@keyframes recordGlowDark{{0%,100%{{box-shadow:0 0 7px rgba(245,197,66,.42),0 0 18px rgba(245,197,66,.18),inset 0 0 10px rgba(245,197,66,.06)}}50%{{box-shadow:0 0 12px rgba(245,197,66,.72),0 0 30px rgba(245,197,66,.34),inset 0 0 16px rgba(245,197,66,.12)}}}}body.light .record-glow-card{{border-color:#2d78c8;box-shadow:0 0 7px rgba(45,120,200,.30),0 0 18px rgba(45,120,200,.14),inset 0 0 10px rgba(45,120,200,.05);animation:recordGlowLight 2.4s ease-in-out infinite}}@keyframes recordGlowLight{{0%,100%{{box-shadow:0 0 6px rgba(45,120,200,.28),0 0 15px rgba(45,120,200,.12),inset 0 0 8px rgba(45,120,200,.04)}}50%{{box-shadow:0 0 10px rgba(45,120,200,.52),0 0 24px rgba(45,120,200,.24),inset 0 0 14px rgba(45,120,200,.09)}}}}.thumb{{width:100%;height:180px;object-fit:contain;border-radius:12px;background:#090505}}.meta{{color:#d8c49d;font-size:14px;line-height:1.7}}.price{{font-size:22px;color:var(--accent);font-weight:900}}.tablewrap{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:11px;border-bottom:1px solid #492222;text-align:left;vertical-align:top}}th{{color:#e6c34f;background:#1a0c0c}}.settings details{{border:1px solid #572727;border-radius:14px;margin:10px 0;background:rgba(20,8,8,.7)}}.settings summary{{cursor:pointer;padding:15px;font-weight:800;color:#f2cd5b}}.settings .inside{{padding:15px;border-top:1px solid #4d2323}}.preview{{min-height:160px;border:1px dashed #8d5555;border-radius:14px;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#120808}}.preview-image{{width:100%;min-height:160px;height:250px;background-position:center center;background-repeat:no-repeat;background-size:contain;transition:background-size .18s ease,background-position .18s ease,background-repeat .18s ease;background-color:#120808}}.preview-image.color-preview{{display:flex;align-items:center;justify-content:center;background-image:none!important}}.loginbox{{max-width:520px;margin:7vh auto}}.loginbox .skullframe{{padding:38px 30px}}.logininput::placeholder{{color:#c8bca5;opacity:1}}.remember{{display:flex;gap:8px;align-items:center;margin:10px 0;color:#ddcfb3}}.remember input{{width:auto}}.shake{{animation:shake .32s}}@keyframes shake{{0%,100%{{transform:translateX(0)}}25%{{transform:translateX(-7px)}}75%{{transform:translateX(7px)}}}}.pulse{{animation:pulse .5s}}@keyframes pulse{{50%{{transform:scale(1.04)}}}}.totp{{letter-spacing:8px;text-align:center;font-size:28px}}.qrbox{{background:white;padding:14px;border-radius:16px;display:inline-block}}.qrbox svg{{max-width:280px;height:auto}}.copyright{{text-align:center;color:#b7a687;font-size:13px;margin-top:35px}}.empty{{padding:35px;text-align:center;color:#b9a98a;border:1px dashed #593737;border-radius:16px}}.recordgrid{{display:grid;grid-template-columns:1fr 1.5fr 1fr 180px;gap:12px;align-items:center}}.cigthumb{{width:72px;height:72px;object-fit:contain;border-radius:8px;background:#0a0505;vertical-align:middle;margin-right:8px}}.ordertext{{min-height:170px}}.smallmuted{{font-size:12px;color:#ad9a7c}}.navmenu{{position:relative}}.navmenu summary{{list-style:none}}.navmenu summary::-webkit-details-marker{{display:none}}.navdropdown{{position:absolute;right:0;top:calc(100% + 8px);min-width:190px;padding:8px;border:1px solid #6e2828;border-radius:14px;background:rgba(20,8,8,.96);backdrop-filter:blur(14px);box-shadow:var(--shadow);z-index:30}}.navdropdown a{{display:block;padding:10px 12px;border-radius:10px}}.navdropdown a:hover{{background:#3a1515;color:#f5c542}}.skullframe,.panel,.card,.mainnav,.settings details{{opacity:var(--ui-opacity)}}.loginbox{{position:fixed;left:50%;bottom:12px;transform:translateX(-50%);width:min(300px,calc(100vw - 24px));max-width:300px;margin:0;z-index:5}}.loginbox .skullframe{{padding:7px 9px;background:rgba(15,6,6,.08);border:1px solid rgba(245,197,66,.22);border-radius:14px;box-shadow:0 5px 16px rgba(0,0,0,.10);backdrop-filter:blur(2px)}}.loginbox .hero{{padding:3px 4px 6px}}.loginbox .hero>div{{font-size:22px!important;line-height:1}}.loginbox .hero h1{{font-size:14px;margin:3px 0;font-weight:700}}.loginbox .hero p{{font-size:9px;margin:2px;color:rgba(217,201,167,.72)}}.loginbox form{{font-size:11px}}.loginbox .logininput{{padding:6px 8px;border-radius:8px;font-size:11px;background:rgba(19,9,9,.22)}}.loginbox .remember{{font-size:9px;margin:5px 0;gap:4px;color:rgba(221,207,179,.78)}}.loginbox .remember input{{transform:scale(.75)}}.loginbox .actions{{gap:5px}}.loginbox .btn{{padding:5px 9px;border-radius:8px;font-size:10px;box-shadow:none}}.loginbox .notice{{font-size:9px;padding:5px 7px;margin:5px 0}}body.light{{color:#211814}}body.light:before{{background:linear-gradient(rgba(255,248,230,.2),rgba(255,248,230,.35))}}body.light .mainnav{{background:rgba(255,248,230,.88);border-bottom-color:#a96d24}}body.light .navdropdown{{background:rgba(255,248,230,.96)}}body.light .iconbtn{{background:rgba(255,255,255,.6);color:#2b1a12}}body.light input,body.light select,body.light textarea{{background:rgba(255,255,255,.68);color:#24170f}}body.light .skullframe,body.light .panel,body.light .card{{background:rgba(255,248,230,.48)}}.theme-toggle-large{{display:inline-block;padding:12px 18px;border:1px solid #b98c29;border-radius:14px;background:rgba(80,55,10,.5);color:#f5c542;font-weight:900}}.filepicker{{display:flex;align-items:center;gap:8px}}.filepicker input[type=file]{{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}}.filepicklabel{{display:inline-flex;align-items:center;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.record-sort{{display:block;color:inherit;text-decoration:none;cursor:pointer}}.record-sort:hover{{color:var(--accent)}}.mobile-label{{display:none}}.record-actions{{gap:6px;flex-wrap:nowrap}}.record-actions form{{display:flex;margin:0}}.record-actions .btn{{min-width:42px;padding:8px 10px;display:inline-flex;align-items:center;justify-content:center}}@media(max-width:800px){{.mainnav{{align-items:center;flex-wrap:nowrap;gap:4px;padding:8px 7px}}.brand{{font-size:18px;min-width:0}}.brand-text{{max-width:none}}.navright{{gap:3px}}.iconbtn{{min-width:38px;width:38px;height:38px;padding:5px 4px;font-size:19px}}.navtabs{{order:3;width:100%;justify-content:flex-start}}.recordgrid{{grid-template-columns:1fr}}.wrap{{padding:0 10px 60px}}.desktop-label{{display:none}}.mobile-label{{display:inline}}.tablewrap table{{min-width:620px}}.record-actions .btn{{min-width:36px;padding:7px 8px}}}}
.guest .loginbox{{bottom:30px}}
.guest .loginbox .skullframe:before{{z-index:0;pointer-events:none;font-size:9px;letter-spacing:2px;opacity:.18;line-height:1}}.guest .loginbox .skullframe:after{{content:"💀  🚬  ☠️  💀  🚬  ☠️  💀  🚬";display:block!important;z-index:0;pointer-events:none;font-size:9px;letter-spacing:2px;opacity:.18;line-height:1}}
.guest .loginbox .skullframe>*{{position:relative;z-index:1}}
.guest .copyright{{position:fixed;left:0;right:0;bottom:4px;margin:0;text-align:center;font-size:9px;line-height:12px;z-index:20;pointer-events:none}}
.language-overlay{{display:none;position:fixed;inset:0;z-index:1000;align-items:center;justify-content:center;background:rgba(0,0,0,.62);backdrop-filter:blur(5px);padding:12px}}.language-overlay.open{{display:flex}}.language-popup{{width:max-content;max-width:calc(100vw - 24px);padding:0;border:1px solid rgba(245,197,66,.55);border-radius:12px;background:rgba(24,10,10,.98);box-shadow:0 18px 55px rgba(0,0,0,.55);overflow:hidden}}.language-popup-grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:0}}.language-flag{{display:flex;align-items:center;justify-content:center;width:48px;height:46px;font-size:25px;text-decoration:none;border-right:1px solid rgba(120,55,55,.65);transition:.15s}}.language-flag:last-child{{border-right:0}}.language-flag:hover,.language-flag:focus{{background:#3a1515;transform:scale(1.04);outline:none}}.browser-auto{{display:flex;align-items:center;justify-content:center;gap:5px;height:38px;padding:0 10px;border-top:1px solid rgba(120,55,55,.65);color:#f5c542;text-decoration:none;font-size:11px;font-weight:800;white-space:nowrap}}.browser-auto:hover{{background:#3a1515}}@media(max-width:420px){{.language-popup-grid{{grid-template-columns:repeat(4,1fr)}}.language-flag:nth-child(4){{border-right:0}}.language-flag{{width:52px}}.language-flag:nth-child(n+5){{border-top:1px solid rgba(120,55,55,.65)}}}}
{theme_css()}</style>{extra_head}</head><body class="{'dark' if dark else 'light'} theme-{active_theme} {'guest' if not user else 'member'} {'lang-en' if c.get('language','zh-Hant')=='en' else 'lang-zh'}" style="--ui-opacity:{ui_opacity}">{nav}{flash_html}<main class="wrap">{body}</main><div class="copyright">{esc(t("Copyright ©️洗錢多過賺錢既垃圾系統2026", c))}</div>
<script>function fitNavBrand(){{const nav=document.querySelector('.mainnav');const brand=document.querySelector('.brand');const text=document.querySelector('.brand-text');if(!nav||!brand||!text)return;let size=20;text.style.fontSize=size+'px';text.style.transform='none';for(let i=0;i<24;i++){{if(brand.scrollWidth<=brand.clientWidth+1)break;size-=0.5;text.style.fontSize=Math.max(size,9)+'px'}}if(brand.scrollWidth>brand.clientWidth){{const ratio=brand.clientWidth/brand.scrollWidth;text.style.transform='scaleX('+Math.max(.72,Math.min(1,ratio))+')';}} }}window.addEventListener('resize',fitNavBrand);document.addEventListener('DOMContentLoaded',fitNavBrand);setTimeout(fitNavBrand,60);document.querySelectorAll('button,.btn').forEach(b=>b.addEventListener('click',()=>{{b.classList.remove('pulse');void b.offsetWidth;b.classList.add('pulse')}}));document.querySelectorAll('.logout').forEach(b=>b.addEventListener('click',()=>b.classList.add('pulse')));function openThemePopup(){{const p=document.getElementById('themePopup');if(p){{p.classList.add('open');p.setAttribute('aria-hidden','false')}}}}function closeThemePopup(){{const p=document.getElementById('themePopup');if(p){{p.classList.remove('open');p.setAttribute('aria-hidden','true')}}}}function openLanguagePopup(){{const p=document.getElementById('languagePopup');if(p){{p.classList.add('open');p.setAttribute('aria-hidden','false')}}}}function closeLanguagePopup(){{const p=document.getElementById('languagePopup');if(p){{p.classList.remove('open');p.setAttribute('aria-hidden','true')}}}}document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeLanguagePopup()}});</script></body></html>'''


def login_page(message="", totp=False, hide_notice=False):
    if totp:
        body=f'''<div class="loginbox"><section class="skullframe"><div class="hero"><div style="font-size:55px">🚬☠️💀</div><h1>雙重認證</h1><p>請輸入 Authenticator App 顯示的 6 位數字</p></div><form method="post" action="/login-2fa"><input type="hidden" name="csrf" value="{esc(message[1] if isinstance(message,tuple) else '')}"><input class="totp" name="code" inputmode="numeric" maxlength="6" pattern="\\d{{6}}" autocomplete="one-time-code" placeholder="6位數字" required><div class="actions" style="justify-content:center;margin-top:18px"><button class="btn gold" type="submit">☠️ 驗證登入</button></div></form></section></div>'''
    else:
        body=f'''<div class="loginbox"><section class="skullframe"><div class="hero"><h1 class="login-random-message">{esc(random.choice(LOGOUT_MESSAGES))}</h1></div><form method="post" action="/login"><input type="hidden" name="csrf" value="{csrf_for_guest()}"><input class="logininput" name="username" placeholder="登入名稱" autocomplete="username" required><input class="logininput" style="margin-top:10px" type="password" name="password" placeholder="密碼" autocomplete="current-password" required><label class="remember"><input type="checkbox" name="remember" value="1"> 記住我（只限此裝置及此 Browser，永久至登出）</label><div class="actions" style="justify-content:center"><button class="btn gold" type="submit">🚬 登入</button><a class="btn gray" href="/theme-toggle" title="日間和夜間模式">🌙</a><button class="btn gray theme-trigger" type="button" onclick="openThemePopup()" title="選擇主題">🎨</button><button class="btn gray lang-trigger" type="button" onclick="openLanguagePopup()" title="選擇語言">🌍</button></div></form>{f'<div class="notice danger">{esc(message)}</div>' if message and not hide_notice else ''}</section></div><div id="themePopup" class="theme-picker-overlay" aria-hidden="true" onclick="if(event.target===this)closeThemePopup()"><div class="theme-picker" role="dialog" aria-modal="true" aria-label="Theme"><div class="theme-picker-grid">{''.join(f'<a class="theme-choice {"current" if theme_name(config())==code else ""}" href="/theme-select?name={code}"><span class="theme-icon">{label.split(" ",1)[0]}</span><span>{esc(t(label,config()))}</span></a>' for code,label in THEME_LABEL_KEYS.items())}</div></div></div><div id="languagePopup" class="language-overlay" aria-hidden="true" onclick="if(event.target===this)closeLanguagePopup()"><div class="language-popup" role="dialog" aria-modal="true" aria-label="Language"><div class="language-popup-grid"><a class="language-flag" href="/language?lang=zh-Hant" title="繁體中文" aria-label="繁體中文">🇭🇰</a><a class="language-flag" href="/language?lang=en" title="English" aria-label="English">🇬🇧</a><a class="language-flag" href="/language?lang=th" title="ไทย" aria-label="ไทย">🇹🇭</a><a class="language-flag" href="/language?lang=ja" title="日本語" aria-label="日本語">🇯🇵</a><a class="language-flag" href="/language?lang=ko" title="한국어" aria-label="한국어">🇰🇷</a><a class="language-flag" href="/language?lang=ru" title="Русский" aria-label="Русский">🇷🇺</a><a class="language-flag" href="/language?lang=es" title="Español" aria-label="Español">🇪🇸</a></div><a class="browser-auto" href="/language?auto=1">🌐 <span>Browser 自動偵測</span></a></div></div>'''
    return layout("登入", body, user=None)

GUEST_CSRF = secrets.token_urlsafe(24)
def csrf_for_guest(): return GUEST_CSRF


def current_user(handler):
    if IS_RASPBERRY_PI4 and getattr(handler, "session", None):
        return handler.session.get("user")
    sid = handler.cookies.get("sid")
    if not sid: return None
    sid_value = sid.value if hasattr(sid, "value") else str(sid)
    with LOCK: s = SESSIONS.get(sid_value)
    if s: return s.get("user")
    return None


def csrf_ok(handler, token):
    sid = handler.cookies.get("sid")
    sid_value = sid.value if hasattr(sid, 'value') else str(sid) if sid else ''
    with LOCK: s = SESSIONS.get(sid_value) if sid_value else None
    return bool(s and hmac.compare_digest(str(token or ""), s.get("csrf", "")))


def request_data(handler):
    ctype = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length else b""
    if ctype.startswith("application/x-www-form-urlencoded"):
        return {k: v[0] for k,v in urllib.parse.parse_qs(raw.decode("utf-8", "replace")).items()}
    if ctype.startswith("multipart/form-data"):
        boundary = ctype.split("boundary=",1)[1].encode()
        out = {}
        for part in raw.split(b"--" + boundary):
            if not part or part in (b"--\r\n",b"--"): continue
            if b"\r\n\r\n" not in part: continue
            head, data = part.split(b"\r\n\r\n",1); data=data.rstrip(b"\r\n-")
            hs = head.decode("utf-8", "replace")
            m = re.search(r'name="([^"]+)"', hs); fm = re.search(r'filename="([^"]*)"', hs)
            if not m: continue
            name=m.group(1)
            if fm and fm.group(1): out[name] = (fm.group(1), data, re.search(r'Content-Type:\s*([^\r\n]+)', hs, re.I).group(1) if re.search(r'Content-Type:\s*([^\r\n]+)', hs, re.I) else "application/octet-stream")
            else: out[name]=data.decode("utf-8","replace")
        return out
    return {}


def set_cookie(handler, name, value, max_age=None, httponly=True):
    c=SimpleCookie(); c[name]=value
    if max_age is not None: c[name]["max-age"]=str(max_age)
    c[name]["path"]="/"
    if httponly: c[name]["httponly"]=True
    c[name]["samesite"]="Lax"
    handler.send_header("Set-Cookie", c.output(header="").strip())


def redirect(handler, path, flash=None, cookie_clear=False):
    handler.send_response(303); handler.send_header("Location", path)
    if cookie_clear:
        set_cookie(handler,"sid","",0)
    handler.end_headers()


def require_login(handler):
    user=current_user(handler)
    if not user:
        redirect(handler,"/"); return None
    return user


def home_body():
    return '''<section class="skullframe"><div class="hero"><div style="font-size:72px">🚬☠️💀</div><h1>食少支煙系統</h1><p>墨西哥亡靈節主題 · 訂煙、記錄、落單集中管理</p><div class="cards" style="margin-top:28px"><a class="card" href="/?page=clients"><h2>👤 訂煙者</h2><p class="meta">管理訂煙者及 WhatsApp 聯絡資料。</p></a><a class="card" href="/?page=types"><h2>🚬 煙款</h2><p class="meta">管理品牌、名稱、價錢、代碼及相片。</p></a><a class="card record-glow-card" href="/?page=record"><h2>📋 訂煙記錄</h2><p class="meta">建立每一行獨立訂煙 Order。</p></a><a class="card" href="/?page=seller"><h2>🚬 賣煙者</h2><p class="meta">管理賣煙者、電話、評價及評語。</p></a><a class="card" href="/?page=order"><h2>📦 落單</h2><p class="meta">按煙款選擇後產生落單 WhatsApp 訊息。</p></a></div></div></section>'''


def settings_body(handler):
    c=config(); csrf=handler.session["csrf"]
    bg=c.get("background",{}); preview=''
    if bg.get("type")=="image" and bg.get("value"):
        preview_url=f"/uploads/profile/{urllib.parse.quote(os.path.basename(str(bg.get('value',''))))}"
        preview=f'<div id="backgroundPreview" class="preview-image" data-image-url="{esc(preview_url)}" style="background-image:url(\'{esc(preview_url)}\')"></div>'
    else:
        preview=f'<div id="backgroundPreview" class="preview-image color-preview"><span style="color:{esc(bg.get("value","#120808"))}">● 背景顏色預覽</span></div>'
    profile_files = sorted(x.name for x in PROFILE_UPLOAD_DIR.iterdir() if x.is_file() and x.suffix.lower() in {".jpg",".jpeg",".png",".gif",".webp",".bmp"})
    current_profile = os.path.basename(bg.get("value", "")) if bg.get("type")=="image" else ""
    if profile_files:
        profile_options = '<option value="">Choose file</option>' + ''.join(f'<option value="{esc(n)}" {"selected" if n==current_profile else ""}>{esc(n)}</option>' for n in profile_files)
        profile_picker = f'<select name="profile_existing" id="profile_existing">{profile_options}</select>'
    else:
        profile_picker = '<div class="smallmuted">Choose file</div>'
    totp_enabled=c.get("totp",{}).get("enabled",False)
    qr_html=''
    if handler.query.get("showqr") == ["1"]:
        if handler.query.get("adminok") == ["1"]:
            secret=c.get("totp",{}).get("secret","")
            if secret:
                uri="otpauth://totp/食少支煙系統:"+urllib.parse.quote(c.get("username","smoker"))+"?secret="+secret+"&issuer="+urllib.parse.quote("食少支煙系統")
                qr_html=f'<div class="qrbox">{qr_svg(uri)}</div><p class="smallmuted">Secret：{esc(secret)}</p><form method="post" action="/settings" onsubmit="return confirm(\'重新產生後舊 Code 即刻失效，確定？\')" style="margin-top:10px"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="totp_regen"><button class="btn danger">♻️ 重新產生金鑰（舊 Code 即刻失效）</button></form>'
            else: qr_html='<div class="notice">尚未產生 2FA 金鑰。</div>'
        else:
            qr_html=f'''<form method="post" action="/settings"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="verify_qr"><label class="small">輸入 admin 密碼後顯示 QR Code</label><input type="password" name="admin_password" required><button class="btn gold" style="margin-top:8px">🔐 驗證並顯示 QR Code</button></form>'''
    security_settings = '' if IS_RASPBERRY_PI4 else f'''
    <details open><summary>🔐 更改登入名和密碼</summary><div class="inside"><form method="post" action="/settings"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="credentials"><div class="formgrid"><input type="text" name="current_username" placeholder="目前登入名" required><input type="password" name="current_password" placeholder="目前密碼" required><input type="text" name="new_username" placeholder="新登入名" required><input type="password" name="new_password" placeholder="新密碼" required></div><button class="btn gold" style="margin-top:12px">儲存新登入資料</button></form></div></details>
    <details open><summary>☠️ 更改 admin 密碼</summary><div class="inside"><form method="post" action="/settings"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="adminpass"><div class="formgrid"><input type="password" name="current_admin" placeholder="目前 admin 密碼" required><input type="password" name="new_admin" placeholder="新 admin 密碼" required></div><button class="btn gold" style="margin-top:12px">更新 admin 密碼</button></form></div></details>
    <details open><summary>📱 雙重認證（2FA / TOTP）</summary><div class="inside"><form method="post" action="/settings"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="totp_save"><label class="remember"><input type="checkbox" name="totp_enabled" value="1" {'checked' if totp_enabled else ''}> 啟用雙重認證（TOTP）</label><button class="btn gold">💾 儲存2FA開關</button></form><div class="actions" style="margin-top:10px"><a class="btn gray" href="/?page=settings&showqr=1">👁️ 顯示/隱藏 QR Code</a></div>{qr_html}</div></details>
    '''
    return f'''<section class="skullframe settings"><h1>⚙️ 系統設定</h1>
    <details open><summary>🎨 更變背景</summary><div class="inside"><div class="formgrid"><div class="preview">{preview}</div><form method="post" action="/settings" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="background"><label class="small">背景類型</label><select name="bg_type" onchange="document.getElementById('imgopts').style.display=this.value==='image'?'block':'none';document.getElementById('coloropts').style.display=this.value==='color'?'block':'none'"><option value="color" {'selected' if bg.get('type')=='color' else ''}>顏色</option><option value="image" {'selected' if bg.get('type')=='image' else ''}>相片</option></select><div id="coloropts" style="{'display:block' if bg.get('type')=='color' else 'display:none'};margin-top:10px"><label class="small">常用顏色</label><select name="color"><option value="#120808">亡靈黑</option><option value="#3b0d0d">深紅</option><option value="#17210d">墨綠</option><option value="#0d1721">深藍</option><option value="#22130a">咖啡</option><option value="#1b1630">紫黑</option></select></div><div id="imgopts" style="{'display:block' if bg.get('type')=='image' else 'display:none'};margin-top:10px"><label class="small">已上載相片</label>{profile_picker}<label class="small" style="margin-top:10px">上載新相片</label><div class="filepicker"><input id="background_file" type="file" name="background_file" accept="image/*" onchange="document.getElementById('backgroundFileName').textContent=this.files.length?this.files[0].name:'Choose file'"><label for="background_file" class="btn gray filepicklabel"><span id="backgroundFileName">Choose file</span></label></div><label class="small" style="margin-top:10px">顯示方式</label><select id="bgModePreview" name="bg_mode" onchange="updateBackgroundPreview(this.value)"><option {'selected' if bg.get('mode','fill')=='fill' else ''}>fill</option><option {'selected' if bg.get('mode')=='fit' else ''}>fit</option><option {'selected' if bg.get('mode')=='center' else ''}>center</option><option {'selected' if bg.get('mode')=='stretch' else ''}>stretch</option><option {'selected' if bg.get('mode')=='tile' else ''}>tile</option><option {'selected' if bg.get('mode')=='Cover' else ''}>Cover</option><option {'selected' if bg.get('mode')=='Contain' else ''}>Contain</option><option {'selected' if bg.get('mode')=='Span' else ''}>Span</option><option {'selected' if bg.get('mode')=='Mirror' else ''}>Mirror</option><option {'selected' if bg.get('mode')=='Reflect' else ''}>Reflect</option></select></div><button class="btn gold" style="margin-top:12px">💀 儲存背景</button></form></div></div></details>
    <script>function updateBackgroundPreview(mode){{const p=document.getElementById('backgroundPreview');if(!p)return;const url=p.dataset.imageUrl;if(!url)return;p.style.backgroundImage="url('\"+url+"')";p.style.backgroundPosition='center center';p.style.backgroundSize='auto';p.style.backgroundRepeat='no-repeat';p.style.transform='none';p.style.backgroundOrigin='padding-box';if(mode==='fill'||mode==='Cover')p.style.backgroundSize='cover';else if(mode==='fit'||mode==='Contain')p.style.backgroundSize='contain';else if(mode==='center')p.style.backgroundSize='auto';else if(mode==='stretch')p.style.backgroundSize='100% 100%';else if(mode==='tile'){{p.style.backgroundSize='auto';p.style.backgroundRepeat='repeat';}}else if(mode==='Span'){{p.style.backgroundSize='100% auto';}}else if(mode==='Mirror'){{p.style.backgroundSize='50% 100%';p.style.backgroundRepeat='repeat-x';p.style.backgroundPosition='left center';}}else if(mode==='Reflect'){{p.style.backgroundSize='50% 100%';p.style.backgroundRepeat='repeat-x';p.style.backgroundPosition='right center';}}}}document.addEventListener('DOMContentLoaded',()=>{{const s=document.getElementById('bgModePreview');if(s)updateBackgroundPreview(s.value);}});</script>
    <details open><summary>{esc(t("主題和特效模式", c))}</summary><div class="inside"><div class="theme-settings-row"><a class="theme-toggle-large" href="/theme-toggle">{'☀️ '+t("日間和夜間模式", c) if c.get('dark_mode',True) else '🌙 '+t("日間和夜間模式", c)}</a>{''.join(f'<a class="theme-toggle-large theme-setting-choice {"current" if theme_name(c)==code else ""}" href="/theme-select?name={code}">{esc(t(label,c))}</a>' for code,label in THEME_LABEL_KEYS.items())}</div><p class="smallmuted">{esc(t("按一下即時切換，不使用 checkbox。", c))}</p></div></details>
    <details open><summary>🌍 語言 / Language</summary><div class="inside"><p class="smallmuted">目前語言：{LANGUAGE_NAMES.get(c.get('language','zh-Hant'), c.get('language','en'))}</p><div class="actions"><a class="btn gray" href="/language?lang=zh-Hant">🇭🇰 繁體中文</a><a class="btn gray" href="/language?lang=en">🇬🇧 English</a><a class="btn gray" href="/language?lang=th">🇹🇭 ไทย</a><a class="btn gray" href="/language?lang=ja">🇯🇵 日本語</a><a class="btn gray" href="/language?lang=ko">🇰🇷 한국어</a><a class="btn gray" href="/language?lang=ru">🇷🇺 Русский</a><a class="btn gray" href="/language?lang=es">🇪🇸 Español</a><a class="btn gray" href="/language?auto=1">🌐 Browser 自動</a></div><p class="smallmuted">預設會按 Browser 語言自動切換；手動選擇後會記住此 Browser 的設定。</p></div></details>
    <details open><summary>🪟 透明化顯示比例</summary><div class="inside"><form method="post" action="/settings"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="action" value="transparency"><label class="small">系統透明化：<output id="opacityValue">{c.get('transparency',50)}%</output></label><input type="range" name="transparency" min="5" max="100" value="{c.get('transparency',50)}" oninput="opacityValue.value=this.value+'%'" style="width:100%"><div class="smallmuted">5% 最透明　　100% 不透明</div><button class="btn gold">💾 儲存透明度</button></form></div></details>
    {security_settings}
    </section>'''


def module_helpers():
    return {
        "load_json": load_json, "save_json": save_json, "esc": esc,
        "save_upload": save_upload, "save_cigarette_upload": lambda item: save_upload(item, 'cigarette'), "redirect": redirect,
        "TYPES_FILE": TYPES_FILE, "CLIENTS_FILE": CLIENTS_FILE, "RECORD_FILE": RECORD_FILE, "SELLERS_FILE": SELLERS_FILE,
        "UPLOAD_DIR": UPLOAD_DIR, "PROFILE_UPLOAD_DIR": PROFILE_UPLOAD_DIR, "CIGARETTE_UPLOAD_DIR": CIGARETTE_UPLOAD_DIR,
    }


def page_types(handler):
    return cigarette_types.page(handler, module_helpers())


def page_clients(handler):
    return clients_module.page(handler, module_helpers())


def page_record(handler):
    return record_module.page(handler, module_helpers())


def page_seller(handler):
    return seller_module.page(handler, module_helpers())


def handle_types_post(handler, data):
    return cigarette_types.handle_post(handler, data, module_helpers())


def handle_clients_post(handler, data):
    return clients_module.handle_post(handler, data, module_helpers())


def handle_record_post(handler, data):
    return record_module.handle_post(handler, data, module_helpers())


def handle_seller_post(handler, data):
    return seller_module.handle_post(handler, data, module_helpers())


def page_order(handler):
    return order_module.page(handler, module_helpers())


def make_cookie(name, value, max_age=None):
    parts=[f"{name}={value}", "Path=/", "HttpOnly", "SameSite=Lax"]
    if max_age is not None: parts.append(f"Max-Age={int(max_age)}")
    return "; ".join(parts)


class Handler(BaseHTTPRequestHandler):
    server_version = "SmokeSystem/1.0"
    def parse_url(self):
        p=urllib.parse.urlparse(self.path); self.path_only=p.path; self.query=urllib.parse.parse_qs(p.query); return p
    def setup_session(self):
        self.cookies=SimpleCookie(self.headers.get("Cookie",""))
        browser_lang = detect_browser_language(self.headers.get("Accept-Language", ""))
        manual_lang = None
        if self.cookies.get("manual_lang"):
            value = self.cookies.get("manual_lang").value
            if value in SUPPORTED_LANGUAGES:
                manual_lang = value
        REQUEST_LANGUAGE.set(manual_lang or browser_lang)
        sid=self.cookies.get("sid")
        self.session=None
        if sid:
            with LOCK: self.session=SESSIONS.get(sid.value)
        # Raspberry Pi 4 uses an automatically authenticated local session.
        if IS_RASPBERRY_PI4 and self.session is None:
            auto_sid = make_session(config().get("username", DEFAULT_LOGIN), False)
            with LOCK: self.session=SESSIONS.get(auto_sid)
            self._pi_auto_sid = auto_sid
        # Restore a persistent login from the same browser/device.
        if self.session is None:
            rem=self.cookies.get("remember")
            if rem:
                username=valid_remember_token(rem.value)
                if username:
                    sid_value=make_session(username, True)
                    with LOCK: self.session=SESSIONS.get(sid_value)
                    self._restored_sid=sid_value
                else:
                    self._restored_sid=None
            else:
                self._restored_sid=None
        else:
            self._restored_sid=None
    def send_html(self, body, status=200, extra_headers=None):
        body = localize_html(body)
        b=body.encode("utf-8"); self.send_response(status); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Language", config().get("language","en")); self.send_header("Content-Length",str(len(b))); self.send_header("X-Content-Type-Options","nosniff"); self.send_header("X-Frame-Options","SAMEORIGIN"); self.send_header("Referrer-Policy","same-origin");
        if getattr(self, "_pi_auto_sid", None):
            self.send_header("Set-Cookie", make_cookie("sid", self._pi_auto_sid))
        if extra_headers:
            for k,v in extra_headers: self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self.parse_url(); self.path_only = self.path_only.rstrip('/') or '/'; self.setup_session()
        if self.path_only=='/language':
            params=self.query
            if params.get('auto') == ['1']:
                value=''; max_age=0
            elif params.get('lang') and params.get('lang')[0] in SUPPORTED_LANGUAGES:
                value=params.get('lang')[0]; max_age=31536000
            elif params.get('toggle') == ['1']:
                current=config().get('language','zh-Hant')
                value='en' if current == 'zh-Hant' else 'zh-Hant'; max_age=31536000
            else:
                value=None; max_age=None
            if value is not None:
                target=self.headers.get('Referer','/')
                self.send_response(303); self.send_header('Location', target)
                if value:
                    self.send_header('Set-Cookie', make_cookie('manual_lang', value, max_age))
                else:
                    self.send_header('Set-Cookie', make_cookie('manual_lang', '', 0))
                self.end_headers(); return
        if self.path_only=='/theme-select':
            name=(self.query.get('name') or [''])[0]
            if name in THEMES:
                c=config(); c['theme']=name; save_json(CONFIG_FILE,c)
            self.send_response(303); self.send_header('Location', self.headers.get('Referer','/')); self.end_headers(); return
        if self.path_only=='/theme-toggle':
            c=config(); c['dark_mode']=not bool(c.get('dark_mode',True)); save_json(CONFIG_FILE,c)
            self.send_response(303); self.send_header('Location', self.headers.get('Referer','/')); self.end_headers(); return
        if self.path_only.startswith('/uploads/'):
            rel = urllib.parse.unquote(self.path_only[len('/uploads/'):]).lstrip('/')
            parts = [x for x in rel.split('/') if x not in ('', '.', '..')]
            if len(parts) < 2 or parts[0] not in ('profile','cigarette'):
                self.send_error(404); return
            fp = UPLOAD_DIR.joinpath(*parts)
            try:
                fp.resolve().relative_to(UPLOAD_DIR.resolve())
            except ValueError:
                self.send_error(404); return
            if not fp.exists() or not fp.is_file(): self.send_error(404); return
            data=fp.read_bytes()
            stat=fp.stat()
            etag=f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
            if self.headers.get('If-None-Match') == etag:
                self.send_response(304)
                self.send_header('ETag', etag)
                self.send_header('Cache-Control', 'private, max-age=31536000, immutable')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(fp.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('ETag', etag)
            self.send_header('Last-Modified', self.date_time_string(stat.st_mtime))
            self.send_header('Cache-Control', 'private, max-age=31536000, immutable')
            self.send_header('Vary', 'Accept-Encoding')
            self.end_headers(); self.wfile.write(data); return
        if IS_RASPBERRY_PI4 and self.path_only in ('/login', '/login-2fa'):
            redirect(self, '/?page=home'); return
        # The 2FA page is a GET page after the username/password POST redirects here.
        if self.path_only=='/login-2fa':
            pending=self.cookies.get('pending2fa')
            if not pending or not with_lock_get(pending.value):
                self.send_html(login_page('2FA 驗證工作階段已失效，請重新登入。'),401); return
            self.send_html(login_page('', totp=True)); return
        if self.path_only=='/logout':
            if IS_RASPBERRY_PI4:
                redirect(self, '/?page=home'); return
            sid=self.cookies.get('sid');
            if sid:
                with LOCK: SESSIONS.pop(sid.value,None)
            rem=self.cookies.get('remember')
            if rem: revoke_remember_token(rem.value)
            msg=random.choice(LOGOUT_MESSAGES); self.send_html(login_page(msg, hide_notice=True),200,[("Set-Cookie",'sid=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax'),("Set-Cookie",'remember=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax')]); return
        user=current_user(self)
        if self.path_only in ('/',''):
            if not user: self.send_html(login_page()); return
            page=self.query.get('page',['home'])[0]
            if page=='settings': body=settings_body(self); title='設定'
            elif page=='types': body=page_types(self); title='煙款'
            elif page=='clients': body=page_clients(self); title='訂煙者'
            elif page=='seller': body=page_seller(self); title='賣煙者'
            elif page=='record': body=page_record(self); title='訂煙記錄'
            elif page=='order': body=page_order(self); title='落單'
            else: body=home_body(); title='主頁'
            headers=[]
            if getattr(self,'_restored_sid',None):
                headers.append(('Set-Cookie', make_cookie('sid', self._restored_sid, 315360000)))
            self.send_html(layout(title,body,page,user),200,headers); return
        self.send_error(404)
    def do_POST(self):
        self.parse_url(); self.path_only = self.path_only.rstrip('/') or '/'; self.setup_session(); data=request_data(self)
        if self.path_only=='/login':
            if IS_RASPBERRY_PI4:
                redirect(self, '/?page=home'); return
            if data.get('csrf')!=GUEST_CSRF: self.send_html(login_page('登入頁面已失效，請重新整理。'),403); return
            c=config(); u=str(data.get('username','')); p=str(data.get('password',''))
            if hmac.compare_digest(u,c.get('username','')) and hmac.compare_digest(p,c.get('password','')):
                if c.get('totp',{}).get('enabled'):
                    pending=secrets.token_urlsafe(24); with_lock_store(pending,{'user':u,'remember':data.get('remember')=='1','created':time.time()});
                    self.send_response(303); self.send_header('Location','/login-2fa'); set_cookie(self,'pending2fa',pending,300); self.end_headers(); return
                remember=data.get('remember')=='1'; sid=make_session(u,remember); self.send_response(303); self.send_header('Location','/?page=home'); set_cookie(self,'sid',sid,315360000 if remember else None); 
                if remember: set_cookie(self,'remember',make_remember_token(u),315360000)
                self.end_headers(); return
            self.send_html(login_page('登入名稱或密碼錯誤。'),401); return
        if self.path_only=='/login-2fa':
            if IS_RASPBERRY_PI4:
                redirect(self, '/?page=home'); return
            pending=self.cookies.get('pending2fa'); p=with_lock_get(pending.value if pending else '')
            c=config()
            if not p or time.time()-p.get('created',0)>300 or not valid_totp(data.get('code',''),c.get('totp',{}).get('secret','')):
                self.send_html(login_page('2FA 驗證失敗。'),401); return
            remember=bool(p.get('remember')); sid=make_session(p['user'],remember); self.send_response(303); self.send_header('Location','/?page=home'); set_cookie(self,'sid',sid,315360000 if remember else None); 
            if remember: set_cookie(self,'remember',make_remember_token(p['user']),315360000)
            set_cookie(self,'pending2fa','',0); self.end_headers(); return
        user=require_login(self)
        if not user: return
        if not csrf_ok(self,data.get('csrf')): self.send_html(layout('錯誤','<div class="skullframe"><div class="notice danger">CSRF 驗證失敗，請重新整理頁面。</div></div>',user=user),403); return
        if self.path_only=='/types':
            if handle_types_post(self, data): return
        if self.path_only=='/clients':
            if handle_clients_post(self, data): return
        if self.path_only=='/record':
            if handle_record_post(self, data): return
        if self.path_only=='/seller':
            if handle_seller_post(self, data): return
        if self.path_only=='/settings':
            action=str(data.get('action','')).strip(); c=config()
            if IS_RASPBERRY_PI4 and action in {'credentials', 'adminpass', 'verify_qr', 'totp_save', 'totp_regen'}:
                redirect(self, '/?page=settings'); return
            if action=='background':
                if data.get('bg_type')=='image':
                    uploaded = data.get('background_file')
                    if isinstance(uploaded, tuple) and uploaded[0]:
                        chosen = save_upload(uploaded, 'profile')
                    else:
                        chosen = os.path.basename(str(data.get('profile_existing','')).strip())
                    if chosen and (PROFILE_UPLOAD_DIR / chosen).is_file():
                        c['background']={'type':'image','value':chosen,'mode':data.get('bg_mode','fill')}
                    else:
                        c['background']={'type':'color','value':data.get('color','#120808'),'mode':'fill'}
                else: c['background']={'type':'color','value':data.get('color','#120808'),'mode':'fill'}
                save_json(CONFIG_FILE,c)
            elif action=='transparency':
                try: c['transparency']=max(5,min(100,int(data.get('transparency','50'))))
                except (ValueError, TypeError): c['transparency']=50
                save_json(CONFIG_FILE,c)
            elif action=='credentials':
                if hmac.compare_digest(str(data.get('current_username','')),c.get('username','')) and hmac.compare_digest(str(data.get('current_password','')),c.get('password','')):
                    c['username']=str(data.get('new_username','')).strip(); c['password']=str(data.get('new_password','')); save_json(CONFIG_FILE,c)
                else: self.send_html(layout('設定錯誤','<section class="skullframe"><div class="notice danger">目前登入名稱或密碼錯誤。</div></section>',user=user)); return
            elif action=='adminpass':
                if hmac.compare_digest(str(data.get('current_admin','')),c.get('admin_password','')):
                    c['admin_password']=str(data.get('new_admin','')); save_json(CONFIG_FILE,c)
                else: self.send_html(layout('設定錯誤','<section class="skullframe"><div class="notice danger">目前 admin 密碼錯誤。</div></section>',user=user)); return
            elif action=='verify_qr':
                if hmac.compare_digest(str(data.get('admin_password','')),c.get('admin_password','')): redirect(self,'/?page=settings&showqr=1&adminok=1'); return
                self.send_html(layout('設定錯誤','<section class="skullframe"><div class="notice danger">admin 密碼錯誤。</div></section>',user=user)); return
            elif action=='totp_save':
                if not c.get('totp',{}).get('secret'): c['totp']['secret']=new_totp_secret()
                c['totp']['enabled']=data.get('totp_enabled')=='1'; save_json(CONFIG_FILE,c)
            elif action=='totp_regen':
                c['totp']['secret']=new_totp_secret(); save_json(CONFIG_FILE,c)
            redirect(self,'/?page=settings'); return
        if self.path_only == '/settings':
            redirect(self,'/?page=settings'); return
        self.send_error(404)


def with_lock_store(k,v):
    with LOCK: SESSIONS['pending:'+k]=v

def with_lock_get(k):
    with LOCK: return SESSIONS.get('pending:'+k)

def save_upload(item, subdir='profile'):
    filename, data, ctype=item
    allowed={'.jpg','.jpeg','.png','.gif','.webp','.bmp'}
    safe_name = os.path.basename(str(filename or '')).strip()
    ext = Path(safe_name).suffix.lower()
    if not safe_name or ext not in allowed:
        raise ValueError('只接受圖片檔案。')
    target_dir = PROFILE_UPLOAD_DIR if subdir == 'profile' else CIGARETTE_UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / safe_name).write_bytes(data)
    return safe_name


def main():
    import argparse
    parser=argparse.ArgumentParser(description='🚬食少支煙系統')
    parser.add_argument('--port',type=int,default=PORT_DEFAULT)
    parser.add_argument('--host',default='0.0.0.0')
    args=parser.parse_args(); config()
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'🚬 食少支煙系統 running at http://0.0.0.0:{args.port}')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
