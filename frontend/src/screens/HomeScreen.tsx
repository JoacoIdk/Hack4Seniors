import { FontAwesome5, Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import AppButton from '../components/AppButton';
import ScreenBanner from '../components/ScreenBanner';
import { useApp } from '../context/AppContext';
import { CHALLENGE_PLACES, CHALLENGES, ChallengeKind } from '../data/mockData';
import type { HomeStackParamList } from '../navigation/types';
import { colors, fontSize, radius, shadow } from '../theme';

type Props = NativeStackScreenProps<HomeStackParamList, 'Home'>;

type Challenge = {
  kind: ChallengeKind;
  text: string;
  points: number;
};

const pick = <T,>(items: readonly T[]): T => items[Math.floor(Math.random() * items.length)];

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return '¡Buenos días!';
  if (hour >= 12 && hour < 20) return '¡Buenas tardes!';
  return '¡Buenas noches!';
};

// ===== Pantalla: Inicio (HomeScreen) =====
export default function HomeScreen({ navigation }: Props) {
  const { points, addPoints, completedCount, totalGames } = useApp();
  const [challenge, setChallenge] = useState<Challenge | null>(null);

  const generateChallenge = (kind: ChallengeKind) => {
    const config = CHALLENGES[kind];
    setChallenge({
      kind,
      points: config.points,
      text: `Ve a ${pick(CHALLENGE_PLACES)} y ${pick(config.actions)}.`,
    });
  };

  const markDone = () => {
    if (!challenge) return;
    addPoints(challenge.points);
    Alert.alert('¡Muy bien!', `Completaste el desafío y ganaste ${challenge.points} puntos.`);
    setChallenge(null);
  };

  return (
    <View style={styles.container}>
      <ScreenBanner
        title={getGreeting()}
        subtitle="¿Qué te gustaría hacer hoy?"
        right={
          <View style={styles.pointsPill}>
            <FontAwesome5 name="coins" size={16} color={colors.primaryDark} />
            <Text style={styles.pointsText}>Mis puntos: {points}</Text>
          </View>
        }
      />

      <ScrollView contentContainerStyle={styles.content}>
        {/* ----- Desafíos ----- */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Desafíos del día</Text>

          {challenge ? (
            <>
              <View style={styles.challengeBox}>
                <Text style={styles.challengeTag}>
                  {challenge.kind === 'hard' ? 'Desafiante' : 'Simple'} · +{challenge.points} puntos
                </Text>
                <Text style={styles.challengeText}>{challenge.text}</Text>
              </View>
              <AppButton
                label="Marcar listo"
                variant="primary"
                icon={<Ionicons name="checkmark-circle" size={24} color={colors.white} />}
                onPress={markDone}
              />
              <Pressable onPress={() => setChallenge(null)} style={styles.cancel} accessibilityRole="button">
                <Text style={styles.cancelText}>Cancelar</Text>
              </Pressable>
            </>
          ) : (
            <>
              <AppButton
                label="Quiero algo desafiante"
                icon={<Ionicons name="flame" size={22} color={colors.white} />}
                onPress={() => generateChallenge('hard')}
              />
              <Text style={styles.hint}>Gana {CHALLENGES.hard.points} puntos</Text>
              <AppButton
                label="Dame algo simple"
                variant="outline"
                icon={<Ionicons name="leaf" size={22} color={colors.accentDark} />}
                onPress={() => generateChallenge('easy')}
              />
              <Text style={styles.hint}>Gana {CHALLENGES.easy.points} puntos</Text>
            </>
          )}
        </View>
      </ScrollView>

      {/* ----- Juegos diarios ----- */}
      <View style={styles.footer}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Juegos Diarios, ${completedCount} de ${totalGames} completados`}
          onPress={() => navigation.navigate('GameSelection')}
          style={({ pressed }) => [styles.gamesButton, pressed && styles.pressed]}
        >
          <Ionicons name="game-controller" size={32} color={colors.white} />
          <View style={styles.gamesTexts}>
            <Text style={styles.gamesTitle}>Juegos Diarios</Text>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${(completedCount / totalGames) * 100}%` as const }]} />
            </View>
          </View>
          <Text style={styles.gamesCounter}>
            {completedCount}/{totalGames}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}
// ===== Fin HomeScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  pointsPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.white,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.round,
  },
  pointsText: {
    color: colors.primaryDark,
    fontSize: fontSize.small,
    fontWeight: '700',
  },
  content: {
    padding: 20,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    ...shadow,
  },
  cardTitle: {
    fontSize: fontSize.large,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 16,
  },
  hint: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 14,
  },
  challengeBox: {
    backgroundColor: colors.accentLight,
    borderRadius: radius.md,
    padding: 18,
    marginBottom: 16,
  },
  challengeTag: {
    fontSize: fontSize.small,
    fontWeight: '700',
    color: colors.accentDark,
    marginBottom: 8,
  },
  challengeText: {
    fontSize: fontSize.large,
    color: colors.text,
    lineHeight: 30,
  },
  cancel: {
    alignSelf: 'center',
    padding: 12,
    marginTop: 4,
  },
  cancelText: {
    fontSize: fontSize.body,
    color: colors.textSecondary,
    textDecorationLine: 'underline',
  },
  footer: {
    padding: 20,
    paddingTop: 8,
  },
  gamesButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.accent,
    borderRadius: radius.lg,
    paddingVertical: 20,
    paddingHorizontal: 22,
    ...shadow,
  },
  pressed: {
    opacity: 0.85,
  },
  gamesTexts: {
    flex: 1,
    marginHorizontal: 16,
  },
  gamesTitle: {
    color: colors.white,
    fontSize: fontSize.large,
    fontWeight: '700',
    marginBottom: 8,
  },
  progressTrack: {
    height: 8,
    borderRadius: radius.round,
    backgroundColor: 'rgba(255,255,255,0.35)',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.white,
  },
  gamesCounter: {
    color: colors.white,
    fontSize: fontSize.title,
    fontWeight: '800',
  },
});
