// Tipos de las respuestas del backend (ver backend/src/models.py).

export type PublicProfile = {
  id: number;
  username: string | null;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  city: string | null;
  interests: string[];
  created_at: string;
};

export type Me = PublicProfile & {
  email: string;
  birth_date: string | null;
  language: string;
  points: number;
};

export type TokenOut = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type RegisterIn = {
  email: string;
  password: string;
  username: string;
  display_name: string;
};

export type PointsSummary = {
  balance: number;
  today: { chat: number; puzzle: number; mission: number; earned: number; spent: number };
  puzzle_points_remaining_today: number;
};

export type Mission = {
  id: number;
  date: string;
  title: string;
  description: string | null;
  kind: string;
  target: number;
  points: number;
  progress: number;
  completed: boolean;
  claimed: boolean;
};

export type MissionClaimOut = {
  mission_id: number;
  points_awarded: number;
  balance: number;
};

export type PuzzleKind = 'chess' | 'crossword' | 'sudoku' | 'wordsearch' | 'trivia' | 'riddle' | 'other';

export type Puzzle<D = Record<string, unknown>> = {
  id: number;
  date: string;
  kind: PuzzleKind;
  title: string;
  description: string | null;
  difficulty: string | null;
  data: D;
  solved: boolean;
  attempts: number;
};

export type ChessMove = { from: string; to: string };

export type ChessData = {
  fen: string;
  prompt?: string;
  // Alterna jugada del usuario (blancas) y respuesta fija de las negras.
  line: ChessMove[];
  notation?: string;
  explanation?: string;
};

export type CrosswordWord = {
  id: string;
  number: number;
  direction: 'across' | 'down';
  row: number;
  col: number;
  length: number;
  clue: string;
};

export type CrosswordData = {
  // Una fila por string: '#' = casilla con letra, '.' = vacía.
  cells: string[];
  words: CrosswordWord[];
};

export type PuzzleSolveOut = {
  correct: boolean;
  already_solved: boolean;
  attempts: number;
  points_awarded: number;
  puzzle_points_today: number;
  puzzle_points_remaining_today: number;
};

export type Promotion = {
  id: number;
  company_id: number;
  company_name: string | null;
  kind: 'individual' | 'group';
  title: string;
  description: string | null;
  points_cost: number;
  discount_type: 'percent' | 'amount';
  discount_value: number;
};

export type Redemption = {
  id: number;
  code: string;
  promotion_id: number;
  promotion_title: string | null;
  company_name: string | null;
  points_spent: number;
  status: 'active' | 'reserved' | 'claimed' | 'cancelled' | 'expired';
  created_at: string;
  expires_at: string;
};

export type FriendCode = {
  code: string;
  expires_in: number;
};

export type FriendScanOut = {
  status: 'pending' | 'friends' | 'already_friends';
  user: PublicProfile;
  detail: string;
};
