import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Cpu, 
  ShieldAlert, 
  Terminal, 
  Lock, 
  Unlock, 
  Box, 
  FileText, 
  RefreshCcw,
  Zap,
  Radio,
  Share2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const LogItem = ({ item }) => {
  const isTX = item.direction === "TX";
  const colorClass = item.service.includes("POSITIVE") ? "text-green-400" : 
                    item.service.includes("NEGATIVE") ? "text-red-400" :
                    isTX ? "text-cyan-400" : "text-blue-400";

  return (
    <motion.div 
      initial={{ opacity: 0, x: -10 }} 
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-3 p-2 border-b border-white/5 font-mono text-xs hover:bg-white/5 transition-colors"
    >
      <span className="text-gray-500 w-24">{item.timestamp}</span>
      <span className={`w-12 font-bold ${isTX ? 'text-cyan-500' : 'text-blue-500'}`}>{item.id}</span>
      <span className={`w-8 ${isTX ? 'bg-cyan-500/10 text-cyan-400' : 'bg-blue-500/10 text-blue-400'} px-1 rounded text-center`}>{item.direction}</span>
      <span className={`flex-grow ${colorClass} truncate`}>{item.service} ({item.sid})</span>
      <span className="text-gray-400 hidden lg:block tracking-widest">{item.data_hex}</span>
    </motion.div>
  );
};

