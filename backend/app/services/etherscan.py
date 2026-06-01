from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"
ETHEREUM_CHAIN_ID = "1"


def _api_key() -> Optional[str]:
    return os.environ.get("ETHERSCAN_API_KEY")


def _query(params: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        return {"status": "0", "message": "NOTOK", "result": "ETHERSCAN_API_KEY is not configured."}

    try:
        response = httpx.get(
            ETHERSCAN_V2_URL,
            params={"chainid": ETHEREUM_CHAIN_ID, "apikey": api_key, **params},
            headers={"User-Agent": "ChainWatchAI/0.4"},
            timeout=12,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "status": "0",
            "message": "NOTOK",
            "result": f"Etherscan returned HTTP {exc.response.status_code}",
        }
    except httpx.RequestError as exc:
        return {
            "status": "0",
            "message": "NOTOK",
            "result": f"Etherscan request failed: {exc}",
        }


def _normalize_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = payload.get("result")
    if isinstance(result, list):
        return result
    return []


def get_contract_creation(contract_address: str) -> Optional[Dict[str, Any]]:
    payload = _query(
        {
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": contract_address,
        }
    )
    results = _normalize_list(payload)
    return results[0] if results else None


def get_address_transactions(address: str, offset: int = 25) -> List[Dict[str, Any]]:
    payload = _query(
        {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 999999999,
            "page": 1,
            "offset": offset,
            "sort": "desc",
        }
    )
    return _normalize_list(payload)


def get_internal_transactions(address: str, offset: int = 25) -> List[Dict[str, Any]]:
    payload = _query(
        {
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": 0,
            "endblock": 999999999,
            "page": 1,
            "offset": offset,
            "sort": "desc",
        }
    )
    return _normalize_list(payload)


def get_token_transfers_for_address(address: str, contract_address: str, offset: int = 40) -> List[Dict[str, Any]]:
    payload = _query(
        {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "contractaddress": contract_address,
            "startblock": 0,
            "endblock": 999999999,
            "page": 1,
            "offset": offset,
            "sort": "desc",
        }
    )
    return _normalize_list(payload)


def get_contract_source(contract_address: str) -> Optional[Dict[str, Any]]:
    payload = _query(
        {
            "module": "contract",
            "action": "getsourcecode",
            "address": contract_address,
        }
    )
    results = _normalize_list(payload)
    return results[0] if results else None


def get_contract_owner(contract_address: str) -> Optional[str]:
    payload = _query(
        {
            "module": "proxy",
            "action": "eth_call",
            "to": contract_address,
            "data": "0x8da80503",
            "tag": "latest",
        }
    )
    if "result" in payload and isinstance(payload["result"], str):
        res = payload["result"].strip()
        if res.startswith("0x") and len(res) >= 66:
            return "0x" + res[-40:]
    return None


def get_token_balance(contract_address: str, holder_address: str) -> Optional[int]:
    """Retrieve ERC-20 token balance of a specific address using eth_call proxy."""
    # balanceOf(address) signature: 70a08231
    clean_holder = holder_address.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + clean_holder
    payload = _query(
        {
            "module": "proxy",
            "action": "eth_call",
            "to": contract_address,
            "data": data,
            "tag": "latest",
        }
    )
    if "result" in payload and isinstance(payload["result"], str):
        res = payload["result"].strip()
        if res.startswith("0x") and len(res) > 2:
            try:
                return int(res, 16)
            except ValueError:
                return None
    return None


def get_total_supply(contract_address: str) -> Optional[int]:
    """Retrieve ERC-20 total supply using eth_call proxy."""
    # totalSupply() signature: 18160ddd
    payload = _query(
        {
            "module": "proxy",
            "action": "eth_call",
            "to": contract_address,
            "data": "0x18160ddd",
            "tag": "latest",
        }
    )
    if "result" in payload and isinstance(payload["result"], str):
        res = payload["result"].strip()
        if res.startswith("0x") and len(res) > 2:
            try:
                return int(res, 16)
            except ValueError:
                return None
    return None


