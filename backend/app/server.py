from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from services.dexscreener import lookup_token_or_pair
from services.env_loader import load_env
from services.etherscan import (
    ETHEREUM_CHAIN_ID,
    get_address_transactions,
    get_contract_creation,
    get_internal_transactions,
    get_token_transfers_for_address,
    get_contract_source,
    get_contract_owner,
    get_token_balance,
    get_total_supply,
)
from services.graph_builder import build_investigation_graph
from services.risk_engine import analyst_explanation, score_pair, analyze_contract_source
from services.goplus import check_token_security


ROOT = Path(__file__).resolve().parents[2]
load_env(ROOT / ".env")
FRONTEND_SOURCE = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_SOURCE / "dist"
FRONTEND = FRONTEND_DIST if FRONTEND_DIST.exists() else FRONTEND_SOURCE
PORT = 8000


def _json_response(handler: BaseHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _pair_to_summary(pair: Dict[str, Any]) -> Dict[str, Any]:
    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}
    return {
        "chainId": pair.get("chainId"),
        "dexId": pair.get("dexId"),
        "pairAddress": pair.get("pairAddress"),
        "url": pair.get("url"),
        "baseToken": base,
        "quoteToken": quote,
        "priceUsd": pair.get("priceUsd"),
        "fdv": pair.get("fdv"),
        "marketCap": pair.get("marketCap"),
        "liquidity": pair.get("liquidity") or {},
        "volume": pair.get("volume") or {},
        "txns": pair.get("txns") or {},
        "priceChange": pair.get("priceChange") or {},
        "pairCreatedAt": pair.get("pairCreatedAt"),
    }


MAP_CHAIN_TO_GOPLUS = {
    "ethereum": "1",
    "bsc": "56",
    "arbitrum": "42161",
    "polygon": "137",
    "optimism": "10",
    "base": "8453",
    "avalanche": "43114",
    "linea": "59144",
    "zksync": "324",
    "fantom": "250",
    "gnosis": "100",
    "solana": "solana",
}


def analyze(query: str) -> Dict[str, Any]:
    result = lookup_token_or_pair(query)
    if not result.pairs:
        return {
            "query": query,
            "found": False,
            "source": result.source,
            "error": result.error,
            "message": "No token or pair was found. Try a live token contract or symbol that exists on DexScreener.",
        }

    # Support all chains, sorted by liquidity
    pairs = sorted(
        result.pairs,
        key=lambda item: float(((item.get("liquidity") or {}).get("usd")) or 0),
        reverse=True,
    )
    primary = pairs[0]
    token_name = (primary.get("baseToken") or {}).get("name") or "This token"
    chain_id = primary.get("chainId")

    # Fetch multi-chain security details and Etherscan info if Ethereum
    contract_intel = None
    goplus_intel = None
    token_address = ((primary.get("baseToken") or {}).get("address") or "").strip()
    
    if token_address:
        # Check security on the matched chain using GoPlus
        goplus_chain = MAP_CHAIN_TO_GOPLUS.get(chain_id)
        if goplus_chain:
            goplus_intel = check_token_security(token_address, chain_id=goplus_chain)
        
        # Contract-level static analysis is currently Ethereum-only (Etherscan V2 free-tier)
        if chain_id == "ethereum":
            source_data = get_contract_source(token_address)
            owner_address = get_contract_owner(token_address)
            
            source_code = source_data.get("SourceCode") if source_data else None
            contract_name = source_data.get("ContractName") if source_data else None
            license_type = source_data.get("LicenseType") if source_data else None
            
            parsed_intel = analyze_contract_source(source_code, owner_address)
            contract_intel = {
                **parsed_intel,
                "contractName": contract_name,
                "licenseType": license_type,
                "owner": owner_address,
            }

    on_chain = _ethereum_token_intelligence(primary)
    risk = score_pair(primary, pair_count=len(pairs), contract_intel=contract_intel, on_chain=on_chain, goplus_intel=goplus_intel)

    return {
        "query": query,
        "found": True,
        "source": result.source,
        "token": _pair_to_summary(primary),
        "relatedPairs": [_pair_to_summary(pair) for pair in pairs[:6]],
        "risk": risk,
        "onChain": on_chain,
        "contractIntel": contract_intel,
        "goplusIntel": goplus_intel,
        "explanation": analyst_explanation(token_name, risk),
    }