export default function App() {
  const [traffic, setTraffic] = useState([]);
  const [status, setStatus] = useState({ status: "checking...", session: "-", security: "-", dtc_count: 0 });
  const [liveData, setLiveData] = useState({ voltage: 0, temperature: 0, speed: 0, torque: 0 });
  const [isLive, setIsLive] = useState(false);
  const logEndRef = useRef(null);
  
  // Connect WebSocket for Live Traffic
  useEffect(() => {
    let ws;
    const connect = () => {
      ws = new WebSocket(`ws://${window.location.host}/ws/traffic`);
      ws.onopen = () => setIsLive(true);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setTraffic(prev => [data, ...prev].slice(0, 100)); // Keep last 100
      };
      ws.onclose = () => {
        setIsLive(false);
        setTimeout(connect, 3000); // Retry logic
      };
    };
    connect();
    return () => ws?.close();
  }, []);

  // Poll for status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/ecu/status');
        const data = await res.json();
        setStatus(data);
      } catch (e) {
        setStatus(prev => ({ ...prev, status: "offline" }));
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  // Poll for live metrics
  useEffect(() => {
    const fetchLive = async () => {
      try {
        const res = await fetch('/api/ecu/live_data');
        const data = await res.json();
        setLiveData(data);
      } catch (e) {}
    };
    fetchLive();
    const interval = setInterval(fetchLive, 500); // 2Hz refresh for telemetry
    return () => clearInterval(interval);
  }, []);

  const triggerService = async (endpoint, body = {}) => {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      return await res.json();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden text-gray-200">
      
      {/* Sidebar - Control Hub */}
      <aside className="w-80 glass border-r border-white/10 p-6 flex flex-col gap-8 bg-slate-900/50">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/20 rounded-lg neon-glow">
            <Zap className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">INVERTER <span className="text-cyan-400">CORE</span></h1>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest">Active PWM Simulation</p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="space-y-4">
          <div className="glass p-3 rounded-xl border-white/5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">System Ready</span>
              <div className={`w-2 h-2 rounded-full ${isLive ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' : 'bg-red-500'}`} />
            </div>
            <div className="flex items-center gap-3">
              <Activity className="text-cyan-400 w-4" />
              <span className="text-xs font-mono uppercase tracking-widest">Transport: Bridge Connected</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="glass p-3 rounded-xl">
              <span className="text-[10px] text-gray-500 block mb-1">SESSION</span>
              <span className="text-sm font-bold text-cyan-400">{status.session}</span>
            </div>
            <div className="glass p-3 rounded-xl">
              <span className="text-[10px] text-gray-500 block mb-1">SECURITY</span>
              <span className="text-sm font-bold text-orange-400">{status.security}</span>
            </div>
          </div>
        </div>

        {/* Remote Control Buttons */}
        <div className="space-y-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Tester Control Panel</p>
          
          <button onClick={() => triggerService('/api/ecu/session', { session_type: 3 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
              <Terminal className="w-4 text-cyan-400 group-hover:scale-110 transition-transform" />
              <span className="text-sm">Extended Session</span>
            </div>
            <Zap className="w-3 text-gray-600" />
          </button>

          <button onClick={() => triggerService('/api/ecu/session', { session_type: 2 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
              <RefreshCcw className="w-4 text-purple-400 group-hover:rotate-180 transition-transform duration-500" />
              <span className="text-sm">Programming mode</span>
            </div>
            <Box className="w-3 text-gray-600" />
          </button>

          <button onClick={() => triggerService('/api/ecu/unlock')} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group border-l-2 border-orange-500/50">
            <div className="flex items-center gap-3">
              <Unlock className="w-4 text-orange-400" />
              <span className="text-sm">Unlock Level 01</span>
            </div>
            <ShieldAlert className="w-3 text-gray-600" />
          </button>

          <button onClick={() => triggerService('/api/ecu/reset', { reset_type: 1 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
              <RefreshCcw className="w-4 text-red-400" />
              <span className="text-sm">Hard Reset (0x11)</span>
            </div>
            <span className="text-[8px] text-gray-600 font-mono">0x01</span>
          </button>

          <button onClick={() => triggerService('/api/ecu/read_vin')} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
              <FileText className="w-4 text-green-400" />
              <span className="text-sm">Read VIN (0x22)</span>
            </div>
            <Share2 className="w-3 text-gray-600" />
          </button>

          <button onClick={() => triggerService('/api/ecu/memory_dump')} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
              <Activity className="w-4 text-yellow-400" />
              <span className="text-sm">Flash Dump (0x23)</span>
            </div>
            <span className="text-[8px] text-gray-600 font-mono">8b</span>
          </button>

          <button onClick={() => triggerService('/api/ecu/clear_dtcs')} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group hover:border-red-500/30">
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-4 text-red-500" />
              <span className="text-sm">Clear DTCs (0x14)</span>
            </div>
          </button>

          <button onClick={() => triggerService('/api/ecu/routine', { routine_id: 0x0202 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group border border-red-500/20">
            <div className="flex items-center gap-3">
              <Zap className="w-4 text-red-400 group-hover:scale-125 transition-transform" />
              <div className="flex flex-col items-start leading-tight">
                <span className="text-sm">DC Bus Discharge</span>
                <span className="text-[10px] text-gray-500 font-mono">RID 0x0202</span>
              </div>
            </div>
          </button>

          <button onClick={() => triggerService('/api/ecu/routine', { routine_id: 0x0208 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group">
            <div className="flex items-center gap-3">
              <RefreshCcw className="w-4 text-purple-400" />
              <span className="text-sm">Resolver Calibration</span>
            </div>
            <span className="text-[8px] text-gray-600 font-mono">0208</span>
          </button>

          <button onClick={() => triggerService('/api/ecu/routine', { routine_id: 0x0203 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/5 transition-all group border border-cyan-500/20">
            <div className="flex items-center gap-3">
              <Activity className="w-4 text-cyan-400 animate-pulse" />
              <span className="text-sm">Full System Self-Test</span>
            </div>
          </button>

          <button onClick={() => triggerService('/api/ecu/comm_control', { control_type: 0x03 })} className="w-full flex items-center justify-between p-3 glass rounded-xl hover:bg-white/20 transition-all group bg-red-950/20">
            <div className="flex items-center gap-3">
              <Radio className="w-4 text-gray-400" />
              <span className="text-sm text-gray-400">Kill COM (0x28)</span>
            </div>
          </button>
        </div>

        {/* Footer info */}
        <div className="mt-auto pt-6 border-t border-white/5 text-[10px] text-gray-500">
          <p>CAN PORT: /vcan0</p>
          <p>TX ID: 0x7E0 | RX ID: 0x7E8</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-grow flex flex-col bg-slate-950">
        
        {/* Inverter Metrics - Telemetry Hub */}
        <header className="h-24 border-b border-white/5 flex items-center px-8 gap-6 bg-slate-900/20">
          <div className="flex-1 grid grid-cols-4 gap-4">
             <div className="glass p-3 rounded-xl border-l border-cyan-500/30">
                <span className="text-[10px] text-gray-500 block mb-1 uppercase font-bold tracking-widest">Bus Voltage</span>
                <span className="text-lg font-mono text-cyan-400">{liveData.voltage} <span className="text-[10px] text-gray-600">V</span></span>
             </div>
             <div className="glass p-3 rounded-xl border-l border-orange-500/30">
                <span className="text-[10px] text-gray-500 block mb-1 uppercase font-bold tracking-widest">IGBT Temp</span>
                <span className="text-lg font-mono text-orange-400">{liveData.temperature} <span className="text-[10px] text-gray-600">°C</span></span>
             </div>
             <div className="glass p-3 rounded-xl border-l border-purple-500/30">
                <span className="text-[10px] text-gray-500 block mb-1 uppercase font-bold tracking-widest">Motor Speed</span>
                <span className="text-lg font-mono text-purple-400">{liveData.speed} <span className="text-[10px] text-gray-600">RPM</span></span>
             </div>
             <div className="glass p-3 rounded-xl border-l border-green-500/30">
                <span className="text-[10px] text-gray-500 block mb-1 uppercase font-bold tracking-widest">Actual Torque</span>
                <span className="text-lg font-mono text-green-400">{liveData.torque} <span className="text-[10px] text-gray-600">Nm</span></span>
             </div>
          </div>
        </header>

        {/* Live Traffic Hub */}
        <section className="flex-grow p-8 flex flex-col gap-4 overflow-hidden">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Terminal className="text-cyan-400" />
              CAN-Bus Traffic Engine
            </h2>
            <div className="flex gap-2">
               <span className="px-2 py-1 glass rounded text-[10px] uppercase text-cyan-400 font-bold tracking-widest">vcan0</span>
               <span className="px-2 py-1 glass rounded text-[10px] uppercase text-white/50 font-bold tracking-widest">1MBIT/s</span>
            </div>
          </div>

          <div className="flex-grow glass rounded-2xl overflow-hidden flex flex-col bg-slate-900/30">
            {/* Log Table Header */}
            <div className="flex items-center gap-3 p-3 border-b border-white/10 bg-white/5 font-bold text-[10px] uppercase tracking-widest text-gray-400">
               <span className="w-24">Timestamp</span>
               <span className="w-12">CAN ID</span>
               <span className="w-8">DIR</span>
               <span className="flex-grow">Service / Payload Decode</span>
               <span className="hidden lg:block">Raw Hex Data</span>
            </div>
            
            {/* Scrollable Log Container */}
            <div className="flex-grow overflow-y-auto scroll-hide p-2 bg-black/20">
              <AnimatePresence>
                {traffic.map((msg, idx) => (
                  <LogItem key={idx} item={msg} />
                ))}
              </AnimatePresence>
              {traffic.length === 0 && (
                <div className="h-full flex flex-col items-center justify-center opacity-20">
                   <Activity className="w-16 h-16 mb-4 animate-pulse" />
                   <p className="text-sm font-mono tracking-widest uppercase">Waiting for bus activity...</p>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
