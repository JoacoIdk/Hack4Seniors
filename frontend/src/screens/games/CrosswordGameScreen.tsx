import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Keyboard,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TextInputKeyPressEventData,
  useWindowDimensions,
  View,
} from 'react-native';

import AppButton from '../../components/AppButton';
import { useApp } from '../../context/AppContext';
import { CROSSWORD_GRID, CROSSWORD_WORDS, CrosswordWord } from '../../data/mockData';
import type { HomeStackParamList } from '../../navigation/types';
import { colors, fontSize, radius } from '../../theme';

type Props = NativeStackScreenProps<HomeStackParamList, 'CrosswordGame'>;

type CellKey = string;

const SIZE = CROSSWORD_GRID.length;

const cellKey = (row: number, col: number): CellKey => `${row}-${col}`;

// Compara sin distinguir mayúsculas ni tildes.
const normalize = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();

// ----- Índices precalculados a partir de los datos fijos -----
const WORD_BY_ID: Record<string, CrosswordWord> = Object.fromEntries(CROSSWORD_WORDS.map((w) => [w.id, w]));

const WORD_CELLS: Record<string, CellKey[]> = Object.fromEntries(
  CROSSWORD_WORDS.map((w) => [
    w.id,
    Array.from({ length: w.answer.length }, (_, i) =>
      w.direction === 'across' ? cellKey(w.row, w.col + i) : cellKey(w.row + i, w.col),
    ),
  ]),
);

const CELL_WORDS: Record<CellKey, string[]> = {};
CROSSWORD_WORDS.forEach((w) => {
  WORD_CELLS[w.id].forEach((key) => {
    (CELL_WORDS[key] ??= []).push(w.id);
  });
});

const CELL_NUMBERS: Record<CellKey, number> = Object.fromEntries(
  CROSSWORD_WORDS.map((w) => [cellKey(w.row, w.col), w.number]),
);

const directionLabel = (word: CrosswordWord) => (word.direction === 'across' ? 'Horizontal' : 'Vertical');

