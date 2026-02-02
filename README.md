<p align="center">
  <img src="https://i.ibb.co/QFt3Z9bC/tmpg1y9wbs8.jpg" width="360" alt="Gojo Satoru" style="border-radius:20px;">
</p>

<h1 align="center"><b>Gojo Satoru</b></h1>

<p align="center">
  <i>Fast · Reliable · Secure</i>
</p>

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.10%2B-3676AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
  </a>
  <a href="https://ffmpeg.org/">
    <img src="https://img.shields.io/badge/FFmpeg-Supported-007808.svg?style=flat-square&logo=ffmpeg&logoColor=white" alt="FFmpeg Supported" />
  </a>
  <a href="https://core.telegram.org/bots/api">
    <img src="https://img.shields.io/badge/Telegram%20Bot-API-2496ED.svg?style=flat-square&logo=telegram&logoColor=white" alt="Telegram Bot API" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square&logo=open-source-initiative&logoColor=white" alt="MIT License" />
  </a>
</p>

---

## 📖 About

**Gojo Satoru RTMP Streaming Bot** is a robust Telegram bot engineered for seamless, reliable live streaming via RTMP.  
Inspired by the power and precision of *Gojo Satoru* from Jujutsu Kaisen, the bot delivers professional-grade streaming with minimal effort.

**Key Features**  
- **RTMP Streaming to Telegram**: Directly broadcast live video to Telegram groups/channels  
- **Ultra-low latency & stability**: Optimized for smooth streaming and minimal delay  
- **High-quality audio**: Crystal-clear audio streaming  
- **Intuitive commands**: Easy setup and management via Telegram  
- **Service integrations**: Supports YouTube and other platforms with cookie-based auth

---

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/TheJeager/SatoruGojo.git
   cd SatoruGojo
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your Telegram Bot Token & configure settings**
   - Edit `config.py` or set your environment variables.

4. **Run the bot**
   ```bash
   python main.py
   ```

---

## 🛠️ Requirements

- Python **3.10+**
- FFmpeg (installed and accessible in your PATH)
- Telegram Bot API token ([BotFather Guide](https://core.telegram.org/bots#botfather))

---

## 🔐 Authentication via Cookies

Gojo Satoru supports cookie-based authentication for streaming platforms like YouTube.

**Export your cookies:**

| Browser    | Extension        | Download Link                                                                |
|------------|------------------|-----------------------------------------------------------------------------|
| Chrome     | Get cookies.txt  | [Chrome Web Store](https://chromewebstore.google.com/detail/get-cookiestxt-clean/ahmnmhfbokciafffnknlekllgcnafnie) |
| Firefox    | cookies.txt      | [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) |

**Steps:**
1. Install the extension in your browser.
2. Log in to the streaming site (use a **secondary account**).
3. Export `cookies.txt` using the extension.
4. Upload/reference `cookies.txt` file in your bot's settings.

> ⚠️ **Safety tip:**  
> - Do not log in again after exporting cookies—they may become invalid.
> - Use secondary accounts to safeguard your credentials.

---

## 📑 License

This project is licensed under the [MIT License](LICENSE).

---

## ✨ Credits

- Inspired by: *Gojo Satoru (Jujutsu Kaisen)*
- Developed by [Eren Jeager](https://github.com/TheJeager)
- Powered by Python, FFmpeg, and Telegram Bot API
