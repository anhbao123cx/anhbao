import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import time
import threading
from flask import Flask, jsonify

# ======================
# Cấu hình
# ======================
BASE = "https://aibcr.to"
LOGIN_URL = f"{BASE}/login"
LOBBY_URL = f"{BASE}/ae/lobby"
GETNEWRESULT_URL = f"{BASE}/baccarat/getnewresult"

USERNAME = "Nam1411"
PASSWORD = "Nam14112009"

# ======================
# Biến toàn cục
# ======================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
})

last_results = {}      # cache để phát hiện thay đổi
filtered_data = []     # danh sách đầy đủ các bàn
auto_running = True

# ======================
# Hàm phụ
# ======================
def get_csrf_token(html):
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("input", {"name": "_token"})
    if t and t.get("value"):
        return t["value"]
    meta = soup.find("meta", {"name": "csrf-token"})
    if meta and meta.get("content"):
        return meta["content"]
    return None

def login():
    r = session.get(LOGIN_URL, timeout=15)
    token = get_csrf_token(r.text)
    payload = {"username": USERNAME, "password": PASSWORD, "action": "Login"}
    if token:
        payload["_token"] = token
    headers = {"Referer": LOGIN_URL, "Origin": BASE, "Content-Type": "application/x-www-form-urlencoded"}
    resp = session.post(LOGIN_URL, data=payload, headers=headers, timeout=15)
    print("✅ Đăng nhập:", resp.status_code)

def go_to_lobby():
    session.get(LOBBY_URL, timeout=15)

def call_getnewresult():
    global filtered_data
    xsrf_token = unquote(session.cookies.get("XSRF-TOKEN", ""))
    headers = {
        "Referer": LOBBY_URL,
        "Origin": BASE,
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": xsrf_token,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        resp = session.post(GETNEWRESULT_URL, headers=headers, data={"gameCode": "ae"}, timeout=15)
        if not resp.ok:
            print(f"⚠️ getnewresult lỗi: {resp.status_code}")
            return

        data = resp.json().get("data", [])
        new_filtered = []

        for t in data:
            tb_name = t.get("table_name", "")
            curr = t.get("result", "")
            prev = last_results.get(tb_name, "")

            # Nếu kết quả mới khác cache thì cập nhật
            if curr and curr != prev:
                last_results[tb_name] = curr
                new_filtered.append({
                    "table_name": tb_name,
                    "result": curr,
                    "goodRoad": t.get("goodRoad", ""),
                    "shoeId": t.get("shoeId", ""),
                    "round": t.get("round", ""),
                    "time": time.strftime("%H:%M:%S")
                })

        if new_filtered:
            # Cập nhật vào danh sách chính
            fd_dict = {item["table_name"]: item for item in filtered_data}
            for f in new_filtered:
                fd_dict[f["table_name"]] = f
                print(f"✅ {f['table_name']} đổi: {f['result']}")
            filtered_data = list(fd_dict.values())

    except Exception as e:
        print("❌ Lỗi call_getnewresult:", e)

# ======================
# Tự động treo
# ======================
def auto_loop():
    while auto_running:
        call_getnewresult()
        time.sleep(1)

# ======================
# API duy nhất
# ======================
app = Flask(__name__)

@app.route("/data")
def get_data():
    # Sắp xếp theo tên bàn (nếu muốn)
    sorted_data = sorted(filtered_data, key=lambda x: x["table_name"])
    return jsonify(sorted_data)

# ======================
# Khởi động
# ======================
if __name__ == "__main__":
    login()
    go_to_lobby()
    threading.Thread(target=auto_loop, daemon=True).start()
    print("🚀 API chạy tại: http://127.0.0.1:5000/data")
    app.run(host="0.0.0.0", port=5000)
    
