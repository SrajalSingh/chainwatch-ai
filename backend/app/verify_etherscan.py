from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode

import httpx

from services.env_loader import load_env


ROOT = Path(__file__).resolve().parents[2]
ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"
BASE_CHAIN_ID = "1"


def main() -> None:
    load_env(ROOT / ".env")
    api_key = os.environ.get("ETHERSCAN_API_KEY")

    if not api_key:
        raise SystemExit("ETHERSCAN_API_KEY was not found in .env")

    params = urlencode(
        {
            "chainid": BASE_CHAIN_ID,
            "module": "proxy",
            "action": "eth_blockNumber",
            "apikey": api_key,
        }
    )
    response = httpx.get(
        f"{ETHERSCAN_V2_URL}?{params}",
        headers={"User-Agent": "ChainWatchAI/0.2"},
        timeout=12,
    )
    payload = json.loads(response.text)

    result = payload.get("result")
    if isinstance(result, str) and result.startswith("0x"):
        print("Etherscan V2 key works for Ethereum.")
        print(f"Latest Ethereum block: {int(result, 16)}")
        return

    print("Etherscan responded, but the key/request was not accepted.")
    print(f"Status: {payload.get('status')}")
    print(f"Message: {payload.get('message')}")
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
