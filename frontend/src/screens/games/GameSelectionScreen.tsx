import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useCallback } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { PuzzleKind } from '../../api/types';
import { useApp } from '../../context/AppContext';
import type { HomeStackParamList } from '../../navigation/types';
import { colors, fontSize, radius, shadow } from '../../theme';

type Props = NativeStackScreenProps<HomeStackParamList, 'GameSelection'>;

// Cómo se muestra cada tipo de juego del backend. Sin ruta = aún no se puede jugar en la app.
const GAME_KINDS: Partial<
  Record<PuzzleKind, { icon: keyof typeof Ionicons.glyphMap; route?: 'ChessGame' | 'CrosswordGame' }>
> = {
  chess: { icon: 'extension-puzzle-outline', route: 'ChessGame' },
  crossword: { icon: 'grid-outline', route: 'CrosswordGame' },
};

const DEFAULT_KIND = { icon: 'images-outline' as const, route: undefined };

// ===== Pantalla: Selección de Juegos (GameSelectionScreen) =====
export default function GameSelectionScreen({ navigation }: Props) {
  const { puzzles, completedCount, totalGames, puzzlePointsRemaining, refreshPuzzles, refreshPoints } = useApp();

  useFocusEffect(
    useCallback(() => {
      refreshPuzzles().catch(() => undefined);
      refreshPoints().catch(() => undefined);
    }, [refreshPuzzles, refreshPoints]),
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.counterBox}>
        <Text style={styles.counterLabel}>Completados hoy</Text>
        <Text style={styles.counterValue}>
          {completedCount}/{totalGames}
        </Text>
        <Text style={styles.counterHint}>
          {puzzlePointsRemaining > 0
            ? `Cada juego te da 5 puntos la primera vez (te quedan ${puzzlePointsRemaining} hoy)`
            : 'Ya ganaste todos los puntos de juegos de hoy'}
        </Text>
      </View>

      {puzzles.length === 0 ? <Text style={styles.empty}>Hoy no hay juegos. ¡Vuelve mañana!</Text> : null}

      {puzzles.map((puzzle) => {
        const done = puzzle.solved;
        const { icon, route } = GAME_KINDS[puzzle.kind] ?? DEFAULT_KIND;
        return (
          <Pressable
            key={puzzle.id}
            accessibilityRole="button"
            accessibilityState={{ disabled: done }}
            accessibilityLabel={`${puzzle.title}${done ? ', completado' : ''}`}
            disabled={done || !route}
            onPress={() => route && navigation.navigate(route, { puzzleId: puzzle.id })}
            style={({ pressed }) => [styles.gameButton, done && styles.gameDone, pressed && styles.pressed]}
          >
            <View style={[styles.iconCircle, done && styles.iconCircleDone]}>
              <Ionicons name={icon} size={30} color={done ? colors.textSecondary : colors.white} />
            </View>
            <View style={styles.gameTexts}>
              <Text style={[styles.gameTitle, done && styles.textDone]}>{puzzle.title}</Text>
              <Text style={styles.gameDescription}>
                {done ? 'Completado hoy' : route ? puzzle.description : 'Próximamente en la app'}
              </Text>
            </View>
            {done ? (
              <Text style={styles.check}>✔️</Text>
            ) : (
              <Ionicons name="chevron-forward" size={28} color={colors.accent} />
            )}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}
// ===== Fin GameSelectionScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 20,
    gap: 16,
  },
  counterBox: {
    backgroundColor: colors.primaryLight,
    borderRadius: radius.lg,
    padding: 20,
    alignItems: 'center',
  },
  counterLabel: {
    fontSize: fontSize.body,
    color: colors.primaryDark,
    fontWeight: '600',
  },
  counterValue: {
    fontSize: 48,
    fontWeight: '800',
    color: colors.primary,
  },
  counterHint: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  empty: {
    fontSize: fontSize.body,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  gameButton: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 96,
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    borderWidth: 2,
    borderColor: colors.accent,
    padding: 16,
    ...shadow,
  },
  gameDone: {
    borderColor: colors.border,
    backgroundColor: colors.surface,
    elevation: 0,
    shadowOpacity: 0,
  },
  pressed: {
    opacity: 0.85,
  },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  iconCircleDone: {
    backgroundColor: colors.border,
  },
  gameTexts: {
    flex: 1,
  },
  gameTitle: {
    fontSize: fontSize.large,
    fontWeight: '700',
    color: colors.text,
  },
  textDone: {
    color: colors.textSecondary,
  },
  gameDescription: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    marginTop: 4,
  },
  check: {
    fontSize: 28,
  },
});