// ===== Pantalla: Mini Crucigrama (CrosswordGameScreen) =====
export default function CrosswordGameScreen({ navigation }: Props) {
  const { completeGame } = useApp();
  const { width } = useWindowDimensions();
  const cellSize = Math.floor((Math.min(width, 480) - 40) / SIZE);

  const inputRefs = useRef<Record<CellKey, TextInput | null>>({});
  const finishedRef = useRef(false);

  const [letters, setLetters] = useState<Record<CellKey, string>>({});
  const [activeWordId, setActiveWordId] = useState(CROSSWORD_WORDS[0].id);
  const [focusedKey, setFocusedKey] = useState<CellKey | null>(null);

  const activeWord = WORD_BY_ID[activeWordId];
  const activeCells = WORD_CELLS[activeWordId];

  const isSolved = useMemo(
    () =>
      Object.keys(CELL_WORDS).every((key) => {
        const [row, col] = key.split('-').map(Number);
        return normalize(letters[key] ?? '') === CROSSWORD_GRID[row][col];
      }),
    [letters],
  );

  useEffect(() => {
    if (!isSolved || finishedRef.current) return;
    finishedRef.current = true;
    Keyboard.dismiss();
    completeGame('crossword');
    Alert.alert('¡Crucigrama completado!', 'Excelente memoria. Ganaste 5 puntos.', [
      { text: 'Continuar', onPress: () => navigation.goBack() },
    ], { cancelable: false });
  }, [isSolved, completeGame, navigation]);

  const focusCell = (key: CellKey) => inputRefs.current[key]?.focus();

  const handleFocus = (key: CellKey) => {
    setFocusedKey(key);
    if (!activeCells.includes(key)) setActiveWordId(CELL_WORDS[key][0]);
  };

  // Tocar de nuevo una celda de cruce alterna entre horizontal y vertical.
  const handlePressIn = (key: CellKey) => {
    const words = CELL_WORDS[key];
    if (focusedKey === key && words.length > 1) {
      setActiveWordId(words.find((id) => id !== activeWordId) ?? activeWordId);
    }
  };

  const handleChange = (key: CellKey, text: string) => {
    const letter = text.toUpperCase().replace(/[^A-ZÁÉÍÓÚÜÑ]/g, '').slice(-1);
    setLetters((prev) => ({ ...prev, [key]: letter }));

    if (!letter) return;
    const index = activeCells.indexOf(key);
    if (index >= 0 && index < activeCells.length - 1) focusCell(activeCells[index + 1]);
  };

  // Borrar en una celda vacía retrocede a la anterior de la palabra.
  const handleKeyPress = (key: CellKey, event: NativeSyntheticEvent<TextInputKeyPressEventData>) => {
    if (event.nativeEvent.key !== 'Backspace' || letters[key]) return;
    const index = activeCells.indexOf(key);
    if (index > 0) {
      const previous = activeCells[index - 1];
      setLetters((prev) => ({ ...prev, [previous]: '' }));
      focusCell(previous);
    }
  };

  const selectWord = (word: CrosswordWord) => {
    setActiveWordId(word.id);
    const cells = WORD_CELLS[word.id];
    focusCell(cells.find((key) => !letters[key]) ?? cells[0]);
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {/* ----- Pista activa ----- */}
      <View style={styles.clueBox}>
        <Text style={styles.clueLabel}>
          {activeWord.number} · {directionLabel(activeWord)} · {activeWord.answer.length} letras
        </Text>
        <Text style={styles.clueText}>{activeWord.clue}</Text>
      </View>

      {/* ----- Cuadrícula ----- */}
      <View style={styles.grid}>
        {CROSSWORD_GRID.map((rowLetters, row) => (
          <View key={row} style={styles.row}>
            {rowLetters.map((solution, col) => {
              const key = cellKey(row, col);
              if (solution === null) {
                return <View key={key} style={{ width: cellSize, height: cellSize }} />;
              }
              const inActiveWord = activeCells.includes(key);
              const isFocused = focusedKey === key;
              return (
                <View
                  key={key}
                  style={[
                    styles.cell,
                    { width: cellSize, height: cellSize },
                    inActiveWord && styles.cellActiveWord,
                    isFocused && styles.cellFocused,
                  ]}
                >
                  {CELL_NUMBERS[key] ? <Text style={styles.cellNumber}>{CELL_NUMBERS[key]}</Text> : null}
                  <TextInput
                    ref={(ref) => {
                      inputRefs.current[key] = ref;
                    }}
                    style={[styles.cellInput, { fontSize: cellSize * 0.5 }]}
                    value={letters[key] ?? ''}
                    onChangeText={(text) => handleChange(key, text)}
                    onKeyPress={(event) => handleKeyPress(key, event)}
                    onFocus={() => handleFocus(key)}
                    onPressIn={() => handlePressIn(key)}
                    autoCapitalize="characters"
                    autoCorrect={false}
                    autoComplete="off"
                    caretHidden
                    selectTextOnFocus
                    textAlign="center"
                    accessibilityLabel={`Fila ${row + 1}, columna ${col + 1}`}
                  />
                </View>
              );
            })}
          </View>
        ))}
      </View>

      {/* ----- Lista de pistas ----- */}
      <Text style={styles.sectionTitle}>Pistas</Text>
      {CROSSWORD_WORDS.map((word) => (
        <Pressable
          key={word.id}
          onPress={() => selectWord(word)}
          accessibilityRole="button"
          style={[styles.clueItem, word.id === activeWordId && styles.clueItemActive]}
        >
          <Text style={styles.clueItemNumber}>{word.number}</Text>
          <View style={styles.clueItemBody}>
            <Text style={styles.clueItemDirection}>{directionLabel(word)}</Text>
            <Text style={styles.clueItemText}>{word.clue}</Text>
          </View>
        </Pressable>
      ))}

      <AppButton label="Volver" variant="primary" style={styles.backButton} onPress={() => navigation.goBack()} />
    </ScrollView>
  );
}
// ===== Fin CrosswordGameScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 20,
  },
  clueBox: {
    backgroundColor: colors.accentLight,
    borderRadius: radius.md,
    padding: 16,
    marginBottom: 20,
    minHeight: 90,
  },
  clueLabel: {
    fontSize: fontSize.small,
    fontWeight: '700',
    color: colors.accentDark,
    marginBottom: 6,
  },
  clueText: {
    fontSize: fontSize.large,
    color: colors.text,
    fontWeight: '600',
  },
  grid: {
    alignSelf: 'center',
  },
  row: {
    flexDirection: 'row',
  },
  cell: {
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.white,
    justifyContent: 'center',
  },
  cellActiveWord: {
    backgroundColor: colors.accentLight,
  },
  cellFocused: {
    borderWidth: 3,
    borderColor: colors.accent,
  },
  cellNumber: {
    position: 'absolute',
    top: 1,
    left: 3,
    fontSize: 10,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  cellInput: {
    flex: 1,
    padding: 0,
    fontWeight: '700',
    color: colors.text,
  },
  sectionTitle: {
    fontSize: fontSize.large,
    fontWeight: '700',
    color: colors.text,
    marginTop: 28,
    marginBottom: 12,
  },
  clueItem: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    marginBottom: 10,
  },
  clueItemActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentLight,
  },
  clueItemNumber: {
    width: 36,
    fontSize: fontSize.large,
    fontWeight: '800',
    color: colors.primary,
    textAlign: 'center',
  },
  clueItemBody: {
    flex: 1,
    marginLeft: 8,
  },
  clueItemDirection: {
    fontSize: fontSize.small,
    color: colors.textSecondary,
  },
  clueItemText: {
    fontSize: fontSize.body,
    color: colors.text,
  },
  backButton: {
    marginTop: 16,
  },
});
