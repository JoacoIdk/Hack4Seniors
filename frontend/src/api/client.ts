// Cliente HTTP del backend (FastAPI). Guarda el token de sesión en memoria.
import Constants from 'expo-constants';

// EXPO_PUBLIC_API_URL lo define run.sh; si no, se usa la IP del computador que sirve Expo.
const resolveApiUrl = () => {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  const host = Constants.expoConfig?.hostUri?.split(':')[0] ?? 'localhost';
  return `http://${host}:8000`;
};

export const API_URL = resolveApiUrl();

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export const setToken = (value: string | null) => {
  token = value;
};

// Se llama cuando el backend rechaza el token (sesión vencida o cuenta suspendida).
export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  onUnauthorized = handler;
};

// El backend responde en inglés; se traducen los mensajes que ve la persona usuaria.
const TRANSLATIONS: Record<string, string> = {
  'Invalid email or password': 'Correo o contraseña incorrectos.',
  'This account has been suspended': 'Esta cuenta está suspendida.',
  'This account cannot sign in here': 'Esta cuenta no puede ingresar a esta app.',
  'Email is already in use': 'Ese correo ya está registrado.',
  'Username is already in use': 'Ese nombre de usuario ya está en uso.',
  'Not enough points': 'No tienes puntos suficientes.',
  'This promotion is sold out': 'Esta recompensa se agotó.',
  'You have reached the limit for this promotion': 'Ya canjeaste esta recompensa el máximo de veces.',
  'Mission already claimed': 'Ya reclamaste esta misión.',
  'Mission not completed yet': 'Aún no completas esta misión.',
  'This code is invalid or has expired': 'Este código no es válido o ya venció.',
  'You cannot add yourself': 'No puedes agregarte a ti mismo.',
};

// FastAPI responde { detail: string } o, en errores de validación, { detail: [{ msg }] }.
const errorMessage = (body: unknown, status: number) => {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return TRANSLATIONS[detail] ?? detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return `Error ${status}`;
};

type Options = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
};

export async function api<T>(path: string, { method = 'GET', body }: Options = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Revisa tu conexión.');
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized?.();
    throw new ApiError(response.status, errorMessage(data, response.status));
  }
  return data as T;
}
