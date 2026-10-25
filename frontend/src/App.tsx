import { useState } from 'react';
import { TopNav, type NavTab } from './components/TopNav';
import { RepairStudioPage } from './pages/RepairStudioPage';
import { BenchmarksPage } from './pages/BenchmarksPage';
import { HistoryPage } from './pages/HistoryPage';
import { useRepoMedic } from './hooks/useRepoMedic';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('studio');
  const rm = useRepoMedic();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <TopNav
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        modelStatus={rm.modelStatus}
        backendOnline={rm.backendOnline}
        sessionCount={rm.sessions.length}
      />

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {activeTab === 'studio' && (
          <RepairStudioPage
            projects={rm.projects}
            activeSession={rm.activeSession}
            sessionFiles={rm.sessionFiles}
            modelStatus={rm.modelStatus}
            busyAction={rm.busyAction}
            uiError={rm.uiError}
            onClearError={rm.clearError}
            onStartProject={rm.startSessionAndDiagnose}
            onDiagnose={rm.runDiagnose}
            onRepair={rm.runRepair}
            onApprove={rm.runApprove}
            onReject={rm.runReject}
            onRollback={rm.runRollback}
            onReset={rm.runReset}
          />
        )}

        {activeTab === 'benchmarks' && <BenchmarksPage projects={rm.projects} />}

        {activeTab === 'history' && (
          <HistoryPage
            sessions={rm.sessions}
            onOpenSession={async (sid) => {
              await rm.selectSession(sid);
              setActiveTab('studio');
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
