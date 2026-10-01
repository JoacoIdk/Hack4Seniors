import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
} from 'react-native';

import AppButton from '../components/AppButton';
import ScreenBanner from '../components/ScreenBanner';
import { useApp } from '../context/AppContext';
import { colors, fontSize, radius } from '../theme';

type Mode = 'login' | 'register';

// Nombre de usuario válido para el backend: 3 a 30 letras minúsculas, números, "_" o ".".
const USERNAME_PATTERN = /^[a-z0-9_.]{3,30}$/;

function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput style={styles.input} placeholderTextColor={colors.textSecondary} {...props} />
    </View>
  );
}

// ===== Pantalla: Inicio de sesión y registro (AuthScreen) =====
export default function AuthScreen() {
  const { signIn, register } = useApp();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRegister = mode === 'register';

  const validate = () => {
    if (!email.trim() || !password) return 'Escribe tu correo y contraseña.';
    if (!isRegister) return null;
    if (!displayName.trim()) return 'Escribe tu nombre.';
    if (!USERNAME_PATTERN.test(username.trim().toLowerCase())) {
      return 'El nombre de usuario debe tener entre 3 y 30 letras o números, sin espacios.';
    }
    if (password.length < 8) return 'La contraseña debe tener al menos 8 caracteres.';
    return null;
  };

  const submit = async () => {
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (isRegister) {
        await register({
          email: email.trim(),
          password,
          display_name: displayName.trim(),
          username: username.trim().toLowerCase(),
        });
      } else {
        await signIn(email.trim(), password);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ocurrió un error. Inténtalo de nuevo.');
      setBusy(false);
    }
  };

  const switchMode = () => {
    setMode(isRegister ? 'login' : 'register');
    setError(null);
  };

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScreenBanner
        title={isRegister ? 'Crear cuenta' : '¡Bienvenido!'}
        subtitle={isRegister ? 'Completa tus datos para comenzar' : 'Ingresa con tu correo y contraseña'}
      />

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {isRegister ? (
          <>
            <Field label="Tu nombre" value={displayName} onChangeText={setDisplayName} placeholder="Rosa Martínez" />
            <Field
              label="Nombre de usuario"
              value={username}
              onChangeText={setUsername}
              placeholder="rosa.martinez"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </>
        ) : null}
        <Field
          label="Correo electrónico"
          value={email}
          onChangeText={setEmail}
          placeholder="nombre@correo.cl"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          autoComplete="email"
        />
        <Field
          label="Contraseña"
          value={password}
          onChangeText={setPassword}
          placeholder={isRegister ? 'Al menos 8 caracteres' : ''}
          secureTextEntry
          autoComplete={isRegister ? 'new-password' : 'current-password'}
          onSubmitEditing={submit}
        />

        {error ? (
          <View style={styles.errorBox}>
            <Ionicons name="alert-circle" size={24} color={colors.error} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <AppButton
          label={busy ? 'Cargando…' : isRegister ? 'Crear cuenta' : 'Entrar'}
          variant="primary"
          disabled={busy}
          onPress={submit}
          style={styles.submit}
        />

        <Pressable onPress={switchMode} style={styles.switch} accessibilityRole="button" disabled={busy}>
          <Text style={styles.switchText}>
            {isRegister ? '¿Ya tienes cuenta? Inicia sesión' : '¿No tienes cuenta? Créala aquí'}
          </Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
// ===== Fin AuthScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 20,
  },
  field: {
    marginBottom: 16,
  },
  label: {
    fontSize: fontSize.body,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 6,
  },
  input: {
    minHeight: 56,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    fontSize: fontSize.body,
    color: colors.text,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#FBEAEA',
    borderRadius: radius.md,
    padding: 14,
    marginBottom: 16,
  },
  errorText: {
    flex: 1,
    fontSize: fontSize.body,
    color: colors.error,
  },
  submit: {
    marginTop: 4,
  },
  switch: {
    alignSelf: 'center',
    padding: 16,
  },
  switchText: {
    fontSize: fontSize.body,
    color: colors.accentDark,
    textDecorationLine: 'underline',
  },
});
