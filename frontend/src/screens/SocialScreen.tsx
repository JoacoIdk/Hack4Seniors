import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { BarcodeScanningResult, CameraView, useCameraPermissions } from 'expo-camera';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
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
import QRCode from 'react-native-qrcode-svg';

import { api } from '../api/client';
import type { FriendCode, FriendScanOut, Me, PublicProfile } from '../api/types';
import AppButton from '../components/AppButton';
import ScreenBanner from '../components/ScreenBanner';
import { useApp } from '../context/AppContext';
import { colors, fontSize, radius, shadow } from '../theme';

const SCAN_MESSAGES: Record<FriendScanOut['status'], (name: string) => [string, string]> = {
  pending: (name) => ['¡Casi listo!', `Ahora pídele a ${name} que escanee tu código para ser amigos.`],
  friends: (name) => ['¡Nuevo amigo!', `Ahora tú y ${name} son amigos.`],
  already_friends: (name) => ['Ya son amigos', `Tú y ${name} ya eran amigos.`],
};

// ===== Pantalla: Social (SocialScreen) =====
export default function SocialScreen() {
  const { me, setMe, signOut } = useApp();
  const [draft, setDraft] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [friends, setFriends] = useState<PublicProfile[]>([]);
  const [qrVisible, setQrVisible] = useState(false);
  const [scannerVisible, setScannerVisible] = useState(false);

  const loadFriends = useCallback(async () => {
    try {
      setFriends(await api<PublicProfile[]>('/friends'));
    } catch {
      // La lista de amigos no es crítica; se reintenta al volver a la pestaña.
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void loadFriends();
    }, [loadFriends]),
  );

  // El estado "Estoy pensando..." se guarda como la biografía del perfil.
  const publishStatus = async () => {
    const text = draft.trim();
    if (!text) return;
    setSaving(true);
    try {
      setMe(await api<Me>('/me', { method: 'PATCH', body: { bio: text } }));
      setDraft('');
      setEditing(false);
    } catch (e) {
      Alert.alert('No se pudo publicar', e instanceof Error ? e.message : '');
    } finally {
      setSaving(false);
    }
  };

  const cancelEditing = () => {
    setDraft('');
    setEditing(false);
  };

  const confirmSignOut = () =>
    Alert.alert('Cerrar sesión', '¿Quieres salir de tu cuenta?', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Salir', style: 'destructive', onPress: () => void signOut() },
    ]);

  const handleScanned = async (code: string) => {
    setScannerVisible(false);
    try {
      const result = await api<FriendScanOut>('/friends/scan', { method: 'POST', body: { code } });
      const [title, message] = SCAN_MESSAGES[result.status](result.user.display_name);
      Alert.alert(title, message);
      if (result.status === 'friends') void loadFriends();
    } catch (e) {
      Alert.alert('No se pudo leer el código', e instanceof Error ? e.message : '');
    }
  };

  const status = me?.bio ?? '';

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
        <Text style={styles.name}>{me?.display_name}</Text>
        {me?.username ? <Text style={styles.username}>@{me.username}</Text> : null}

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
            onPress={() => setScannerVisible(true)}
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
                label={saving ? 'Publicando…' : 'Publicar'}
                variant="primary"
                style={styles.editorButton}
                disabled={!draft.trim() || saving}
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

        {/* ----- Amigos ----- */}
        <Text style={styles.sectionTitle}>Mis amigos</Text>
        {friends.length === 0 ? (
          <Text style={styles.statusEmpty}>
            Aún no tienes amigos en la app. Para agregar a alguien, escaneen sus códigos QR en persona.
          </Text>
        ) : (
          friends.map((friend) => (
            <View key={friend.id} style={styles.friend}>
              <View style={styles.friendAvatar}>
                <Ionicons name="person" size={26} color={colors.primary} />
              </View>
              <View style={styles.friendBody}>
                <Text style={styles.friendName}>{friend.display_name}</Text>
                {friend.bio ? <Text style={styles.friendBio}>{friend.bio}</Text> : null}
              </View>
            </View>
          ))
        )}

        <AppButton label="Cerrar sesión" variant="outline" style={styles.signOut} onPress={confirmSignOut} />
      </ScrollView>

      <FriendCodeModal visible={qrVisible} username={me?.username} onClose={() => setQrVisible(false)} />
      <ScannerModal visible={scannerVisible} onScanned={handleScanned} onClose={() => setScannerVisible(false)} />
    </KeyboardAvoidingView>
  );
}

