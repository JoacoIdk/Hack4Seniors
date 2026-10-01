import React, { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, fontSize, radius } from '../theme';

type Props = {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  children?: ReactNode;
};

// ===== Componente: ScreenBanner (cabecera verde de cada pestaña) =====
export default function ScreenBanner({ title, subtitle, right, children }: Props) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.banner, { paddingTop: insets.top + 16 }]}>
      <View style={styles.row}>
        <View style={styles.texts}>
          {title ? <Text style={styles.title}>{title}</Text> : null}
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
        {right}
      </View>
      {children}
    </View>
  );
}
// ===== Fin ScreenBanner =====

const styles = StyleSheet.create({
  banner: {
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingBottom: 24,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.lg,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  texts: {
    flex: 1,
  },
  title: {
    color: colors.white,
    fontSize: fontSize.title,
    fontWeight: '700',
  },
  subtitle: {
    color: colors.primaryLight,
    fontSize: fontSize.body,
    marginTop: 4,
  },
});
