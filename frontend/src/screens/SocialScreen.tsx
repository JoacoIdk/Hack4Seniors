import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import AppButton from '../components/AppButton';
import ScreenBanner from '../components/ScreenBanner';
import { USER_PROFILE } from '../data/mockData';
import { colors, fontSize, radius, shadow } from '../theme';

// ===== Pantalla: Social (SocialScreen) =====
export default function SocialScreen() {
  const [status, setStatus] = useState('');
  const [draft, setDraft] = useState('');
  const [editing, setEditing] = useState(false);
  const [qrVisible, setQrVisible] = useState(false);

  const publishStatus = () => {
    const text = draft.trim();
    if (!text) return;
    setStatus(text);
    setDraft('');
    setEditing(false);
  };

  const cancelEditing = () => {
    setDraft('');
    setEditing(false);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {/* ----- Cabecera con ícono de mensajería ----- */}
      <ScreenBanner
        title="Social"
        right={
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Mensajes"
            hitSlop={12}
            onPress={() => Alert.alert('Mensajes', 'Próximamente podrás conversar con tus amigos.')}
          >
            <Ionicons name="chatbubble-ellipses-outline" size={30} color={colors.white} />
          </Pressable>
        }
      />

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {/* ----- Perfil ----- */}
        <View style={styles.avatar}>
          <Ionicons name="person" size={64} color={colors.primary} />
        </View>
        <Text style={styles.name}>{USER_PROFILE.name}</Text>
        <Text style={styles.username}>{USER_PROFILE.username}</Text>

        {/* ----- Acciones QR ----- */}
        <View style={styles.qrRow}>
          <AppButton
            label="Mostrar QR"
            style={styles.qrButton}
            icon={<Ionicons name="qr-code-outline" size={22} color={colors.white} />}
            onPress={() => setQrVisible(true)}
          />
          <AppButton
            label="Leer QR"
            variant="outline"
            style={styles.qrButton}
            icon={<Ionicons name="scan-outline" size={22} color={colors.accentDark} />}
            onPress={() => Alert.alert('Leer QR', 'Aquí se abrirá la cámara para escanear el QR de un amigo.')}
          />
        </View>

        {/* ----- Estado ----- */}
        <View style={styles.statusCard}>
          <Text style={styles.statusLabel}>Estoy pensando...</Text>
          <Text style={[styles.statusText, !status && styles.statusEmpty]}>
            {status || 'Aún no has compartido nada.'}
          </Text>
        </View>

        {/* ----- Input de estado ----- */}
        {editing ? (
          <View style={styles.editor}>
            <TextInput
              style={styles.input}
              value={draft}
              onChangeText={setDraft}
              placeholder="Escribe lo que estás pensando"
              placeholderTextColor={colors.textSecondary}
              multiline
              autoFocus
              maxLength={200}
            />
            <View style={styles.editorActions}>
              <AppButton label="Cancelar" variant="outline" style={styles.editorButton} onPress={cancelEditing} />
              <AppButton
                label="Publicar"
                variant="primary"
                style={styles.editorButton}
                disabled={!draft.trim()}
                onPress={publishStatus}
              />
            </View>
          </View>
        ) : (
          <AppButton
            label="¿Qué estás pensando?"
            variant="outline"
            icon={<Ionicons name="create-outline" size={22} color={colors.accentDark} />}
            onPress={() => setEditing(true)}
          />
        )}
      </ScrollView>

      {/* ----- Modal del QR (maqueta) ----- */}
      <Modal visible={qrVisible} transparent animationType="fade" onRequestClose={() => setQrVisible(false)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Mi código QR</Text>
            <Ionicons name="qr-code" size={200} color={colors.text} />
            <Text style={styles.modalSubtitle}>{USER_PROFILE.username}</Text>
            <AppButton label="Cerrar" variant="primary" style={styles.modalButton} onPress={() => setQrVisible(false)} />
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}
// ===== Fin SocialScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 20,
    alignItems: 'stretch',
  },
  avatar: {
    alignSelf: 'center',
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.primaryLight,
    borderWidth: 4,
    borderColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
  },
  name: {
    textAlign: 'center',
    fontSize: fontSize.title,
    fontWeight: '700',
    color: colors.text,
    marginTop: 12,
  },
  username: {
    textAlign: 'center',
    fontSize: fontSize.body,
    color: colors.textSecondary,
    marginTop: 2,
  },
  qrRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  qrButton: {
    flex: 1,
    paddingHorizontal: 10,
  },
  statusCard: {
    backgroundColor: colors.accentLight,
    borderRadius: radius.md,
    padding: 18,
    marginTop: 20,
    marginBottom: 16,
  },
  statusLabel: {
    fontSize: fontSize.small,
    fontWeight: '700',
    color: colors.accentDark,
    marginBottom: 6,
  },
  statusText: {
    fontSize: fontSize.large,
    color: colors.text,
    lineHeight: 30,
  },
  statusEmpty: {
    color: colors.textSecondary,
    fontStyle: 'italic',
    fontSize: fontSize.body,
  },
  editor: {
    gap: 12,
  },
  input: {
    minHeight: 100,
    borderWidth: 2,
    borderColor: colors.accent,
    borderRadius: radius.md,
    padding: 14,
    fontSize: fontSize.body,
    color: colors.text,
    textAlignVertical: 'top',
  },
  editorActions: {
    flexDirection: 'row',
    gap: 12,
  },
  editorButton: {
    flex: 1,
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
    marginBottom: 16,
  },
  modalSubtitle: {
    fontSize: fontSize.body,
    color: colors.textSecondary,
    marginTop: 12,
  },
  modalButton: {
    alignSelf: 'stretch',
    marginTop: 20,
  },
});
