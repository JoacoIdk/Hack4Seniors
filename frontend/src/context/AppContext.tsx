import React, { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react';

export type GameId = 'chess' | 'crossword' | 'puzzle';

type GamesState = Record<GameId, boolean>;

type AppContextValue = {
  points: number;
  addPoints: (amount: number) => void;
  games: GamesState;
  completeGame: (id: GameId) => void;
  completedCount: number;
  totalGames: number;
};

const GAME_REWARD = 5;

// El Puzle Diario inicia como ya completado (contador en 1/3).
const INITIAL_GAMES: GamesState = {
  chess: false,
  crossword: false,
  puzzle: true,
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [points, setPoints] = useState(0);
  const [games, setGames] = useState<GamesState>(INITIAL_GAMES);

  const addPoints = useCallback((amount: number) => {
    setPoints((prev) => prev + amount);
  }, []);

  // Solo otorga puntos la primera vez que se completa un juego.
  const completeGame = useCallback(
    (id: GameId) => {
      if (games[id]) return;
      setGames((prev) => ({ ...prev, [id]: true }));
      setPoints((prev) => prev + GAME_REWARD);
    },
    [games],
  );

  const value = useMemo<AppContextValue>(() => {
    const ids = Object.keys(games) as GameId[];
    return {
      points,
      addPoints,
      games,
      completeGame,
      completedCount: ids.filter((id) => games[id]).length,
      totalGames: ids.length,
    };
  }, [points, addPoints, games, completeGame]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp debe usarse dentro de <AppProvider>');
  }
  return context;
}
