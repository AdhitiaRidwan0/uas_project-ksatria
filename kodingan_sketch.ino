#include <WiFi.h>
#include <PubSubClient.h>

const char* ssid = "Wokwi-GUEST";
const char* password = "";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;

// Jalur MQTT Broker
const char* topic_telemetri = "kesatria/kamar/telemetri";
const char* topic_relay     = "kesatria/kamar/relay";
const char* topic_ledstrip  = "kesatria/kamar/ledstrip"; // Jalur Slider DAC
const char* topic_mode      = "kesatria/kamar/mode";     // Jalur Mode Kendali Web

// Definisi PIN Komponen
const int pinPIRKamar = 23;
const int pinPIRWc    = 19;
const int pinTrig     = 5;
const int pinEcho     = 18;
const int pinACS      = 36; // ADC Potensio Arus
const int pinDACAmbient = 25; // DAC Lampu Ambient

const int pinRelayKamar = 22;
const int pinRelayWc    = 21;
const int pinRelayMeja  = 4;

// Variabel untuk menyimpan status mode kendali (default: auto)
String modeKamar = "auto";
String modeWc    = "auto";
String modeMeja  = "auto";

WiFiClient espClient;
PubSubClient client(espClient);
unsigned long lastMsg = 0;

void setup_wifi() {
  delay(10);
  Serial.println("\n--- Menghubungkan Wi-Fi Wokwi ---");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi Terhubung!");
}

// Fungsi CALLBACK: Menerima kendali dari MQTT Website
void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) { message += (char)payload[i]; }
  
  // A. Memproses Perintah Overrule Relay dari AI (Jika ada instruksi force-off)
  if (String(topic) == topic_relay) {
    if (message.length() == 3) {
      if (message.charAt(0) == '0') digitalWrite(pinRelayKamar, LOW);
      if (message.charAt(1) == '0')    digitalWrite(pinRelayWc, LOW);
      if (message.charAt(2) == '0')  digitalWrite(pinRelayMeja, LOW);
      Serial.println("-> Optimasi Energi Diterapkan oleh AI Pengawas.");
    }
  }
  
  // B. Memproses Nilai Slider DAC untuk Kecerahan LED Ambient
  if (String(topic) == topic_ledstrip) {
    int brightness = message.toInt();
    if (brightness >= 0 && brightness <= 255) {
      dacWrite(pinDACAmbient, brightness); // Eksekusi DAC
      Serial.print("-> Brightness DAC Diatur ke: ");
      Serial.println(brightness);
    }
  }

  // C. BARU: Memproses Perubahan Mode (Auto / Always ON / Always OFF) dari Dashboard Website
  if (String(topic) == topic_mode) {
    // Format pesan dari web: "auto,on,off"
    // Kita pecah string berdasarkan tanda koma
    int koma1 = message.indexOf(',');
    int koma2 = message.indexOf(',', koma1 + 1);
    
    if (koma1 != -1 && koma2 != -1) {
      modeKamar = message.substring(0, koma1);
      modeWc    = message.substring(koma1 + 1, koma2);
      modeMeja  = message.substring(koma2 + 1);
      
      Serial.printf("-> Mode Diperbarui via Web -> Kamar: %s, WC: %s, Meja: %s\n", 
                    modeKamar.c_str(), modeWc.c_str(), modeMeja.c_str());
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Mencoba koneksi MQTT...");
    String clientId = "ESP32-Kesatria-" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      Serial.println("TERHUBUNG!");
      client.subscribe(topic_relay);
      client.subscribe(topic_ledstrip);
      client.subscribe(topic_mode); // Kriteria Tambahan: Subscribe ke mode kendali dashboard
    } else {
      delay(5000);
    }
  }
}

long bacaJarakUltrasonik() {
  digitalWrite(pinTrig, LOW); delayMicroseconds(2);
  digitalWrite(pinTrig, HIGH); delayMicroseconds(10);
  digitalWrite(pinTrig, LOW);
  return pulseIn(pinEcho, HIGH) * 0.034 / 2;
}

void setup() {
  Serial.begin(115200);
  
  pinMode(pinPIRKamar, INPUT); pinMode(pinPIRWc, INPUT);
  pinMode(pinTrig, OUTPUT); pinMode(pinEcho, INPUT);
  pinMode(pinRelayKamar, OUTPUT); pinMode(pinRelayWc, OUTPUT); pinMode(pinRelayMeja, OUTPUT);
  
  dacWrite(pinDACAmbient, 0); // Awalan DAC mati

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) { reconnect(); }
  client.loop();

  // Membaca kondisi fisik sensor
  int pirKamar = digitalRead(pinPIRKamar);
  int pirWc    = digitalRead(pinPIRWc);
  long jarak   = bacaJarakUltrasonik();

  // ========================================================
  //   LOGIKA KENDALI UTAM DENGAN PILIHAN MODE DARI WEB
  // ========================================================
  
  // 1. Logika Jalur Lampu Kamar
  if (modeKamar == "on")       digitalWrite(pinRelayKamar, HIGH);
  else if (modeKamar == "off") digitalWrite(pinRelayKamar, LOW);
  else                         digitalWrite(pinRelayKamar, pirKamar == 1 ? HIGH : LOW); // Mode Auto (Sensor)

  // 2. Logika Jalur Lampu WC
  if (modeWc == "on")       digitalWrite(pinRelayWc, HIGH);
  else if (modeWc == "off") digitalWrite(pinRelayWc, LOW);
  else                         digitalWrite(pinRelayWc, pirWc == 1 ? HIGH : LOW);       // Mode Auto (Sensor)

  // 3. Logika Jalur Lampu Meja
  if (modeMeja == "on")       digitalWrite(pinRelayMeja, HIGH);
  else if (modeMeja == "off") digitalWrite(pinRelayMeja, LOW);
  else                         digitalWrite(pinRelayMeja, (jarak > 0 && jarak < 50) ? HIGH : LOW); // Mode Auto (Sensor)

  // ========================================================
  //   KIRIM TELEMETRI DATA SENSOR (TIAP 2 DETIK)
  // ========================================================
  unsigned long now = millis();
  if (now - lastMsg > 2000) { 
    lastMsg = now;
    int watt = analogRead(pinACS); 

    // Update payload agar dashboard web tahu status terkini pin lampu (HIGH/LOW)
    String statusKamar = String(digitalRead(pinRelayKamar));
    String statusWc    = String(digitalRead(pinRelayWc));
    String statusMeja  = String(digitalRead(pinRelayMeja));
    String gabunganStatus = statusKamar + statusWc + statusMeja;

    String payload = "{\"pir_kamar\":" + String(pirKamar) + 
                     ",\"pir_wc\":" + String(pirWc) + 
                     ",\"jarak_meja\":" + String(jarak) + 
                     ",\"total_watt\":" + String(watt) + "}";
    
    client.publish(topic_telemetri, payload.c_str());
    client.publish(topic_relay, gabunganStatus.c_str()); // Sync status lampu ke web
  }
}