// ----- Modal con mi QR de amistad (el código vence, así que se renueva solo) -----
function FriendCodeModal({ visible, username, onClose }: { visible: boolean; username?: string | null; onClose: () => void }) {
  const [friendCode, setFriendCode] = useState<FriendCode | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const fetchCode = async () => {
      try {
        const code = await api<FriendCode>('/me/friend-code');
        if (cancelled) return;
        setFriendCode(code);
        setError(null);
        timer = setTimeout(fetchCode, Math.max(code.expires_in - 15, 15) * 1000);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'No se pudo generar tu código.');
      }
    };
    void fetchCode();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      setFriendCode(null);
    };
  }, [visible]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Mi código QR</Text>
          {error ? (
            <Text style={styles.modalSubtitle}>{error}</Text>
          ) : friendCode ? (
            <QRCode value={friendCode.code} size={220} />
          ) : (
            <View style={styles.qrPlaceholder}>
              <ActivityIndicator size="large" color={colors.accent} />
            </View>
          )}
          {username ? <Text style={styles.modalSubtitle}>@{username}</Text> : null}
          <Text style={styles.modalHint}>Pide a tu amigo que lo escanee con "Leer QR", y luego escanea el suyo.</Text>
          <AppButton label="Cerrar" variant="primary" style={styles.modalButton} onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

// ----- Modal con la cámara para leer el QR de un amigo -----
function ScannerModal({
  visible,
  onScanned,
  onClose,
}: {
  visible: boolean;
  onScanned: (code: string) => void;
  onClose: () => void;
}) {
  const [permission, requestPermission] = useCameraPermissions();
  // La cámara puede reportar el mismo código varias veces seguidas.
  const handledRef = useRef(false);

  useEffect(() => {
    if (visible) handledRef.current = false;
  }, [visible]);

  const handleBarcode = ({ data }: BarcodeScanningResult) => {
    if (handledRef.current) return;
    handledRef.current = true;
    onScanned(data);
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.scanner}>
        {permission?.granted ? (
          <CameraView
            style={StyleSheet.absoluteFill}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
            onBarcodeScanned={handleBarcode}
          />
        ) : (
          <View style={styles.permissionBox}>
            <Text style={styles.permissionText}>Necesitamos usar la cámara para leer el código QR de tu amigo.</Text>
            <AppButton label="Permitir cámara" onPress={requestPermission} />
          </View>
        )}
        <View style={styles.scannerFooter}>
          {permission?.granted ? <Text style={styles.scannerHint}>Apunta la cámara al código QR</Text> : null}
          <AppButton label="Cancelar" variant="primary" onPress={onClose} />
        </View>
      </View>
    </Modal>
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
  modalHint: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
  },
  qrPlaceholder: {
    width: 220,
    height: 220,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sectionTitle: {
    fontSize: fontSize.large,
    fontWeight: '700',
    color: colors.text,
    marginTop: 28,
    marginBottom: 12,
  },
  friend: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 10,
  },
  friendAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  friendBody: {
    flex: 1,
  },
  friendName: {
    fontSize: fontSize.body,
    fontWeight: '700',
    color: colors.text,
  },
  friendBio: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
    marginTop: 2,
  },
  signOut: {
    marginTop: 28,
  },
  scanner: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'flex-end',
  },
  permissionBox: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
    gap: 16,
  },
  permissionText: {
    fontSize: fontSize.large,
    color: colors.white,
    textAlign: 'center',
  },
  scannerFooter: {
    padding: 24,
    paddingBottom: 48,
    gap: 12,
  },
  scannerHint: {
    fontSize: fontSize.large,
    fontWeight: '700',
    color: colors.white,
    textAlign: 'center',
  },
});
