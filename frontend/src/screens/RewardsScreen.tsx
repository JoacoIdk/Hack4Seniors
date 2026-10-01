import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';

import ScreenBanner from '../components/ScreenBanner';
import { useApp } from '../context/AppContext';
import { formatReward, REWARDS } from '../data/mockData';
import { colors, fontSize, radius } from '../theme';

// ===== Pantalla: Mis puntos (RewardsScreen) =====
export default function RewardsScreen() {
  const { points } = useApp();

  return (
    <View style={styles.container}>
      <ScreenBanner>
        <View style={styles.totalBox}>
          <Text style={styles.totalLabel}>Mis puntos</Text>
          <Text style={styles.totalValue}>{points}</Text>
          <Text style={styles.totalHint}>Canjéalos en los negocios de tu barrio</Text>
        </View>
      </ScreenBanner>

      <FlatList
        data={REWARDS}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        ListHeaderComponent={<Text style={styles.sectionTitle}>Recompensas</Text>}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        renderItem={({ item }) => {
          const available = points >= item.cost;
          return (
            <View style={styles.item}>
              <View style={styles.iconCircle}>
                <Ionicons name="gift-outline" size={26} color={colors.accentDark} />
              </View>
              <View style={styles.itemBody}>
                <Text style={styles.itemText}>{formatReward(item)}</Text>
                <View style={[styles.chip, available && styles.chipAvailable]}>
                  <Text style={[styles.chipText, available && styles.chipTextAvailable]}>
                    {available ? '¡Disponible!' : `Te faltan ${item.cost - points} puntos`}
                  </Text>
                </View>
              </View>
            </View>
          );
        }}
      />
    </View>
  );
}
// ===== Fin RewardsScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  totalBox: {
    alignItems: 'center',
  },
  totalLabel: {
    color: colors.primaryLight,
    fontSize: fontSize.large,
    fontWeight: '600',
  },
  totalValue: {
    color: colors.white,
    fontSize: fontSize.huge,
    fontWeight: '800',
  },
  totalHint: {
    color: colors.primaryLight,
    fontSize: fontSize.small,
  },
  list: {
    padding: 20,
  },
  sectionTitle: {
    fontSize: fontSize.large,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 14,
  },
  separator: {
    height: 12,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.white,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.accentLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  itemBody: {
    flex: 1,
  },
  itemText: {
    fontSize: fontSize.body,
    color: colors.text,
    lineHeight: 26,
  },
  chip: {
    alignSelf: 'flex-start',
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: radius.round,
    backgroundColor: colors.surface,
  },
  chipAvailable: {
    backgroundColor: colors.primaryLight,
  },
  chipText: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  chipTextAvailable: {
    color: colors.primaryDark,
  },
});
