from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search?q={query}"
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"
# Newer v1 endpoint: chain-scoped, returns a list directly, separate rate-limit bucket
DEXSCREENER_TOKEN_V1_URL = "https://api.dexscreener.com/tokens/v1/{chain}/{address}"

GECKOTERMINAL_POOL_URL = "https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{address}/pools"
GECKOTERMINAL_SEARCH_URL = "https://api.geckoterminal.com/api/v2/search/pools?query={query}"


@dataclass
class DexScreenerResult:
    pairs: List[Dict[str, Any]]
    source: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pure-Python Keccak-256 (zero external dependencies).
# Ethereum's EIP-55 address checksum uses Keccak-256, which is NOT the same
# as Python's stdlib hashlib.sha3_256 (different domain-separation padding).
# ---------------------------------------------------------------------------
_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_KECCAK_ROTC = [1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14, 27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44]
_KECCAK_PIL  = [10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4, 15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1]


def _keccak_f(A: List[int]) -> List[int]:
    M64 = 0xFFFFFFFFFFFFFFFF
    for rc in _KECCAK_RC:
        C = [A[x] ^ A[x+5] ^ A[x+10] ^ A[x+15] ^ A[x+20] for x in range(5)]
        D = [C[(x+4)%5] ^ (((C[(x+1)%5] << 1) | (C[(x+1)%5] >> 63)) & M64) for x in range(5)]
        A = [A[x+5*y] ^ D[x] for y in range(5) for x in range(5)]
        B = [0] * 25
        B[0] = A[0]
        t = A[1]
        for i in range(24):
            j = _KECCAK_PIL[i]
            n = _KECCAK_ROTC[i]
            B[j] = ((t << n) | (t >> (64 - n))) & M64
            t = A[j]
        A = [B[x+5*y] ^ ((~B[(x+1)%5+5*y]) & B[(x+2)%5+5*y]) for y in range(5) for x in range(5)]
        A[0] ^= rc
    return A


def _keccak256(data: bytes) -> str:
    """Return the Keccak-256 digest of *data* as a hex string."""
    rate = 136  # 1088-bit rate / 8
    msg = bytearray(data) + b"\x01"
    msg += b"\x00" * ((-len(msg)) % rate)
    msg[-1] |= 0x80
    state: List[int] = [0] * 25
    for off in range(0, len(msg), rate):
        for i in range(17):
            state[i] ^= int.from_bytes(msg[off + i*8: off + i*8 + 8], "little")
        state = _keccak_f(state)
    return b"".join(s.to_bytes(8, "little") for s in state[:4]).hex()


def is_evm_address(query: str) -> bool:
    """Return True if *query* looks like an EVM contract address."""
    return bool(re.match(r"^0x[0-9a-fA-F]{40}$", query.strip()))


