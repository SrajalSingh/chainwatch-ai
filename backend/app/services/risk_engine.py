from __future__ import annotations

"""
ChainWatch AI — Risk Engine v2
================================
Scores a DexScreener pair for launch risk. Returns a structured dict
that the frontend renders in the Risk Intelligence panel.

Score bands (0-100 — higher = more dangerous):
  0–24   Low       ✅ Generally safe for cautious entry
  25–44  Moderate  ⚠️  Some flags — do your own research
  45–64  High      🚨 Multiple red flags — high caution
  65–100 Critical  ☠️  Avoid or exit immediately

Verdict: "Buy", "Caution", "Avoid"
"""

from typing import Any, Dict, List


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _age_hours(pair: Dict[str, Any]) -> float | None:
    """Return hours since the pair was created, or None if unknown."""
    created_at_ms = pair.get("pairCreatedAt")
    if not created_at_ms:
        return None
    from time import time
    hours = (time() * 1000 - _float(created_at_ms)) / 1000 / 60 / 60
    return max(0.0, hours)


def _age_label(hours: float | None) -> str:
    if hours is None:
        return "Unknown age"
    if hours < 1:
        return f"{int(hours * 60)}m old"
    if hours < 48:
        return f"{round(hours, 1)}h old"
    days = hours / 24
    if days > 365:
        return f"{round(days / 365, 1)} years old"
    if days > 30:
        return f"{round(days / 30, 1)} months old"
    return f"{round(days, 1)} days old"


def _category(name: str, icon: str, points: int, max_points: int, status: str, evidence: List[str]) -> Dict[str, Any]:
    return {
        "name": name,
        "icon": icon,
        "points": points,
        "maxPoints": max_points,
        "status": status,
        "evidence": evidence,
    }


def _status(points: int, high: int, medium: int) -> str:
    if points >= high:
        return "High Concern"
    if points >= medium:
        return "Watch"
    return "Stable"


# ─────────────────────────────────────────────────────────────
# Contract source analysis
# ─────────────────────────────────────────────────────────────

def analyze_contract_source(source_code: str | None, owner_address: str | None) -> Dict[str, Any]:
    """Parse a Solidity source to detect dangerous permission patterns."""
    if not source_code:
        return {
            "isVerified": False,
            "isOwnable": False,
            "ownershipRenounced": False,
            "hasBlacklist": False,
            "hasMint": False,
            "hasPause": False,
            "hasTaxModifier": False,
            "hasMaxWallet": False,
        }

    code_lower = source_code.lower()

    has_blacklist = any(kw in code_lower for kw in [
        "blacklist", "isblacklisted", "blacklists", "freezefunds", "freezewallet", "_blacklisted"
    ])

    has_mint = any(kw in code_lower for kw in [
        "function mint", "function _mint", "externalmint"
    ])

    has_pause = any(kw in code_lower for kw in [
        "function pause", "function setpaused", "whennotpaused", "_paused"
    ])

    # Hidden tax / fee modifier that can be changed post-launch
    has_tax_modifier = any(kw in code_lower for kw in [
        "settaxfee", "setbuytax", "setselltax", "_taxfee", "setfee", "updatefee", "setsellpercentage"
    ])

    # Max wallet/tx cap that devs can lift anytime
    has_max_wallet = any(kw in code_lower for kw in [
        "maxwallet", "maxwalletamount", "_maxwallet", "maxtxamount", "_maxtx"
    ])

    is_ownable = any(kw in code_lower for kw in [
        "ownable", "owner()", "_owner", "transferownership"
    ])

    ownership_renounced = False
    if is_ownable:
        zero = "0x0000000000000000000000000000000000000000"
        if owner_address == zero or owner_address is None:
            ownership_renounced = True

    return {
        "isVerified": True,
        "isOwnable": is_ownable,
        "ownershipRenounced": ownership_renounced,
        "hasBlacklist": has_blacklist,
        "hasMint": has_mint,
        "hasPause": has_pause,
        "hasTaxModifier": has_tax_modifier,
        "hasMaxWallet": has_max_wallet,
    }


# ─────────────────────────────────────────────────────────────
# Main scoring function
# ─────────────────────────────────────────────────────────────

