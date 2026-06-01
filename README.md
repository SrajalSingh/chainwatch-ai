# ChainWatch AI 🛡️

**Crypto fraud intelligence console** — real-time on-chain investigation tool for Ethereum tokens using DexScreener market data and Etherscan free-tier APIs.

---

## Features

| Feature | Status |
|---|---|
| DexScreener token/pair lookup by name, symbol, or address | ✅ Live |
| Multi-factor rug-pull risk scoring (6 categories) | ✅ Live |
| Smart contract source audit (blacklist / mint / pause / ownership) | ✅ Ethereum |
| Ethereum deployer wallet graph (SVG, arrowheads, legend) | ✅ Ethereum |
| On-chain intelligence (creator txns, failed txns, contract deployments) | ✅ Ethereum |
| Price change sparkbars (5m / 1h / 6h / 24h) | ✅ Live |
| Market cap, FDV, txn count, token age | ✅ Live |
| Investigation history sidebar (localStorage, up to 20 entries) | ✅ Live |
| Clickable Etherscan links for creator wallet & creation tx | ✅ Ethereum |
| Related pair listing with DexScreener links | ✅ Live |
| URL query param (`?q=TOKEN`) for deep-linking | ✅ Live |

---

## Architecture

```
chainwatch-ai/
├── backend/
│   └── app/
│       ├── server.py          # Python HTTP server (port 8000) — API + static file proxy
│       └── services/
│           ├── dexscreener.py # DexScreener token/pair lookup
│           ├── etherscan.py   # Etherscan V2 free-tier: creation, txns, transfers, source
│           ├── graph_builder.py  # Investigation graph node/edge builder
│           ├── risk_engine.py    # Risk scoring (6 categories) + contract source analysis
│           └── env_loader.py  # .env loader
├── frontend/
│   ├── index.html
│   └── src/
│       ├── main.jsx           # Single-file React app
│       └── styles.css         # Vanilla CSS design system
├── .env                       # API keys (not committed)
├── requirements.txt           # Python deps
└── package.json               # Root scripts: dev, build
```

**Request flow:**
1. Vite dev server (`localhost:5173`) proxies `/api/*` → Python server (`localhost:8000`)
2. Python server calls DexScreener → selects highest-liquidity pair
3. If Ethereum: fetches Etherscan contract creation, creator txns, token transfers, source code
4. Risk engine scores pair across 6 categories → returns structured JSON
5. React renders dashboard, graph (SVG), audit panel, history sidebar

---

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- Etherscan API key (free tier sufficient)

### 1. Install dependencies
```bash
# Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Node
npm install
```

### 2. Set environment variables
Create a `.env` file in the project root:
```env
ETHERSCAN_API_KEY=your_etherscan_api_key_here
```

### 3. Start development servers
```bash
npm run dev
```
This starts both the Vite frontend (port 5173) and Python backend (port 8000) concurrently.

Open: **http://localhost:5173**

### Individual commands
```bash
npm run dev:backend    # Python server only
npm run dev:frontend   # Vite dev server only
npm run build          # Production Vite build (served by Python)
```

---

## API

### `GET /api/analyze?query=<token>`

Accepts: token symbol (`PEPE`), contract address (`0x698...`), or pair address.

**Response shape:**
```json
{
  "found": true,
  "query": "PEPE",
  "source": "dexscreener",
  "token": {
    "chainId": "ethereum",
    "dexId": "uniswap",
    "priceUsd": "0.00001234",
    "marketCap": 1234567890,
    "fdv": 1400000000,
    "liquidity": { "usd": 12345678 },
    "volume": { "h24": 98765432 },
    "txns": { "h24": { "buys": 4200, "sells": 3100 } },
    "priceChange": { "m5": 0.12, "h1": -1.4, "h6": 3.2, "h24": -5.1 },
    "pairCreatedAt": 1683000000000,
    "baseToken": { "name": "Pepe", "symbol": "PEPE", "address": "0x698..." }
  },
  "risk": {
    "score": 42,
    "level": "Moderate",
    "confidence": "Medium",
    "reasons": ["..."],
    "categories": [{ "name": "Liquidity", "points": 5, "maxPoints": 20, "evidence": [] }],
    "signals": { "priceChangeH24": "-5.1%", "volumeUsd24h": "$98.7M" },
    "dataGaps": ["Holder concentration data not available on free tier"]
  },
  "onChain": {
    "available": true,
    "creatorAddress": "0xabc...",
    "creationTxHash": "0xdef...",
    "deploymentTimestamp": "1683000000",
    "creatorRecentTxCount": 18,
    "creatorRecentFailedTxCount": 2,
    "creatorRecentContractCreations": 1,
    "creatorTokenTransferCount": 40,
    "graph": { "available": true, "nodes": [...], "edges": [...] }
  },
  "contractIntel": {
    "isVerified": true,
    "contractName": "PepeToken",
    "licenseType": "MIT",
    "owner": "0x0000000000000000000000000000000000000000",
    "ownershipRenounced": true,
    "hasBlacklist": false,
    "hasMint": false,
    "hasPause": false
  },
  "relatedPairs": [...],
  "explanation": "..."
}
```

### `GET /api/health`
Returns `{ "status": "ok", "service": "chainwatch-ai" }`.

---

## Risk Score Categories

| Category | Max Points | Description |
|---|---|---|
| Liquidity | 20 | Low liquidity = higher manipulation risk |
| Volume | 15 | Suspicious volume ratios |
| Market Structure | 20 | Pair count, new token flags |
| On-Chain Activity | 15 | Creator wallet behavior |
| Contract Security | 20 | Blacklist, mint, pause, ownership |
| Price Action | 10 | Extreme price changes |

Score 0–39 = Low · 40–59 = Moderate · 60–79 = High · 80–100 = Critical

---

## Known Limitations & Next Steps

| Gap | Priority | Notes |
|---|---|---|
| Holder concentration data | High | Requires Etherscan Pro or Moralis |
| Non-Ethereum chain on-chain data | Medium | DexScreener supports BSC, Solana etc. |
| Price chart (candlestick) | Medium | DexScreener has a chart API |
| Wallet profiling (known scammer DBs) | Medium | MistTrack, Chainabuse APIs |
| Real-time WebSocket updates | Low | Long-poll backend needed |
| Export investigation report as PDF | Low | jsPDF or Puppeteer |
| Solidity AST parsing (vs. regex) | Low | More accurate contract audit |

---

## Tech Stack

- **Frontend**: React 18 (Vite), Vanilla CSS, Lucide React icons
- **Backend**: Python 3, `http.server.ThreadingHTTPServer`, no framework
- **APIs**: DexScreener (free, no key needed), Etherscan V2 (free tier, key required)
- **Storage**: `localStorage` for investigation history (client-only)
