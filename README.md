# 📡 Mocosn Phone & LeakOSINT Intelligence Engine

A modern glassmorphic intelligence dashboard and REST API integrating **Phone Metadata Validation** (carrier, geolocation, timezones, E.164) with the **LeakOSINT API** (`https://leakosintapi.com/`) for real-time breached database lookups, credential leaks, and OSINT investigations.

---

## 🚀 Key Features

- **⚡ Unified Smart Search**:
  - Automatically identifies whether your target is a phone number, email address, username, or full name.
  - Combines offline carrier/telephony intelligence with live database leak checks.
- **📱 Phone Intelligence**:
  - Validates numbers against international telecommunication standards (libphonenumber).
  - Extracts **Carrier/Operator**, **Geographical Location**, **Timezones**, **Number Type** (Mobile, VoIP, Fixed Line), **E.164**, **International**, and **National** formats.
  - One-click copy for all formatted phone variations.
- **🛡️ LeakOSINT Breach Intelligence**:
  - Connects directly to `https://leakosintapi.com/` using JSON POST requests.
  - Scans breached databases for leaked credentials, emails, passwords/hashes, names, IPs, addresses, and phone records.
  - Displays database name, `InfoLeak` metadata, and individual records with highlighted sensitive fields.
  - Export capabilities: One-click copy of JSON results or download as `.json` report.
- **💰 Live Pricing & Complexity Calculator**:
  - Implements the exact pricing formula from the official LeakOSINT documentation:
    $$\text{Price (\USD)} = 0.0002 \times (5 + \sqrt{\text{Limit} \times \text{Complexity}})$$
  - Dynamically computes query complexity (1, 5, 16, or 40) in real-time as you type, ignoring dates, short strings (<4 chars), and short numbers (<6 digits), and grouping quoted phrases.
- **🌐 Dual Interface**:
  - **Glassmorphic Web Portal**: Dark theme with particle field animation, star backdrop, and collapsible settings.
  - **REST API (`/api/lookup`)**: Programmatic JSON endpoints for automations, scripts, and OSINT pipelines.
- **🤖 Telegram Bot (`telegram_bot.py`)**:
  - Full-featured Telegram bot script with pagination buttons (`<<`, `N/M`, `>>`), HTML formatting, and report caching matching the official documentation example.

---

## 📋 LeakOSINT API Reference

Based on `documentation.html`:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `token` | String | Yes | Personal token received by sending `/api` to the LeakOSINT bot (100 free requests included). |
| `request` | String / Array | Yes | Target string (phone number, email, username, full name) or array of queries. |
| `limit` | Integer | No | Search limit / range in database (`100` to `10000`, default `100`). |
| `lang` | String | No | Language code for results (`en`, `ru`, default `en`). |
| `type` | String | No | Report format (`json`, `short`, `html`, default `json`). |
| `bot_name` | String | No | Format `@name` (if query is routed to a custom bot mirror). |

> **Note:** The API enforces a rate limit of **3 requests per second per IP**.

---

## 🛠️ Installation & Setup

### 1. Clone & Install Dependencies

```bash
git clone <repo-url>
cd phoneinfo

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Personal LeakOSINT API Token (send /api to Telegram bot to get yours)
LEAKOSINT_API_TOKEN=your_token_here

# Default limit (100-10000)
LEAKOSINT_DEFAULT_LIMIT=100

# Default language ('en' or 'ru')
LEAKOSINT_DEFAULT_LANG=en

# Optional: Telegram bot token if running telegram_bot.py
TELEGRAM_BOT_TOKEN=
```

*(Note: If you don't set `LEAKOSINT_API_TOKEN` in `.env`, you can enter your token directly in the web UI under **API & Search Settings**; it will be cached securely in your browser's `localStorage`.)*

---

## 🖥️ Running the Web App

Launch the Flask application:

```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 🔌 REST API Endpoints

### 1. Unified Intelligence Lookup

- **Endpoint**: `POST /api/lookup` or `GET /api/lookup`
- **Request Body (JSON)**:
  ```json
  {
    "query": "+14155552671",
    "mode": "smart",
    "limit": 100,
    "lang": "en",
    "token": "optional_override_token"
  }
  ```
- **Response (JSON)**:
  ```json
  {
    "query": "+14155552671",
    "mode": "smart",
    "pricing": {
      "complexity": 1,
      "estimated_price_usd": "$0.00300",
      "limit": 100,
      "words": ["+14155552671"]
    },
    "phone_intelligence": {
      "valid": true,
      "carrier": "Twilio",
      "location": "California",
      "country_code": "+1",
      "e164": "+14155552671",
      "international": "+1 415-555-2671",
      "national": "(415) 555-2671",
      "number_type": "VoIP",
      "region_code": "US",
      "timezones": ["America/Los_Angeles"]
    },
    "leak_intelligence": {
      "has_results": true,
      "total_databases": 1,
      "total_records": 1,
      "databases": [ ... ]
    }
  }
  ```

### 2. Live Cost & Complexity Estimator

- **Endpoint**: `GET /api/estimate-cost?query=Elon%20Reeve%20Musk&limit=100`
- **Response**:
  ```json
  {
    "query": "Elon Reeve Musk",
    "limit": 100,
    "complexity": 16,
    "word_count": 3,
    "words": ["Elon", "Reeve", "Musk"],
    "estimated_price_usd": "$0.00900",
    "formula": "0.0002 * (5 + sqrt(Limit * Complexity))"
  }
  ```

---

## 🤖 Running the Telegram Bot

If you have a Telegram Bot Token:

1. Install PyTelegramBotAPI (if not already installed):
   ```bash
   pip install pyTelegramBotAPI
   ```
2. Set `TELEGRAM_BOT_TOKEN` in your `.env`.
3. Run the bot:
   ```bash
   python telegram_bot.py
   ```

---

## ☁️ Deployment (Vercel)

The repository includes a ready-to-deploy [`vercel.json`](file:///e:/laptop/laptopdata/Programs/phoneinfo/vercel.json):

```bash
vercel deploy
```

Set `LEAKOSINT_API_TOKEN` in your Vercel Project Environment Settings.
