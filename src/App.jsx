import React, { useState, useEffect, useCallback, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { getFirestore, collection, getDocs, query, orderBy, doc, getDoc } from 'firebase/firestore';

const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             import.meta.env.VITE_FIREBASE_APP_ID
};
const app = initializeApp(firebaseConfig);
const db  = getFirestore(app);

// --- HELPERS ---
function msUntilNextScan() {
  const now = new Date();
  const istOffset = 5.5 * 60 * 60 * 1000;
  const istNow = new Date(now.getTime() + istOffset - now.getTimezoneOffset() * 60000);
  const target = new Date(istNow);
  target.setHours(16, 15, 0, 0);
  if (istNow >= target) target.setDate(target.getDate() + 1);
  while (target.getDay() === 0 || target.getDay() === 6) target.setDate(target.getDate() + 1);
  return target - istNow;
}
function formatCountdown(ms) {
  if (ms <= 0) return 'Running soon...';
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
function tradeProgress(entry, sl, target, exitPrice, status) {
  const ref   = (status !== 'ACTIVE' && exitPrice != null) ? exitPrice : entry;
  const range = target - sl;
  if (range <= 0) return 0;
  return Math.min(100, Math.max(0, ((ref - sl) / range) * 100));
}
function toTVSymbol(ticker) {
  return 'NSE:' + ticker.replace('.NS', '');
}

const SECTOR_COLORS = {
  'IT':           'bg-blue-900 text-blue-300',
  'Banks':        'bg-indigo-900 text-indigo-300',
  'Finance':      'bg-purple-900 text-purple-300',
  'Pharma':       'bg-green-900 text-green-300',
  'Healthcare':   'bg-teal-900 text-teal-300',
  'FMCG':         'bg-yellow-900 text-yellow-300',
  'Auto':         'bg-orange-900 text-orange-300',
  'Energy':       'bg-red-900 text-red-300',
  'Metals':       'bg-gray-700 text-gray-300',
  'Chemicals':    'bg-lime-900 text-lime-300',
  'Infra':        'bg-amber-900 text-amber-300',
  'Realty':       'bg-rose-900 text-rose-300',
  'Cement':       'bg-stone-700 text-stone-300',
  'Electricals':  'bg-cyan-900 text-cyan-300',
  'Retail':       'bg-pink-900 text-pink-300',
  'Media':        'bg-violet-900 text-violet-300',
  'Paints':       'bg-emerald-900 text-emerald-300',
  'Consumer Tech':'bg-sky-900 text-sky-300',
  'Textiles':     'bg-fuchsia-900 text-fuchsia-300',
  'Building Mat': 'bg-zinc-700 text-zinc-300',
  'Consumer':     'bg-orange-900 text-orange-200',
};

function TradingViewChart({ ticker }) {
  const containerRef = useRef(null);
  const tvSymbol     = toTVSymbol(ticker);
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.innerHTML = '';
    const script = document.createElement('script');
    script.src   = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbol: tvSymbol, width: '100%', height: 220, locale: 'en',
      dateRange: '1M', colorTheme: 'dark', trendLineColor: '#22c55e',
      underLineColor: 'rgba(34,197,94,0.1)', underLineTopColor: 'rgba(34,197,94,0.4)',
      isTransparent: true, autosize: true,
      largeChartUrl: `https://www.tradingview.com/chart/?symbol=${tvSymbol}`
    });
    container.appendChild(script);
    return () => { container.innerHTML = ''; };
  }, [tvSymbol]);
  return (
    <div ref={containerRef}
      className="w-full rounded-lg overflow-hidden mt-2 bg-gray-900 border border-gray-700"
      style={{ minHeight: 220 }} />
  );
}

