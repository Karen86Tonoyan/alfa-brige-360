import React, { useState, useEffect, useCallback } from "react";

// =============================================================================
// TYPES
// =============================================================================

type ModelId = "gpt" | "claude" | "gemini" | "deepseek" | "opus" | "ollama_mistral" | "ollama_qwen" | "ollama_llama";

type RoleId = "architect" | "integrator" | "tester" | "coder" | "analyst";

type ModelStatus = "online" | "degraded" | "offline";

interface Model {
  id: ModelId;
  name: string;
  type: "CLOUD" | "LOCAL";
  status: ModelStatus;
  latency?: number;
  lastUsed?: string;
}

interface LogEntry {
  id: string;
  timestamp: Date;
  level: "INFO" | "WARN" | "ERROR" | "TASK" | "SECURITY";
  source: string;
  message: string;
}

interface TaskResult {
  role: string;
  model: string;
  status: "pending" | "running" | "success" | "failed";
  output?: string;
}

// =============================================================================
// DATA
// =============================================================================

const ALL_MODELS: Model[] = [
  { id: "gpt", name: "GPT-5.1 (Paweł)", type: "CLOUD", status: "online", latency: 120 },
  { id: "claude", name: "Claude 3.7 Sonnet", type: "CLOUD", status: "online", latency: 95 },
  { id: "gemini", name: "Gemini 2.5 Flash", type: "CLOUD", status: "online", latency: 80 },
  { id: "deepseek", name: "DeepSeek R1", type: "CLOUD", status: "degraded", latency: 250 },
  { id: "opus", name: "Claude Opus 4", type: "CLOUD", status: "online", latency: 180 },
  { id: "ollama_mistral", name: "Mistral 7B (Local)", type: "LOCAL", status: "online", latency: 45 },
  { id: "ollama_qwen", name: "Qwen 2.5 (Local)", type: "LOCAL", status: "online", latency: 50 },
  { id: "ollama_llama", name: "Llama 3.2 (Local)", type: "LOCAL", status: "offline", latency: 0 },
];

const ROLE_CONFIG: Record<RoleId, { label: string; description: string; icon: string; defaultModel: ModelId }> = {
  architect: {
    label: "ARCHITEKT",
    description: "Planowanie, dekompozycja zadań",
    icon: "🏛️",
    defaultModel: "claude"
  },
  integrator: {
    label: "INTEGRATOR",
    description: "Łączenie modułów, API",
    icon: "🔗",
    defaultModel: "gpt"
  },
  tester: {
    label: "TESTER",
    description: "Walidacja, testy, QA",
    icon: "🧪",
    defaultModel: "gemini"
  },
  coder: {
    label: "CODER",
    description: "Implementacja kodu",
    icon: "💻",
    defaultModel: "opus"
  },
  analyst: {
    label: "ANALITYK",
    description: "Analiza danych, raporty",
    icon: "📊",
    defaultModel: "deepseek"
  },
};

const STATUS_COLORS: Record<ModelStatus, string> = {
  online: "bg-emerald-500",
  degraded: "bg-amber-500",
  offline: "bg-red-500",
};

const LOG_COLORS: Record<LogEntry["level"], string> = {
  INFO: "text-zinc-400",
  WARN: "text-amber-400",
  ERROR: "text-red-400",
  TASK: "text-blue-400",
  SECURITY: "text-purple-400",
};

// =============================================================================
// COMPONENTS
// =============================================================================

// Model Card in Pool
const ModelCard: React.FC<{ model: Model }> = ({ model }) => (
  <div className="flex items-center gap-3 p-3 bg-zinc-900/50 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors">
    <div className={`w-2 h-2 rounded-full ${STATUS_COLORS[model.status]}`} />
    <div className="flex-1 min-w-0">
      <div className="text-sm font-medium text-zinc-200 truncate">{model.name}</div>
      <div className="text-xs text-zinc-500">{model.type} • {model.latency}ms</div>
    </div>
  </div>
);

