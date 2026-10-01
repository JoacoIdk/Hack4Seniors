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

import type { CrosswordData, CrosswordWord, Puzzle } from '../../api/types';
import AppButton from '../../components/AppButton';
import type { HomeStackParamList } from '../../navigation/types';
import { colors, fontSize, radius } from '../../theme';
import { PuzzleStatus, rewardMessage, SolveFn, usePuzzle } from './usePuzzle';

type Props = NativeStackScreenProps<HomeStackParamList, 'CrosswordGame'>;

type CellKey = string;

const cellKey = (row: number, col: number): CellKey => `${row}-${col}`;

// Compara sin distinguir mayúsculas ni tildes.
const normalize = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();

const directionLabel = (word: CrosswordWord) => (word.direction === 'across' ? 'Horizontal' : 'Vertical');

// ----- Índices calculados a partir de los datos del juego -----
function buildIndexes({ cells, words }: CrosswordData) {
  const wordById: Record<string, CrosswordWord> = Object.fromEntries(words.map((w) => [w.id, w]));
  const wordCells: Record<string, CellKey[]> = Object.fromEntries(
    words.map((w) => [
      w.id,
      Array.from({ length: w.length }, (_, i) =>
        w.direction === 'across' ? cellKey(w.row, w.col + i) : cellKey(w.row + i, w.col),
      ),
    ]),
  );
  const cellWords: Record<CellKey, string[]> = {};
  words.forEach((w) => {
    wordCells[w.id].forEach((key) => {
      (cellWords[key] ??= []).push(w.id);
    });
  });
  const cellNumbers: Record<CellKey, number> = Object.fromEntries(words.map((w) => [cellKey(w.row, w.col), w.number]));
  const grid = cells.map((row) => row.split('').map((c) => c === '#'));
  return { wordById, wordCells, cellWords, cellNumbers, grid };
}

// ===== Pantalla: Mini Crucigrama (CrosswordGameScreen) =====
export default function CrosswordGameScreen({ navigation, route }: Props) {
  const { puzzle, error, reload, solve } = usePuzzle<CrosswordData>(route.params.puzzleId);

  useEffect(() => {
    if (puzzle) navigation.setOptions({ title: puzzle.title });
  }, [navigation, puzzle]);

  if (!puzzle) return <PuzzleStatus error={error} onRetry={reload} />;
  return <CrosswordGame puzzle={puzzle} solve={solve} onDone={() => navigation.goBack()} />;
}

type GameProps = {
  puzzle: Puzzle<CrosswordData>;
  solve: SolveFn;
  onDone: () => void;
};

function CrosswordGame({ puzzle, solve, onDone }: GameProps) {
  const { words } = puzzle.data;
  const { wordById, wordCells, cellWords, cellNumbers, grid } = useMemo(() => buildIndexes(puzzle.data), [puzzle]);
  const size = grid.length;

  const { width } = useWindowDimensions();
  const cellSize = Math.floor((Math.min(width, 480) - 40) / size);

  const inputRefs = useRef<Record<CellKey, TextInput | null>>({});
  // Última respuesta enviada, para no reenviar la misma combinación de letras.
  const submittedRef = useRef<string | null>(null);

  const [letters, setLetters] = useState<Record<CellKey, string>>({});
  const [activeWordId, setActiveWordId] = useState(words[0].id);
  const [focusedKey, setFocusedKey] = useState<CellKey | null>(null);

  const activeWord = wordById[activeWordId];
  const activeCells = wordCells[activeWordId];

  // Cuando todas las casillas tienen letra, se arma la respuesta { idPalabra: "PALABRA" }.
  const answer = useMemo(() => {
    const filled = Object.keys(cellWords).every((key) => letters[key]);
    if (!filled) return null;
    return Object.fromEntries(
      words.map((w) => [w.id, wordCells[w.id].map((key) => normalize(letters[key])).join('')]),
    );
  }, [letters, words, wordCells, cellWords]);

  useEffect(() => {
    if (!answer) return;
    const serialized = JSON.stringify(answer);
    if (submittedRef.current === serialized) return;
    submittedRef.current = serialized;
    Keyboard.dismiss();

    solve(answer)
      .then((result) => {
        if (!result.correct) {
          Alert.alert('Revisa tus palabras', 'Algunas palabras no son correctas. ¡Inténtalo de nuevo!');
          return;
        }
        Alert.alert('¡Crucigrama completado!', `Excelente memoria. ${rewardMessage(result)}`, [
          { text: 'Continuar', onPress: onDone },
        ], { cancelable: false });
      })
      .catch((e) => {
        submittedRef.current = null;
        Alert.alert('No se pudo enviar tu respuesta', e instanceof Error ? e.message : '');
      });
  }, [answer, solve, onDone]);

  const focusCell = (key: CellKey) => inputRefs.current[key]?.focus();

  const handleFocus = (key: CellKey) => {
    setFocusedKey(key);
    if (!activeCells.includes(key)) setActiveWordId(cellWords[key][0]);
  };

  // Tocar de nuevo una celda de cruce alterna entre horizontal y vertical.
  const handlePressIn = (key: CellKey) => {
    const ids = cellWords[key];
    if (focusedKey === key && ids.length > 1) {
      setActiveWordId(ids.find((id) => id !== activeWordId) ?? activeWordId);
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
    const cells = wordCells[word.id];
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
          {activeWord.number} · {directionLabel(activeWord)} · {activeWord.length} letras
        </Text>
        <Text style={styles.clueText}>{activeWord.clue}</Text>
      </View>

      {/* ----- Cuadrícula ----- */}
      <View style={styles.grid}>
        {grid.map((rowCells, row) => (
          <View key={row} style={styles.row}>
            {rowCells.map((isCell, col) => {
              const key = cellKey(row, col);
              if (!isCell) {
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
                  {cellNumbers[key] ? <Text style={styles.cellNumber}>{cellNumbers[key]}</Text> : null}
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
      {words.map((word) => (
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

      <AppButton label="Volver" variant="primary" style={styles.backButton} onPress={onDone} />
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
