# Hack4Seniors – Frontend (prototipo)

App en React Native + Expo (TypeScript). Todos los datos están fijos en `src/data/mockData.ts`.

## Ejecutar

Requiere Node.js 20+.

```bash
cd frontend
npm install
npx expo install --fix   # alinea las versiones con el SDK de Expo instalado
npx expo start
```

Abre la app con **Expo Go** (escanea el QR) o con un emulador (`a` para Android, `i` para iOS).

## Estructura

```
App.tsx                         Proveedores (gestos, safe area, estado, navegación)
src/theme.ts                    Colores (#2D8A53 banners, #28B0B8 acentos) y tamaños
src/context/AppContext.tsx      Puntos globales y estado de los juegos diarios
src/data/mockData.ts            Desafíos, recompensas, perfil, ajedrez y crucigrama
src/navigation/RootNavigator.tsx Pestañas inferiores con deslizamiento + stack de Inicio
src/screens/                    Inicio, Mis puntos, Explorar, Social
src/screens/games/              Selección de juegos, Ajedrez, Crucigrama
```

## Notas

- **Pestañas con deslizamiento:** se usa `@react-navigation/material-top-tabs` con `tabBarPosition="bottom"`. El swipe se desactiva en Explorar (mapa) y dentro de los juegos.
- **Mapa:** en Expo Go funciona sin configuración. Para un build propio en Android, reemplaza `TU_API_KEY_DE_GOOGLE_MAPS` en `app.json`.
- **Ajedrez:** posición `8/8/5k2/1R6/8/8/8/R6K w - - 0 1`, solución 1.Ta6+ Re7 2.Tb7+ Rd8 3.Ta8#. Las respuestas de las negras son fijas.
- **Reanimated:** `babel-preset-expo` ya incluye el plugin; no hace falta configurarlo en `babel.config.js`.