def is_solana_address(query: str) -> bool:
    """Return True if *query* looks like a Solana address (Base58, length 32-44)."""
    return bool(re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", query.strip()))


def to_checksum_address(address: str) -> str:
    """Convert an EVM address to EIP-55 checksummed form (pure Python)."""
    addr = address.lower().replace("0x", "")
    h = _keccak256(addr.encode())
    result = "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(addr))
    return "0x" + result


# ---------------------------------------------------------------------------
# GeckoTerminal Adapter
# ---------------------------------------------------------------------------
MAP_GECKO_TO_DEXSCREENER_CHAIN = {
    "eth": "ethereum",
    "bsc": "bsc",
    "base": "base",
    "arbitrum": "arbitrum",
    "polygon": "polygon",
    "optimism": "optimism",
    "avax": "avalanche",
    "solana": "solana",
}

MAP_DEXSCREENER_TO_GECKO_CHAIN = {v: k for k, v in MAP_GECKO_TO_DEXSCREENER_CHAIN.items()}


def _map_gecko_pool_to_dex_pair(pool: Dict[str, Any], gecko_network: str) -> Dict[str, Any]:
    attributes = pool.get("attributes") or {}
    relationships = pool.get("relationships") or {}
    
    # Parse base and quote tokens
    base_data = relationships.get("base_token", {}).get("data", {})
    quote_data = relationships.get("quote_token", {}).get("data", {})
    
    base_address = base_data.get("id", "").split("_")[-1] if base_data.get("id") else ""
    quote_address = quote_data.get("id", "").split("_")[-1] if quote_data.get("id") else ""
    
    # Parse name to extract symbols
    pool_name = attributes.get("name", "")
    base_symbol = ""
    quote_symbol = ""
    if "/" in pool_name:
        parts = pool_name.split("/")
        base_symbol = parts[0].strip()
        # Strip fee suffix if present (e.g. "WETH 1%" -> "WETH")
        quote_symbol = parts[1].split()[0].strip()
        
    base_token = {
        "address": base_address,
        "name": base_symbol,
        "symbol": base_symbol
    }
    quote_token = {
        "address": quote_address,
        "name": quote_symbol,
        "symbol": quote_symbol
    }
    
    # Dex ID
    dex_id = relationships.get("dex", {}).get("data", {}).get("id", "unknown")
    if "_" in dex_id:
        dex_id = dex_id.split("_")[0]
        
    # Liquidity
    reserve_usd = attributes.get("reserve_in_usd")
    liquidity = {"usd": float(reserve_usd) if reserve_usd is not None else 0.0}
    
    # Volume
    volume_usd = attributes.get("volume_usd") or {}
    volume = {
        "h24": float(volume_usd.get("h24") or 0.0),
        "h6": float(volume_usd.get("h6") or 0.0),
        "h1": float(volume_usd.get("h1") or 0.0),
        "m5": float(volume_usd.get("m5") or 0.0),
    }
    
    # Transactions
    txns_data = attributes.get("transactions") or {}
    txns = {}
    for period in ["h24", "h6", "h1", "m5"]:
        p_data = txns_data.get(period) or {}
        txns[period] = {
            "buys": int(p_data.get("buys") or 0),
            "sells": int(p_data.get("sells") or 0)
        }
        
    # Price changes
    price_change_data = attributes.get("price_change_percentage") or {}
    price_change = {
        "h24": float(price_change_data.get("h24") or 0.0),
        "h6": float(price_change_data.get("h6") or 0.0),
        "h1": float(price_change_data.get("h1") or 0.0),
        "m5": float(price_change_data.get("m5") or 0.0),
    }
    
    # Pair created at (ISO 8601 string, e.g. "2025-02-07T15:30:11Z")
    pair_created_at = None
    created_at_str = attributes.get("pool_created_at")
    if created_at_str:
        try:
            dt = datetime.strptime(created_at_str.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
            pair_created_at = int(dt.timestamp() * 1000)
        except Exception:
            pass
            
    chain_id = MAP_GECKO_TO_DEXSCREENER_CHAIN.get(gecko_network, gecko_network)
            
    return {
        "chainId": chain_id,
        "dexId": dex_id,
        "pairAddress": attributes.get("address"),
        "url": f"https://geckoterminal.com/{gecko_network}/pools/{attributes.get('address')}",
        "baseToken": base_token,
        "quoteToken": quote_token,
        "priceUsd": str(attributes.get("base_token_price_usd")) if attributes.get("base_token_price_usd") is not None else None,
        "fdv": str(attributes.get("fdv_usd")) if attributes.get("fdv_usd") is not None else None,
        "marketCap": str(attributes.get("market_cap_usd")) if attributes.get("market_cap_usd") is not None else None,
        "liquidity": liquidity,
        "volume": volume,
        "txns": txns,
        "priceChange": price_change,
        "pairCreatedAt": pair_created_at
    }


# ---------------------------------------------------------------------------
# API Query Logic
# ---------------------------------------------------------------------------
def _fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    default_headers = {"User-Agent": "ChainWatchAI/0.4"}
    if headers:
        default_headers.update(headers)
    response = httpx.get(url, headers=default_headers, timeout=12)
    response.raise_for_status()
    return json.loads(response.text)


def lookup_token_or_pair(query: str) -> DexScreenerResult:
    clean_query = query.strip()
    if not clean_query:
        return DexScreenerResult(pairs=[], source="none", error="Empty query")

    # Major EVM chains we scan sequentially for address lookups
    supported_evm_chains = ["ethereum", "bsc", "base", "arbitrum", "polygon", "optimism", "avalanche"]
    last_error: Optional[str] = None

    # CASE 1: EVM Address Lookups
    if is_evm_address(clean_query):
        checksummed = to_checksum_address(clean_query)
        
        # Phase 1: Try DexScreener v1 endpoints
        for chain in supported_evm_chains:
            url = DEXSCREENER_TOKEN_V1_URL.format(chain=chain, address=checksummed)
            try:
                pairs = _fetch_json(url)
                if isinstance(pairs, list) and len(pairs) > 0:
                    return DexScreenerResult(pairs=pairs, source=f"dexscreener_v1_{chain}")
            except httpx.HTTPStatusError as exc:
                last_error = f"DexScreener HTTP {exc.response.status_code}"
                if exc.response.status_code == 429:
                    break  # Bypasses loops once rate limit is detected to query fallback
            except Exception as exc:
                last_error = str(exc)
                continue

        # Phase 2: GeckoTerminal fallback
        for chain in supported_evm_chains:
            network = MAP_DEXSCREENER_TO_GECKO_CHAIN.get(chain)
            if not network:
                continue
            url = GECKOTERMINAL_POOL_URL.format(network=network, address=checksummed)
            try:
                headers = {"Accept": "application/json;version=20230203"}
                payload = _fetch_json(url, headers=headers)
                data = payload.get("data") or []
                if isinstance(data, list) and len(data) > 0:
                    mapped_pairs = [_map_gecko_pool_to_dex_pair(pool, network) for pool in data]
                    return DexScreenerResult(pairs=mapped_pairs, source=f"geckoterminal_{chain}")
            except Exception as exc:
                last_error = f"GeckoTerminal error: {exc}"
                continue

        # Phase 3: Legacy DexScreener Endpoint as a last ditch effort
        try:
            payload = _fetch_json(DEXSCREENER_TOKEN_URL.format(address=checksummed))
            pairs = payload.get("pairs") or []
            if pairs:
                return DexScreenerResult(pairs=pairs, source="dexscreener_legacy")
        except Exception as exc:
            last_error = f"DexScreener legacy fallback failed: {exc}"

        return DexScreenerResult(pairs=[], source="dexscreener", error=last_error or "Token not found")

    # CASE 2: Solana Address Lookups
    if is_solana_address(clean_query):
        # Phase 1: Try DexScreener v1 Solana
        url = DEXSCREENER_TOKEN_V1_URL.format(chain="solana", address=clean_query)
        try:
            pairs = _fetch_json(url)
            if isinstance(pairs, list) and len(pairs) > 0:
                return DexScreenerResult(pairs=pairs, source="dexscreener_v1_solana")
        except httpx.HTTPStatusError as exc:
            last_error = f"DexScreener Solana HTTP {exc.response.status_code}"
        except Exception as exc:
            last_error = str(exc)

        # Phase 2: Try GeckoTerminal Solana
        url = GECKOTERMINAL_POOL_URL.format(network="solana", address=clean_query)
        try:
            headers = {"Accept": "application/json;version=20230203"}
            payload = _fetch_json(url, headers=headers)
            data = payload.get("data") or []
            if isinstance(data, list) and len(data) > 0:
                mapped_pairs = [_map_gecko_pool_to_dex_pair(pool, "solana") for pool in data]
                return DexScreenerResult(pairs=mapped_pairs, source="geckoterminal_solana")
        except Exception as exc:
            last_error = f"GeckoTerminal Solana error: {exc}"

        return DexScreenerResult(pairs=[], source="solana", error=last_error or "Solana token not found")

    # CASE 3: Text/Symbol/Name Queries
    # Phase 1: DexScreener search API
    try:
        payload = _fetch_json(DEXSCREENER_SEARCH_URL.format(query=clean_query))
        pairs = payload.get("pairs") or []
        if pairs:
            return DexScreenerResult(pairs=pairs, source="dexscreener_search")
    except httpx.HTTPStatusError as exc:
        last_error = f"DexScreener search HTTP {exc.response.status_code}"
    except Exception as exc:
        last_error = str(exc)

    # Phase 2: GeckoTerminal search pools fallback
    try:
        headers = {"Accept": "application/json;version=20230203"}
        payload = _fetch_json(GECKOTERMINAL_SEARCH_URL.format(query=clean_query), headers=headers)
        data = payload.get("data") or []
        if isinstance(data, list) and len(data) > 0:
            mapped_pairs = []
            for pool in data:
                # Deduce network from the pool ID (e.g. "eth_0x..." -> network="eth")
                pool_id = pool.get("id", "")
                network = "eth"
                if "_" in pool_id:
                    network = pool_id.split("_")[0]
                mapped_pairs.append(_map_gecko_pool_to_dex_pair(pool, network))
            return DexScreenerResult(pairs=mapped_pairs, source="geckoterminal_search")
    except Exception as exc:
        last_error = f"GeckoTerminal search error: {exc}"

    return DexScreenerResult(pairs=[], source="dexscreener", error=last_error)
