import { useState, useEffect, useCallback, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { getFirestore, collection, query, orderBy, getDocs, doc, getDoc } from 'firebase/firestore';

// --- FIREBASE CONFIG ---
const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             import.meta.env.VITE_FIREBASE_APP_ID,
};
const app = initializeApp(firebaseConfig);
const db  = getFirestore(app);

// --- SECTOR COLORS ---
const SECTOR_COLORS = {
  Energy:          'bg-amber-900/40 text-amber-400 border-amber-700',
  IT:              'bg-blue-900/40 text-blue-400 border-blue-700',
  Banks:           'bg-emerald-900/40 text-emerald-400 border-emerald-700',
  Finance:         'bg-cyan-900/40 text-cyan-400 border-cyan-700',
  FMCG:            'bg-pink-900/40 text-pink-400 border-pink-700',
  Pharma:          'bg-violet-900/40 text-violet-400 border-violet-700',
  Healthcare:      'bg-rose-900/40 text-rose-400 border-rose-700',
  Auto:            'bg-orange-900/40 text-orange-400 border-orange-700',
  Infra:           'bg-teal-900/40 text-teal-400 border-teal-700',
  Metals:          'bg-slate-900/40 text-slate-400 border-slate-700',
  Paints:          'bg-indigo-900/40 text-indigo-400 border-indigo-700',
  Chemicals:       'bg-lime-900/40 text-lime-400 border-lime-700',
  Cement:          'bg-stone-900/40 text-stone-400 border-stone-700',
  Electricals:     'bg-yellow-900/40 text-yellow-400 border-yellow-700',
  Retail:          'bg-fuchsia-900/40 text-fuchsia-400 border-fuchsia-700',
  'Consumer Tech': 'bg-sky-900/40 text-sky-400 border-sky-700',
  Realty:          'bg-purple-900/40 text-purple-400 border-purple-700',
  Media:           'bg-red-900/40 text-red-400 border-red-700',
  Textiles:        'bg-green-900/40 text-green-400 border-green-700',
  'Building Mat':  'bg-zinc-900/40 text-zinc-400 border-zinc-700',
  Consumer:        'bg-gray-900/40 text-gray-400 border-gray-700',
  Telecom:         'bg-cyan-900/40 text-cyan-400 border-cyan-700',
  Other:           'bg-gray-800 text-gray-400 border-gray-600',
};

// --- COUNTDOWN HELPERS ---
function msUntilNextScan() {
  const now = new Date();
  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const next = new Date(ist);
  next.setHours(20, 0, 0, 0);
  if (next <= ist) next.setDate(next.getDate() + 1);
  while (next.getDay() === 0 || next.getDay() === 6) next.setDate(next.getDate() + 1);
  return next - ist;
}

function msUntilFriday() {
  const now = new Date();
  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const next = new Date(ist);
  const daysUntilFriday = (5 - next.getDay() + 7) % 7;
  next.setDate(next.getDate() + (daysUntilFriday === 0 ? 7 : daysUntilFriday));
  next.setHours(18, 0, 0, 0);
  return next - ist;
}

function formatCountdown(ms) {
  if (ms <= 0) return 'Running soon...';
  const d = Math.floor(ms / 86400000);
  const h = Math.floor((ms % 86400000) / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  if (m >= 5) return `${m}m`;
  return `${m}m ${s}s`;
}

function tradeProgress(entry, sl, target, exitPrice, status) {
  if (!entry || !sl || !target) return 0;
  const range = target - sl;
  if (range <= 0) return 0;
  const ref = (status !== 'ACTIVE' && exitPrice != null) ? exitPrice : entry;
  return Math.min(100, Math.max(0, ((ref - sl) / range) * 100));
}

function toTVSymbol(ticker) {
  return 'NSE:' + (ticker?.replace('.NS', '') ?? ticker);
}

// --- TRADINGVIEW MINI CHART ---
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
      symbol: tvSymbol, width: '100%', height: 200, locale: 'en',
      dateRange: '3M', colorTheme: 'dark', trendLineColor: '#22c55e',
      underLineColor: 'rgba(34,197,94,0.1)', underLineTopColor: 'rgba(34,197,94,0.4)',
      isTransparent: true, autosize: true,
      largeChartUrl: `https://www.tradingview.com/chart/?symbol=${tvSymbol}`,
    });
    container.appendChild(script);
    return () => { container.innerHTML = ''; };
  }, [tvSymbol]);
  return (
    <div ref={containerRef}
      className="w-full rounded-lg overflow-hidden mt-1 bg-gray-950 border border-gray-800"
      style={{ minHeight: 200 }} />
  );
}