// --- MAIN COMPONENT ---
export default function Dashboard() {
  const [allSignals, setAllSignals]     = useState([]);
  const [stats, setStats]               = useState({ winRate: '–', totalPnl: '0.00', activeCount: 0, totalTrades: 0, profitFactor: '–' });
  const [regime, setRegime]             = useState({ regime: 'LOADING', nifty_close: 0, nifty_ema50: 0 });
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [tab, setTab]                   = useState('ALL');
  const [sortBy, setSortBy]             = useState('date');
  const [filterConf, setFilterConf]     = useState(0);
  const [sectorFilter, setSectorFilter] = useState('ALL');
  const [expandedId, setExpandedId]     = useState(null);
  const [countdown, setCountdown]       = useState(msUntilNextScan());
  const [lastRefresh, setLastRefresh]   = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCountdown(msUntilNextScan()), 60000);
    return () => clearInterval(timer);
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const q        = query(collection(db, 'signals'), orderBy('date', 'desc'));
      const snapshot = await getDocs(q);
      const data     = snapshot.docs.map(d => ({ id: d.id, ...d.data() }));
      setAllSignals(data);

      const regimeSnap = await getDoc(doc(db, 'market_status', 'current'));
      if (regimeSnap.exists()) {
        setRegime(regimeSnap.data());
      } else {
        setRegime({ regime: 'UNKNOWN', nifty_close: 0, nifty_ema50: 0 });
      }

      let wins = 0, losses = 0, active = 0, totalPnl = 0, grossWins = 0, grossLosses = 0;
      data.forEach(sig => {
        if (sig.status === 'ACTIVE') { active++; return; }
        const pnl = sig.pnl_percentage ?? 0;
        if (sig.status === 'WIN')                                 { wins++;   grossWins   += pnl; }
        if (sig.status === 'LOSS' || sig.status === 'TIME_EXIT') { losses++; grossLosses += Math.abs(pnl); }
        totalPnl += pnl;
      });
      const closedTrades = wins + losses;
      const profitFactor = grossLosses > 0
        ? (grossWins / grossLosses).toFixed(2)
        : wins > 0 ? '∞' : '–';
      setStats({
        winRate:     closedTrades > 0 ? ((wins / closedTrades) * 100).toFixed(1) : '–',
        totalPnl:    totalPnl.toFixed(2),
        activeCount: active,
        totalTrades: closedTrades,
        profitFactor
      });
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Firestore fetch error:', err);
    }
  }, []);

  useEffect(() => {
    fetchData().finally(() => setLoading(false));
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const sectors  = ['ALL', ...Array.from(new Set(allSignals.map(s => s.sector).filter(Boolean))).sort()];
  const filtered = allSignals
    .filter(s => tab === 'ALL' ? true : tab === 'ACTIVE' ? s.status === 'ACTIVE' : s.status !== 'ACTIVE')
    .filter(s => sectorFilter === 'ALL' ? true : (s.sector ?? 'Other') === sectorFilter)
    .filter(s => (s.confidence ?? 0) >= filterConf)
    .sort((a, b) => {
      if (sortBy === 'pnl')        return (b.pnl_percentage ?? -999) - (a.pnl_percentage ?? -999);
      if (sortBy === 'confidence') return (b.confidence ?? 0) - (a.confidence ?? 0);
      return new Date(b.date) - new Date(a.date);
    });

  const statusColor = s => ({ WIN: 'bg-green-500', LOSS: 'bg-red-500', ACTIVE: 'bg-blue-500', TIME_EXIT: 'bg-yellow-500' }[s] ?? 'bg-gray-500');

  const regimeIsOn      = regime.regime === 'ON';
  const regimeIsUnknown = regime.regime === 'LOADING' || regime.regime === 'UNKNOWN';
  const regimeBanner    = regimeIsUnknown
    ? { bg: 'bg-gray-800 border-gray-600',     text: 'text-gray-400',  label: 'REGIME: AWAITING FIRST SCAN',              sub: 'Run the scanner once to activate' }
    : regimeIsOn
    ? { bg: 'bg-green-900/40 border-green-700', text: 'text-green-400', label: '✅ REGIME ON — BULLISH (SAFE TO TRADE)',     sub: `Nifty 50: ₹${regime.nifty_close?.toLocaleString('en-IN')} • Above 50 EMA (₹${regime.nifty_ema50?.toLocaleString('en-IN')})` }
    : { bg: 'bg-red-900/40 border-red-700',     text: 'text-red-400',   label: '⚠️ REGIME OFF — BEARISH (NO NEW ENTRIES)', sub: `Nifty 50: ₹${regime.nifty_close?.toLocaleString('en-IN')} • Below 50 EMA (₹${regime.nifty_ema50?.toLocaleString('en-IN')})` };

  if (loading) return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center gap-3">
      <div className="w-8 h-8 border-4 border-green-400 border-t-transparent rounded-full animate-spin" />
      <p className="text-gray-400 text-sm">Connecting to Firestore...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white font-sans max-w-lg mx-auto">

      {/* STICKY HEADER */}
      <div className="sticky top-0 bg-gray-900 border-b border-gray-800 px-4 pt-4 pb-2 z-10">
        <div className="flex justify-between items-start mb-1">
          <div>
            <h1 className="text-xl font-bold text-green-400">⚡ Quant Swing</h1>
            <p className="text-xs text-gray-500">ATR-Volume Demand Pullback · Nifty 200</p>
          </div>
          <button onClick={handleRefresh} disabled={refreshing}
            className="flex items-center gap-1 bg-gray-800 px-3 py-1.5 rounded-lg text-xs text-gray-300 active:bg-gray-700">
            <span className={refreshing ? 'animate-spin inline-block' : ''}>↻</span>
            {refreshing ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        <div className="flex justify-between text-xs text-gray-600">
          <span>Next scan: <span className="text-green-500 font-semibold">{formatCountdown(countdown)}</span></span>
          <span>Updated: {lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>

      <div className="px-4 pt-3">

        {/* MACRO REGIME BANNER */}
        <div className={`p-3 rounded-xl mb-4 border ${regimeBanner.bg}`}>
          <p className={`font-bold text-sm text-center ${regimeBanner.text}`}>{regimeBanner.label}</p>
          <p className="text-xs text-gray-500 text-center mt-0.5">{regimeBanner.sub}</p>
        </div>

        {/* PORTFOLIO STATS */}
        <div className="mb-3">
          <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">Portfolio Overview</p>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Active Trades" value={stats.activeCount} color="text-blue-400" />
            <StatCard label={`Win Rate (${stats.totalTrades})`} value={`${stats.winRate}%`} color="text-yellow-400" />
            <StatCard
              label="Total PnL"
              value={`${parseFloat(stats.totalPnl) >= 0 ? '+' : ''}${stats.totalPnl}%`}
              color={parseFloat(stats.totalPnl) >= 0 ? 'text-green-400' : 'text-red-400'}
            />
            <StatCard
              label="Profit Factor"
              value={stats.profitFactor}
              color={parseFloat(stats.profitFactor) >= 1.5 ? 'text-green-400' : parseFloat(stats.profitFactor) >= 1.0 ? 'text-yellow-400' : 'text-red-400'}
            />
          </div>
        </div>

        {/* TABS */}
        <div className="flex gap-1 mb-3 bg-gray-800 rounded-lg p-1">
          {['ALL', 'ACTIVE', 'CLOSED'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                tab === t ? 'bg-green-500 text-black' : 'text-gray-400'
              }`}>{t}</button>
          ))}
        </div>

        {/* SECTOR FILTER PILLS */}
        {sectors.length > 1 && (
          <div className="mb-3">
            <p className="text-xs text-gray-600 uppercase tracking-wider mb-1.5">Sector</p>
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
              {sectors.map(sec => (
                <button key={sec} onClick={() => setSectorFilter(sec)}
                  className={`flex-shrink-0 px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
                    sectorFilter === sec ? 'bg-green-500 text-black' : 'bg-gray-800 text-gray-400 border border-gray-700'
                  }`}>{sec}</button>
              ))}
            </div>
          </div>
        )}

        {/* SORT + FILTER */}
        <div className="flex gap-2 mb-4">
          <select value={sortBy} onChange={e => setSortBy(e.target.value)}
            className="flex-1 bg-gray-800 text-gray-300 text-xs px-2 py-2 rounded-lg border border-gray-700">
            <option value="date">Sort: Latest</option>
            <option value="pnl">Sort: Best PnL</option>
            <option value="confidence">Sort: Confidence</option>
          </select>
          <select value={filterConf} onChange={e => setFilterConf(Number(e.target.value))}
            className="flex-1 bg-gray-800 text-gray-300 text-xs px-2 py-2 rounded-lg border border-gray-700">
            <option value={0}>All Scores</option>
            <option value={65}>65+ Score</option>
            <option value={80}>80+ Score</option>
            <option value={95}>95+ Score</option>
          </select>
        </div>

        {/* SECTION LABEL */}
        <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">
          {tab === 'ACTIVE' ? 'Active Positions' : tab === 'CLOSED' ? 'Signal History' : 'All Signals'}
          <span className="ml-2 text-gray-700">({filtered.length})</span>
        </p>

        {/* SIGNAL CARDS */}
        <div className="space-y-3 pb-8">
          {filtered.map(sig => {
            const isExpanded  = expandedId === sig.id;
            const riskPct     = sig.entry > 0 ? (((sig.entry - sig.stop_loss) / sig.entry) * 100).toFixed(2) : null;
            const progress    = tradeProgress(sig.entry, sig.stop_loss, sig.target, sig.exit_price, sig.status);
            const progColor   = progress >= 66 ? 'bg-green-500' : progress >= 33 ? 'bg-yellow-500' : 'bg-red-500';
            const sectorColor = SECTOR_COLORS[sig.sector] ?? 'bg-gray-800 text-gray-400';
            return (
              <div key={sig.id} className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                <div className="p-4 cursor-pointer" onClick={() => setExpandedId(isExpanded ? null : sig.id)}>
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-base font-bold">{sig.ticker?.replace('.NS', '')}</span>
                        {sig.sector && (
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${sectorColor}`}>{sig.sector}</span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{sig.date}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 text-xs rounded-full font-semibold ${statusColor(sig.status)}`}>{sig.status}</span>
                      <span className="text-gray-600 text-xs">{isExpanded ? '▲' : '▼'}</span>
                    </div>
                  </div>
                  <div className="mb-1">
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>SL ₹{sig.stop_loss?.toFixed(0)}</span>
                      <span>Entry ₹{sig.entry?.toFixed(0)}</span>
                      <span>T ₹{sig.target?.toFixed(0)}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div className={`h-2 rounded-full transition-all ${progColor}`} style={{ width: `${progress}%` }} />
                    </div>
                  </div>
                  {sig.status !== 'ACTIVE' && sig.pnl_percentage != null && (
                    <div className="mt-2 flex justify-between text-sm">
                      <span className="text-gray-400 text-xs">Exit ₹{sig.exit_price?.toFixed(2)}</span>
                      <span className={`font-bold ${sig.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {sig.pnl_percentage > 0 ? '+' : ''}{sig.pnl_percentage?.toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
                {isExpanded && (
                  <div className="border-t border-gray-700 px-4 py-3 space-y-3">
                    <TradingViewChart ticker={sig.ticker} />
                    <div className="grid grid-cols-3 gap-3">
                      <PriceCell label="Entry"     value={sig.entry} />
                      <PriceCell label="Stop Loss" value={sig.stop_loss} className="text-red-400" />
                      <PriceCell label="Target"    value={sig.target}    className="text-green-400" />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <MetricCell label="Risk %" value={riskPct ? `${riskPct}%` : '–'} color="text-orange-400" />
                      <MetricCell label="RRR"     value={sig.rrr ?? '1:2'}             color="text-blue-400" />
                      <MetricCell label="ATR"     value={sig.atr ? `₹${sig.atr}` : '–'} color="text-gray-300" />
                    </div>
                    {sig.confidence && (
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-500">Confidence</span>
                          <span className="text-purple-400 font-bold">{sig.confidence}/100</span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-1.5">
                          <div className="h-1.5 rounded-full bg-purple-500" style={{ width: `${sig.confidence}%` }} />
                        </div>
                      </div>
                    )}
                    {riskPct && sig.entry > 0 && (
                      <div className="bg-gray-900 rounded-lg p-2 text-xs text-gray-400">
                        <span className="text-gray-300 font-semibold">📐 Position Sizing: </span>
                        Risk is <span className="text-orange-400">{riskPct}%</span> of entry.
                        For ₹1L at 1% risk → buy{' '}
                        <span className="text-white font-bold">
                          {Math.max(1, Math.floor(1000 / (sig.entry - sig.stop_loss)))}
                        </span>{' '}shares.
                      </div>
                    )}
                    <p className="text-xs text-gray-700">Created: {sig.created_at?.slice(0, 16).replace('T', ' ')} IST</p>
                  </div>
                )}
              </div>
            );
          })}

          {/* EMPTY STATE */}
          {filtered.length === 0 && (
            <div className="text-center py-12">
              <p className="text-4xl mb-3">📊</p>
              <p className="text-gray-400 font-semibold mb-1">
                {sectorFilter !== 'ALL' ? `No ${sectorFilter} signals` :
                 tab === 'ACTIVE' ? 'No active trades' :
                 tab === 'CLOSED' ? 'No closed trades yet' : 'No signals yet'}
              </p>
              <p className="text-gray-600 text-sm">Next scan in <span className="text-green-500">{formatCountdown(countdown)}</span></p>
              <p className="text-gray-700 text-xs mt-1">Weekdays at 4:15 PM IST</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const StatCard = ({ label, value, color }) => (
  <div className="bg-gray-800 p-3 rounded-lg text-center">
    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);
const PriceCell = ({ label, value, className = 'text-white' }) => (
  <div>
    <p className="text-gray-500 text-xs">{label}</p>
    <p className={`font-bold text-sm ${className}`}>₹{value?.toFixed(2)}</p>
  </div>
);
const MetricCell = ({ label, value, color = 'text-white' }) => (
  <div>
    <p className="text-gray-500 text-xs">{label}</p>
    <p className={`font-bold text-sm ${color}`}>{value}</p>
  </div>
);
