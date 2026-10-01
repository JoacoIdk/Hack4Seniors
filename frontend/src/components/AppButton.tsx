import React, { ReactNode } from 'react';
import { Pressable, StyleProp, StyleSheet, Text, View, ViewStyle } from 'react-native';

import { colors, fontSize, radius } from '../theme';

type Variant = 'accent' | 'primary' | 'outline';

type Props = {
  label: string;
  onPress: () => void;
  variant?: Variant;
  icon?: ReactNode;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
};

// ===== Componente: AppButton (botón grande y accesible) =====
export default function AppButton({ label, onPress, variant = 'accent', icon, disabled, style }: Props) {
  const isOutline = variant === 'outline';

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        styles[variant],
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
        style,
      ]}
    >
      {icon ? <View style={styles.icon}>{icon}</View> : null}
      <Text style={[styles.label, isOutline && styles.labelOutline]}>{label}</Text>
    </Pressable>
  );
}
// ===== Fin AppButton =====

const styles = StyleSheet.create({
  base: {
    minHeight: 56,
    paddingHorizontal: 18,
    borderRadius: radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  accent: {
    backgroundColor: colors.accent,
  },
  primary: {
    backgroundColor: colors.primary,
  },
  outline: {
    backgroundColor: colors.white,
    borderWidth: 2,
    borderColor: colors.accent,
  },
  disabled: {
    backgroundColor: colors.disabled,
    borderColor: colors.disabled,
  },
  pressed: {
    opacity: 0.8,
  },
  icon: {
    marginRight: 10,
  },
  label: {
    color: colors.white,
    fontSize: fontSize.body,
    fontWeight: '700',
    textAlign: 'center',
  },
  labelOutline: {
    color: colors.accentDark,
  },
});
