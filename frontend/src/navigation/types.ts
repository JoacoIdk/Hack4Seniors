import type { NavigatorScreenParams } from '@react-navigation/native';

export type HomeStackParamList = {
  Home: undefined;
  GameSelection: undefined;
  ChessGame: undefined;
  CrosswordGame: undefined;
};

export type TabParamList = {
  MisPuntos: undefined;
  Inicio: NavigatorScreenParams<HomeStackParamList>;
  Explorar: undefined;
  Social: undefined;
};
