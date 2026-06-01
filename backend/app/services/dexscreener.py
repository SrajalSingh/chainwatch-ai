from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search?q={query}"
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"


@dataclass
class DexScreenerResult:
    pairs: List[Dict[str, Any]]
    source: str
    error: Optional[str] = None


def _fetch_json(url: str) -> Dict[str, Any]:
    response = httpx.get(url, headers={"User-Agent": "ChainWatchAI/0.3"}, timeout=12)
    response.raise_for_status()
    return json.loads(response.text)


def lookup_token_or_pair(query: str) -> DexScreenerResult:
    clean_query = query.strip()
    if not clean_query:
        return DexScreenerResult(pairs=[], source="none", error="Empty query")

    urls = [
        (DEXSCREENER_TOKEN_URL.format(address=clean_query), "token"),
        (DEXSCREENER_SEARCH_URL.format(query=clean_query), "search"),
    ]

    last_error: Optional[str] = None
    for url, source in urls:
        try:
            payload = _fetch_json(url)
        except httpx.HTTPStatusError as exc:
            last_error = f"DexScreener returned HTTP {exc.response.status_code}"
            continue
        except httpx.RequestError as exc:
            last_error = f"Network error: {exc}"
            continue
        except TimeoutError:
            last_error = "DexScreener request timed out"
            continue
        except Exception as exc:  # Defensive boundary around a third-party API.
            last_error = f"Unexpected DexScreener error: {exc}"
            continue

        pairs = payload.get("pairs") or []
        if pairs:
            return DexScreenerResult(pairs=pairs, source=source)

    return DexScreenerResult(pairs=[], source="dexscreener", error=last_error)
