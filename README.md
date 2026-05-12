<![CDATA[<div align="center">

# 🏟️ NSE Arena

**A real-time paper trading competition platform for Indian (NSE) markets**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

Practice trading NSE stocks risk-free. Compete on seasonal leaderboards. Write custom analysis scripts. Let AI agents trade alongside you.

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| **Paper Trading** | Buy / sell NSE-listed stocks with ₹1,00,000 virtual capital per season |
| **Live Market Data** | Real-time OHLCV data via yfinance, streamed over WebSockets through Redis Pub/Sub |
| **TradingView Charts** | Full TradingView Advanced Chart widget embedded for professional-grade charting |
| **PineScript Editor** | Write & run PineScript-lite scripts — a custom scripting engine that supports SMA, EMA, RSI, MACD, Bollinger Bands, and more |
| **Indicator Overlay** | Script outputs are rendered on a `lightweight-charts` instance with multi-pane support |
| **AI Agents** | Background Gemini-powered AI agents that autonomously analyze and trade |
| **Seasonal Competitions** | Time-boxed seasons (default 30 days) with separate leaderboards |
| **Trader Scoring** | Multi-factor scoring: returns, risk management, consistency, discipline |
| **Leaderboard** | Ranked standings with live PnL tracking |
| **Auth System** | JWT-based registration & login with bcrypt password hashing |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                   Frontend (Vite + React)         │
│  ┌──────────┐ ┌────────────┐ ┌────────────────┐  │
│  │Dashboard │ │Leaderboard │ │ Script Editor  │  │
│  │  + Chart │ │            │ │ (Monaco+LWC)   │  │
│  └────┬─────┘ └─────┬──────┘ └───────┬────────┘  │
│       │              │                │           │
│       └──────────────┼────────────────┘           │
│                      │  REST + WebSocket          │
└──────────────────────┼───────────────────────────-┘
                       │
┌──────────────────────┼────────────────────────────┐
│              Backend (FastAPI + Uvicorn)           │
│  ┌─────┐ ┌──────┐ ┌──────────┐ ┌──────────────┐  │
│  │Auth │ │Trade │ │ Market   │ │  Scripting   │  │
│  │     │ │Engine│ │ Data     │ │  Engine      │  │
│  └──┬──┘ └──┬───┘ └────┬────┘ └──────┬───────┘  │
│     │       │          │             │           │
│  ┌──┴───────┴──┐  ┌────┴────┐  ┌────┴────────┐  │
│  │ PostgreSQL  │  │  Redis  │  │  Gemini AI  │  │
│  │  (SQLAlchemy│  │ (cache+ │  │  (agents)   │  │
│  │   async)    │  │  pubsub)│  │             │  │
│  └─────────────┘  └─────────┘  └─────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
StockPaper/
├── backend/
│   ├── main.py                 # FastAPI app & lifespan events
│   ├── config.py               # Environment / app configuration
│   ├── database.py             # SQLAlchemy async engine & session
│   ├── db/
│   │   └── models.py           # ORM models (User, Trade, Season, etc.)
│   ├── api/
│   │   ├── dependencies.py     # Auth & DB dependency injection
│   │   └── routes/
│   │       ├── auth.py         # Register / Login / JWT
│   │       ├── trades.py       # Place & manage trades
│   │       ├── portfolio.py    # Holdings & PnL
│   │       ├── leaderboard.py  # Season rankings
│   │       ├── seasons.py      # Season management
│   │       ├── scripts.py      # PineScript execution API
│   │       ├── ai.py           # AI agent endpoints
│   │       └── websocket.py    # Live price WebSocket
│   ├── market_data/            # yfinance fetcher & Redis broadcaster
│   ├── engine/                 # Order matching engine
│   ├── scoring/                # Trader scoring algorithm
│   ├── scripting/              # PineScript-lite parser & indicators
│   ├── ai/                     # Gemini-based AI trading agents
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── tokens.css              # Design tokens (dark theme)
│   │   ├── screens/
│   │   │   ├── Dashboard.jsx       # Main trading dashboard
│   │   │   ├── AuthScreen.jsx      # Login / Register
│   │   │   ├── Leaderboard.jsx     # Season rankings
│   │   │   ├── AIFeed.jsx          # AI agent activity feed
│   │   │   ├── ScriptEditor.jsx    # PineScript editor screen
│   │   │   └── Profile.jsx         # User profile & stats
│   │   ├── components/
│   │   │   ├── TradingViewChart.jsx # TradingView widget wrapper
│   │   │   ├── IndicatorChart.jsx   # lightweight-charts for scripts
│   │   │   ├── MonacoEditor.jsx     # Monaco code editor
│   │   │   ├── OrderPanel.jsx       # Buy/Sell order form
│   │   │   ├── PositionsTable.jsx   # Open positions table
│   │   │   ├── NavBar.jsx           # Navigation bar
│   │   │   └── ...
│   │   └── hooks/
│   │       └── useAuth.js
│   └── package.json
└── docker-compose.yml          # Full-stack Docker setup
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** ≥ 18
- **Python** ≥ 3.11
- **Redis** (optional — app degrades gracefully without it)
- **PostgreSQL** (or use the default SQLite for local dev)

### 1. Clone the Repository

```bash
git clone https://github.com/DhyeyTandel/NSE_ARENA.git
cd NSE_ARENA
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional — defaults work for local dev)
cp .env .env.local
# Edit .env.local with your Gemini API key, DB URL, etc.

# Run the server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Swagger docs at `http://localhost:8000/docs`.

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The app will be available at `http://localhost:5173`.

### 4. Docker (Full Stack)

```bash
# From the project root
docker-compose up --build
```

This starts the backend, PostgreSQL, and Redis together.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Create a new account |
| `POST` | `/auth/login` | Get JWT access token |
| `GET` | `/price/{ticker}` | Fetch OHLCV data for an NSE stock |
| `POST` | `/trades/` | Place a buy/sell order |
| `GET` | `/portfolio/` | Get current holdings & PnL |
| `GET` | `/leaderboard/` | Season leaderboard standings |
| `GET` | `/seasons/active` | Current active season info |
| `POST` | `/scripts/run` | Execute a PineScript-lite script |
| `GET` | `/scripts/templates` | List built-in script templates |
| `GET` | `/score/{user_id}` | Get trader score & grade |
| `GET` | `/health` | Health check (incl. Redis status) |
| `WS` | `/ws/{user_id}` | Live price stream via WebSocket |

---

## 📜 PineScript-Lite

The scripting engine supports a subset of PineScript v5 syntax. Write scripts in the built-in Monaco editor, hit **Run**, and see indicator overlays rendered on the chart.

**Supported indicators:**

- `ta.sma(source, length)` — Simple Moving Average
- `ta.ema(source, length)` — Exponential Moving Average
- `ta.rsi(source, length)` — Relative Strength Index
- `ta.macd(source, fast, slow, signal)` — MACD
- `ta.bb(source, length, mult)` — Bollinger Bands
- `ta.crossover(a, b)` / `ta.crossunder(a, b)` — Cross signals

**Example script:**

```pinescript
//@version=5
indicator("Golden Cross", overlay=true)

fast = ta.sma(close, 50)
slow = ta.sma(close, 200)

plot(fast, "SMA 50", color=color.orange)
plot(slow, "SMA 200", color=color.blue)

buySignal = ta.crossover(fast, slow)
sellSignal = ta.crossunder(fast, slow)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite 8, TradingView Widget, lightweight-charts, Monaco Editor |
| **Backend** | FastAPI, Uvicorn, SQLAlchemy 2.0 (async), Pydantic v2 |
| **Database** | PostgreSQL 15 (prod) / SQLite (local dev) |
| **Cache & Pub/Sub** | Redis 7 |
| **Market Data** | yfinance |
| **AI** | Google Gemini (generativeai SDK) |
| **Auth** | JWT (python-jose) + bcrypt (passlib) |
| **Containerization** | Docker + Docker Compose |
| **Testing** | pytest + pytest-asyncio (backend), Vitest + Testing Library (frontend) |

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./nse_arena.db` | Async DB connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `SECRET_KEY` | *(dev default)* | JWT signing secret — **change in prod** |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini API key for AI agents |

---

## 📄 License

This project is for educational and personal use.

---

<div align="center">
  <sub>Built with ☕ and 📈 by <a href="https://github.com/DhyeyTandel">Dhyey Tandel</a></sub>
</div>
]]>
