import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CircleDollarSign,
  Clock,
  DatabaseZap,
  ExternalLink,
  Network,
  Radar,
  Search,
  ShieldAlert,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import "./styles.css";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

function formatMoney(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number === 0) return "--";
  return money.format(number);
}

function formatSignal(key, value) {
  if (key.toLowerCase().includes("usd") || key === "fdv" || key === "marketCap") {
    return formatMoney(value);
  }
  return value ?? "--";
}

function labelize(key) {
  return key.replace(/([A-Z])/g, " $1").replace(/^./, (char) => char.toUpperCase());
}

function scoreColor(score) {
  if (score >= 80) return "var(--red)";
  if (score >= 60) return "var(--amber)";
  return "var(--accent)";
}

const HISTORY_KEY = "chainwatch_history";
const HISTORY_LIMIT = 20;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveToHistory(payload) {
  const base = (payload.token?.baseToken) || {};
  const risk = payload.risk || {};
  const entry = {
    id: `${payload.query}-${Date.now()}`,
    query: payload.query,
    name: base.name || payload.query,
    symbol: base.symbol || "",
    score: Number(risk.score || 0),
    level: risk.level || "Unknown",
    scannedAt: Date.now(),
  };
  const prev = loadHistory().filter((h) => h.query.toLowerCase() !== payload.query.toLowerCase());
  const next = [entry, ...prev].slice(0, HISTORY_LIMIT);
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch {}
  return next;
}

