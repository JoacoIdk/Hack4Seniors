import { FontAwesome5, Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { api } from '../api/client';
import type { Mission, MissionClaimOut } from '../api/types';
import AppButton from '../components/AppButton';
import ScreenBanner from '../components/ScreenBanner';
import { useApp } from '../context/AppContext';
import type { HomeStackParamList } from '../navigation/types';
import { colors, fontSize, radius, shadow } from '../theme';

type Props = NativeStackScreenProps<HomeStackParamList, 'Home'>;

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return '¡Buenos días!';
  if (hour >= 12 && hour < 20) return '¡Buenas tardes!';
  return '¡Buenas noches!';
};

// ===== Pantalla: Inicio (HomeScreen) =====
export default function HomeScreen({ navigation }: Props) {
  const { me, points, refreshPoints, refreshPuzzles, completedCount, totalGames } = useApp();
  const [missions, setMissions] = useState<Mission[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState<number | null>(null);

  const loadMissions = useCallback(async () => {
    try {
      setMissions(await api<Mission[]>('/missions'));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar los desafíos.');
    }
  }, []);

  // El progreso de las misiones cambia al jugar o hacer amigos: se recarga al volver.
  useFocusEffect(
    useCallback(() => {
      void loadMissions();
      refreshPoints().catch(() => undefined);
      refreshPuzzles().catch(() => undefined);
    }, [loadMissions, refreshPoints, refreshPuzzles]),
  );

  const claim = async (mission: Mission) => {
    setClaiming(mission.id);
    try {
      const result = await api<MissionClaimOut>(`/missions/${mission.id}/claim`, { method: 'POST' });
      Alert.alert('¡Muy bien!', `Completaste "${mission.title}" y ganaste ${result.points_awarded} puntos.`);
      await Promise.all([loadMissions(), refreshPoints()]);
    } catch (e) {
      Alert.alert('No se pudo reclamar', e instanceof Error ? e.message : '');
    } finally {
      setClaiming(null);
    }
  };

  return (
    <View style={styles.container}>
      <ScreenBanner
        title={getGreeting()}
        subtitle={me ? `Hola, ${me.display_name.split(' ')[0]}. ¿Qué te gustaría hacer hoy?` : '¿Qué te gustaría hacer hoy?'}
        right={
          <View style={styles.pointsPill}>
            <FontAwesome5 name="coins" size={16} color={colors.primaryDark} />
            <Text style={styles.pointsText}>Mis puntos: {points}</Text>
          </View>
        }
      />

      <ScrollView contentContainerStyle={styles.content}>
        {/* ----- Desafíos (misiones del día) ----- */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Desafíos del día</Text>

          {error ? (
            <>
              <Text style={styles.hint}>{error}</Text>
              <AppButton label="Reintentar" variant="outline" onPress={loadMissions} />
            </>
          ) : missions === null ? (
            <ActivityIndicator size="large" color={colors.accent} />
          ) : missions.length === 0 ? (
            <Text style={styles.hint}>Hoy no hay desafíos. ¡Vuelve mañana!</Text>
          ) : (
            missions.map((mission) => (
              <View key={mission.id} style={[styles.challengeBox, mission.claimed && styles.challengeDone]}>
                <Text style={styles.challengeTag}>
                  +{mission.points} puntos · {mission.progress}/{mission.target}
                </Text>
                <Text style={styles.challengeText}>{mission.title}</Text>
                {mission.description ? <Text style={styles.challengeDescription}>{mission.description}</Text> : null}
                <View style={styles.progressTrackDark}>
                  <View
                    style={[styles.progressFillDark, { width: `${(mission.progress / mission.target) * 100}%` as const }]}
                  />
                </View>
                {mission.claimed ? (
                  <Text style={styles.claimedText}>✔️ Reclamado</Text>
                ) : mission.completed ? (
                  <AppButton
                    label={claiming === mission.id ? 'Reclamando…' : `Reclamar ${mission.points} puntos`}
                    variant="primary"
                    disabled={claiming !== null}
                    icon={<Ionicons name="checkmark-circle" size={24} color={colors.white} />}
                    onPress={() => claim(mission)}
                    style={styles.claimButton}
                  />
                ) : null}
              </View>
            ))
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
              <View
                style={[
                  styles.progressFill,
                  { width: `${totalGames ? (completedCount / totalGames) * 100 : 0}%` as const },
                ]}
              />
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
  challengeDone: {
    backgroundColor: colors.surface,
  },
  challengeDescription: {
    fontSize: fontSize.body,
    color: colors.textSecondary,
    marginTop: 4,
  },
  progressTrackDark: {
    height: 8,
    borderRadius: radius.round,
    backgroundColor: colors.border,
    overflow: 'hidden',
    marginTop: 12,
  },
  progressFillDark: {
    height: '100%',
    backgroundColor: colors.accent,
  },
  claimedText: {
    fontSize: fontSize.body,
    fontWeight: '700',
    color: colors.primaryDark,
    marginTop: 12,
  },
  claimButton: {
    marginTop: 14,
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
