import React, { useState, useEffect, useCallback } from 'react';
import { initializeApp } from 'firebase/app';
import { getFirestore, collection, getDocs, query, orderBy } from 'firebase/firestore';

// Firebase init via Vercel environment variables
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// --- HELPERS ---
// Returns milliseconds until next 4:15 PM IST weekday run
function msUntilNextScan() {
  const now = new Date();
  // IST = UTC+5:30
  const istOffset = 5.5 * 60 * 60 * 1000;
  const istNow = new Date(now.getTime() + istOffset - now.getTimezoneOffset() * 60000);
  const target = new Date(istNow);
  target.setHours(16, 15, 0, 0);
  // If past 4:15 PM today, aim for tomorrow
  if (istNow >= target) target.setDate(target.getDate() + 1);
  // Skip Saturday(6) and Sunday(0)
  while (target.getDay() === 0 || target.getDay() === 6) target.setDate(target.getDate() + 1);
  return target - istNow;
}

// Format milliseconds into "Xh Ym" string
function formatCountdown(ms) {
  if (ms <= 0) return 'Running soon...';
  const totalMin = Math.floor(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// Compute progress percentage of current price between SL and Target
function tradeProgress(entry, sl, target, exitPrice, status) {
  const ref = (status !== 'ACTIVE' && exitPrice != null) ? exitPrice : entry;
  const range = target - sl;
  if (range <= 0) return 0;
  return Math.min(100, Math.max(0, ((ref - sl) / range) * 100));
}

// --- MAIN COMPONENT ---
export default function Dashboard() {
  const [signals, setSignals]       = useState([]);
  const [stats, setStats]           = useState({ winRate: '–', totalPnl: '0.00', activeCount: 0, totalTrades: 0, bestWin: 0, worstLoss: 0 });
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab]               = useState('ALL');         // ALL | ACTIVE | CLOSED
  const [sortBy, setSortBy]         = useState('date');        // date | pnl | confidence
  const [filterConf, setFilterConf] = useState(0);            // min confidence 0–100
  const [expandedId, setExpandedId] = useState(null);         // expanded card id
  const [countdown, setCountdown]   = useState(msUntilNextScan());
  const [lastRefresh, setLastRefresh] = useState(new Date());

  // Countdown ticker — updates every 60 seconds
  useEffect(() => {
    const timer = setInterval(() => setCountdown(msUntilNextScan()), 60000);
    return () => clearInterval(timer);
  }, []);

  // Core data fetch — reusable for initial load and manual refresh
  const fetchData = useCallback(async () => {
    try {
      const q = query(collection(db, 'signals'), orderBy('date', 'desc'));
      const snapshot = await getDocs(q);
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setSignals(data);

      // Compute portfolio stats from closed trades only
      let wins = 0, losses = 0, active = 0, totalPnl = 0, bestWin = 0, worstLoss = 0;
      data.forEach(sig => {
        if (sig.status === 'ACTIVE') { active++; return; }
        if (sig.status === 'WIN') wins++;
        if (sig.status === 'LOSS' || sig.status === 'TIME_EXIT') losses++;
        if (sig.pnl_percentage != null) {
          totalPnl += sig.pnl_percentage;
          if (sig.pnl_percentage > bestWin) bestWin = sig.pnl_percentage;
          if (sig.pnl_percentage < worstLoss) worstLoss = sig.pnl_percentage;
        }
      });
      const closedTrades = wins + losses;
      setStats({
        winRate:     closedTrades > 0 ? ((wins / closedTrades) * 100).toFixed(1) : '–',
        totalPnl:    totalPnl.toFixed(2),
        activeCount: active,
        totalTrades: closedTrades,
        bestWin:     bestWin.toFixed(2),
        worstLoss:   worstLoss.toFixed(2)
      });
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Firestore fetch error:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchData().finally(() => setLoading(false));
  }, [fetchData]);

  // Manual refresh handler
  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  // --- FILTERING + SORTING PIPELINE ---
  const filtered = signals
    .filter(s => {
      if (tab === 'ACTIVE') return s.status === 'ACTIVE';
      if (tab === 'CLOSED') return s.status !== 'ACTIVE';
      return true;
    })
    .filter(s => (s.confidence ?? 0) >= filterConf)
    .sort((a, b) => {
      if (sortBy === 'pnl')        return (b.pnl_percentage ?? -999) - (a.pnl_percentage ?? -999);
      if (sortBy === 'confidence') return (b.confidence ?? 0) - (a.confidence ?? 0);
      return new Date(b.date) - new Date(a.date); // default: date desc
    });

  // Status badge color
  const statusColor = s => ({
    WIN: 'bg-green-500', LOSS: 'bg-red-500',
    ACTIVE: 'bg-blue-500', TIME_EXIT: 'bg-yellow-500'
  }[s] ?? 'bg-gray-500');

  // Loading screen
  if (loading) return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center gap-3">
      <div className="w-8 h-8 border-4 border-green-400 border-t-transparent rounded-full animate-spin" />
      <p className="text-gray-400 text-sm">Connecting to Firestore...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white font-sans max-w-lg mx-auto">

      {/* ── HEADER ── */}
      <div className="sticky top-0 bg-gray-900 border-b border-gray-800 px-4 pt-4 pb-2 z-10">
        <div className="flex justify-between items-start mb-1">
          <div>
            <h1 className="text-xl font-bold text-green-400">⚡ Quant Swing</h1>
            <p className="text-xs text-gray-500">ATR-Volume Demand Pullback · Nifty 200</p>
          </div>
          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 bg-gray-800 px-3 py-1.5 rounded-lg text-xs text-gray-300 active:bg-gray-700"
          >
            <span className={refreshing ? 'animate-spin' : ''}>↻</span>
            {refreshing ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {/* Next scan countdown */}
        <div className="flex justify-between items-center text-xs text-gray-600 mb-2">
          <span>Next scan: <span className="text-green-500 font-semibold">{formatCountdown(countdown)}</span></span>
          <span>Updated: {lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>

      <div className="px-4 pt-3">

        {/* ── STATS ROW ── */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <StatCard label="Active Trades"   value={stats.activeCount}  color="text-blue-400" />
          <StatCard label={`Win Rate (${stats.totalTrades} closed)`} value={`${stats.winRate}%`} color="text-yellow-400" />
          <StatCard
            label="Total PnL"
            value={`${parseFloat(stats.totalPnl) >= 0 ? '+' : ''}${stats.totalPnl}%`}
            color={parseFloat(stats.totalPnl) >= 0 ? 'text-green-400' : 'text-red-400'}
          />
          <StatCard label="Best Win" value={`+${stats.bestWin}%`} color="text-green-400" />
        </div>

        {/* ── TABS ── */}
        <div className="flex gap-1 mb-3 bg-gray-800 rounded-lg p-1">
          {['ALL', 'ACTIVE', 'CLOSED'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                tab === t ? 'bg-green-500 text-black' : 'text-gray-400 hover:text-white'
              }`}
            >{t}</button>
          ))}
        </div>

        {/* ── SORT + FILTER ROW ── */}
        <div className="flex gap-2 mb-4">
          {/* Sort selector */}
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="flex-1 bg-gray-800 text-gray-300 text-xs px-2 py-2 rounded-lg border border-gray-700"
          >
            <option value="date">Sort: Latest First</option>
            <option value="pnl">Sort: Best PnL</option>
            <option value="confidence">Sort: Confidence</option>
          </select>

          {/* Min confidence filter */}
          <select
            value={filterConf}
            onChange={e => setFilterConf(Number(e.target.value))}
            className="flex-1 bg-gray-800 text-gray-300 text-xs px-2 py-2 rounded-lg border border-gray-700"
          >
            <option value={0}>All Confidence</option>
            <option value={65}>65+ Score</option>
            <option value={80}>80+ Score</option>
            <option value={95}>95+ Score</option>
          </select>
        </div>

        {/* ── SIGNAL CARDS ── */}
        <div className="space-y-3 pb-8">
          {filtered.map(sig => {
            const isExpanded = expandedId === sig.id;
            const riskPct = sig.entry > 0
              ? (((sig.entry - sig.stop_loss) / sig.entry) * 100).toFixed(2)
              : null;
            const progress = tradeProgress(sig.entry, sig.stop_loss, sig.target, sig.exit_price, sig.status);
            const progressColor = progress >= 66 ? 'bg-green-500' : progress >= 33 ? 'bg-yellow-500' : 'bg-red-500';

            return (
              <div
                key={sig.id}
                className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden"
              >
                {/* Card Header — always visible, tap to expand */}
                <div
                  className="p-4 cursor-pointer active:bg-gray-750"
                  onClick={() => setExpandedId(isExpanded ? null : sig.id)}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold">{sig.ticker?.replace('.NS', '')}</span>
                      <span className="text-xs text-gray-500">{sig.date}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 text-xs rounded-full font-semibold ${statusColor(sig.status)}`}>
                        {sig.status}
                      </span>
                      <span className="text-gray-500 text-xs">{isExpanded ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* Progress bar — Entry to Target */}
                  <div className="mt-3 mb-1">
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>SL ₹{sig.stop_loss?.toFixed(0)}</span>
                      <span>Entry ₹{sig.entry?.toFixed(0)}</span>
                      <span>T ₹{sig.target?.toFixed(0)}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${progressColor}`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>

                  {/* PnL for closed trades — visible without expanding */}
                  {sig.status !== 'ACTIVE' && sig.pnl_percentage != null && (
                    <div className="mt-2 flex justify-between text-sm">
                      <span className="text-gray-400 text-xs">Exit ₹{sig.exit_price?.toFixed(2)}</span>
                      <span className={`font-bold text-sm ${sig.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {sig.pnl_percentage > 0 ? '+' : ''}{sig.pnl_percentage?.toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>

                {/* Expanded Details — only shown when card is tapped */}
                {isExpanded && (
                  <div className="border-t border-gray-700 px-4 py-3 bg-gray-850 space-y-3">

                    {/* Full price grid */}
                    <div className="grid grid-cols-3 gap-3">
                      <PriceCell label="Entry"     value={sig.entry} />
                      <PriceCell label="Stop Loss" value={sig.stop_loss} className="text-red-400" />
                      <PriceCell label="Target"    value={sig.target}    className="text-green-400" />
                    </div>

                    {/* Risk metrics row */}
                    <div className="grid grid-cols-3 gap-3">
                      <MetricCell label="Risk %"     value={riskPct ? `${riskPct}%` : '–'} color="text-orange-400" />
                      <MetricCell label="RRR"         value={sig.rrr ?? '1:2'}             color="text-blue-400" />
                      <MetricCell label="ATR"         value={sig.atr ? `₹${sig.atr}` : '–'} color="text-gray-300" />
                    </div>

                    {/* Confidence score with visual bar */}
                    {sig.confidence && (
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-500">Confidence Score</span>
                          <span className="text-purple-400 font-bold">{sig.confidence}/100</span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-1.5">
                          <div
                            className="h-1.5 rounded-full bg-purple-500"
                            style={{ width: `${sig.confidence}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Position sizing helper */}
                    {riskPct && (
                      <div className="bg-gray-900 rounded-lg p-2 text-xs text-gray-400">
                        <span className="text-gray-300 font-semibold">📐 Position Sizing: </span>
                        Risk is <span className="text-orange-400">{riskPct}%</span> of entry.
                        For ₹1L capital at 1% risk → buy{' '}
                        <span className="text-white font-bold">
                          {sig.entry > 0 ? Math.floor(1000 / (sig.entry - sig.stop_loss)) : '–'}
                        </span>{' '}shares.
                      </div>
                    )}

                    <p className="text-xs text-gray-600">Created: {sig.created_at?.slice(0, 16).replace('T', ' ')} IST</p>
                  </div>
                )}
              </div>
            );
          })}

          {/* Empty state with next scan time */}
          {filtered.length === 0 && (
            <div className="text-center py-12">
              <p className="text-4xl mb-3">📊</p>
              <p className="text-gray-400 font-semibold mb-1">
                {tab === 'ACTIVE' ? 'No active trades right now' :
                 tab === 'CLOSED' ? 'No closed trades yet' :
                 'No signals yet'}
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

// Reusable stat card
const StatCard = ({ label, value, color }) => (
  <div className="bg-gray-800 p-3 rounded-lg text-center">
    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);

// Price cell in expanded card
const PriceCell = ({ label, value, className = 'text-white' }) => (
  <div>
    <p className="text-gray-500 text-xs">{label}</p>
    <p className={`font-bold text-sm ${className}`}>₹{value?.toFixed(2)}</p>
  </div>
);

// Metric cell in expanded card
const MetricCell = ({ label, value, color = 'text-white' }) => (
  <div>
    <p className="text-gray-500 text-xs">{label}</p>
    <p className={`font-bold text-sm ${color}`}>{value}</p>
  </div>
);