function App() {
  const [query, setQuery] = useState(() => new URLSearchParams(window.location.search).get("q") || "");
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState("");
  const [history, setHistory] = useState(loadHistory);

  const runAnalysis = useCallback(async (nextQuery = query) => {
    const cleanQuery = nextQuery.trim();
    if (!cleanQuery) {
      setAlert("Enter a token, pair, wallet, or symbol to analyze.");
      setAnalysis(null);
      window.history.replaceState({}, "", window.location.pathname);
      return;
    }

    setLoading(true);
    setAlert("");
    const nextUrl = `${window.location.pathname}?q=${encodeURIComponent(cleanQuery)}`;
    window.history.replaceState({}, "", nextUrl);
    try {
      const response = await fetch(`/api/analyze?query=${encodeURIComponent(cleanQuery)}`);
      const payload = await response.json();
      if (!payload.found) {
        setAlert(payload.message || payload.error || "No matching token was found.");
        setAnalysis(null);
        return;
      }
      setAnalysis(payload);
      setHistory(saveToHistory(payload));
    } catch (error) {
      setAlert(`Analysis failed: ${error.message}`);
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    const startingQuery = new URLSearchParams(window.location.search).get("q") || "";
    if (startingQuery) runAnalysis(startingQuery);
  }, []);

  const risk = analysis?.risk || {};
  const token = analysis?.token || {};
  const onChain = analysis?.onChain || {};
  const base = token.baseToken || {};
  const score = Number(risk.score || 0);
  const scoreDegrees = Math.round((score / 100) * 360);

  return (
    <main className="app-shell">
      <HistorySidebar history={history} onSelect={(q) => { setQuery(q); runAnalysis(q); }} />
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">ChainWatch AI</p>
            <h1>Crypto fraud intelligence console</h1>
          </div>
          <div className="status-pill">
            <span />
            Live Intel
          </div>
        </header>

        <form
          className="search-panel"
          onSubmit={(event) => {
            event.preventDefault();
            runAnalysis();
          }}
        >
          <div className="search-copy">
            <label htmlFor="query">Investigate token or wallet</label>
            <p>Search a contract address, pair address, wallet, or token symbol.</p>
          </div>
          <div className="search-row">
            <div className="input-wrap">
              <Search size={18} />
              <input
                id="query"
                name="query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Try: PEPE, WETH, or a token address"
                autoComplete="off"
              />
            </div>
            <button type="submit" disabled={loading}>
              <Radar size={18} />
              {loading ? "Scanning" : "Analyze"}
            </button>
          </div>
        </form>

        {alert ? <section className="alert">{alert}</section> : null}

        <section className="dashboard">
          <article className="risk-panel">
            <div className="panel-title">
              <p>
                <ShieldAlert size={17} />
                Risk Score
              </p>
              <span>
                {risk.level || "Awaiting scan"}
                {risk.verdict && (
                  <span
                    style={{
                      marginLeft: "8px",
                      padding: "2px 10px",
                      borderRadius: "99px",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      letterSpacing: "0.04em",
                      background:
                        risk.verdict === "Buy" ? "rgba(79,224,181,0.18)" :
                        risk.verdict === "Caution" ? "rgba(255,183,77,0.18)" :
                        "rgba(255,94,104,0.18)",
                      color:
                        risk.verdict === "Buy" ? "#4fe0b5" :
                        risk.verdict === "Caution" ? "#ffb74d" :
                        "#ff5e68",
                      border:
                        risk.verdict === "Buy" ? "1px solid rgba(79,224,181,0.4)" :
                        risk.verdict === "Caution" ? "1px solid rgba(255,183,77,0.4)" :
                        "1px solid rgba(255,94,104,0.4)",
                    }}
                  >
                    {risk.verdictEmoji} {risk.verdict}
                  </span>
                )}
              </span>
            </div>
            <div
              className="score-ring"
              style={{
                background: `conic-gradient(${scoreColor(score)} ${scoreDegrees}deg, #1b2630 ${scoreDegrees}deg)`,
              }}
            >
              <strong>{Number.isFinite(score) && analysis ? score : "--"}</strong>
              <small>/100</small>
            </div>
            {risk.verdictReason && (
              <div
                style={{
                  margin: "10px 0 6px",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  fontSize: "0.8rem",
                  lineHeight: 1.55,
                  background:
                    risk.verdict === "Buy" ? "rgba(79,224,181,0.07)" :
                    risk.verdict === "Caution" ? "rgba(255,183,77,0.07)" :
                    "rgba(255,94,104,0.07)",
                  borderLeft:
                    risk.verdict === "Buy" ? "3px solid #4fe0b5" :
                    risk.verdict === "Caution" ? "3px solid #ffb74d" :
                    "3px solid #ff5e68",
                  color: "var(--text-muted)",
                }}
              >
                {risk.verdictReason}
              </div>
            )}
            <p className="explanation">
              {analysis?.explanation || "Enter a token or wallet to generate the first ChainWatch intelligence brief."}
            </p>
          </article>

          <article className="intel-panel">
            <div className="panel-title">
              <p>
                <Network size={17} />
                Investigation Graph
              </p>
              <span>{onChain.available ? "Ethereum live" : loading ? "Scanning..." : "No data"}</span>
            </div>
            {loading ? (
              <div className="graph graph-empty">
                <div className="graph-message">
                  <div className="graph-loading">
                    <span /><span /><span />
                  </div>
                  <p>Fetching on-chain data…</p>
                </div>
              </div>
            ) : (
              <InvestigationGraph graph={onChain.graph} />
            )}
          </article>

          <article className="token-panel">
            <div className="panel-title">
              <p>
                <CircleDollarSign size={17} />
                Token Snapshot
              </p>
              <span>{analysis?.source || "No source"}</span>
            </div>
            <dl className="stats">
              <Stat label="Name" value={base.name ? `${base.name} (${base.symbol || "--"})` : "--"} />
              <Stat label="Chain" value={token.chainId || "--"} />
              <Stat label="DEX" value={token.dexId || "--"} />
              <Stat label="Price" value={token.priceUsd ? `$${token.priceUsd}` : "--"} />
              <Stat label="Market Cap" value={formatMoney(token.marketCap)} />
              <Stat label="FDV" value={formatMoney(token.fdv)} />
              <Stat label="Liquidity" value={formatMoney(token.liquidity?.usd)} />
              <Stat label="24h Volume" value={formatMoney(token.volume?.h24)} />
              <Stat label="Txns 24h" value={
                (token.txns?.h24)
                  ? `${(token.txns.h24.buys || 0) + (token.txns.h24.sells || 0)} (${token.txns.h24.buys || 0}B / ${token.txns.h24.sells || 0}S)`
                  : "--"
              } />
              <Stat label="Token Age" value={risk.signals?.ageLabel || (token.pairCreatedAt ? formatAge(token.pairCreatedAt) : "--")} />
              <Stat label="Verdict" value={risk.verdict ? `${risk.verdictEmoji} ${risk.verdict}` : "--"} />
              <Stat label="Confidence" value={risk.confidence || "--"} />
            </dl>
            <PriceChangeBars priceChange={token.priceChange} />
          </article>
        </section>

        <section className="breakdown-panel">
          <div className="panel-title">
            <p>
              <BarChart3 size={17} />
              Risk Factor Breakdown
            </p>
            <span>Heuristics model</span>
          </div>
          <Breakdown categories={risk.categories || []} />
        </section>

        <section className="breakdown-panel">
          <div className="panel-title">
            <p>
              <ShieldCheck size={17} />
              Smart Contract Audit
            </p>
            <span>
              {analysis?.contractIntel?.isVerified
                ? "Etherscan verified · Solidity scan"
                : analysis?.contractIntel
                ? "Source unverified"
                : "Ethereum only"}
            </span>
          </div>
          <ContractAuditPanel contractIntel={analysis?.contractIntel} />
        </section>

        <section className="breakdown-panel">
          <div className="panel-title">
            <p>
              <Wallet size={17} />
              On-Chain Intelligence
            </p>
            <span>{onChain.coverage || "Explorer data unavailable"}</span>
          </div>
          <OnChainPanel onChain={onChain} />
        </section>

        <section className="details-grid">
          <SignalPanel
            icon={<AlertTriangle size={17} />}
            title="Red Flags"
            subtitle="Risk signals"
            items={risk.flags?.length ? risk.flags : (risk.reasons || ["No analysis yet."])}
          />
          {risk.rugSignals?.length > 0 && (
            <SignalPanel
              icon={<ShieldAlert size={17} />}
              title="Rug Pull Signals"
              subtitle="Critical"
              items={risk.rugSignals}
              danger
            />
          )}
          <MarketSignals signals={risk.signals || {}} />
          <SignalPanel
            icon={<DatabaseZap size={17} />}
            title="Data Gaps"
            subtitle="Not yet checked"
            items={risk.dataGaps || ["Run an analysis to see what still needs explorer/RPC data."]}
            muted
          />
          <RelatedPairs pairs={analysis?.relatedPairs || []} />
        </section>
      </section>
    </main>
  );
}

function formatAge(ms) {
  const diff = Date.now() - Number(ms);
  const days = Math.floor(diff / 86400000);
  if (days > 365) return `${Math.floor(days / 365)}y ${Math.floor((days % 365) / 30)}mo`;
  if (days > 30) return `${Math.floor(days / 30)}mo ${days % 30}d`;
  if (days > 0) return `${days}d`;
  const hrs = Math.floor(diff / 3600000);
  return hrs > 0 ? `${hrs}h` : "<1h";
}

function Stat({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function PriceChangeBars({ priceChange }) {
  if (!priceChange) return null;
  const periods = [
    { key: "m5", label: "5m" },
    { key: "h1", label: "1h" },
    { key: "h6", label: "6h" },
    { key: "h24", label: "24h" },
  ];
  const hasData = periods.some((p) => priceChange[p.key] != null);
  if (!hasData) return null;

  return (
    <div className="price-bars">
      <p className="price-bars-title">Price Change</p>
      <div className="price-bars-grid">
        {periods.map(({ key, label }) => {
          const val = Number(priceChange[key] ?? 0);
          const isPos = val >= 0;
          const pct = Math.min(100, Math.abs(val) * 2);
          return (
            <div key={key} className="price-bar-col">
              <div className="price-bar-track">
                <div
                  className={`price-bar-fill ${isPos ? "pos" : "neg"}`}
                  style={{ height: `${pct}%` }}
                />
              </div>
              <span className={`price-bar-val ${isPos ? "pos" : "neg"}`}>
                {isPos ? "+" : ""}{val.toFixed(2)}%
              </span>
              <span className="price-bar-label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HistorySidebar({ history, onSelect }) {
  if (!history.length) return null;
  return (
    <aside className="history-sidebar">
      <div className="history-header">
        <Clock size={14} />
        Recent Scans
      </div>
      <ul className="history-list">
        {history.map((item) => {
          const color = item.score >= 80 ? "var(--red)" : item.score >= 60 ? "var(--amber)" : "var(--accent)";
          return (
            <li key={item.id}>
              <button
                className="history-item"
                onClick={() => onSelect(item.query)}
                title={item.query}
              >
                <span
                  className="history-score"
                  style={{ background: color, color: item.score >= 60 ? "#07090d" : "#04100d" }}
                >
                  {item.score}
                </span>
                <span className="history-meta">
                  <strong>{item.symbol || item.name}</strong>
                  <small>{item.level}</small>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}


const EDGE_COLORS = {
  deploy: "rgba(255, 94, 104, 0.8)",
  "token-tx": "rgba(79, 224, 181, 0.8)",
  "native-tx": "rgba(97, 168, 255, 0.7)",
};

const NODE_FILL = {
  token: "#61a8ff",
  creator: "#ff5e68",
  counterparty: "#4fe0b5",
};

const NODE_TEXT_COLOR = {
  token: "#07111e",
  creator: "#fff",
  counterparty: "#04100d",
};

const LEGEND_ITEMS = [
  { color: "#61a8ff", label: "Token Contract" },
  { color: "#ff5e68", label: "Creator / Deployer" },
  { color: "#4fe0b5", label: "Counterparty" },
];

const EDGE_LEGEND = [
  { color: "rgba(255, 94, 104, 0.8)", label: "Deploy" },
  { color: "rgba(79, 224, 181, 0.8)", label: "Token Transfer" },
  { color: "rgba(97, 168, 255, 0.7)", label: "Native Tx" },
];

function InvestigationGraph({ graph }) {
  const [hoveredId, setHoveredId] = useState(null);

  if (!graph?.available || !graph.nodes?.length) {
    return (
      <div className="graph graph-empty">
        <div className="graph-message">
          {graph?.summary?.headline || "A deployer wallet graph will appear here for Ethereum tokens once explorer data is available."}
        </div>
      </div>
    );
  }

  // Use a fixed wide viewBox — always fills the panel regardless of aspect ratio
  const VW = 800;
  const VH = 400;
  const PAD = 60; // px padding inside viewBox

  // Map backend 0–100 coords → viewBox pixel space
  const mapX = (x) => PAD + (x / 100) * (VW - 2 * PAD);
  const mapY = (y) => PAD + (y / 100) * (VH - 2 * PAD);

  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));

  // Which node ids are connected to hovered node?
  const connectedIds = new Set();
  if (hoveredId) {
    connectedIds.add(hoveredId);
    graph.edges.forEach((e) => {
      if (e.source === hoveredId) connectedIds.add(e.target);
      if (e.target === hoveredId) connectedIds.add(e.source);
    });
  }

  const dimEdge = (edge) =>
    hoveredId && edge.source !== hoveredId && edge.target !== hoveredId;

  const dimNode = (node) =>
    hoveredId && !connectedIds.has(node.id);

  return (
    <div className="graph">
      <svg
        viewBox={`0 0 ${VW} ${VH}`}
        preserveAspectRatio="xMidYMid meet"
        className="graph-svg"
        aria-label="Wallet investigation network"
      >
        <defs>
          {Object.entries(EDGE_COLORS).map(([kind, color]) => (
            <marker
              key={kind}
              id={`arrow-${kind}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
            </marker>
          ))}
        </defs>

        {/* Edges */}
        {graph.edges.map((edge) => {
          const src = nodeMap.get(edge.source);
          const tgt = nodeMap.get(edge.target);
          if (!src || !tgt) return null;
          const color = EDGE_COLORS[edge.kind] || "rgba(145,163,173,0.5)";
          const x1 = mapX(src.x);
          const y1 = mapY(src.y);
          const x2 = mapX(tgt.x);
          const y2 = mapY(tgt.y);
          const dx = x2 - x1;
          const dy = y2 - y1;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const srcR = src.type === "token" ? 28 : 22;
          const tgtR = tgt.type === "token" ? 28 : 22;
          const sx = x1 + (dx / dist) * srcR;
          const sy = y1 + (dy / dist) * srcR;
          const ex = x2 - (dx / dist) * (tgtR + 4);
          const ey = y2 - (dy / dist) * (tgtR + 4);
          const faded = dimEdge(edge);
          return (
            <g key={`${edge.source}-${edge.target}-${edge.kind}`} opacity={faded ? 0.08 : 0.9} style={{ transition: "opacity 0.2s" }}>
              <line
                x1={sx} y1={sy} x2={ex} y2={ey}
                stroke={color}
                strokeWidth={hoveredId && !faded ? 2.5 : 1.5}
                markerEnd={`url(#arrow-${edge.kind})`}
              />
              {edge.count > 1 && (
                <text
                  x={(sx + ex) / 2}
                  y={(sy + ey) / 2 - 8}
                  fontSize="11"
                  fill={color}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontWeight="700"
                >
                  ×{edge.count}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {graph.nodes.map((node) => {
          const cx = mapX(node.x);
          const cy = mapY(node.y);
          const fill = NODE_FILL[node.type] || "#4fe0b5";
          const textColor = NODE_TEXT_COLOR[node.type] || "#04100d";
          const isToken = node.type === "token";
          const r = isToken ? 28 : 22;
          const faded = dimNode(node);
          const hovered = hoveredId === node.id;
          return (
            <g
              key={node.id}
              style={{ cursor: "pointer", transition: "opacity 0.2s" }}
              opacity={faded ? 0.15 : 1}
              onMouseEnter={() => setHoveredId(node.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              <title>{node.id}</title>
              {/* Glow ring on hover */}
              {hovered && (
                <circle
                  cx={cx} cy={cy} r={r + 8}
                  fill="none"
                  stroke={fill}
                  strokeWidth="2"
                  opacity="0.4"
                />
              )}
              <circle
                cx={cx} cy={cy} r={r}
                fill={fill}
                stroke={hovered ? "#fff" : "transparent"}
                strokeWidth="1.5"
              />
              <text
                x={cx} y={cy - (isToken ? 4 : 3)}
                fontSize={isToken ? "11" : "9"}
                fontWeight="800"
                fill={textColor}
                textAnchor="middle"
                dominantBaseline="middle"
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {node.label}
              </text>
              <text
                x={cx} y={cy + (isToken ? 9 : 8)}
                fontSize="7"
                fill={textColor}
                textAnchor="middle"
                dominantBaseline="middle"
                opacity="0.7"
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {node.type.toUpperCase()}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="graph-legend">
        <div className="graph-legend-group">
          {LEGEND_ITEMS.map((item) => (
            <div key={item.label} className="graph-legend-item">
              <span className="graph-legend-dot" style={{ background: item.color }} />
              {item.label}
            </div>
          ))}
        </div>
        <div className="graph-legend-group">
          {EDGE_LEGEND.map((item) => (
            <div key={item.label} className="graph-legend-item">
              <span className="graph-legend-line" style={{ background: item.color }} />
              {item.label}
            </div>
          ))}
        </div>
        {graph.summary?.createdAt && (
          <div className="graph-legend-item" style={{ marginLeft: "auto", color: "var(--muted)", fontSize: "11px" }}>
            Deployed {new Date(Number(graph.summary.createdAt) * 1000).toLocaleDateString()}
          </div>
        )}
      </div>
    </div>
  );
}


function Breakdown({ categories }) {
  if (!categories.length) {
    return (
      <div className="breakdown-grid">
        <div className="empty-state">Run an analysis to see category-level risk evidence.</div>
      </div>
    );
  }

  return (
    <div className="breakdown-grid">
      {categories.map((category) => {
        const percent = Math.min(100, Math.round((Number(category.points || 0) / Number(category.maxPoints || 1)) * 100));
        const barColor = percent >= 70 ? "var(--red)" : percent >= 40 ? "var(--amber)" : "var(--accent)";
        return (
          <article className="breakdown-card" key={category.name}>
            <div className="breakdown-head">
              <div>
                <span
                  style={{
                    color: percent >= 70 ? "var(--red)" : percent >= 40 ? "var(--amber)" : "var(--accent)",
                  }}
                >
                  {category.status || "Stable"}
                </span>
                <strong>
                  {category.icon ? `${category.icon} ` : ""}{category.name}
                </strong>
              </div>
              <b style={{ color: barColor }}>
                {category.points || 0}<small style={{ color: "var(--text-muted)", fontWeight: 400 }}>/{category.maxPoints || 0}</small>
              </b>
            </div>
            <div className="bar">
              <i style={{ width: `${percent}%`, background: barColor }} />
            </div>
            <ul>
              {(category.evidence || []).map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </article>
        );
      })}
    </div>
  );
}

function SignalPanel({ icon, title, subtitle, items, muted = false, danger = false }) {
  return (
    <article
      style={danger ? { border: "1px solid rgba(255,94,104,0.3)", borderRadius: "14px", padding: "4px" } : {}}
    >
      <div className="panel-title">
        <p style={danger ? { color: "var(--red)" } : {}}>
          {icon}
          {title}
        </p>
        <span style={danger ? { color: "var(--red)", opacity: 0.8 } : {}}>{subtitle}</span>
      </div>
      <ul className={`signal-list ${muted ? "muted-list" : ""} ${danger ? "danger-list" : ""}`}>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

function MarketSignals({ signals }) {
  return (
    <article>
      <div className="panel-title">
        <p>
          <Activity size={17} />
          Market Signals
        </p>
        <span>Live data</span>
      </div>
      <div className="signal-grid">
        {Object.entries(signals).length ? (
          Object.entries(signals).map(([key, value]) => (
            <div key={key}>
              <span>{labelize(key)}</span>
              <strong>{formatSignal(key, value)}</strong>
            </div>
          ))
        ) : (
          <div className="empty-card">No signals loaded.</div>
        )}
      </div>
    </article>
  );
}

function RelatedPairs({ pairs }) {
  return (
    <article>
      <div className="panel-title">
        <p>
          <ExternalLink size={17} />
          Related Pairs
        </p>
        <span>Top liquidity</span>
      </div>
      <div className="pairs-list">
        {pairs.length ? (
          pairs.map((pair) => {
            const base = pair.baseToken?.symbol || "TOKEN";
            const quote = pair.quoteToken?.symbol || "QUOTE";
            return (
              <div className="pair" key={pair.pairAddress || pair.url}>
                <span>
                  {pair.chainId || "--"} / {pair.dexId || "--"}
                </span>
                <strong>
                  {base}/{quote} · {formatMoney(pair.liquidity?.usd)}
                </strong>
                {pair.url ? (
                  <a href={pair.url} target="_blank" rel="noreferrer">
                    Open on DexScreener
                  </a>
                ) : null}
              </div>
            );
          })
        ) : (
          <div className="empty-card">No related pairs loaded.</div>
        )}
      </div>
    </article>
  );
}

function EtherscanLink({ href, children }) {
  if (!href || href === "--") return <strong>{children}</strong>;
  return (
    <strong>
      <a href={href} target="_blank" rel="noreferrer" className="etherscan-link">
        {children} ↗
      </a>
    </strong>
  );
}

function OnChainPanel({ onChain }) {
  if (!onChain?.available) {
    return <div className="empty-state">{onChain?.coverage || "Explorer intelligence is not available for this result."}</div>;
  }

  const creator = onChain.creatorAddress;
  const txHash = onChain.creationTxHash;
  const deployTs = onChain.deploymentTimestamp
    ? new Date(Number(onChain.deploymentTimestamp) * 1000).toLocaleString()
    : "--";

  const creatorHref = creator ? `https://etherscan.io/address/${creator}` : null;
  const txHref = txHash ? `https://etherscan.io/tx/${txHash}` : null;
  const shortCreator = creator ? `${creator.slice(0, 10)}...${creator.slice(-8)}` : "--";
  const shortTx = txHash ? `${txHash.slice(0, 10)}...${txHash.slice(-6)}` : "--";

  return (
    <div className="signal-grid">
      <div>
        <span>Creator Wallet</span>
        <EtherscanLink href={creatorHref}>{shortCreator}</EtherscanLink>
      </div>
      <div>
        <span>Creation Tx</span>
        <EtherscanLink href={txHref}>{shortTx}</EtherscanLink>
      </div>
      <div>
        <span>Deploy Timestamp</span>
        <strong>{deployTs}</strong>
      </div>
      <div>
        <span>Recent Creator Tx</span>
        <strong>{onChain.creatorRecentTxCount ?? "--"}</strong>
      </div>
      <div>
        <span>Failed Tx</span>
        <strong>{onChain.creatorRecentFailedTxCount ?? "--"}</strong>
      </div>
      <div>
        <span>Contract Deployments</span>
        <strong>{onChain.creatorRecentContractCreations ?? "--"}</strong>
      </div>
      <div>
        <span>Token Transfers</span>
        <strong>{onChain.creatorTokenTransferCount ?? "--"}</strong>
      </div>
      <div>
        <span>Creator Holdings</span>
        <strong style={{ color: onChain.creatorHoldingPercent > 20.0 ? "var(--red)" : onChain.creatorHoldingPercent > 5.0 ? "var(--amber)" : "var(--accent)" }}>
          {onChain.creatorHoldingPercent != null
            ? onChain.creatorHoldingPercent === 0
              ? "0%"
              : onChain.creatorHoldingPercent < 0.01
              ? "<0.01%"
              : `${onChain.creatorHoldingPercent.toFixed(2)}%`
            : "--"}
        </strong>
      </div>
      <div>
        <span>Burned Supply</span>
        <strong style={{ color: "var(--accent)" }}>
          {onChain.burnedPercent != null
            ? onChain.burnedPercent === 0
              ? "0%"
              : onChain.burnedPercent < 0.01
              ? "<0.01%"
              : `${onChain.burnedPercent.toFixed(2)}%`
            : "--"}
        </strong>
      </div>
    </div>
  );
}

function ContractAuditPanel({ contractIntel }) {
  if (!contractIntel) {
    return (
      <div className="empty-state">
        Smart contract source audit is not available for this result. Explorer intelligence currently runs only on Ethereum free-tier Etherscan contracts.
      </div>
    );
  }

  if (!contractIntel.isVerified) {
    return (
      <div className="empty-state" style={{ borderColor: "var(--red)", background: "rgba(255, 94, 104, 0.04)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--red)", fontWeight: 900, marginBottom: "6px" }}>
          <ShieldAlert size={18} />
          <span>Unverified Smart Contract Source</span>
        </div>
        This contract source code has not been verified on Etherscan. Critical checks for blacklist, minting, and owner privileges cannot be audited.
      </div>
    );
  }

  return (
    <div className="audit-layout">
      <div className="audit-meta">
        <div className="pair">
          <span>Contract Name</span>
          <strong>{contractIntel.contractName || "Unknown"}</strong>
        </div>
        <div className="pair">
          <span>License Type</span>
          <strong>{contractIntel.licenseType || "None"}</strong>
        </div>
        <div className="pair">
          <span>Owner Address</span>
          <strong title={contractIntel.owner} style={{ overflowWrap: "anywhere", fontSize: "13px" }}>
            {contractIntel.owner ? `${contractIntel.owner.slice(0, 14)}...${contractIntel.owner.slice(-10)}` : "None / Zero Address"}
          </strong>
        </div>
      </div>

      <div className="audit-grid">
        <div className={`audit-card-status ${contractIntel.ownershipRenounced ? "pass" : "warn"}`}>
          <div className="badge-icon">
            {contractIntel.ownershipRenounced ? (
              <ShieldCheck size={18} color="var(--accent)" />
            ) : (
              <AlertTriangle size={18} color="var(--amber)" />
            )}
          </div>
          <div>
            <strong>Ownership Status</strong>
            <p>
              {contractIntel.ownershipRenounced
                ? "Renounced (Zero Address). Admin privileges are disabled."
                : "Active Owner. Administrator can invoke privileged contract changes."}
            </p>
          </div>
        </div>

        <div className={`audit-card-status ${contractIntel.hasBlacklist ? "fail" : "pass"}`}>
          <div className="badge-icon">
            {contractIntel.hasBlacklist ? (
              <ShieldAlert size={18} color="var(--red)" />
            ) : (
              <ShieldCheck size={18} color="var(--accent)" />
            )}
          </div>
          <div>
            <strong>Blacklist Capability</strong>
            <p>
              {contractIntel.hasBlacklist
                ? "Blacklist functions detected. Wallets can be frozen (honeypot risk)."
                : "No blacklist or freeze functions were found in source code."}
            </p>
          </div>
        </div>

        <div className={`audit-card-status ${contractIntel.hasMint ? "fail" : "pass"}`}>
          <div className="badge-icon">
            {contractIntel.hasMint ? (
              <ShieldAlert size={18} color="var(--red)" />
            ) : (
              <ShieldCheck size={18} color="var(--accent)" />
            )}
          </div>
          <div>
            <strong>Minting Check</strong>
            <p>
              {contractIntel.hasMint
                ? "External minting functions found. Owner can dilute token supply."
                : "No external minting functions were found in contract code."}
            </p>
          </div>
        </div>

        <div className={`audit-card-status ${contractIntel.hasPause ? "warn" : "pass"}`}>
          <div className="badge-icon">
            {contractIntel.hasPause ? (
              <AlertTriangle size={18} color="var(--amber)" />
            ) : (
              <ShieldCheck size={18} color="var(--accent)" />
            )}
          </div>
          <div>
            <strong>Trading Pause</strong>
            <p>
              {contractIntel.hasPause
                ? "Pausable function detected. Owner can halt global trading."
                : "No pause or trading halt features were found in source."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
