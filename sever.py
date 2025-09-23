import os
import subprocess
from threading import Thread
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "message": "Load test service is running"
    })

def run_load_test():
    cmd = [
        "python", "load_test.py",
        "--url", "https://nhacaituoilon.site",
        "--requests", "100000000000000",   # chỉnh số request hợp lý
        "--concurrency", "20",
        "--confirm"
    ]
    subprocess.run(cmd)

if __name__ == "__main__":
    # chạy load test ở background
    t = Thread(target=run_load_test, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
