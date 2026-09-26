from flask import Flask, jsonify
import threading
from update_playlist import build_multichannel_playlist, push_to_github

app = Flask(__name__)

def run_job():
    print("[*] Webhook triggered: Starting scraper...")
    build_multichannel_playlist()
    push_to_github()

@app.route("/")
def home():
    return "IPTV Scraper Bot is running."

@app.route("/trigger")
def trigger():
    # Run scraper in a background thread so the HTTP request responds immediately
    threading.Thread(target=run_job).start()
    return jsonify({"status": "Scraper job initiated"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