// Role Card with Model Selector
const RoleCard: React.FC<{
  roleId: RoleId;
  assignedModelId: ModelId;
  onModelChange: (modelId: ModelId) => void;
  lastTask?: TaskResult;
}> = ({ roleId, assignedModelId, onModelChange, lastTask }) => {
  const config = ROLE_CONFIG[roleId];
  const model = ALL_MODELS.find(m => m.id === assignedModelId)!;
  
  return (
    <div className="bg-zinc-900/80 rounded-xl border border-zinc-800 p-4 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-2xl">{config.icon}</span>
        <div>
          <h3 className="text-sm font-bold text-amber-400 tracking-wider">{config.label}</h3>
          <p className="text-xs text-zinc-500">{config.description}</p>
        </div>
      </div>
      
      {/* Model Selector */}
      <select
        value={assignedModelId}
        onChange={(e) => onModelChange(e.target.value as ModelId)}
        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-amber-500"
      >
        {ALL_MODELS.filter(m => m.status !== "offline").map(m => (
          <option key={m.id} value={m.id}>
            {m.name} ({m.type})
          </option>
        ))}
      </select>
      
      {/* Status */}
      <div className="flex items-center gap-2 text-xs">
        <div className={`w-2 h-2 rounded-full ${STATUS_COLORS[model.status]}`} />
        <span className="text-zinc-400">{model.status.toUpperCase()}</span>
        <span className="text-zinc-600">•</span>
        <span className="text-zinc-500">{model.latency}ms</span>
      </div>
      
      {/* Last Task */}
      {lastTask && (
        <div className={`text-xs px-2 py-1 rounded ${
          lastTask.status === "success" ? "bg-emerald-500/20 text-emerald-400" :
          lastTask.status === "failed" ? "bg-red-500/20 text-red-400" :
          lastTask.status === "running" ? "bg-blue-500/20 text-blue-400" :
          "bg-zinc-800 text-zinc-500"
        }`}>
          {lastTask.status === "running" ? "⏳ W trakcie..." : 
           lastTask.status === "success" ? "✓ Ostatnie: OK" :
           lastTask.status === "failed" ? "✗ Ostatnie: BŁĄD" :
           "Oczekuje..."}
        </div>
      )}
    </div>
  );
};

// Log Entry
const LogLine: React.FC<{ entry: LogEntry }> = ({ entry }) => (
  <div className="flex gap-2 text-xs font-mono">
    <span className="text-zinc-600 shrink-0">
      [{entry.timestamp.toLocaleTimeString()}]
    </span>
    <span className={`shrink-0 ${LOG_COLORS[entry.level]}`}>
      [{entry.level}]
    </span>
    <span className="text-zinc-500 shrink-0">[{entry.source}]</span>
    <span className="text-zinc-300">{entry.message}</span>
  </div>
);

// =============================================================================
// MAIN PANEL
// =============================================================================

