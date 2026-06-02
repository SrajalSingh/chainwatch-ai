from __future__ import annotations

import httpx
from typing import Any, Dict, Optional

GOPLUS_URL = "https://api.gopluslabs.io/api/v1/token_security/{chain_id}"

def check_token_security(token_address: str, chain_id: str = "1") -> Dict[str, Any]:
    """
    Fetch token security data from the GoPlus Security API.
    Chain ID defaults to '1' for Ethereum.
    """
    url = GOPLUS_URL.format(chain_id=chain_id)
    try:
        response = httpx.get(
            url,
            params={"contract_addresses": token_address},
            headers={"User-Agent": "ChainWatchAI/0.4"},
            timeout=10
        )
        response.raise_for_status()
        payload = response.json()
        
        if payload.get("code") == 1:
            result_dict = payload.get("result") or {}
            # Search case-insensitively for the matching address
            for addr, data in result_dict.items():
                if addr.lower() == token_address.lower():
                    return data
            
            # If not found by matching, return the first key's data if available
            if result_dict:
                return next(iter(result_dict.values()))
    except Exception as e:
        print(f"[ChainWatch] GoPlus API check failed for {token_address}: {e}")
    
    return {}