def _ethereum_token_intelligence(pair: Dict[str, Any]) -> Dict[str, Any]:
    if pair.get("chainId") != "ethereum":
        return {
            "available": False,
            "coverage": "Explorer intelligence currently runs only on Ethereum free-tier Etherscan.",
            "graph": {
                "available": False,
                "summary": {"headline": "No Ethereum graph available for this asset yet."},
                "nodes": [],
                "edges": [],
            },
        }

    token_address = ((pair.get("baseToken") or {}).get("address") or "").strip()
    if not token_address:
        return {
            "available": False,
            "coverage": "Ethereum token address missing from market data.",
            "graph": {"available": False, "summary": {"headline": "No token contract address available."}, "nodes": [], "edges": []},
        }

    creation = get_contract_creation(token_address)
    creator = creation.get("contractCreator") if creation else None
    creator_txs = get_address_transactions(creator, offset=20) if creator else []
    creator_internal = get_internal_transactions(creator, offset=20) if creator else []
    creator_token_transfers = get_token_transfers_for_address(creator, token_address, offset=40) if creator else []

    recent_contract_creations = sum(1 for tx in creator_internal if tx.get("type") == "create")
    recent_failed_txs = sum(1 for tx in creator_txs if tx.get("isError") == "1")
    graph = build_investigation_graph(token_address, creator, creation, creator_txs, creator_token_transfers)

    # Fetch token supply and creator balance to calculate holding concentration
    total_supply = get_total_supply(token_address)
    creator_balance = get_token_balance(token_address, creator) if creator else None
    zero_balance = get_token_balance(token_address, "0x0000000000000000000000000000000000000000")
    dead_balance = get_token_balance(token_address, "0x000000000000000000000000000000000000dEaD")

    creator_holding_percent = 0.0
    burned_percent = 0.0

    if total_supply and total_supply > 0:
        if creator_balance is not None:
            creator_holding_percent = round((creator_balance / total_supply) * 100.0, 4)
        total_burned = (zero_balance or 0) + (dead_balance or 0)
        burned_percent = round((total_burned / total_supply) * 100.0, 4)

    return {
        "available": True,
        "coverage": "Ethereum free-tier Etherscan V2",
        "chainId": ETHEREUM_CHAIN_ID,
        "creatorAddress": creator,
        "creationTxHash": creation.get("txHash") if creation else None,
        "deploymentTimestamp": creation.get("timestamp") if creation else None,
        "creatorRecentTxCount": len(creator_txs),
        "creatorRecentFailedTxCount": recent_failed_txs,
        "creatorRecentContractCreations": recent_contract_creations,
        "creatorTokenTransferCount": len(creator_token_transfers),
        "totalSupply": total_supply,
        "creatorBalance": creator_balance,
        "creatorHoldingPercent": creator_holding_percent,
        "burnedPercent": burned_percent,
        "graph": graph,
    }


class ChainWatchHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            _json_response(self, {"status": "ok", "service": "chainwatch-ai"})
            return

        if parsed.path == "/api/analyze":
            query = (parse_qs(parsed.query).get("query") or [""])[0].strip()
            if not query:
                _json_response(self, {"found": False, "error": "Missing query"}, status=400)
                return
            _json_response(self, analyze(query))
            return

        self._serve_static(parsed.path)

    def _serve_static(self, path: str) -> None:
        target = "index.html" if path in {"/", ""} else path.lstrip("/")
        file_path = (FRONTEND / target).resolve()
        if not str(file_path).startswith(str(FRONTEND.resolve())) or not file_path.exists():
            self.send_error(404)
            return

        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "text/javascript",
            ".jsx": "text/javascript",
            ".svg": "image/svg+xml",
        }
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[ChainWatch] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ChainWatchHandler)
    print(f"ChainWatch AI running at http://0.0.0.0:{PORT}")
    server.serve_forever()
