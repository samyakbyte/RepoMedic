import { useCallback, useEffect, useRef, useState } from 'react';
import { api, RepoMedicApiError } from '../services/api';
import {
  WORKING_STATES,
  type ModelStatus,
  type Project,
  type SessionDetail,
  type SessionSummary,
} from '../types/api';

export interface UiError {
  code: string;
  message: string;
  hint?: string | null;
}

export function useRepoMedic() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
  const [sessionFiles, setSessionFiles] = useState<Record<string, string>>({});
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [uiError, setUiError] = useState<UiError | null>(null);

  const pollTimerRef = useRef<number | null>(null);

  const toUiError = (err: unknown): UiError => {
    if (err instanceof RepoMedicApiError) {
      return { code: err.code, message: err.message, hint: err.hint };
    }
    if (err instanceof Error) {
      return { code: 'NETWORK_ERROR', message: err.message, hint: 'Verify the backend server is running on port 8000.' };
    }
    return { code: 'UNKNOWN', message: String(err) };
  };

  const refreshStatusAndLists = useCallback(async () => {
    try {
      const [projs, sessList, mStatus] = await Promise.all([
        api.listProjects(),
        api.listSessions(),
        api.getModelStatus(),
      ]);
      setBackendOnline(true);
      setProjects(projs);
      setSessions(sessList);
      setModelStatus(mStatus);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const refreshActiveSession = useCallback(async (sessionId: string) => {
    const detail = await api.getSession(sessionId);
    setActiveSession(detail);
    try {
      const f = await api.getSessionFiles(sessionId);
      setSessionFiles(f.files);
    } catch {
      // non-fatal
    }
    return detail;
  }, []);

  useEffect(() => {
    void refreshStatusAndLists();
    const id = window.setInterval(() => {
      void api.getModelStatus().then(
        (m) => {
          setBackendOnline(true);
          setModelStatus(m);
        },
        () => setBackendOnline(false)
      );
    }, 10000);
    return () => window.clearInterval(id);
  }, [refreshStatusAndLists]);

  // Poll active session whenever it is in a working background state
  useEffect(() => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (!activeSession || !WORKING_STATES.has(activeSession.state)) {
      return;
    }
    pollTimerRef.current = window.setInterval(async () => {
      try {
        const updated = await refreshActiveSession(activeSession.id);
        if (!WORKING_STATES.has(updated.state)) {
          const list = await api.listSessions();
          setSessions(list);
        }
      } catch (err) {
        setUiError(toUiError(err));
      }
    }, 900);

    return () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [activeSession, refreshActiveSession]);

  const startSessionAndDiagnose = useCallback(
    async (projectId: string) => {
      setUiError(null);
      setBusyAction(`start:${projectId}`);
      try {
        const created = await api.createSession(projectId);
        await api.diagnoseSession(created.id);
        await refreshActiveSession(created.id);
        setSessions(await api.listSessions());
      } catch (err) {
        setUiError(toUiError(err));
      } finally {
        setBusyAction(null);
      }
    },
    [refreshActiveSession]
  );

  const selectSession = useCallback(
    async (sessionId: string) => {
      setUiError(null);
      setBusyAction('load');
      try {
        await refreshActiveSession(sessionId);
      } catch (err) {
        setUiError(toUiError(err));
      } finally {
        setBusyAction(null);
      }
    },
    [refreshActiveSession]
  );

  const runDiagnose = useCallback(async () => {
    if (!activeSession) return;
    setUiError(null);
    setBusyAction('diagnose');
    try {
      await api.diagnoseSession(activeSession.id);
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      setUiError(toUiError(err));
    } finally {
      setBusyAction(null);
    }
  }, [activeSession, refreshActiveSession]);

  const runRepair = useCallback(async () => {
    if (!activeSession) return;
    setUiError(null);
    setBusyAction('repair');
    try {
      await api.repairSession(activeSession.id);
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      setUiError(toUiError(err));
    } finally {
      setBusyAction(null);
    }
  }, [activeSession, refreshActiveSession]);

  const runApprove = useCallback(async () => {
    if (!activeSession) return;
    setUiError(null);
    setBusyAction('approve');
    try {
      await api.approvePatch(activeSession.id);
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      setUiError(toUiError(err));
    } finally {
      setBusyAction(null);
    }
  }, [activeSession, refreshActiveSession]);

  const runReject = useCallback(
    async (reason?: string) => {
      if (!activeSession) return;
      setUiError(null);
      setBusyAction('reject');
      try {
        await api.rejectPatch(activeSession.id, reason);
        await refreshActiveSession(activeSession.id);
      } catch (err) {
        setUiError(toUiError(err));
      } finally {
        setBusyAction(null);
      }
    },
    [activeSession, refreshActiveSession]
  );

  const runRollback = useCallback(async () => {
    if (!activeSession) return;
    setUiError(null);
    setBusyAction('rollback');
    try {
      await api.rollbackPatch(activeSession.id);
      await refreshActiveSession(activeSession.id);
    } catch (err) {
      setUiError(toUiError(err));
    } finally {
      setBusyAction(null);
    }
  }, [activeSession, refreshActiveSession]);

  const runReset = useCallback(async () => {
    if (!activeSession) return;
    setUiError(null);
    setBusyAction('reset');
    try {
      await api.resetSession(activeSession.id);
      await refreshActiveSession(activeSession.id);
      setSessions(await api.listSessions());
    } catch (err) {
      setUiError(toUiError(err));
    } finally {
      setBusyAction(null);
    }
  }, [activeSession, refreshActiveSession]);

  return {
    projects,
    sessions,
    activeSession,
    sessionFiles,
    modelStatus,
    backendOnline,
    busyAction,
    uiError,
    clearError: () => setUiError(null),
    refreshStatusAndLists,
    startSessionAndDiagnose,
    selectSession,
    clearActiveSession: () => {
      setActiveSession(null);
      setSessionFiles({});
      setUiError(null);
    },
    runDiagnose,
    runRepair,
    runApprove,
    runReject,
    runRollback,
    runReset,
  };
}
