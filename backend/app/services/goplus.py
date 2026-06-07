from __future__ import annotations

import httpx
from typing import Any, Dict, Optional

GOPLUS_URL = "https://api.gopluslabs.io/api/v1/token_security/{chain_id}"

def check_token_security(token_address: str, chain_id: str = "1") -> Dict[str, Any]:
    """
    Fetch token security data from the GoPlus Security API.
    Chain ID defaults to '1' for Ethereum.
    If chain_id is 'solana', it uses the Solana endpoint.
    """
    if chain_id == "solana":
        url = "https://api.gopluslabs.io/api/v1/solana/token_security"
    else:
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
            # Solana addresses are base58 and case-sensitive; EVM addresses are hex and case-insensitive
            is_solana = chain_id == "solana"
            for addr, data in result_dict.items():
                match = (addr == token_address) if is_solana else (addr.lower() == token_address.lower())
                if match:
                    return data

            # If not found by exact match, return the first key's data if available
            if result_dict:
                return next(iter(result_dict.values()))
    except Exception as e:
        print(f"[ChainWatch] GoPlus API check failed for {token_address}: {e}")
    
    return {}
