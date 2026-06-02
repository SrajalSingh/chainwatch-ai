# ChainWatch AI 🛡️

**ChainWatch AI** is a real-time, on-chain crypto fraud intelligence console designed to audit and profile Ethereum tokens. By combining DexScreener market data, Etherscan explorer intelligence, and sandboxed simulation audits via the GoPlus Security API, ChainWatch AI delivers high-fidelity risk verdicts for retail traders and analysts.

---

## 🚀 Key Features

* **DexScreener Market Analytics**: Search token symbols, contract addresses, or trading pairs to instantly capture liquidity, volume, trading counts, and price sparkbars.
* **GoPlus Security Audit (Honeypot & Taxes)**:
  * **Honeypot Simulation**: Run a sandboxed buy/sell transaction to verify token tradeability before investing.
  * **Buy/Sell Tax Auditor**: Identify hidden trading fees or high slippage requirements.
  * **Vulnerability & Backdoor Checks**: Spot active contract pauses, balance modification exploits (owner backdoor), self-destruct instructions, upgradeable proxies, and address blacklists.
* **Smart Contract Audit**: Solidity source code checks directly from Etherscan to flag active ownership, minting capabilities, pausable states, and unverified source code alerts.
* **On-Chain Wallet Mapping**: Build and inspect developer transaction relationships, deployer wallet history, failed transaction counts, and creator holding concentration.
* **Interactive Dashboard**: A clean, responsive user interface featuring:
  * Dynamic **Risk Score Ring** (0–100 risk rating).
  * Live-updating **Price Charts** (DexScreener embeds).
  * **Investigation History** sidebar (localStorage, up to 20 entries) for quick switching.
  * Auto-collapsing details grid focused on **Red Flags**, **Critical Rug Pull Signals**, and **Related Pairs**.

---

## 🏗️ Architecture

```
chainwatch-ai/
├── backend/
│   └── app/
│       ├── server.py          # Python HTTP server (port 8000) — API & static server
│       └── services/
│           ├── dexscreener.py # DexScreener API wrapper
│           ├── etherscan.py   # Etherscan V2 API client (creator, deployments, source code)
│           ├── goplus.py      # GoPlus Security API client (honeypot & contract vulnerabilities)
│           ├── graph_builder.py  # SVG node/edge generator for creator wallet map
│           ├── risk_engine.py    # Algorithmic risk scoring (6 categories) & logic parser
│           └── env_loader.py  # Local environment variables manager
├── frontend/
│   ├── index.html
│   └── src/
│       ├── main.jsx           # React app (UI components & state)
│       └── styles.css         # Clean, premium Vanilla CSS stylesheet
├── .env                       # API Configuration (Etherscan API key)
├── requirements.txt           # Backend Python dependencies
└── package.json               # Root scripts (Dev server, building frontend)
```

### Request Flow
1. **Frontend Search**: The client enters a token symbol or address in the console.
2. **Server Routing**: The backend server fetches market stats from DexScreener and filters for Ethereum Mainnet.
3. **On-Chain Intelligence**: If verified, the server queries Etherscan for developer activity history and retrieves contract source code.
4. **Sandboxed Simulations**: The backend calls GoPlus API (`contract_addresses` parameter) to run automated honeypot simulations and retrieve tax metrics.
5. **Scoring & Risk Engine**: The scoring model aggregates all metrics, flags critical alerts, determines the final verdict (Buy, Caution, Avoid), and formats the final payload.
6. **Reactive Render**: React compiles the UI, loading the sparkbars, price chart, smart contract audit, and honeypot indicators.

---

## 🛠️ Running Locally

### Prerequisites
* **Node.js** (v18+)
* **Python** (v3.10+)
* **Etherscan API Key** (Free tier)

### 1. Clone & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/your-username/chainwatch-ai.git
cd chainwatch-ai

# Install backend python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install frontend Node dependencies
npm install
```

### 2. Set Up Environment Variables
Create a `.env` file in the project root:
```env
ETHERSCAN_API_KEY=your_etherscan_key_here
```

### 3. Start Development Servers
```bash
npm run dev
```
This launches:
* **Vite Dev Server** (Frontend) on `http://localhost:5173`
* **Python HTTP Server** (Backend API) on `http://localhost:8000`

---

## 📊 API Reference

### `GET /api/analyze?query=<token>`
Accepts a token symbol, pair address, or contract address.

**Sample Response Payload:**
```json
{
  "query": "WETH",
  "found": true,
  "source": "token",
  "token": {
    "chainId": "ethereum",
    "dexId": "uniswap",
    "pairAddress": "0x88e6A...",
    "baseToken": {
      "address": "0xC02aa...",
      "name": "Wrapped Ether",
      "symbol": "WETH"
    },
    "priceUsd": "1935.50"
  },
  "risk": {
    "score": 0,
    "level": "Low",
    "verdict": "Buy",
    "verdictEmoji": "✅",
    "verdictReason": "Risk profile is low. Entry conditions look acceptable...",
    "rugSignals": [],
    "flags": []
  },
  "goplusIntel": {
    "is_honeypot": "0",
    "buy_tax": "0",
    "sell_tax": "0",
    "owner_change_balance": "0",
    "selfdestruct": "0",
    "transfer_pausable": "0",
    "is_proxy": "0",
    "is_blacklisted": "0"
  },
  "explanation": "Wrapped Ether scores 0/100 — Low Risk. Verdict: Buy..."
}
```

### `GET /api/health`
Returns `{ "status": "ok", "service": "chainwatch-ai" }` to verify backend server status.

---

## 🛡️ Risk Categories

The risk model grades projects out of **100 points** (lower is safer):
* **Token Age (25 pts)**: Heavy rug-pull warnings for brand new tokens (<24h old).
* **Rug Pull Signals (20 pts)**: Honeypot checks, extreme pumps/dumps, owner backdoors.
* **Liquidity Health (20 pts)**: Thin liquidity limits trading volume and increases slippage risk.
* **Volume & Trading (15 pts)**: Wash trading, high volume-to-liquidity ratios.
* **Contract Security (15 pts)**: Verification states, active blacklisting, mint capabilities, pausable states.
* **Market Structure (5 pts)**: Valuation, supply distribution, related trading pair visibility.

---

## 📖 About Section

ChainWatch AI was created to solve the "black-box" nature of token launches. By grouping multiple security services into a single, clean interface, users get a clear overview of contract integrity and market liquidity. 

*Disclaimer: ChainWatch AI is an informational tool. Smart contracts can have complex exploits not caught by automated audits. Always perform your own research and never trade more than you can afford to lose.*
