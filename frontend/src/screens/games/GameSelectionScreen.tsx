import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useApp } from '../../context/AppContext';
import { DAILY_GAMES } from '../../data/mockData';
import type { HomeStackParamList } from '../../navigation/types';
import { colors, fontSize, radius, shadow } from '../../theme';

type Props = NativeStackScreenProps<HomeStackParamList, 'GameSelection'>;

// ===== Pantalla: Selección de Juegos (GameSelectionScreen) =====
export default function GameSelectionScreen({ navigation }: Props) {
  const { games, completedCount, totalGames } = useApp();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.counterBox}>
        <Text style={styles.counterLabel}>Completados hoy</Text>
        <Text style={styles.counterValue}>
          {completedCount}/{totalGames}
        </Text>
        <Text style={styles.counterHint}>Cada juego te da 5 puntos la primera vez</Text>
      </View>

      {DAILY_GAMES.map((game) => {
        const done = games[game.id];
        return (
          <Pressable
            key={game.id}
            accessibilityRole="button"
            accessibilityState={{ disabled: done }}
            accessibilityLabel={`${game.title}${done ? ', completado' : ''}`}
            disabled={done || !game.route}
            onPress={() => game.route && navigation.navigate(game.route)}
            style={({ pressed }) => [styles.gameButton, done && styles.gameDone, pressed && styles.pressed]}
          >
            <View style={[styles.iconCircle, done && styles.iconCircleDone]}>
              <Ionicons name={game.icon} size={30} color={done ? colors.textSecondary : colors.white} />
            </View>
            <View style={styles.gameTexts}>
              <Text style={[styles.gameTitle, done && styles.textDone]}>{game.title}</Text>
              <Text style={styles.gameDescription}>{done ? 'Completado hoy' : game.description}</Text>
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
