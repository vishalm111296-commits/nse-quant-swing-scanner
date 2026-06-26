import React, { useState, useEffect } from 'react';
import { initializeApp } from 'firebase/app';
import { getFirestore, collection, getDocs, query, orderBy } from 'firebase/firestore';

// Initialize Firebase using secure Vite environment variables
// Add these to Vercel Dashboard > Project Settings > Environment Variables
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

export default function Dashboard() {
  // State management for signals list and computed portfolio stats
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState({ winRate: '\u2013', totalPnl: '0.00', activeCount: 0, totalTrades: 0 });
  const [loading, setLoading] = useState(true);

  // Fetch all signals from Firestore on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const q = query(collection(db, 'signals'), orderBy('date', 'desc'));
        const snapshot = await getDocs(q);
        const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        setSignals(data);

        // Aggregate closed trade stats (exclude ACTIVE from PnL)
        let wins = 0, losses = 0, active = 0, totalPnl = 0;
        data.forEach(sig => {
          if (sig.status === 'ACTIVE') active++;
          else if (sig.status === 'WIN') { wins++; }
          else if (sig.status === 'LOSS' || sig.status === 'TIME_EXIT') { losses++; }

          // Only include pnl_percentage for closed (non-ACTIVE) trades
          if (sig.pnl_percentage != null && sig.status !== 'ACTIVE') {
            totalPnl += sig.pnl_percentage;
          }
        });

        const closedTrades = wins + losses;
        setStats({
          winRate: closedTrades > 0 ? ((wins / closedTrades) * 100).toFixed(1) : '\u2013',
          totalPnl: totalPnl.toFixed(2),
          activeCount: active,
          totalTrades: closedTrades
        });
      } catch (err) {
        console.error('Firestore fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Map trade status to Tailwind badge color class
  const statusColor = (status) => {
    switch (status) {
      case 'WIN':       return 'bg-green-500';
      case 'LOSS':      return 'bg-red-500';
      case 'ACTIVE':    return 'bg-blue-500';
      case 'TIME_EXIT': return 'bg-yellow-500';
      default:          return 'bg-gray-500';
    }
  };

  // Full-screen loading spinner while Firestore data loads
  if (loading) return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
      <p className="text-gray-400 animate-pulse">Loading signals...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 font-sans max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-1 text-center text-green-400">⚡ Quant Swing</h1>
      <p className="text-center text-gray-500 text-xs mb-4">ATR-Volume Demand Pullback — Nifty 200</p>

      {/* Portfolio Stats Header */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <StatCard label="Active" value={stats.activeCount} color="text-blue-400" />
        <StatCard label={`Win Rate (${stats.totalTrades})`} value={`${stats.winRate}%`} color="text-yellow-400" />
        <StatCard
          label="Total PnL"
          value={`${parseFloat(stats.totalPnl) >= 0 ? '+' : ''}${stats.totalPnl}%`}
          color={parseFloat(stats.totalPnl) >= 0 ? 'text-green-400' : 'text-red-400'}
        />
      </div>

      {/* Signal Cards List — ordered by date desc */}
      <div className="space-y-4">
        {signals.map((sig) => (
          <div key={sig.id} className="bg-gray-800 rounded-xl p-4 border border-gray-700">

            {/* Card Header: Ticker + Date + Status Badge */}
            <div className="flex justify-between items-center mb-3">
              <div>
                <span className="text-lg font-bold">{sig.ticker.replace('.NS', '')}</span>
                <span className="text-xs text-gray-500 ml-2">{sig.date}</span>
              </div>
              <span className={`px-2 py-1 text-xs rounded-full font-semibold ${statusColor(sig.status)}`}>
                {sig.status}
              </span>
            </div>

            {/* Price Grid: Entry / SL / Target */}
            <div className="grid grid-cols-3 gap-2 text-sm">
              <PriceCell label="Entry"     value={sig.entry} />
              <PriceCell label="Stop Loss" value={sig.stop_loss} className="text-red-400" />
              <PriceCell label="Target"    value={sig.target}    className="text-green-400" />
            </div>

            {/* Confidence Score and ATR (shown if available) */}
            {sig.confidence && (
              <div className="mt-2 text-xs text-gray-500">
                Confidence: <span className="text-purple-400 font-bold">{sig.confidence}/100</span>
                {sig.atr && <span className="ml-3">ATR: \u20b9{sig.atr}</span>}
              </div>
            )}

            {/* Exit Details — only shown for closed trades */}
            {sig.status !== 'ACTIVE' && sig.pnl_percentage != null && (
              <div className="mt-2 pt-2 border-t border-gray-700 flex justify-between text-sm">
                <span className="text-gray-400">Exit: \u20b9{sig.exit_price?.toFixed(2)}</span>
                <span className={`font-bold ${sig.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {sig.pnl_percentage > 0 ? '+' : ''}{sig.pnl_percentage?.toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        ))}

        {/* Empty state — shown before first scan runs */}
        {signals.length === 0 && (
          <p className="text-center text-gray-500 py-10">
            No signals yet. Scanner runs at 4:15 PM IST.
          </p>
        )}
      </div>
    </div>
  );
}

// Reusable summary stat card for header metrics
const StatCard = ({ label, value, color }) => (
  <div className="bg-gray-800 p-3 rounded-lg text-center">
    <p className="text-xs text-gray-400">{label}</p>
    <p className={`text-xl font-bold ${color}`}>{value}</p>
  </div>
);

// Reusable price cell for entry/sl/target grid
const PriceCell = ({ label, value, className = 'text-white' }) => (
  <div>
    <p className="text-gray-400 text-xs">{label}</p>
    <p className={`font-bold ${className}`}>\u20b9{value?.toFixed(2)}</p>
  </div>
);
