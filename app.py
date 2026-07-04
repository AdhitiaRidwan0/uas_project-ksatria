import time
import json
from flask import Flask, render_template_string, request, jsonify
import paho.mqtt.client as mqtt
from google import genai

# 1. SETUP GEMINI AI (Untuk fungsi pengawas/analisis di background)
GEMINI_API_KEY = "AQ.Ab8RN6LuetIGG1E8HY3VuaVXGl4sEC-w-brOD0KCLtsNEWUw0g"
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# 2. SETUP FLASK WEB SERVER
app = Flask(__name__)

# Data global terpadu untuk monitoring dan kontrol
data_kamar = {
    "pir_kamar": 0,
    "pir_wc": 0,
    "jarak_meja": 150,
    "total_watt": 0,
    "status_relay": "000",
    "brightness_ambient": 0,    # Status awal kecerahan DAC
    "mode_kamar": "auto",       # Opsi: auto, on, off
    "mode_wc": "auto",          # Opsi: auto, on, off
    "mode_meja": "auto",        # Opsi: auto, on, off
    "analisis_ai": "Menunggu telemetri aktif..."
}

# 3. SETUP MQTT BROKER
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_TELEMETRI = "kesatria/kamar/telemetri"
TOPIC_RELAY = "kesatria/kamar/relay"
TOPIC_LEDSTRIP = "kesatria/kamar/ledstrip"
TOPIC_MODE = "kesatria/kamar/mode"  # Jalur untuk mengirim mode kendali ke ESP32

waktu_analisis_terakhir = 0
jeda_analisis = 30 # Minta analisis Gemini tiap 30 detik agar hemat kuota API

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Python Backend & Web Server Sukses Terhubung ke HiveMQ!")
        client.subscribe(TOPIC_TELEMETRI)
        client.subscribe(TOPIC_RELAY)
    else:
        print(f"Gagal konek ke MQTT, error code: {reason_code}")

def on_message(client, userdata, msg):
    global waktu_analisis_terakhir
    topic = msg.topic
    payload_str = msg.payload.decode()

    if topic == TOPIC_RELAY:
        if len(payload_str) == 3 and payload_str.isdigit():
            data_kamar["status_relay"] = payload_str
        return

    if topic == TOPIC_TELEMETRI:
        try:
            payload = json.loads(payload_str)
            data_kamar["pir_kamar"] = payload["pir_kamar"]
            data_kamar["pir_wc"] = payload["pir_wc"]
            data_kamar["jarak_meja"] = payload["jarak_meja"]
            data_kamar["total_watt"] = int(payload["total_watt"] * (3000.0 / 4095.0))

            # Proses Background AI Gemini untuk Evaluasi Energi Efisiensi
            waktu_sekarang = time.time()
            if waktu_sekarang - waktu_analisis_terakhir > jeda_analisis:
                waktu_analisis_terakhir = waktu_sekarang
                
                status_kamar = "ADA AKTIVITAS" if data_kamar["pir_kamar"] == 1 else "KOSONG"
                status_wc = "ADA AKTIVITAS" if data_kamar["pir_wc"] == 1 else "KOSONG"
                
                prompt = f"""
                Kamu adalah AI pengawas energi kamar kos UTB. 
                Data saat ini: Kamar={status_kamar}, WC={status_wc}, Jarak Meja={data_kamar['jarak_meja']}cm, Daya={data_kamar['total_watt']}W.
                Berikan satu kalimat evaluasi/saran singkat apakah penggunaan energi saat ini boros atau efisien. Jangan berikan tag keputusan angka lagi.
                """
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    data_kamar["analisis_ai"] = response.text.strip()
                except Exception as ai_err:
                    data_kamar["analisis_ai"] = "Sistem otomatis berjalan stabil via kendali lokal."
                    
        except Exception as e:
            print("Error parsing data telemetri:", e)