const AlfaSeatPanel: React.FC = () => {
  // State
  const [roles, setRoles] = useState<Record<RoleId, ModelId>>({
    architect: "claude",
    integrator: "gpt",
    tester: "gemini",
    coder: "opus",
    analyst: "deepseek",
  });
  
  const [task, setTask] = useState("");
  const [mode, setMode] = useState<"PLAN" | "BUILD" | "TEST" | "FULL">("BUILD");
  const [isExecuting, setIsExecuting] = useState(false);
  const [taskResults, setTaskResults] = useState<Record<RoleId, TaskResult>>({} as any);
  
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: "1", timestamp: new Date(), level: "INFO", source: "SYSTEM", message: "ALFA_SEAT online. Panel dowodzenia gotowy." },
    { id: "2", timestamp: new Date(), level: "SECURITY", source: "CERBER", message: "Integralność systemu: OK. Fingerprint verified." },
    { id: "3", timestamp: new Date(), level: "INFO", source: "ROUTER", message: "Pipeline federacji AI skonfigurowany." },
  ]);
  
  const [logFilter, setLogFilter] = useState<"ALL" | LogEntry["level"]>("ALL");
  const [systemStatus, setSystemStatus] = useState<"ONLINE" | "DEGRADED" | "OFFLINE">("ONLINE");

  // Helpers
  const getModel = (id: ModelId) => ALL_MODELS.find(m => m.id === id)!;
  
  const addLog = useCallback((level: LogEntry["level"], source: string, message: string) => {
    setLogs(prev => [{
      id: Date.now().toString(),
      timestamp: new Date(),
      level,
      source,
      message
    }, ...prev].slice(0, 100));
  }, []);

  // Handlers
  const handleRoleChange = (role: RoleId, modelId: ModelId) => {
    setRoles(prev => ({ ...prev, [role]: modelId }));
    const model = getModel(modelId);
    addLog("INFO", "ROLES", `Rola ${ROLE_CONFIG[role].label} → ${model.name}`);
  };

  const handleExecute = async () => {
    if (!task.trim() || isExecuting) return;
    
    setIsExecuting(true);
    addLog("TASK", "COMMANDER", `🔥 ROZKAZ: "${task}"`);
    addLog("INFO", "PIPELINE", `Tryb: ${mode}`);
    
    // Simulate pipeline execution
    const pipeline: RoleId[] = 
      mode === "PLAN" ? ["architect"] :
      mode === "TEST" ? ["tester", "analyst"] :
      mode === "BUILD" ? ["architect", "integrator", "coder"] :
      ["architect", "integrator", "coder", "tester", "analyst"];
    
    for (const roleId of pipeline) {
      const model = getModel(roles[roleId]);
      
      setTaskResults(prev => ({
        ...prev,
        [roleId]: { role: ROLE_CONFIG[roleId].label, model: model.name, status: "running" }
      }));
      
      addLog("TASK", ROLE_CONFIG[roleId].label, `Uruchamiam ${model.name}...`);
      
      // Simulate work
      await new Promise(r => setTimeout(r, 1000 + Math.random() * 1500));
      
      const success = Math.random() > 0.1;
      
      setTaskResults(prev => ({
        ...prev,
        [roleId]: { 
          role: ROLE_CONFIG[roleId].label, 
          model: model.name, 
          status: success ? "success" : "failed",
          output: success ? "Zadanie wykonane pomyślnie" : "Błąd wykonania"
        }
      }));
      
      addLog(
        success ? "INFO" : "ERROR",
        ROLE_CONFIG[roleId].label,
        success ? `✓ Zakończono pomyślnie` : `✗ Błąd wykonania`
      );
    }
    
    addLog("TASK", "PIPELINE", "Pipeline zakończony.");
    setIsExecuting(false);
    setTask("");
  };

  // Check system status based on models
  useEffect(() => {
    const onlineCount = ALL_MODELS.filter(m => m.status === "online").length;
    const total = ALL_MODELS.length;
    
    if (onlineCount === total) setSystemStatus("ONLINE");
    else if (onlineCount >= total / 2) setSystemStatus("DEGRADED");
    else setSystemStatus("OFFLINE");
  }, []);

  // Filtered logs
  const filteredLogs = logFilter === "ALL" 
    ? logs 
    : logs.filter(l => l.level === logFilter);

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col">
      
      {/* ===== HEADER ===== */}
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between bg-gradient-to-r from-black via-zinc-950 to-black">
        <div>
          <h1 className="text-xl font-bold tracking-[0.25em] uppercase text-zinc-100">
            ALFA_SEAT <span className="text-amber-500">//</span> CONTROL CENTER
          </h1>
          <p className="text-xs text-zinc-500 mt-1 tracking-wide">
            Panel dowodzenia federacją AI • Król decyduje, kto za co odpowiada
          </p>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="text-[10px] text-zinc-600 uppercase tracking-widest">Status</div>
            <div className={`text-sm font-bold ${
              systemStatus === "ONLINE" ? "text-emerald-400" :
              systemStatus === "DEGRADED" ? "text-amber-400" :
              "text-red-400"
            }`}>
              {systemStatus}
            </div>
          </div>
          <div className="h-8 w-px bg-zinc-800" />
          <div className="text-right">
            <div className="text-[10px] text-zinc-600 uppercase tracking-widest">Profil</div>
            <div className="text-sm font-medium text-amber-300">ALFA_CORE // PROD</div>
          </div>
          <div className="h-8 w-px bg-zinc-800" />
          <div className="text-right">
            <div className="text-[10px] text-zinc-600 uppercase tracking-widest">Modele</div>
            <div className="text-sm font-medium text-zinc-300">
              {ALL_MODELS.filter(m => m.status === "online").length}/{ALL_MODELS.length} online
            </div>
          </div>
        </div>
      </header>

      {/* ===== MAIN CONTENT ===== */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* LEFT PANEL - Model Pool */}
        <aside className="w-64 border-r border-zinc-800 p-4 flex flex-col gap-4 bg-zinc-950/50">
          <h2 className="text-xs font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-2">
            <span>🐴</span> Stajnia Modeli
          </h2>
          <div className="flex-1 overflow-auto space-y-2">
            {ALL_MODELS.map(model => (
              <ModelCard key={model.id} model={model} />
            ))}
          </div>
          <div className="text-[10px] text-zinc-600 text-center">
            Przeciągnij model do roli lub użyj selecta
          </div>
        </aside>

        {/* CENTER - Roles Board */}
        <main className="flex-1 p-6 overflow-auto">
          <h2 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-4 flex items-center gap-2">
            <span>👑</span> Plansza Ról - Federacja AI
          </h2>
          
          <div className="grid grid-cols-5 gap-4 mb-8">
            {(Object.keys(ROLE_CONFIG) as RoleId[]).map(roleId => (
              <RoleCard
                key={roleId}
                roleId={roleId}
                assignedModelId={roles[roleId]}
                onModelChange={(modelId) => handleRoleChange(roleId, modelId)}
                lastTask={taskResults[roleId]}
              />
            ))}
          </div>

          {/* Pipeline Visualization */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 mb-6">
            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">
              Aktualny Pipeline ({mode})
            </h3>
            <div className="flex items-center gap-2 flex-wrap">
              {(mode === "PLAN" ? ["architect"] :
                mode === "TEST" ? ["tester", "analyst"] :
                mode === "BUILD" ? ["architect", "integrator", "coder"] :
                ["architect", "integrator", "coder", "tester", "analyst"]
              ).map((roleId, i, arr) => (
                <React.Fragment key={roleId}>
                  <div className="bg-zinc-800 px-3 py-1.5 rounded-lg text-xs flex items-center gap-2">
                    <span>{ROLE_CONFIG[roleId as RoleId].icon}</span>
                    <span className="text-amber-400">{ROLE_CONFIG[roleId as RoleId].label}</span>
                    <span className="text-zinc-500">→</span>
                    <span className="text-zinc-300">{getModel(roles[roleId as RoleId]).name}</span>
                  </div>
                  {i < arr.length - 1 && <span className="text-zinc-600">→</span>}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Task Console */}
          <div className="bg-zinc-900/80 rounded-xl border border-zinc-800 p-4">
            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3 flex items-center gap-2">
              <span>⚔️</span> Konsola Króla
            </h3>
            
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Wpisz rozkaz dla armii AI... np. 'Zbuduj moduł eksportu ZIP z kompresją'"
              className="w-full h-24 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-amber-500 resize-none font-mono"
              disabled={isExecuting}
            />
            
            <div className="flex items-center gap-4 mt-3">
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as typeof mode)}
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-amber-500"
                disabled={isExecuting}
              >
                <option value="PLAN">📋 PLAN ONLY (Architekt)</option>
                <option value="BUILD">🔨 BUILD (Architekt → Integrator → Coder)</option>
                <option value="TEST">🧪 TEST (Tester + Analityk)</option>
                <option value="FULL">🚀 FULL PIPELINE (Wszystkie role)</option>
              </select>
              
              <button
                onClick={handleExecute}
                disabled={!task.trim() || isExecuting}
                className={`flex-1 py-2.5 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${
                  isExecuting
                    ? "bg-zinc-700 text-zinc-500 cursor-wait"
                    : task.trim()
                      ? "bg-gradient-to-r from-amber-600 to-amber-500 text-black hover:from-amber-500 hover:to-amber-400"
                      : "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                }`}
              >
                {isExecuting ? "⏳ Wykonuję..." : "🔥 EXECUTE"}
              </button>
            </div>
          </div>
        </main>

        {/* RIGHT PANEL - Logs */}
        <aside className="w-80 border-l border-zinc-800 flex flex-col bg-zinc-950/50">
          <div className="p-4 border-b border-zinc-800">
            <h2 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3 flex items-center gap-2">
              <span>📡</span> Telemetria / Logi
            </h2>
            <div className="flex gap-1 flex-wrap">
              {(["ALL", "INFO", "WARN", "ERROR", "TASK", "SECURITY"] as const).map(level => (
                <button
                  key={level}
                  onClick={() => setLogFilter(level)}
                  className={`px-2 py-1 text-[10px] rounded uppercase tracking-wider transition-colors ${
                    logFilter === level
                      ? "bg-amber-500/20 text-amber-400"
                      : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>
          
          <div className="flex-1 overflow-auto p-4 space-y-1 font-mono">
            {filteredLogs.map(entry => (
              <LogLine key={entry.id} entry={entry} />
            ))}
          </div>
        </aside>
      </div>

      {/* ===== FOOTER ===== */}
      <footer className="border-t border-zinc-800 px-6 py-2 flex items-center justify-between text-[10px] text-zinc-600 bg-zinc-950">
        <div>ALFA_SEAT v1.0.0 • ALFA_CORE Integration</div>
        <div>© 2025 Karen86Tonoyan • The King's Private Cloud</div>
      </footer>
    </div>
  );
};

export default AlfaSeatPanel;
