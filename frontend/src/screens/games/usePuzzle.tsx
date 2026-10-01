import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { api } from '../../api/client';
import type { Puzzle, PuzzleSolveOut } from '../../api/types';
import AppButton from '../../components/AppButton';
import { useApp } from '../../context/AppContext';
import { colors, fontSize } from '../../theme';

export type SolveFn = (answer: unknown) => Promise<PuzzleSolveOut>;

// Carga un juego del día y envía la respuesta al backend, que la valida y otorga los puntos.
export function usePuzzle<D>(puzzleId: number) {
  const { refreshPuzzles, refreshPoints } = useApp();
  const [puzzle, setPuzzle] = useState<Puzzle<D> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzle(await api<Puzzle<D>>(`/puzzles/${puzzleId}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar el juego.');
    }
  }, [puzzleId]);

  useEffect(() => {
    void load();
  }, [load]);

  const solve = useCallback<SolveFn>(
    async (answer) => {
      const result = await api<PuzzleSolveOut>(`/puzzles/${puzzleId}/solve`, { method: 'POST', body: { answer } });
      if (result.correct) {
        await Promise.all([refreshPuzzles(), refreshPoints()]).catch(() => undefined);
      }
      return result;
    },
    [puzzleId, refreshPuzzles, refreshPoints],
  );

  return { puzzle, error, reload: load, solve };
}

export const rewardMessage = ({ points_awarded, already_solved }: PuzzleSolveOut) => {
  if (already_solved) return 'Ya habías resuelto este juego.';
  if (points_awarded > 0) return `Ganaste ${points_awarded} puntos.`;
  return 'Ya alcanzaste el máximo de puntos por juegos de hoy, ¡pero sigue practicando!';
};

// Pantalla de carga o error mientras llega el juego.
export function PuzzleStatus({ error, onRetry }: { error: string | null; onRetry: () => void }) {
  return (
    <View style={styles.container}>
      {error ? (
        <>
          <Text style={styles.text}>{error}</Text>
          <AppButton label="Reintentar" onPress={onRetry} />
        </>
      ) : (
        <ActivityIndicator size="large" color={colors.accent} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    gap: 16,
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  text: {
    fontSize: fontSize.body,
    color: colors.text,
    textAlign: 'center',
  },
});
