import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api, setToken, setUnauthorizedHandler } from '../api/client';
import type { Me, PointsSummary, Puzzle, RegisterIn, TokenOut } from '../api/types';

const TOKEN_KEY = 'hack4seniors.token';

type AuthStatus = 'loading' | 'signedOut' | 'signedIn';

type AppContextValue = {
  status: AuthStatus;
  me: Me | null;
  setMe: (me: Me) => void;
  points: number;
  puzzlePointsRemaining: number;
  puzzles: Puzzle[];
  completedCount: number;
  totalGames: number;
  signIn: (email: string, password: string) => Promise<void>;
  register: (data: RegisterIn) => Promise<void>;
  signOut: () => Promise<void>;
  refreshPoints: () => Promise<void>;
  refreshPuzzles: () => Promise<void>;
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [me, setMe] = useState<Me | null>(null);
  const [summary, setSummary] = useState<PointsSummary | null>(null);
  const [puzzles, setPuzzles] = useState<Puzzle[]>([]);

  const signOut = useCallback(async () => {
    setToken(null);
    await AsyncStorage.removeItem(TOKEN_KEY);
    setMe(null);
    setSummary(null);
    setPuzzles([]);
    setStatus('signedOut');
  }, []);

  const refreshPoints = useCallback(async () => {
    setSummary(await api<PointsSummary>('/me/points'));
  }, []);

  const refreshPuzzles = useCallback(async () => {
    setPuzzles(await api<Puzzle[]>('/puzzles/today'));
  }, []);

  // Carga los datos de la sesión; si el token ya no sirve, vuelve al inicio de sesión.
  const startSession = useCallback(
    async (token: string) => {
      setToken(token);
      try {
        const [profile] = await Promise.all([api<Me>('/me'), refreshPoints(), refreshPuzzles()]);
        setMe(profile);
        setStatus('signedIn');
      } catch (error) {
        await signOut();
        throw error;
      }
    },
    [refreshPoints, refreshPuzzles, signOut],
  );

  useEffect(() => {
    setUnauthorizedHandler(() => void signOut());
    AsyncStorage.getItem(TOKEN_KEY)
      .then((token) => (token ? startSession(token) : signOut()))
      .catch(() => undefined);
    return () => setUnauthorizedHandler(null);
  }, [signOut, startSession]);

  const acceptToken = useCallback(
    async ({ access_token }: TokenOut) => {
      await AsyncStorage.setItem(TOKEN_KEY, access_token);
      await startSession(access_token);
    },
    [startSession],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      await acceptToken(await api<TokenOut>('/auth/login', { method: 'POST', body: { email, password, role: 'user' } }));
    },
    [acceptToken],
  );

  const register = useCallback(
    async (data: RegisterIn) => {
      await acceptToken(await api<TokenOut>('/auth/register', { method: 'POST', body: { ...data, language: 'es' } }));
    },
    [acceptToken],
  );

  const value = useMemo<AppContextValue>(
    () => ({
      status,
      me,
      setMe,
      points: summary?.balance ?? me?.points ?? 0,
      puzzlePointsRemaining: summary?.puzzle_points_remaining_today ?? 0,
      puzzles,
      completedCount: puzzles.filter((p) => p.solved).length,
      totalGames: puzzles.length,
      signIn,
      register,
      signOut,
      refreshPoints,
      refreshPuzzles,
    }),
    [status, me, summary, puzzles, signIn, register, signOut, refreshPoints, refreshPuzzles],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp debe usarse dentro de <AppProvider>');
  }
  return context;
}
