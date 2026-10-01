// Todos los datos del prototipo están fijos (hardcoded) en este archivo.
import type { Ionicons } from '@expo/vector-icons';

import type { GameId } from '../context/AppContext';

// ---------------------------------------------------------------------------
// Desafíos (Inicio)
// ---------------------------------------------------------------------------
export const CHALLENGE_PLACES = ['una plaza', 'un café', 'un negocio'];

export const CHALLENGES = {
  hard: {
    points: 15,
    actions: ['saluda a un desconocido', 'pregunta la hora', 'haz un cumplido'],
  },
  easy: {
    points: 10,
    actions: ['camina 15 minutos', 'fotografía un ave', 'fotografía una flor'],
  },
} as const;

export type ChallengeKind = keyof typeof CHALLENGES;

// ---------------------------------------------------------------------------
// Recompensas (Mis puntos)
// ---------------------------------------------------------------------------
export type Reward = {
  id: string;
  food: string;
  business: string;
  discount: number; // 10% a 25%
  cost: number; // 50 a 200, múltiplos de 10
};

export const REWARDS: Reward[] = [
  { id: 'r1', food: 'Empanada de pino', business: 'Panadería La Espiga', discount: 10, cost: 50 },
  { id: 'r2', food: 'Té con galletas', business: 'Salón de Té Las Camelias', discount: 10, cost: 60 },
  { id: 'r3', food: 'Café con medialuna', business: 'Café Aroma', discount: 15, cost: 80 },
  { id: 'r4', food: 'Helado doble', business: 'Heladería Polo Sur', discount: 25, cost: 120 },
  { id: 'r5', food: 'Almuerzo del día', business: 'Restaurante El Rincón', discount: 20, cost: 150 },
  { id: 'r6', food: 'Trozo de torta', business: 'Pastelería Dulce Hogar', discount: 20, cost: 200 },
];

export const formatReward = (reward: Reward) =>
  `${reward.food} de ${reward.business} con ${reward.discount}% de dcto. por ${reward.cost} puntos!`;

// ---------------------------------------------------------------------------
// Perfil (Social)
// ---------------------------------------------------------------------------
export const USER_PROFILE = {
  name: 'Rosa Martínez',
  username: '@rosa.martinez',
};

// ---------------------------------------------------------------------------
// Mapa (Explorar): coordenada de respaldo si no hay permiso de ubicación
// ---------------------------------------------------------------------------
export const DEFAULT_REGION = {
  latitude: -33.4489,
  longitude: -70.6693,
  latitudeDelta: 0.02,
  longitudeDelta: 0.02,
};

// ---------------------------------------------------------------------------
// Juegos diarios
// ---------------------------------------------------------------------------
export type DailyGame = {
  id: GameId;
  title: string;
  description: string;
  icon: keyof typeof Ionicons.glyphMap;
  route?: 'ChessGame' | 'CrosswordGame';
};

export const DAILY_GAMES: DailyGame[] = [
  {
    id: 'chess',
    title: 'Desafío Ajedrez',
    description: 'Encuentra el jaque mate en 3 jugadas',
    icon: 'extension-puzzle-outline',
    route: 'ChessGame',
  },
  {
    id: 'crossword',
    title: 'Mini Crucigrama',
    description: '6 palabras para ejercitar la memoria',
    icon: 'grid-outline',
    route: 'CrosswordGame',
  },
  {
    id: 'puzzle',
    title: 'Puzle Diario',
    description: 'Arma la imagen del día',
    icon: 'images-outline',
  },
];

// ---------------------------------------------------------------------------
// Juego 1: Ajedrez, mate en 3 (juegan las blancas)
// Torres blancas en a1 y b5, rey blanco en h1; rey negro en f6.
// Solución: 1.Ta6+ Re7 2.Tb7+ Rd8 3.Ta8#
// ---------------------------------------------------------------------------
export type ChessMove = { from: string; to: string };

export const CHESS_PUZZLE = {
  fen: '8/8/5k2/1R6/8/8/8/R6K w - - 0 1',
  // Alterna jugada del usuario (blancas) y respuesta fija de las negras.
  solution: [
    { from: 'a1', to: 'a6' },
    { from: 'f6', to: 'e7' },
    { from: 'b5', to: 'b7' },
    { from: 'e7', to: 'd8' },
    { from: 'a6', to: 'a8' },
  ] as ChessMove[],
  explanation:
    'Es el "mate de la escalera": las dos torres empujan al rey hacia el borde, fila por fila.\n\n' +
    '1. Torre a6, jaque: la torre de b5 vigila la fila 5, así que el rey solo puede subir.\n' +
    '2. Torre b7, jaque: ahora la torre de a6 vigila la fila 6 y el rey debe ir a la última fila.\n' +
    '3. Torre a8, jaque mate: la fila 8 está en jaque y la torre de b7 cierra la fila 7. ¡El rey no tiene escapatoria!',
};

// ---------------------------------------------------------------------------
// Juego 2: Mini Crucigrama (7x7). null = casilla vacía.
//
//   . A . . P . I
//   A B U E L O S
//   . R . . A . L
//   . A . . Y . A
//   A Z U C A R .
//   . O . . S . .
//   A S A R . . .
// ---------------------------------------------------------------------------
export const CROSSWORD_GRID: (string | null)[][] = [
  [null, 'A', null, null, 'P', null, 'I'],
  ['A', 'B', 'U', 'E', 'L', 'O', 'S'],
  [null, 'R', null, null, 'A', null, 'L'],
  [null, 'A', null, null, 'Y', null, 'A'],
  ['A', 'Z', 'U', 'C', 'A', 'R', null],
  [null, 'O', null, null, 'S', null, null],
  ['A', 'S', 'A', 'R', null, null, null],
];

export type CrosswordWord = {
  id: string;
  number: number;
  direction: 'across' | 'down';
  row: number;
  col: number;
  answer: string;
  clue: string;
};

// Las horizontales van primero: son la dirección por defecto al tocar un cruce.
export const CROSSWORD_WORDS: CrosswordWord[] = [
  { id: '4-across', number: 4, direction: 'across', row: 1, col: 0, answer: 'ABUELOS', clue: 'Los padres de tus padres' },
  { id: '5-across', number: 5, direction: 'across', row: 4, col: 0, answer: 'AZUCAR', clue: 'Endulza el café o el té' },
  { id: '6-across', number: 6, direction: 'across', row: 6, col: 0, answer: 'ASAR', clue: 'Cocinar a la parrilla' },
  { id: '1-down', number: 1, direction: 'down', row: 0, col: 1, answer: 'ABRAZOS', clue: 'Muestras de cariño que se dan con los brazos' },
  { id: '2-down', number: 2, direction: 'down', row: 0, col: 4, answer: 'PLAYAS', clue: 'Lugares con arena junto al mar' },
  { id: '3-down', number: 3, direction: 'down', row: 0, col: 6, answer: 'ISLA', clue: 'Porción de tierra rodeada de agua' },
];