// ══════════════════════════════════════════════════════════════════════
// ROOT APP — TWO SEPARATE STRATEGY TABS
// ══════════════════════════════════════════════════════════════════════
export default function App() {
  const [activeStrategy, setActiveStrategy] = useState('ATR');

  // --- ATR-VOLUME STATE ---
  const [atrSignals, setAtrSignals]     = useState([]);
  const [atrStats, setAtrStats]         = useState({ winRate: '–', totalPnl: '0.00', activeCount: 0, totalTrades: 0, profitFactor: '–' });
  const [atrRegime, setAtrRegime]       = useState({ regime: 'LOADING', nifty_close: 0, nifty_ema50: 0 });
  const [atrTab, setAtrTab]             = useState('ALL');
  const [atrSortBy, setAtrSortBy]       = useState('date');
  const [atrFilterConf, setAtrFilterConf] = useState(0);
  const [atrSectorFilter, setAtrSectorFilter] = useState('ALL');
  const [atrExpandedId, setAtrExpandedId]     = useState(null);
  const [atrCountdown, setAtrCountdown] = useState(msUntilNextScan());

  // --- SMA200 STATE ---
  const [smaPositions, setSmaPositions]       = useState([]);
  const [smaStats, setSmaStats]               = useState({ activeCount: 0, closedCount: 0, totalPnl: '0.00', winRate: '–', avgHolding: '–' });
  const [smaMarketStatus, setSmaMarketStatus] = useState({ stocks_above_sma200: 0, stocks_below_sma200: 0, stocks_filtered_out: 0, target_positions: 0 });
  const [smaTab, setSmaTab]                   = useState('ACTIVE');
  const [smaSectorFilter, setSmaSectorFilter] = useState('ALL');
  const [smaExpandedId, setSmaExpandedId]     = useState(null);
  const [smaCountdown, setSmaCountdown]       = useState(msUntilFriday());

  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  // Countdown tickers
  useEffect(() => {
    let t;
    const tick = () => { setAtrCountdown(msUntilNextScan()); t = setTimeout(tick, 60000); };
    tick(); return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    let t;
    const tick = () => { setSmaCountdown(msUntilFriday()); t = setTimeout(tick, 60000); };
    tick(); return () => clearTimeout(t);
  }, []);

  const fetchData = useCallback(async () => {
    try {
      // ATR signals
      const atrSnap = await getDocs(query(collection(db, 'signals'), orderBy('date', 'desc')));
      const atrData = atrSnap.docs.map(d => ({ id: d.id, ...d.data() }));
      setAtrSignals(atrData);

      const regSnap = await getDoc(doc(db, 'market_status', 'current'));
      if (regSnap.exists()) setAtrRegime(regSnap.data());

      let wins = 0, losses = 0, active = 0, pnl = 0, gW = 0, gL = 0;
      atrData.forEach(s => {
        if (s.status === 'ACTIVE') { active++; return; }
        const p = s.pnl_percentage ?? 0;
        if (s.status === 'WIN') { wins++; gW += p; }
        if (s.status === 'LOSS' || s.status === 'TIME_EXIT') { losses++; gL += Math.abs(p); }
        pnl += p;
      });
      const closed = wins + losses;
      setAtrStats({
        winRate:     closed > 0 ? ((wins / closed) * 100).toFixed(1) : '–',
        totalPnl:    pnl.toFixed(2),
        activeCount: active,
        totalTrades: closed,
        profitFactor: gL > 0 ? (gW / gL).toFixed(2) : wins > 0 ? '∞' : '–',
      });

      // SMA200 positions
      const smaSnap = await getDocs(query(collection(db, 'sma200_positions'), orderBy('entry_date', 'desc')));
      const smaData = smaSnap.docs.map(d => ({ id: d.id, ...d.data() }));
      setSmaPositions(smaData);

      const msSnap = await getDoc(doc(db, 'sma200_market_status', 'current'));
      if (msSnap.exists()) setSmaMarketStatus(msSnap.data());

      let sW = 0, sL = 0, sActive = 0, sPnl = 0, holdSum = 0, holdCnt = 0;
      smaData.forEach(p => {
        if (p.status === 'ACTIVE') { sActive++; return; }
        const v = p.pnl_percentage ?? p.net_pnl_pct ?? 0;
        if (v > 0) sW++; else sL++;
        sPnl += v;
        if (p.holding_days) { holdSum += p.holding_days; holdCnt++; }
      });
      const sClosed = sW + sL;
      setSmaStats({
        activeCount: sActive,
        closedCount: sClosed,
        totalPnl:    sPnl.toFixed(2),
        winRate:     sClosed > 0 ? ((sW / sClosed) * 100).toFixed(1) : '–',
        avgHolding:  holdCnt > 0 ? (holdSum / holdCnt).toFixed(0) + 'd' : '–',
      });

      setLastRefresh(new Date());
    } catch (e) {
      console.error('Firestore fetch error:', e);
    }
  }, []);

  useEffect(() => { fetchData().finally(() => setLoading(false)); }, [fetchData]);

  const handleRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  if (loading) return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm">Connecting to Firestore...</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-black text-white font-sans">

      {/* STICKY HEADER */}
      <header className="sticky top-0 z-50 bg-black/90 backdrop-blur border-b border-gray-800 px-4 py-3">
        <div className="max-w-2xl mx-auto">
          <div className="flex justify-between items-center mb-2">
            <div>
              <h1 className="text-lg font-bold tracking-tight">⚡ Quant Swing</h1>
              <p className="text-xs text-gray-500">Multi-Strategy Dashboard</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-600">{lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
              <button onClick={handleRefresh} disabled={refreshing}
                className="bg-gray-800 px-3 py-1.5 rounded-lg text-xs text-gray-300 active:bg-gray-700">
                <span className={refreshing ? 'animate-spin inline-block' : ''}>↻</span>
                {refreshing ? ' Loading' : ' Refresh'}
              </button>
            </div>
          </div>
          {/* Strategy Tabs */}
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
            <button onClick={() => setActiveStrategy('ATR')}
              className={`flex-1 py-2 text-xs font-bold rounded-md transition-colors ${
                activeStrategy === 'ATR' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}>
              📊 ATR-Volume
            </button>
            <button onClick={() => setActiveStrategy('SMA200')}
              className={`flex-1 py-2 text-xs font-bold rounded-md transition-colors ${
                activeStrategy === 'SMA200' ? 'bg-green-600 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}>
              📈 SMA 200 Trend
            </button>
          </div>
        </div>
      </header>

      {/* STRATEGY CONTENT */}
      <div className="max-w-2xl mx-auto px-4 pt-4 pb-8">
        {activeStrategy === 'ATR'    && <ATRTab signals={atrSignals} stats={atrStats} regime={atrRegime} tab={atrTab} setTab={setAtrTab} sortBy={atrSortBy} setSortBy={setAtrSortBy} filterConf={atrFilterConf} setFilterConf={setAtrFilterConf} sectorFilter={atrSectorFilter} setSectorFilter={setAtrSectorFilter} expandedId={atrExpandedId} setExpandedId={setAtrExpandedId} countdown={atrCountdown} />}
        {activeStrategy === 'SMA200' && <SMA200Tab positions={smaPositions} stats={smaStats} marketStatus={smaMarketStatus} tab={smaTab} setTab={setSmaTab} sectorFilter={smaSectorFilter} setSectorFilter={setSmaSectorFilter} expandedId={smaExpandedId} setExpandedId={setSmaExpandedId} countdown={smaCountdown} />}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// ATR-VOLUME TAB
// ══════════════════════════════════════════════════════════════════════
function ATRTab({ signals, stats, regime, tab, setTab, sortBy, setSortBy, filterConf, setFilterConf, sectorFilter, setSectorFilter, expandedId, setExpandedId, countdown }) {
  const regimeIsOn      = regime.regime === 'ON';
  const regimeIsUnknown = regime.regime === 'LOADING' || regime.regime === 'UNKNOWN';
  const regimeBanner    = regimeIsUnknown
    ? { bg: 'bg-gray-900 border-gray-700',       text: 'text-gray-400',  label: 'REGIME: AWAITING FIRST SCAN',               sub: 'Run scanner.py to activate' }
    : regimeIsOn
    ? { bg: 'bg-green-950/60 border-green-800',  text: 'text-green-400', label: '✅ REGIME ON — BULLISH',                       sub: `Nifty 50: ₹${regime.nifty_close?.toLocaleString('en-IN') ?? '–'} • Above 50 EMA (₹${regime.nifty_ema50?.toLocaleString('en-IN') ?? '–'})` }
    : { bg: 'bg-red-950/60 border-red-800',      text: 'text-red-400',   label: '⚠️ REGIME OFF — BEARISH (NO NEW ENTRIES)',     sub: `Nifty 50: ₹${regime.nifty_close?.toLocaleString('en-IN') ?? '–'} • Below 50 EMA (₹${regime.nifty_ema50?.toLocaleString('en-IN') ?? '–'})` };

  const sectors  = ['ALL', ...Array.from(new Set(signals.map(s => s.sector).filter(Boolean))).sort()];
  const filtered = signals
    .filter(s => tab === 'ALL' ? true : tab === 'ACTIVE' ? s.status === 'ACTIVE' : s.status !== 'ACTIVE')
    .filter(s => sectorFilter === 'ALL' ? true : (s.sector ?? 'Other') === sectorFilter)
    .filter(s => (s.confidence ?? 0) >= filterConf)
    .sort((a, b) => {
      if (sortBy === 'pnl')        return (b.pnl_percentage ?? -999) - (a.pnl_percentage ?? -999);
      if (sortBy === 'confidence') return (b.confidence ?? 0) - (a.confidence ?? 0);
      return new Date(b.date) - new Date(a.date);
    });

  const statusColor = s => ({ WIN: 'bg-green-600', LOSS: 'bg-red-600', ACTIVE: 'bg-blue-600', TIME_EXIT: 'bg-yellow-600' }[s] ?? 'bg-gray-600');

  return (
    <div className="space-y-4">
      {/* Regime */}
      <div className={`p-3 rounded-xl border ${regimeBanner.bg}`}>
        <p className={`font-bold text-sm text-center ${regimeBanner.text}`}>{regimeBanner.label}</p>
        <p className="text-xs text-gray-500 text-center mt-0.5">{regimeBanner.sub}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2">
        <StatCard label="Active"         value={stats.activeCount}  color="text-blue-400" />
        <StatCard label={`Win (${stats.totalTrades})`} value={`${stats.winRate}%`} color="text-yellow-400" />
        <StatCard label="Total PnL"      value={`${parseFloat(stats.totalPnl) >= 0 ? '+' : ''}${stats.totalPnl}%`} color={parseFloat(stats.totalPnl) >= 0 ? 'text-green-400' : 'text-red-400'} />
        <StatCard label="Profit Factor"  value={stats.profitFactor} color={parseFloat(stats.profitFactor) >= 1.5 ? 'text-green-400' : 'text-yellow-400'} />
      </div>

      {/* Countdown */}
      <p className="text-xs text-gray-600 text-center">Next daily scan: <span className="text-blue-400 font-semibold">{formatCountdown(countdown)}</span> • Weekdays 8 PM IST</p>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
        {['ALL', 'ACTIVE', 'CLOSED'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-md ${
              tab === t ? 'bg-blue-600 text-white' : 'text-gray-500'
            }`}>{t}</button>
        ))}
      </div>

      {/* Sector pills */}
      {sectors.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
          {sectors.map(sec => (
            <button key={sec} onClick={() => setSectorFilter(sec)}
              className={`flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-medium ${
                sectorFilter === sec ? 'bg-blue-600 text-white' : 'bg-gray-900 text-gray-400 border border-gray-700'
              }`}>{sec}</button>
          ))}
        </div>
      )}

      {/* Sort + filter */}
      <div className="flex gap-2">
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}
          className="flex-1 bg-gray-900 text-gray-300 text-xs px-2 py-1.5 rounded-lg border border-gray-700">
          <option value="date">Latest</option>
          <option value="pnl">Best PnL</option>
          <option value="confidence">Confidence</option>
        </select>
        <select value={filterConf} onChange={e => setFilterConf(Number(e.target.value))}
          className="flex-1 bg-gray-900 text-gray-300 text-xs px-2 py-1.5 rounded-lg border border-gray-700">
          <option value={0}>All Scores</option>
          <option value={65}>65+</option>
          <option value={80}>80+</option>
          <option value={95}>95+</option>
        </select>
      </div>

      {/* Cards */}
      <p className="text-xs text-gray-600 uppercase tracking-wider">
        {tab === 'ACTIVE' ? 'Active' : tab === 'CLOSED' ? 'History' : 'All'} ({filtered.length})
      </p>
      <div className="space-y-2">
        {filtered.map(sig => {
          const isExp     = expandedId === sig.id;
          const progress  = tradeProgress(sig.entry, sig.stop_loss, sig.target, sig.exit_price, sig.status);
          const progColor = progress >= 66 ? 'bg-green-500' : progress >= 33 ? 'bg-yellow-500' : 'bg-red-500';
          const sc        = SECTOR_COLORS[sig.sector] ?? SECTOR_COLORS.Other;
          const slDiff    = (sig.entry ?? 0) - (sig.stop_loss ?? 0);
          const posShares = slDiff > 0 ? Math.max(1, Math.floor(1000 / slDiff)) : null;
          const riskPct   = sig.entry > 0 ? (((sig.entry - sig.stop_loss) / sig.entry) * 100).toFixed(2) : null;
          return (
            <div key={sig.id} className="bg-gray-900 rounded-xl border border-gray-800">
              <div className="p-3 cursor-pointer" onClick={() => setExpandedId(isExp ? null : sig.id)}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold">{sig.ticker?.replace('.NS', '')}</span>
                      {sig.sector && <span className={`text-xs px-1.5 py-0.5 rounded border ${sc}`}>{sig.sector}</span>}
                    </div>
                    <span className="text-xs text-gray-600">{sig.date}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`px-2 py-0.5 text-xs rounded-full font-semibold ${statusColor(sig.status)}`}>{sig.status}</span>
                    <span className="text-gray-600 text-xs">{isExp ? '▴' : '▾'}</span>
                  </div>
                </div>
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span>SL ₹{sig.stop_loss?.toFixed(0) ?? '–'}</span>
                  <span>Entry ₹{sig.entry?.toFixed(0) ?? '–'}</span>
                  <span>T ₹{sig.target?.toFixed(0) ?? '–'}</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-1.5">
                  <div className={`h-1.5 rounded-full ${progColor}`} style={{ width: `${progress}%` }} />
                </div>
                {sig.status !== 'ACTIVE' && sig.pnl_percentage != null && (
                  <div className="mt-1.5 flex justify-between text-xs">
                    <span className="text-gray-600">Exit ₹{sig.exit_price?.toFixed(2) ?? '–'}</span>
                    <span className={`font-bold ${sig.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {sig.pnl_percentage > 0 ? '+' : ''}{sig.pnl_percentage?.toFixed(2)}%
                    </span>
                  </div>
                )}
              </div>
              {isExp && (
                <div className="border-t border-gray-800 px-3 py-3 space-y-3">
                  <TradingViewChart ticker={sig.ticker} />
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <PriceCell label="Entry"     value={sig.entry?.toFixed(2)} />
                    <PriceCell label="Stop Loss" value={sig.stop_loss?.toFixed(2)} cls="text-red-400" />
                    <PriceCell label="Target"    value={sig.target?.toFixed(2)}    cls="text-green-400" />
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <MetricCell label="Risk %" value={riskPct ? `${riskPct}%` : '–'}           color="text-orange-400" />
                    <MetricCell label="RRR"     value={sig.rrr ?? '1:2'}                        color="text-blue-400" />
                    <MetricCell label="ATR"     value={sig.atr ? `₹${sig.atr}` : '–'}          color="text-gray-400" />
                  </div>
                  {sig.confidence && (
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-500">Confidence</span>
                        <span className="text-purple-400 font-bold">{sig.confidence}/100</span>
                      </div>
                      <div className="w-full bg-gray-800 rounded-full h-1">
                        <div className="h-1 rounded-full bg-purple-600" style={{ width: `${sig.confidence}%` }} />
                      </div>
                    </div>
                  )}
                  {posShares != null && riskPct && (
                    <p className="text-xs text-gray-500 bg-gray-950 rounded-lg p-2">
                      📐 <span className="text-gray-300">Position sizing:</span> Risk {riskPct}% → buy
                      <span className="text-white font-bold"> {posShares}</span> shares for ₹1L at 1% risk
                    </p>
                  )}
                  <p className="text-xs text-gray-700">Created: {sig.created_at?.slice(0, 16).replace('T', ' ')} IST</p>
                </div>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="text-center py-10">
            <p className="text-3xl mb-2">📊</p>
            <p className="text-gray-500 text-sm">{sectorFilter !== 'ALL' ? `No ${sectorFilter} signals` : tab === 'ACTIVE' ? 'No active trades' : 'No signals yet'}</p>
            <p className="text-gray-700 text-xs mt-1">Next scan: {formatCountdown(countdown)}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// SMA 200 TAB
// ══════════════════════════════════════════════════════════════════════
function SMA200Tab({ positions, stats, marketStatus, tab, setTab, sectorFilter, setSectorFilter, expandedId, setExpandedId, countdown }) {
  const above   = marketStatus?.stocks_above_sma200 ?? 0;
  const below   = marketStatus?.stocks_below_sma200 ?? 0;
  const filtered_out = marketStatus?.stocks_filtered_out ?? 0;
  const total   = above + below;
  const bullPct = total > 0 ? Math.round((above / total) * 100) : 0;

  const smaSectors = ['ALL', ...Array.from(new Set(positions.map(p => p.sector).filter(Boolean))).sort()];
  const filtered   = positions
    .filter(p => tab === 'ACTIVE' ? p.status === 'ACTIVE' : tab === 'CLOSED' ? p.status === 'CLOSED' : true)
    .filter(p => sectorFilter === 'ALL' ? true : (p.sector ?? 'Other') === sectorFilter);

  return (
    <div className="space-y-4">
      {/* Market Strength Banner */}
      <div className={`p-3 rounded-xl border ${
        bullPct >= 60 ? 'bg-green-950/60 border-green-800' :
        bullPct >= 40 ? 'bg-yellow-950/60 border-yellow-800' :
        total === 0   ? 'bg-gray-900 border-gray-700' :
        'bg-red-950/60 border-red-800'
      }`}>
        {total > 0 ? (
          <>
            <p className={`font-bold text-sm text-center ${
              bullPct >= 60 ? 'text-green-400' : bullPct >= 40 ? 'text-yellow-400' : 'text-red-400'
            }`}>📈 {above} / {total} Nifty 200 stocks above SMA 200 ({bullPct}%)</p>
            <p className="text-xs text-gray-500 text-center mt-0.5">
              Filtered out: {filtered_out} • Last scan: {marketStatus?.total_scan_date ?? '–'}
            </p>
          </>
        ) : (
          <p className="text-gray-400 text-sm text-center">Awaiting first Friday scan</p>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2">
        <StatCard label="Active"      value={stats.activeCount}  color="text-green-400" />
        <StatCard label={`Win Rate`}  value={`${stats.winRate}%`} color="text-yellow-400" />
        <StatCard label="Total PnL"   value={`${parseFloat(stats.totalPnl) >= 0 ? '+' : ''}${stats.totalPnl}%`} color={parseFloat(stats.totalPnl) >= 0 ? 'text-green-400' : 'text-red-400'} />
        <StatCard label="Avg Holding" value={stats.avgHolding}   color="text-blue-400" />
      </div>

      {/* Strategy info */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-xs text-gray-400 space-y-1">
        <p className="text-green-400 font-semibold">📋 Strategy Rules</p>
        <p>• UNIVERSE: Nifty 200 (Quality Filtered)</p>
        <p>• BUY: Close {'>'} SMA 200 + Pass all quality filters</p>
        <p>• SELL: Close {'<'} SMA 200 OR Fail quality filter</p>
        <p>• POSITION: Equal weight, max 15 positions</p>
        <p>• FREQUENCY: Weekly (Fridays 6 PM IST)</p>
        <p className="text-green-500">• Expected CAGR: ~10% | Max Drawdown: ~40%</p>
        <p className="text-gray-600 mt-1">🔧 Quality filters remove: micro-caps, illiquid stocks, gap-prone, circuit-limit candidates</p>
      </div>

      {/* Countdown */}
      <p className="text-xs text-gray-600 text-center">Next weekly scan: <span className="text-green-400 font-semibold">{formatCountdown(countdown)}</span> • Fridays 6 PM IST</p>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
        {['ACTIVE', 'CLOSED'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-md ${
              tab === t ? 'bg-green-600 text-white' : 'text-gray-500'
            }`}>{t}</button>
        ))}
      </div>

      {/* Sector pills */}
      {smaSectors.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
          {smaSectors.map(sec => (
            <button key={sec} onClick={() => setSectorFilter(sec)}
              className={`flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-medium ${
                sectorFilter === sec ? 'bg-green-600 text-white' : 'bg-gray-900 text-gray-400 border border-gray-700'
              }`}>{sec}</button>
          ))}
        </div>
      )}

      {/* Position Cards */}
      <p className="text-xs text-gray-600 uppercase tracking-wider">
        {tab === 'ACTIVE' ? 'Active Positions' : 'Closed Positions'} ({filtered.length})
      </p>
      <div className="space-y-2">
        {filtered.map(pos => {
          const isExp     = expandedId === pos.id;
          const sc        = SECTOR_COLORS[pos.sector] ?? SECTOR_COLORS.Other;
          const isWin     = (pos.pnl_percentage ?? 0) >= 0;
          const pnlVal    = pos.status === 'ACTIVE' ? (pos.unrealized_pct ?? 0) : (pos.pnl_percentage ?? 0);
          const m         = pos.quality_metrics ?? {};
          return (
            <div key={pos.id} className="bg-gray-900 rounded-xl border border-gray-800">
              <div className="p-3 cursor-pointer" onClick={() => setExpandedId(isExp ? null : pos.id)}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold">{pos.ticker?.replace('.NS', '')}</span>
                      {pos.sector && <span className={`text-xs px-1.5 py-0.5 rounded border ${sc}`}>{pos.sector}</span>}
                    </div>
                    <span className="text-xs text-gray-600">{pos.entry_date}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`font-bold text-sm ${ pnlVal >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pnlVal >= 0 ? '+' : ''}{pnlVal.toFixed(2)}%
                    </span>
                    <span className={`px-2 py-0.5 text-xs rounded-full font-semibold ${
                      pos.status === 'ACTIVE' ? 'bg-green-700' : isWin ? 'bg-green-600' : 'bg-red-600'
                    }`}>{pos.status}</span>
                    <span className="text-gray-600 text-xs">{isExp ? '▴' : '▾'}</span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-gray-400">
                  <div><p className="text-gray-600">Entry</p><p className="font-medium">₹{pos.entry?.toFixed(2) ?? '–'}</p></div>
                  <div><p className="text-gray-600">SMA 200</p><p className="font-medium text-blue-400">₹{pos.sma200_at_entry?.toFixed(2) ?? '–'}</p></div>
                  <div><p className="text-gray-600">Distance</p><p className={`font-medium ${(pos.distance_from_sma200 ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{pos.distance_from_sma200 != null ? `${pos.distance_from_sma200 >= 0 ? '+' : ''}${pos.distance_from_sma200.toFixed(2)}%` : '–'}</p></div>
                </div>
              </div>
              {isExp && (
                <div className="border-t border-gray-800 px-3 py-3 space-y-3">
                  <TradingViewChart ticker={pos.ticker} />
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <MetricCell label="Shares"         value={pos.shares ?? '–'}                                                                                              color="text-white" />
                    <MetricCell label="Position Value" value={pos.position_value ? `₹${pos.position_value?.toLocaleString('en-IN')}` : '–'}                               color="text-white" />
                    <MetricCell label="Weight"         value={pos.weight_target_pct ? `${pos.weight_target_pct}%` : '–'}                                                    color="text-blue-400" />
                    <MetricCell label="Txn Costs"      value={pos.txn_costs != null ? `₹${pos.txn_costs?.toFixed(0)}` : '–'}                                               color="text-gray-400" />
                  </div>
                  {pos.status === 'CLOSED' && (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <MetricCell label="Exit Price"  value={pos.exit_price  ? `₹${pos.exit_price?.toFixed(2)}`  : '–'} color="text-white" />
                      <MetricCell label="Exit Reason" value={pos.exit_reason ?? '–'}                              color="text-orange-400" />
                      <MetricCell label="Net PnL"     value={pos.net_pnl_pct != null ? `${pos.net_pnl_pct >= 0 ? '+' : ''}${pos.net_pnl_pct?.toFixed(2)}%` : '–'} color={isWin ? 'text-green-400' : 'text-red-400'} />
                      <MetricCell label="Exit Date"   value={pos.exit_date ?? '–'}                                color="text-gray-400" />
                    </div>
                  )}
                  {Object.keys(m).length > 0 && (
                    <div className="bg-gray-950 rounded-lg p-2 text-xs text-gray-500 space-y-0.5">
                      <p className="text-gray-400 font-semibold mb-1">🔍 Quality Metrics (at entry)</p>
                      {m.price        != null && <p>Price: ₹{m.price}</p>}
                      {m.avg_volume   != null && <p>Avg Volume: {m.avg_volume?.toLocaleString('en-IN')}</p>}
                      {m.avg_gap_pct  != null && <p>Avg Gap: {m.avg_gap_pct}%</p>}
                      {m.atr_pct      != null && <p>ATR%: {m.atr_pct}%</p>}
                    </div>
                  )}
                  <p className="text-xs text-gray-700">Entry: {pos.created_at?.slice(0, 16).replace('T', ' ')} IST</p>
                </div>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="text-center py-10">
            <p className="text-3xl mb-2">📈</p>
            <p className="text-gray-500 text-sm">{tab === 'ACTIVE' ? 'No active positions' : 'No closed positions yet'}</p>
            <p className="text-gray-700 text-xs mt-1">Next scan: {formatCountdown(countdown)}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// SHARED UI
// ══════════════════════════════════════════════════════════════════════
const StatCard   = ({ label, value, color }) => (
  <div className="bg-gray-900 p-3 rounded-xl text-center border border-gray-800">
    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);
const PriceCell  = ({ label, value, cls = 'text-white' }) => (
  <div><p className="text-gray-600">{label}</p><p className={`font-semibold ${cls}`}>₹{value ?? '–'}</p></div>
);
const MetricCell = ({ label, value, color = 'text-white' }) => (
  <div><p className="text-gray-600">{label}</p><p className={`font-semibold ${color}`}>{value}</p></div>
);
