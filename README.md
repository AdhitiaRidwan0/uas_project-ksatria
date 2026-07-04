# Project KSATRIA - Smart Room Automation System 🚀

Project KSATRIA adalah sistem otomasi ruangan pintar (Smart Room) berbasis IoT (Internet of Things) menggunakan mikrokontroler **ESP32** dan *dashboard* kontrol berbasis web menggunakan **Flask (Python)**. Sistem ini mengintegrasikan berbagai sensor untuk efisiensi energi dan kenyamanan pengguna secara otomatis maupun manual melalui protokol komunikasi **MQTT**.

---

## 📌 Fitur Utama
- **Otomasi Lampu Kamar & WC:** Menggunakan sensor PIR untuk mendeteksi gerakan secara *real-time*.
- **Otomasi Lampu Meja Belajar:** Menggunakan sensor Ultrasonik untuk mendeteksi keberadaan pengguna berdasarkan jarak objek.
- **Ambient Light Dimmer:** Fitur kontrol tingkat kecerahan lampu ambient menggunakan output DAC internal ESP32.
- **Monitoring Telemetry:** Pengiriman data sensor dan status konsumsi daya (via sensor ACS) secara berkala setiap 2 detik ke broker MQTT.
- **Dual Mode Control:** Sistem dapat berjalan secara otomatis (`auto`) berbasis sensor atau dikontrol penuh secara manual (`on`/`off`) melalui Dashboard Web.
- **High-Speed Lightweight Dashboard:** Web kontrol responsif berbasis Flask yang terhubung langsung ke MQTT Broker tanpa *delay* pemrosesan yang berat.
- **Fix Arus Bocor Relay:** Implementasi kode khusus menggunakan mode *High-Impedance* (`INPUT`) untuk memutus total arus bocor (1.7V) pada modul relay 5V Active Low yang dikendalikan pin IO 3.3V ESP32.

---

## 🛠️ Komponen Elektronik (Hardware)
1. **ESP32 Development Board** (Otak utama sistem)
2. **Modul Relay 5V** (Tipe *Active Low* untuk sakelar lampu)
3. **Sensor PIR HC-SR501** (Deteksi gerakan Kamar & WC)
4. **Sensor Ultrasonik HC-SR04** (Deteksi jarak Meja Belajar)
5. **Sensor Arus ACS36** (Monitoring daya listrik)
6. **Lampu LED 5mm & Resistor 220 Ohm** (Sebagai indikator/beban lampu utama)

---

## 💻 Struktur Folder Repositori
```text
Project_KSATRIA/
│
├── app.py                 # Backend Dashboard Web (Flask & Paho-MQTT)
├── kodingan_sketch.ino    # Source Code utama ESP32 (Arduino IDE)
├── diagram.json           # File konfigurasi simulasi untuk Wokwi
└── templates/             # Folder wajib untuk template HTML Flask
    └── index.html         # Tampilan antarmuka (UI) Dashboard Web
