from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import re
from datetime import datetime
import threading
import time

app = Flask(__name__)
CORS(app)

# Кеш для курсов
cached_rates = {
    "usd": 77.52,
    "eur": 92.08,
    "cny": 11.35,
    "jpy": 51.50,
    "krw": 16.89,
    "krw_usd": 1450.0,
    "eur_cb": 89.63,
    "last_update": None
}

# Кеш для расходов по странам
cached_country_costs = {
    "japan": { "localExpenses": 220000, "brokerFee": 27000, "currencyName": "йен" },
    "china": { "localExpenses": 12500, "brokerFee": 65000, "currencyName": "юаней" },
    "korea": { "localExpenses": 2000000, "brokerFee": 85000, "currencyName": "вон" }
}

# Кеш для фиксированных расходов
cached_fixed_costs = {
    "customsFee": 1300,
    "waycar": 60000
}

def parse_atb_rates():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get('https://www.atb.su/', headers=headers, timeout=15)
        html = response.text
        
        usd_match = re.search(r'USD.*?продажа\s*([\d.]+)', html, re.I)
        if usd_match: cached_rates['usd'] = float(usd_match.group(1))
        
        eur_match = re.search(r'EUR.*?продажа\s*([\d.]+)', html, re.I)
        if eur_match: cached_rates['eur'] = float(eur_match.group(1))
        
        cny_match = re.search(r'CNY.*?продажа\s*([\d.]+)', html, re.I)
        if cny_match: cached_rates['cny'] = float(cny_match.group(1))
        
        jpy_match = re.search(r'JPY.*?продажа\s*([\d.]+)', html, re.I)
        if jpy_match: cached_rates['jpy'] = float(jpy_match.group(1))
        
        krw_match = re.search(r'(?:KRW|Вон).*?продажа\s*([\d.]+)', html, re.I)
        if krw_match: cached_rates['krw'] = float(krw_match.group(1))
        
        return True
    except Exception as e:
        print(f"Ошибка АТБ: {e}")
        return False

def parse_cbr_eur():
    try:
        response = requests.get('https://www.cbr.ru/scripts/XML_daily.asp', timeout=15)
        text = response.text
        match = re.search(r'EUR.*?(\d+[\.,]\d+)', text, re.I)
        if match:
            rate = float(match.group(1).replace(',', '.'))
            if 50 < rate < 150:
                cached_rates['eur_cb'] = rate
                return True
        return False
    except Exception as e:
        print(f"Ошибка ЦБ: {e}")
        return False

def parse_krw_usd():
    try:
        response = requests.get('https://api.exchangerate-api.com/v4/latest/KRW', timeout=10)
        data = response.json()
        if data.get('rates') and data['rates'].get('USD'):
            krw_usd_rate = 1 / data['rates']['USD']
            cached_rates['krw_usd'] = round(krw_usd_rate, 2)
            return True
        return False
    except Exception as e:
        print(f"Ошибка KRW/USD: {e}")
        return False

def update_rates():
    print(f"[{datetime.now()}] Обновление курсов с АТБ...")
    parse_atb_rates()
    parse_cbr_eur()
    parse_krw_usd()
    cached_rates['last_update'] = datetime.now().isoformat()
    print(f"[{datetime.now()}] Курсы обновлены: USD={cached_rates['usd']}, EUR={cached_rates['eur']}")

# Фоновое обновление каждые 30 минут
def background_updater():
    while True:
        time.sleep(1800)  # 30 минут
        update_rates()

@app.route('/rates')
def get_rates():
    return jsonify(cached_rates)

@app.route('/settings', methods=['GET'])
def get_settings():
    return jsonify({
        "rates": cached_rates,
        "countryCosts": cached_country_costs,
        "fixedCosts": cached_fixed_costs
    })

@app.route('/save', methods=['POST'])
def save_settings():
    try:
        data = request.json
        print(f"[{datetime.now()}] Сохранение настроек")
        
        if data.get('rates'):
            for key, value in data['rates'].items():
                if key in cached_rates:
                    cached_rates[key] = value
            print(f"Сохранены курсы: USD={cached_rates['usd']}")
        
        if data.get('countryCosts'):
            for country, costs in data['countryCosts'].items():
                if country in cached_country_costs:
                    cached_country_costs[country] = costs
        
        if data.get('fixedCosts'):
            for key, value in data['fixedCosts'].items():
                if key in cached_fixed_costs:
                    cached_fixed_costs[key] = value
        
        return jsonify({"status": "ok", "message": "Настройки сохранены"})
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/update', methods=['POST'])
def force_update():
    update_rates()
    return jsonify({"status": "ok", "rates": cached_rates})

if __name__ == '__main__':
    # Первое обновление при запуске
    update_rates()
    # Запускаем фоновое обновление
    thread = threading.Thread(target=background_updater)
    thread.daemon = True
    thread.start()
    app.run(host='0.0.0.0', port=10000)
