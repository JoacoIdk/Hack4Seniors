import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Chess } from 'chess.js';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Modal, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Chessboard, { ChessboardRef } from 'react-native-chessboard';

import AppButton from '../../components/AppButton';
import { useApp } from '../../context/AppContext';
import { CHESS_PUZZLE, ChessMove } from '../../data/mockData';
import type { HomeStackParamList } from '../../navigation/types';
import { colors, fontSize, radius, shadow } from '../../theme';

type Props = NativeStackScreenProps<HomeStackParamList, 'ChessGame'>;

type BoardMove = Parameters<ChessboardRef['move']>[0];

const INITIAL_MESSAGE = 'Juegan las blancas. Da jaque mate en 3 jugadas.';
const REPLY_DELAY = 600;

// ===== Pantalla: Desafío Ajedrez (ChessGameScreen) =====
export default function ChessGameScreen({ navigation }: Props) {
  const { completeGame } = useApp();
  const { width } = useWindowDimensions();
  const boardSize = Math.min(width - 40, 420);

  const boardRef = useRef<ChessboardRef>(null);
  // Copia propia de la partida para validar jugadas con chess.js.
  const gameRef = useRef(new Chess(CHESS_PUZZLE.fen));
  // Índice de la próxima jugada del usuario dentro de la solución.
  const stepRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(INITIAL_MESSAGE);
  const [showExplanation, setShowExplanation] = useState(false);

  const clearPending = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
  };

  // Evita que una respuesta pendiente de las negras se ejecute tras salir.
  useEffect(() => () => clearPending(), []);

  const resetAttempt = () => {
    clearPending();
    gameRef.current = new Chess(CHESS_PUZZLE.fen);
    stepRef.current = 0;
    boardRef.current?.resetBoard(CHESS_PUZZLE.fen);
    setMessage(INITIAL_MESSAGE);
    setBusy(false);
  };

  const finishGame = useCallback(() => {
    completeGame('chess');
    Alert.alert('¡Jaque mate!', 'Resolviste el desafío y ganaste 5 puntos.', [
      { text: 'Continuar', onPress: () => navigation.goBack() },
    ], { cancelable: false });
  }, [completeGame, navigation]);

  const handleMove = useCallback(
    ({ move }: { move: { from: string; to: string; color: string } }) => {
      // Las respuestas de las negras las ejecuta la app; se ignoran aquí.
      if (move.color !== 'w') return;

      const game = gameRef.current;
      try {
        game.move({ from: move.from, to: move.to, promotion: 'q' });
      } catch {
        return;
      }

      if (game.isCheckmate()) {
        setBusy(true);
        setMessage('¡Jaque mate! ¡Excelente!');
        finishGame();
        return;
      }

      const expected = CHESS_PUZZLE.solution[stepRef.current];
      if (move.from !== expected.from || move.to !== expected.to) {
        game.undo();
        setBusy(true);
        setMessage('Esa no es la jugada. ¡Inténtalo de nuevo!');
        timeoutRef.current = setTimeout(() => {
          boardRef.current?.undo();
          setBusy(false);
        }, 400);
        return;
      }

      const reply: ChessMove = CHESS_PUZZLE.solution[stepRef.current + 1];
      stepRef.current += 2;
      setBusy(true);
      setMessage('¡Bien jugado! Ahora mueven las negras...');
      timeoutRef.current = setTimeout(async () => {
        game.move(reply);
        await boardRef.current?.move(reply as BoardMove);
        setBusy(false);
        setMessage('Tu turno. ¡Sigue buscando el mate!');
      }, REPLY_DELAY);
    },
    [finishGame],
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.messageBox}>
        <Ionicons name="information-circle" size={26} color={colors.accentDark} />
        <Text style={styles.messageText}>{message}</Text>
      </View>

      <View style={[styles.boardWrapper, { width: boardSize, height: boardSize }]}>
        <Chessboard
          ref={boardRef}
          fen={CHESS_PUZZLE.fen}
          boardSize={boardSize}
          gestureEnabled={!busy}
          onMove={handleMove}
          colors={{ black: colors.primary, white: '#EEF5F0' }}
        />
      </View>

      <View style={styles.controls}>
        <AppButton
          label="Reiniciar intento"
          icon={<Ionicons name="refresh" size={22} color={colors.white} />}
          onPress={resetAttempt}
        />
        <AppButton
          label="Explicación"
          variant="outline"
          icon={<Ionicons name="bulb-outline" size={22} color={colors.accentDark} />}
          onPress={() => setShowExplanation(true)}
        />
        <AppButton label="Volver" variant="primary" onPress={() => navigation.goBack()} />
      </View>

      <Modal
        visible={showExplanation}
        transparent
        animationType="fade"
        onRequestClose={() => setShowExplanation(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Explicación</Text>
            <Text style={styles.modalSolution}>1. Ta6+ Re7  2. Tb7+ Rd8  3. Ta8#</Text>
            <Text style={styles.modalText}>{CHESS_PUZZLE.explanation}</Text>
            <AppButton label="Entendido" variant="primary" onPress={() => setShowExplanation(false)} />
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}
// ===== Fin ChessGameScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 20,
    alignItems: 'center',
  },
  messageBox: {
    alignSelf: 'stretch',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.accentLight,
    borderRadius: radius.md,
    padding: 14,
    marginBottom: 20,
  },
  messageText: {
    flex: 1,
    fontSize: fontSize.body,
    color: colors.text,
    fontWeight: '600',
  },
  boardWrapper: {
    borderRadius: radius.sm,
    overflow: 'hidden',
    ...shadow,
  },
  controls: {
    alignSelf: 'stretch',
    gap: 12,
    marginTop: 24,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center',
    padding: 24,
  },
  modalCard: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    padding: 24,
    gap: 14,
    ...shadow,
  },
  modalTitle: {
    fontSize: fontSize.title,
    fontWeight: '700',
    color: colors.primary,
  },
  modalSolution: {
    fontSize: fontSize.body,
    fontWeight: '700',
    color: colors.accentDark,
  },
  modalText: {
    fontSize: fontSize.body,
    color: colors.text,
    lineHeight: 26,
  },
});
