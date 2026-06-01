from __future__ import annotations

from collections import defaultdict
from math import cos, pi, sin
from typing import Any, Dict, Iterable, List, Tuple


def _short(address: str) -> str:
    if not address:
        return "Unknown"
    if address.lower() == "0x0000000000000000000000000000000000000000":
        return "MINT"
    return f"{address[:6]}...{address[-4:]}"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _token_amount(transfer: Dict[str, Any]) -> float:
    raw_value = _to_float(transfer.get("value"))
    decimals = _to_float(transfer.get("tokenDecimal"), 18.0)
    if decimals <= 0:
        return raw_value
    return raw_value / (10 ** decimals)


def _add_edge(acc: Dict[Tuple[str, str, str], Dict[str, Any]], source: str, target: str, kind: str, amount: float) -> None:
    edge_key = (source, target, kind)
    if edge_key not in acc:
        acc[edge_key] = {
            "source": source,
            "target": target,
            "kind": kind,
            "count": 0,
            "amount": 0.0,
        }
    acc[edge_key]["count"] += 1
    acc[edge_key]["amount"] += amount


def _top_counterparties(creator: str, txs: Iterable[Dict[str, Any]], transfers: Iterable[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "tags": set()})

    for tx in txs:
        other = tx.get("to") if (tx.get("from") or "").lower() == creator.lower() else tx.get("from")
        if not other or other.lower() == creator.lower():
            continue
        scores[other]["score"] += 1
        scores[other]["tags"].add("wallet")

    for transfer in transfers:
        from_address = (transfer.get("from") or "").lower()
        to_address = (transfer.get("to") or "").lower()
        creator_lower = creator.lower()
        if from_address == creator_lower:
            other = transfer.get("to")
        elif to_address == creator_lower:
            other = transfer.get("from")
        else:
            continue
        if not other or other.lower() == creator_lower:
            continue
        scores[other]["score"] += max(1.0, _token_amount(transfer))
        scores[other]["tags"].add("token-transfer")

    ranked = sorted(scores.items(), key=lambda item: item[1]["score"], reverse=True)[:limit]
    return [
        {
            "id": address,
            "address": address,
            "type": "counterparty",
            "label": _short(address),
            "tags": sorted(meta["tags"]),
        }
        for address, meta in ranked
    ]


def _position_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not nodes:
        return nodes

    positioned: List[Dict[str, Any]] = []
    outer = [node for node in nodes if node["type"] not in {"token", "creator"}]
    for node in nodes:
        if node["type"] == "token":
            positioned.append({**node, "x": 50, "y": 48})
        elif node["type"] == "creator":
            positioned.append({**node, "x": 18, "y": 52})

    count = max(1, len(outer))
    for index, node in enumerate(outer):
        angle = (2 * pi * index / count) - (pi / 2)
        positioned.append(
            {
                **node,
                "x": round(50 + cos(angle) * 28, 2),
                "y": round(48 + sin(angle) * 28, 2),
            }
        )
    return positioned


def build_investigation_graph(
    token_address: str,
    creator: str | None,
    creation: Dict[str, Any] | None,
    creator_txs: List[Dict[str, Any]],
    creator_token_transfers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not creator:
        return {
            "available": False,
            "summary": {
                "headline": "No Ethereum deployer record was available for this token.",
            },
            "nodes": [],
            "edges": [],
        }

    nodes: List[Dict[str, Any]] = [
        {"id": token_address, "type": "token", "label": "TOKEN"},
        {"id": creator, "type": "creator", "label": "CREATOR"},
    ]
    nodes.extend(_top_counterparties(creator, creator_txs, creator_token_transfers))
    nodes = _position_nodes(nodes)
    visible_node_ids = {node["id"] for node in nodes}

    edge_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    _add_edge(edge_map, creator, token_address, "deploy", 0.0)

    for tx in creator_txs:
        source = tx.get("from") or creator
        target = tx.get("to") or token_address
        if source.lower() != creator.lower() and target.lower() != creator.lower():
            continue
        _add_edge(edge_map, source, target, "native-tx", _to_float(tx.get("value")))

    for transfer in creator_token_transfers:
        source = transfer.get("from") or creator
        target = transfer.get("to") or token_address
        if source.lower() != creator.lower() and target.lower() != creator.lower():
            continue
        _add_edge(edge_map, source, target, "token-tx", _token_amount(transfer))

    edges = [
        edge
        for edge in edge_map.values()
        if edge["source"] in visible_node_ids and edge["target"] in visible_node_ids
    ]
    created_at = creation.get("timestamp") if creation else None

    return {
        "available": True,
        "summary": {
            "headline": "Ethereum deployer activity graph built from Etherscan V2 free-tier endpoints.",
            "creatorAddress": creator,
            "creationTxHash": creation.get("txHash") if creation else None,
            "createdAt": created_at,
            "recentNativeTxCount": len(creator_txs),
            "recentTokenTransferCount": len(creator_token_transfers),
        },
        "nodes": nodes,
        "edges": edges,
    }