# 4. HALAMAN DASHBOARD INTERFACE (HTML, CSS, JAVASCRIPT AJAX)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🛡️ K.E.S.A.T.R.I.A Smart Controller</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1e1e2e; color: #cdd6f4; text-align: center; padding: 20px; }
        .wrapper { max-width: 900px; margin: 0 auto; }
        .container { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-top: 20px; }
        .card { background: #313244; padding: 20px; border-radius: 12px; width: 250px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); text-align: left; }
        .card h3 { margin-top: 0; color: #89b4fa; border-bottom: 1px solid #45475a; padding-bottom: 8px; }
        .card-large { background: #45475a; padding: 20px; border-radius: 12px; margin: 20px auto; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        .status-indicator { font-size: 20px; font-weight: bold; margin: 15px 0; text-align: center; border-radius: 6px; padding: 5px; }
        .on { background: #2e3f37; color: #a6e3a1; }
        .off { background: #413038; color: #f38ba8; }
        .control-group { margin-top: 15px; }
        label { font-size: 13px; color: #bac2de; block; margin-bottom: 5px; }
        select, input[type="range"] { width: 100%; padding: 8px; background: #181825; border: 1px solid #45475a; color: #cdd6f4; border-radius: 6px; cursor: pointer; }
        .info-spec { font-size: 12px; color: #a6adc8; margin: 4px 0; }
        h1 { margin-bottom: 5px; color: #89b4fa; }
    </style>
    <script>
        // Menggunakan JavaScript AJAX agar saat ganti tombol/slider halaman tidak perlu refresh kasar
        function updateControl(type, val) {
            fetch('/api/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: type, value: val })
            });
        }
        
        // Auto-refresh halaman secara halus tiap 2 detik untuk update sensor otomatis
        setInterval(function() {
            window.location.reload();
        }, 2500);
    </script>
</head>
<body>
    <div class="wrapper">
        <h1>🛡️ K.E.S.A.T.R.I.A Smart Dashboard</h1>
        <p style="color: #a6adc8; margin-top:0;">Sistem IoT Kendali Energi & Penerapan Sinyal ADC/DAC/PWM</p>
        
        <div class="container">
            <div class="card">
                <h3>🔴 Lampu Kamar</h3>
                <div class="status-indicator {{ 'on' if data.status_relay[0] == '1' else 'off' }}">
                    {{ 'MENYALA' if data.status_relay[0] == '1' else 'MATI' }}
                </div>
                <p class="info-spec">📌 Sensor PIR: <b>{{ 'Ada Gerakan' if data.pir_kamar == 1 else 'Kosong' }}</b></p>
                <div class="control-group">
                    <label>Mode Switch:</label>
                    <select onchange="updateControl('mode_kamar', this.value)">
                        <option value="auto" {{ 'selected' if data.mode_kamar == 'auto' }}>🔄 Otomatis (Sensor)</option>
                        <option value="on" {{ 'selected' if data.mode_kamar == 'on' }}>💡 Selalu Nyala (Always ON)</option>
                        <option value="off" {{ 'selected' if data.mode_kamar == 'off' }}>🔌 Selalu Mati (Always OFF)</option>
                    </select>
                </div>
            </div>

            <div class="card">
                <h3>🟢 Lampu WC</h3>
                <div class="status-indicator {{ 'on' if data.status_relay[1] == '1' else 'off' }}">
                    {{ 'MENYALA' if data.status_relay[1] == '1' else 'MATI' }}
                </div>
                <p class="info-spec">📌 Sensor PIR: <b>{{ 'Ada Gerakan' if data.pir_wc == 1 else 'Kosong' }}</b></p>
                <div class="control-group">
                    <label>Mode Switch:</label>
                    <select onchange="updateControl('mode_wc', this.value)">
                        <option value="auto" {{ 'selected' if data.mode_wc == 'auto' }}>🔄 Otomatis (Sensor)</option>
                        <option value="on" {{ 'selected' if data.mode_wc == 'on' }}>💡 Selalu Nyala (Always ON)</option>
                        <option value="off" {{ 'selected' if data.mode_wc == 'off' }}>🔌 Selalu Mati (Always OFF)</option>
                    </select>
                </div>
            </div>

            <div class="card">
                <h3>🔵 Lampu Meja Belajar</h3>
                <div class="status-indicator {{ 'on' if data.status_relay[2] == '1' else 'off' }}">
                    {{ 'MENYALA' if data.status_relay[2] == '1' else 'MATI' }}
                </div>
                <p class="info-spec">📌 Jarak Ultrasonik: <b>{{ data.jarak_meja }} cm</b></p>
                <div class="control-group">
                    <label>Mode Switch:</label>
                    <select onchange="updateControl('mode_meja', this.value)">
                        <option value="auto" {{ 'selected' if data.mode_meja == 'auto' }}>🔄 Otomatis (Sensor)</option>
                        <option value="on" {{ 'selected' if data.mode_meja == 'on' }}>💡 Selalu Nyala (Always ON)</option>
                        <option value="off" {{ 'selected' if data.mode_meja == 'off' }}>🔌 Selalu Mati (Always OFF)</option>
                    </select>
                </div>
            </div>

            <div class="card" style="border: 1px solid #f9e2af;">
                <h3>✨ Ambient LED (DAC Pin 25)</h3>
                <div class="status-indicator on" style="background: #45475a; color: #f9e2af; font-size: 16px;">
                    🎚️ Kecerahan: <span id="val_bright">{{ data.brightness_ambient }}</span> / 255
                </div>
                <p class="info-spec">⚡ Output Isyarat: <b>Analog DAC (0 - 3.3V)</b></p>
                <div class="control-group" style="margin-top: 25px;">
                    <label>Geser Kecerahan:</label>
                    <input type="range" min="0" max="255" value="{{ data.brightness_ambient }}" 
                           oninput="document.getElementById('val_bright').innerText=this.value;"
                           onchange="updateControl('brightness', this.value)">
                </div>
            </div>
        </div>

        <div class="card-large" style="background: #313244; margin-top:25px; text-align: left;">
            <h3 style="margin-top:0; color:#eba0ac;">⚡ Analisis ADC & Monitoring Beban Kamar</h3>
            <p style="font-size: 18px;">Total Konsumsi Daya: <b style="color: #f9e2af; font-size:24px;">{{ data.total_watt }} Watt</b> (Dibaca lewat pin ADC GPIO 36)</p>
        </div>

        <div class="card-large" style="text-align: left; border-left: 6px solid #89b4fa;">
            <h3 style="margin-top:0; color:#89b4fa;">🤖 Rekomendasi Sistem Pakar (Gemini LLM)</h3>
            <p style="font-style: italic; color: #a6adc8; font-size: 15px;">"{{ data.analisis_ai }}"</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, data=data_kamar)

# API Endpoint untuk menangkap aksi penekanan tombol toggle & geseran slider
@app.route('/api/control', methods=['POST'])
def control_api():
    req_data = request.get_json()
    ctrl_type = req_data.get('type')
    value = req_data.get('value')
    
    if ctrl_type == 'brightness':
        data_kamar['brightness_ambient'] = int(value)
        mqtt_client.publish(TOPIC_LEDSTRIP, str(value))
        print(f"Mengirim Perintah Kecerahan DAC ke MQTT: {value}")
        
    elif ctrl_type in ['mode_kamar', 'mode_wc', 'mode_meja']:
        data_kamar[ctrl_type] = value
        # Susun payload string berisi informasi perubahan mode
        # Format: modeKamar,modeWc,modeMeja (Contoh: "auto,on,off")
        payload_mode = f"{data_kamar['mode_kamar']},{data_kamar['mode_wc']},{data_kamar['mode_meja']}"
        mqtt_client.publish(TOPIC_MODE, payload_mode)
        print(f"Mengirim Pembaruan Mode Kendali ke MQTT: {payload_mode}")
        
    return jsonify({"status": "success"})

# Menjalankan MQTT Client Paho v2
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)