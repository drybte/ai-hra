import os
import time
import requests
import datetime
import urllib3
import redis
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

app = Flask(__name__)

api_key = os.environ.get("OPENAI_API_KEY", "")
base_url = os.environ.get("OPENAI_BASE_URL", "https://kurim.ithope.eu/v1")

redis_host = os.environ.get("REDIS_HOST", "cache")
redis_port = int(os.environ.get("REDIS_PORT", 6379))

r = None
for _ in range(10):
    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        r.ping()
        print("Redis connected")
        break
    except Exception:
        print("Waiting for Redis...")
        time.sleep(2)

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "status": "running",
        "timestamp": datetime.datetime.now().isoformat(),
        "author": "Terka",
        "app": "AI Game Advisor"
    })

@app.route('/recommend', methods=['POST'])
def game_advisor():
    data = request.get_json(silent=True) or {}
    genre = data.get("genre", "akční").strip().lower()

    cache_key = f"recommendation:{genre}"

    try:
        if r:
            cached = r.get(cache_key)
            if cached:
                return jsonify({
                    "recommendation": cached,
                    "source": "cache"
                })
    except Exception as e:
        print(f"Redis read error: {e}")

    prompt = (
        f"Uživatel má rád herní žánr: {genre}. "
        "Doporuč mu jednu konkrétní aktuální hru, která do tohoto žánru patří. "
        "Odpověz pouze jednou krátkou větou v češtině a stručně uveď, proč by si ji měl zahrát."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemma3:27b",
        "messages": [
            {"role": "system", "content": "Jsi expert na videohry a herní průmysl."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    try:
        clean_url = base_url.rstrip('/')
        target_url = f"{clean_url}/chat/completions"

        print(f"DEBUG: Doporučuji hru pro žánr: {genre}")

        response = requests.post(
            target_url,
            headers=headers,
            json=payload,
            timeout=20,
            verify=False
        )

        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']

            try:
                if r:
                    r.set(cache_key, ai_response)
            except Exception as e:
                print(f"Redis write error: {e}")

            return jsonify({
                "recommendation": ai_response,
                "source": "api"
            })
        else:
            return jsonify({
                "error": f"Server vrátil {response.status_code}.",
                "details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": f"Spojení selhalo: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
