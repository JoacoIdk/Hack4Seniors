import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Alert, FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import QRCode from 'react-native-qrcode-svg';

import { api } from '../api/client';
import type { Promotion, Redemption } from '../api/types';
import AppButton from '../components/AppButton';
import ScreenBanner from '../components/ScreenBanner';
import { useApp } from '../context/AppContext';
import { colors, fontSize, radius, shadow } from '../theme';

const formatDiscount = (promo: Promotion) =>
  promo.discount_type === 'percent' ? `${promo.discount_value}% de dcto.` : `$${promo.discount_value} de dcto.`;

const formatReward = (promo: Promotion) =>
  `${promo.title}${promo.company_name ? ` de ${promo.company_name}` : ''} con ${formatDiscount(promo)} por ${promo.points_cost} puntos!`;

const formatDate = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: 'numeric', month: 'long' });

// ===== Pantalla: Mis puntos (RewardsScreen) =====
export default function RewardsScreen() {
  const { points, refreshPoints } = useApp();
  const [promotions, setPromotions] = useState<Promotion[] | null>(null);
  const [coupons, setCoupons] = useState<Redemption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [redeeming, setRedeeming] = useState<number | null>(null);
  const [shownCoupon, setShownCoupon] = useState<Redemption | null>(null);

  const load = useCallback(async () => {
    try {
      const [promos, active] = await Promise.all([
        api<Promotion[]>('/market/promotions?limit=100'),
        api<Redemption[]>('/me/redemptions?status=active&limit=100'),
        refreshPoints(),
      ]);
      setPromotions([...promos].sort((a, b) => a.points_cost - b.points_cost));
      setCoupons(active);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar las recompensas.');
    }
  }, [refreshPoints]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const redeem = async (promo: Promotion) => {
    setRedeeming(promo.id);
    try {
      const coupon = await api<Redemption>(`/market/promotions/${promo.id}/redeem`, { method: 'POST' });
      await load();
      setShownCoupon(coupon);
    } catch (e) {
      Alert.alert('No se pudo canjear', e instanceof Error ? e.message : '');
    } finally {
      setRedeeming(null);
    }
  };

  const confirmRedeem = (promo: Promotion) =>
    Alert.alert('¿Canjear recompensa?', `Usarás ${promo.points_cost} puntos en: ${promo.title}.`, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Canjear', onPress: () => void redeem(promo) },
    ]);

  const header = (
    <>
      {coupons.length > 0 ? (
        <View style={styles.couponsSection}>
          <Text style={styles.sectionTitle}>Mis cupones</Text>
          {coupons.map((coupon) => (
            <Pressable
              key={coupon.id}
              accessibilityRole="button"
              onPress={() => setShownCoupon(coupon)}
              style={({ pressed }) => [styles.coupon, pressed && styles.pressed]}
            >
              <Ionicons name="qr-code-outline" size={30} color={colors.white} />
              <View style={styles.itemBody}>
                <Text style={styles.couponTitle}>{coupon.promotion_title}</Text>
                <Text style={styles.couponSubtitle}>
                  {coupon.company_name} · vence el {formatDate(coupon.expires_at)}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={26} color={colors.white} />
            </Pressable>
          ))}
        </View>
      ) : null}
      <Text style={styles.sectionTitle}>Recompensas</Text>
      {error ? (
        <View style={styles.message}>
          <Text style={styles.messageText}>{error}</Text>
          <AppButton label="Reintentar" variant="outline" onPress={load} />
        </View>
      ) : promotions === null ? (
        <ActivityIndicator size="large" color={colors.accent} />
      ) : promotions.length === 0 ? (
        <Text style={styles.messageText}>Aún no hay recompensas disponibles.</Text>
      ) : null}
    </>
  );

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
        data={error ? [] : promotions ?? []}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        ListHeaderComponent={header}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        renderItem={({ item }) => {
          const available = points >= item.points_cost;
          return (
            <View style={styles.item}>
              <View style={styles.iconCircle}>
                <Ionicons name="gift-outline" size={26} color={colors.accentDark} />
              </View>
              <View style={styles.itemBody}>
                <Text style={styles.itemText}>{formatReward(item)}</Text>
                {available ? (
                  <AppButton
                    label={redeeming === item.id ? 'Canjeando…' : '¡Canjear!'}
                    variant="primary"
                    disabled={redeeming !== null}
                    onPress={() => confirmRedeem(item)}
                    style={styles.redeemButton}
                  />
                ) : (
                  <View style={styles.chip}>
                    <Text style={styles.chipText}>Te faltan {item.points_cost - points} puntos</Text>
                  </View>
                )}
              </View>
            </View>
          );
        }}
      />

      {/* ----- Cupón con QR para mostrar en el negocio ----- */}
      <Modal visible={!!shownCoupon} transparent animationType="fade" onRequestClose={() => setShownCoupon(null)}>
        <View style={styles.modalBackdrop}>
          {shownCoupon ? (
            <View style={styles.modalCard}>
              <Text style={styles.modalTitle}>{shownCoupon.promotion_title}</Text>
              <Text style={styles.modalSubtitle}>{shownCoupon.company_name}</Text>
              <View style={styles.qrBox}>
                <QRCode value={shownCoupon.code} size={200} />
              </View>
              <Text style={styles.code}>{shownCoupon.code}</Text>
              <Text style={styles.modalHint}>
                Muestra este código en el negocio. Vence el {formatDate(shownCoupon.expires_at)}.
              </Text>
              <AppButton
                label="Cerrar"
                variant="primary"
                style={styles.modalButton}
                onPress={() => setShownCoupon(null)}
              />
            </View>
          ) : null}
        </View>
      </Modal>
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
  chipText: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  redeemButton: {
    alignSelf: 'flex-start',
    minHeight: 44,
    marginTop: 10,
  },
  couponsSection: {
    marginBottom: 12,
  },
  coupon: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    padding: 16,
    marginBottom: 12,
  },
  pressed: {
    opacity: 0.85,
  },
  couponTitle: {
    fontSize: fontSize.body,
    fontWeight: '700',
    color: colors.white,
  },
  couponSubtitle: {
    fontSize: fontSize.small,
    color: colors.white,
    marginTop: 2,
  },
  message: {
    gap: 12,
  },
  messageText: {
    fontSize: fontSize.body,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  modalCard: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    padding: 24,
    alignItems: 'center',
    ...shadow,
  },
  modalTitle: {
    fontSize: fontSize.title,
    fontWeight: '700',
    color: colors.primary,
    textAlign: 'center',
  },
  modalSubtitle: {
    fontSize: fontSize.body,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  qrBox: {
    padding: 12,
    backgroundColor: colors.white,
  },
  code: {
    fontSize: fontSize.large,
    fontWeight: '800',
    letterSpacing: 2,
    color: colors.text,
    marginTop: 12,
  },
  modalHint: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
  },
  modalButton: {
    alignSelf: 'stretch',
    marginTop: 20,
  },
});