def score_pair(
    pair: Dict[str, Any],
    pair_count: int = 0,
    contract_intel: Dict[str, Any] | None = None,
    on_chain: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Score a token pair for fraud/rug-pull risk.

    Categories and max points (total = 100):
      1. Token Age            25 pts  — New tokens are the highest-risk window
      2. Rug Pull Signals     20 pts  — Contract/developer red flags
      3. Liquidity Health     20 pts  — Thin liquidity = easy manipulation
      4. Volume & Trading     15 pts  — Wash-trading, pump-and-dump patterns
      5. Contract Security    15 pts  — Verified source, permissions audit
      6. Market Structure      5 pts  — Pair count, FDV/MC ratio
    """

    # ── Raw data ─────────────────────────────────────────────
    liquidity = pair.get("liquidity") or {}
    volume    = pair.get("volume") or {}
    txns      = pair.get("txns") or {}
    pc        = pair.get("priceChange") or {}

    liq_usd    = _float(liquidity.get("usd"))
    vol_24h    = _float(volume.get("h24"))
    vol_6h     = _float(volume.get("h6"))
    fdv        = _float(pair.get("fdv"))
    market_cap = _float(pair.get("marketCap"))
    age_hours  = _age_hours(pair)

    h24_txns   = txns.get("h24") or {}
    h6_txns    = txns.get("h6") or {}
    buys_24h   = _float(h24_txns.get("buys"))
    sells_24h  = _float(h24_txns.get("sells"))
    buys_6h    = _float(h6_txns.get("buys"))
    sells_6h   = _float(h6_txns.get("sells"))
    tx_24h     = buys_24h + sells_24h
    tx_6h      = buys_6h + sells_6h

    chg_5m  = _float(pc.get("m5"))
    chg_1h  = _float(pc.get("h1"))
    chg_6h  = _float(pc.get("h6"))
    chg_24h = _float(pc.get("h24"))

    categories: List[Dict[str, Any]] = []
    flags: List[str]     = []   # red flags surfaced in UI
    strengths: List[str] = []   # positive signals surfaced in UI
    rug_signals: List[str] = [] # specific rug-pull indicators

    # ═══════════════════════════════════════════════════════
    # 1. TOKEN AGE  (max 25 pts)
    # ═══════════════════════════════════════════════════════
    age_pts = 0
    age_ev: List[str] = []

    if age_hours is None:
        age_pts += 12
        age_ev.append("⏱️ Launch date is unknown — treat this like a brand-new token.")
    elif age_hours < 1:
        age_pts += 25
        age_ev.append(f"🚨 Token is only {_age_label(age_hours)}. Extremely high rug-pull window — most scams happen in the first hour.")
    elif age_hours < 6:
        age_pts += 22
        age_ev.append(f"🚨 Token is only {_age_label(age_hours)}. Still in the highest-risk launch phase. Most rug-pulls occur within 6 hours.")
    elif age_hours < 24:
        age_pts += 18
        age_ev.append(f"⚠️ Token is {_age_label(age_hours)}. Less than one full day of trading history — elevated risk.")
    elif age_hours < 72:
        age_pts += 14
        age_ev.append(f"⚠️ Token is {_age_label(age_hours)}. Under 3 days old — still in the high-risk early window.")
    elif age_hours < 168:
        age_pts += 9
        age_ev.append(f"⚠️ Token is {_age_label(age_hours)}. Under one week old — moderate caution still warranted.")
    elif age_hours < 720:
        age_pts += 4
        age_ev.append(f"✅ Token is {_age_label(age_hours)}. Survived past the first week, but still maturing.")
        strengths.append("Survived past the first week of trading.")
    else:
        age_pts += 0
        age_ev.append(f"✅ Token is {_age_label(age_hours)}. Has real trading history — age risk is low.")
        strengths.append(f"Token has {_age_label(age_hours)} of trading history.")

    categories.append(_category("Token Age", "⏱️", age_pts, 25, _status(age_pts, 16, 8), age_ev))

    # ═══════════════════════════════════════════════════════
    # 2. RUG PULL SIGNALS  (max 20 pts)
    # ═══════════════════════════════════════════════════════
    rug_pts = 0
    rug_ev: List[str] = []

    # Price dump signals
    if chg_24h < -50:
        rug_pts += 10
        msg = f"🚨 Price crashed {abs(round(chg_24h))}% in 24h — classic rug-pull or mass sell-off pattern."
        rug_ev.append(msg)
        rug_signals.append(msg)
    elif chg_24h < -30:
        rug_pts += 6
        msg = f"⚠️ Price dropped {abs(round(chg_24h))}% in 24h — significant sell pressure detected."
        rug_ev.append(msg)
        rug_signals.append(msg)

    # Extreme short-window pump (classic pump-before-dump)
    if chg_5m > 50 or chg_1h > 200:
        rug_pts += 6
        msg = "🚨 Extreme short-window price spike detected — possible pump-and-dump in progress."
        rug_ev.append(msg)
        rug_signals.append(msg)
    elif chg_1h > 100:
        rug_pts += 4
        msg = "⚠️ Price spiked over 100% in 1 hour — abnormal pump activity."
        rug_ev.append(msg)
        rug_signals.append(msg)

    # Creator is a serial deployer and has holdings concentration (from on-chain data if available)
    if on_chain and on_chain.get("available"):
        creator_contracts = on_chain.get("creatorRecentContractCreations", 0)
        creator_fails = on_chain.get("creatorRecentFailedTxCount", 0)
        creator_holding = on_chain.get("creatorHoldingPercent", 0.0)

        if creator_contracts >= 5:
            rug_pts += 6
            msg = f"🚨 Creator wallet has deployed {creator_contracts} recent contracts — serial token launching is a major rug-pull indicator."
            rug_ev.append(msg)
            rug_signals.append(msg)
        elif creator_contracts >= 2:
            rug_pts += 3
            msg = f"⚠️ Creator wallet has deployed {creator_contracts} recent contracts. Watch for history of abandoned tokens."
            rug_ev.append(msg)

        if creator_fails >= 5:
            rug_pts += 2
            msg = f"⚠️ Creator wallet has {creator_fails} recent failed transactions — unusual pattern."
            rug_ev.append(msg)

        # Creator concentration check
        if creator_holding > 50.0:
            rug_pts += 12
            msg = f"🚨 Creator wallet holds {creator_holding}% of total supply — extreme rug-pull/dump risk."
            rug_ev.append(msg)
            rug_signals.append(msg)
        elif creator_holding > 20.0:
            rug_pts += 8
            msg = f"🚨 Creator wallet holds {creator_holding}% of total supply — high risk of developer dump."
            rug_ev.append(msg)
            rug_signals.append(msg)
        elif creator_holding > 5.0:
            rug_pts += 4
            msg = f"⚠️ Creator wallet holds {creator_holding}% of total supply — elevated concentration."
            rug_ev.append(msg)
        elif creator_holding > 0.0:
            strengths.append(f"Creator wallet concentration is very low ({creator_holding}%).")

    # New token with no sells yet = honeypot signal
    if age_hours is not None and age_hours < 48 and sells_24h == 0 and buys_24h > 10:
        rug_pts += 8
        msg = "🚨 Many buyers but ZERO sells — this is the classic honeypot signature. You may not be able to sell."
        rug_ev.append(msg)
        rug_signals.append(msg)
    elif sells_24h == 0 and buys_24h > 5:
        rug_pts += 5
        msg = "⚠️ No sell transactions recorded. Possible honeypot — test with a tiny amount before committing."
        rug_ev.append(msg)
        rug_signals.append(msg)

    if rug_pts == 0 and not rug_ev:
        rug_ev.append("✅ No obvious rug-pull price patterns detected in recent data.")

    categories.append(_category("Rug Pull Signals", "🪤", rug_pts, 20, _status(rug_pts, 12, 5), rug_ev))

    # ═══════════════════════════════════════════════════════
    # 3. LIQUIDITY HEALTH  (max 20 pts)
    # ═══════════════════════════════════════════════════════
    liq_pts = 0
    liq_ev: List[str] = []

    if liq_usd <= 0:
        liq_pts += 20
        liq_ev.append("🚨 Zero liquidity reported. Token may be untradeable or the pool was drained (rug).")
        rug_signals.append("Zero liquidity — pool may have been drained.")
    elif liq_usd < 5_000:
        liq_pts += 18
        liq_ev.append(f"🚨 Liquidity is critically thin (${liq_usd:,.0f}). A single whale can crash the price instantly.")
    elif liq_usd < 20_000:
        liq_pts += 13
        liq_ev.append(f"⚠️ Low liquidity (${liq_usd:,.0f}). Large buys/sells will cause heavy slippage.")
    elif liq_usd < 100_000:
        liq_pts += 7
        liq_ev.append(f"⚠️ Moderate liquidity (${liq_usd:,.0f}). Manageable but not deep enough for large positions.")
    elif liq_usd < 500_000:
        liq_pts += 2
        liq_ev.append(f"✅ Decent liquidity (${liq_usd:,.0f}). Sufficient for regular trading.")
        strengths.append(f"Decent liquidity pool of ${liq_usd:,.0f}.")
    else:
        liq_ev.append(f"✅ Strong liquidity (${liq_usd:,.0f}). Deep market — manipulation is harder.")
        strengths.append(f"Strong liquidity of ${liq_usd:,.0f}.")

    # FDV vs Liquidity ratio — low liquidity relative to valuation is dangerous
    if fdv > 0 and liq_usd > 0:
        ratio = fdv / liq_usd
        if ratio > 1000:
            liq_pts += 5
            liq_ev.append(f"🚨 FDV is {round(ratio)}× the liquidity pool — extremely easy to manipulate price.")
        elif ratio > 300:
            liq_pts += 3
            liq_ev.append(f"⚠️ FDV is {round(ratio)}× the liquidity pool — limited capital can swing the market heavily.")
        else:
            liq_ev.append(f"✅ FDV-to-liquidity ratio is {round(ratio)}× — within acceptable range.")

    categories.append(_category("Liquidity Health", "💧", liq_pts, 20, _status(liq_pts, 14, 6), liq_ev))

    # ═══════════════════════════════════════════════════════
    # 4. VOLUME & TRADING PATTERN  (max 15 pts)
    # ═══════════════════════════════════════════════════════
    vol_pts = 0
    vol_ev: List[str] = []

    # Sell-to-buy imbalance
    if tx_24h > 0:
        sell_ratio = sells_24h / tx_24h if tx_24h > 0 else 0
        if sell_ratio > 0.75 and sells_24h >= 20:
            vol_pts += 7
            vol_ev.append(f"🚨 {round(sell_ratio * 100)}% of recent transactions are sells — heavy distribution/exit pattern.")
            flags.append("Sell-heavy transaction ratio — possible mass exit.")
        elif sell_ratio < 0.1 and buys_24h >= 10:
            vol_pts += 6
            vol_ev.append(f"⚠️ Only {round(sell_ratio * 100)}% sells — artificially one-sided buying. Could signal bot activity or honeypot.")
        else:
            vol_ev.append(f"✅ Buy/sell balance is {round((1 - sell_ratio) * 100)}% buys / {round(sell_ratio * 100)}% sells — relatively normal.")
            strengths.append("Buy/sell ratio is within normal range.")
    else:
        vol_pts += 5
        vol_ev.append("⚠️ No transactions in the last 24h — token may be dead or very illiquid.")

    # Volume vs Liquidity — wash-trading or pump detection
    if vol_24h > 0 and liq_usd > 0:
        vl_ratio = vol_24h / liq_usd
        if vl_ratio > 20:
            vol_pts += 6
            vol_ev.append(f"🚨 24h volume is {round(vl_ratio)}× the liquidity — extreme wash-trading or pump manipulation likely.")
        elif vl_ratio > 8:
            vol_pts += 4
            vol_ev.append(f"⚠️ 24h volume is {round(vl_ratio)}× the liquidity — elevated, watch for artificial activity.")
        elif vl_ratio > 3:
            vol_pts += 2
            vol_ev.append(f"⚠️ Volume is {round(vl_ratio, 1)}× liquidity — slightly elevated but not alarming.")
        else:
            vol_ev.append(f"✅ Volume/liquidity ratio is {round(vl_ratio, 1)}× — proportionate to pool size.")
    elif vol_24h == 0:
        vol_pts += 4
        vol_ev.append("⚠️ Zero reported trading volume in 24h — no real market activity detected.")

    # Suspiciously low tx count
    if 0 < tx_24h < 10:
        vol_pts += 2
        vol_ev.append(f"⚠️ Only {int(tx_24h)} transactions in 24h — insufficient trading history to assess this token.")

    categories.append(_category("Volume & Trading", "📊", vol_pts, 15, _status(vol_pts, 10, 4), vol_ev))

    # ═══════════════════════════════════════════════════════
    # 5. CONTRACT SECURITY  (max 15 pts)
    # ═══════════════════════════════════════════════════════
    con_pts = 0
    con_ev: List[str] = []

    if contract_intel is not None:
        if not contract_intel.get("isVerified"):
            con_pts += 10
            msg = "🚨 Contract source is NOT verified on Etherscan. The code could contain hidden functions — impossible to audit."
            con_ev.append(msg)
            flags.append("Unverified contract source code.")
        else:
            con_ev.append("✅ Contract source is verified on Etherscan — code is publicly auditable.")
            strengths.append("Contract source is verified on Etherscan.")

            if contract_intel.get("hasBlacklist"):
                con_pts += 5
                msg = "🚨 Contract has blacklisting functions — the dev can block any wallet from selling (honeypot risk)."
                con_ev.append(msg)
                rug_signals.append("Blacklist function found in contract.")
            else:
                con_ev.append("✅ No wallet blacklisting functions found.")
                strengths.append("No blacklisting capabilities in contract.")

            if contract_intel.get("hasMint"):
                con_pts += 4
                msg = "⚠️ Contract has external minting capability — dev can create new tokens, diluting your holdings."
                con_ev.append(msg)
            else:
                con_ev.append("✅ No external minting capability — supply is fixed.")
                strengths.append("Fixed token supply — no inflation risk.")

            if contract_intel.get("hasPause"):
                con_pts += 3
                msg = "⚠️ Contract has a pause function — trading can be halted by the developer at any time."
                con_ev.append(msg)
            else:
                con_ev.append("✅ No pause function — trading cannot be frozen by the dev.")

            if contract_intel.get("hasTaxModifier"):
                con_pts += 4
                msg = "🚨 Contract has hidden tax modifier — the dev can raise buy/sell taxes to 99% at any time."
                con_ev.append(msg)
                rug_signals.append("Adjustable tax function found in contract.")
            else:
                con_ev.append("✅ No tax manipulation functions detected.")

            if contract_intel.get("hasMaxWallet"):
                con_pts += 2
                msg = "⚠️ Contract has a max wallet/tx cap that the dev can change — commonly used to control dump timing."
                con_ev.append(msg)

            if contract_intel.get("isOwnable"):
                if contract_intel.get("ownershipRenounced"):
                    con_ev.append("✅ Contract ownership is renounced — no admin can change contract rules.")
                    strengths.append("Ownership is renounced — no admin backdoors.")
                else:
                    con_pts += 3
                    msg = "⚠️ Contract ownership is active — the owner can change permissions or upgrade the contract."
                    con_ev.append(msg)
            else:
                con_ev.append("✅ No standard Ownable pattern detected in contract.")
    else:
        con_pts += 8
        con_ev.append("⚠️ Contract data is unavailable (non-Ethereum chain or Etherscan API issue). Cannot audit permissions.")

    categories.append(_category("Contract Security", "🔐", con_pts, 15, _status(con_pts, 10, 4), con_ev))

    # ═══════════════════════════════════════════════════════
    # 6. MARKET STRUCTURE  (max 5 pts)
    # ═══════════════════════════════════════════════════════
    mkt_pts = 0
    mkt_ev: List[str] = []

    if pair_count <= 1:
        mkt_pts += 3
        mkt_ev.append("⚠️ Only one trading pair found — very limited market reach. Easy to manipulate.")
    elif pair_count < 4:
        mkt_pts += 1
        mkt_ev.append(f"⚠️ Only {pair_count} related pairs — narrow market depth.")
    else:
        mkt_ev.append(f"✅ {pair_count} related trading pairs found — good market visibility.")
        strengths.append(f"Listed on {pair_count} trading pairs.")

    if fdv > 0 and market_cap > 0 and fdv > market_cap * 10:
        mkt_pts += 2
        mkt_ev.append(f"⚠️ FDV is {round(fdv / market_cap)}× the market cap — large future supply unlock pressure.")
    elif fdv > 0 and market_cap > 0:
        mkt_ev.append(f"✅ FDV is {round(fdv / market_cap)}× the market cap — reasonable supply ratio.")

    categories.append(_category("Market Structure", "🏗️", mkt_pts, 5, _status(mkt_pts, 4, 2), mkt_ev))

    # ═══════════════════════════════════════════════════════
    # Final score + verdict
    # ═══════════════════════════════════════════════════════
    raw_score = sum(c["points"] for c in categories)
    score = max(0, min(100, round(raw_score)))

    # Build flags from categories that are "High Concern"
    for cat in categories:
        if cat["status"] == "High Concern":
            for ev in cat["evidence"]:
                if ev not in flags and ("🚨" in ev or "⚠️" in ev):
                    flags.append(ev)

    if score <= 24:
        level   = "Low"
        verdict = "Buy"
        verdict_emoji = "✅"
        verdict_reason = "Risk profile is low. Entry conditions look acceptable — standard crypto risk applies."
    elif score <= 44:
        level   = "Moderate"
        verdict = "Caution"
        verdict_emoji = "⚠️"
        verdict_reason = "Some risk flags detected. Do your own research before investing. Use small position sizes."
    elif score <= 64:
        level   = "High"
        verdict = "Avoid"
        verdict_emoji = "🚨"
        verdict_reason = "Multiple red flags present. High probability of loss. Avoid unless you accept significant risk."
    else:
        level   = "Critical"
        verdict = "Avoid"
        verdict_emoji = "☠️"
        verdict_reason = "Critical risk indicators. This token exhibits classic rug-pull or scam characteristics."

    # Confidence
    available_signals = sum(1 for v in [
        liq_usd > 0, vol_24h > 0, tx_24h > 0,
        age_hours is not None,
        contract_intel is not None and contract_intel.get("isVerified"),
    ] if v)

    if available_signals >= 4:
        confidence = "High"
    elif available_signals >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    data_gaps = []
    if contract_intel is None:
        data_gaps.append("Contract permissions not checked (Etherscan data unavailable for this chain).")
    if not (on_chain and on_chain.get("available")):
        data_gaps.append("Creator wallet history not available — serial deployer check skipped.")
    data_gaps.append("Top holder concentration requires on-chain holder snapshot (Etherscan Pro or Moralis).")

    return {
        "score": score,
        "level": level,
        "verdict": verdict,
        "verdictEmoji": verdict_emoji,
        "verdictReason": verdict_reason,
        "confidence": confidence,
        "rugSignals": rug_signals,
        "flags": flags[:6],
        "strengths": strengths[:5],
        "categories": categories,
        "dataGaps": data_gaps,
        "signals": {
            "liquidityUsd": round(liq_usd, 2),
            "volume24h": round(vol_24h, 2),
            "volumeLiquidityRatio": round(vol_24h / liq_usd, 2) if liq_usd > 0 else None,
            "ageHours": round(age_hours, 2) if age_hours is not None else None,
            "ageLabel": _age_label(age_hours),
            "buys24h": int(buys_24h),
            "sells24h": int(sells_24h),
            "txCount24h": int(tx_24h),
            "priceChange24h": chg_24h,
            "priceChange1h": chg_1h,
            "priceChange5m": chg_5m,
            "fdv": round(fdv, 2) if fdv else None,
            "marketCap": round(market_cap, 2) if market_cap else None,
            "relatedPairCount": pair_count,
        },
    }


# ─────────────────────────────────────────────────────────────
# Human-readable analyst summary
# ─────────────────────────────────────────────────────────────

def analyst_explanation(token_name: str, risk: Dict[str, Any]) -> str:
    score    = risk["score"]
    level    = risk["level"]
    verdict  = risk["verdict"]
    emoji    = risk["verdictEmoji"]
    confidence = risk.get("confidence", "Medium")
    rug      = risk.get("rugSignals", [])
    sigs     = risk.get("signals", {})
    age_lbl  = sigs.get("ageLabel", "unknown age")

    lead = f"{emoji} {token_name} scores {score}/100 — {level} Risk. Verdict: {verdict}. ({confidence} confidence)"

    if level == "Critical":
        rug_str = " ".join(rug[:2]) if rug else "Multiple critical signals detected."
        return f"{lead} This token has critical danger indicators: {rug_str} Do not invest."

    if level == "High":
        rug_str = " ".join(rug[:1]) if rug else "Multiple high-risk flags."
        return f"{lead} Token is {age_lbl} with significant concerns: {rug_str} Avoid unless you fully understand the risk."

    if level == "Moderate":
        return (
            f"{lead} Token is {age_lbl}. "
            f"Some caution flags are present — use small position sizes, set a stop-loss, "
            f"and verify the contract on Etherscan before committing funds."
        )

    # Low risk
    return (
        f"{lead} Token is {age_lbl}. "
        f"No critical red flags detected in the available data. "
        f"Standard crypto risks apply — always verify independently and never invest more than you can afford to lose."
    )
