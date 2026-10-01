import { FontAwesome5, Ionicons } from '@expo/vector-icons';
import { createMaterialTopTabNavigator } from '@react-navigation/material-top-tabs';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '../context/AppContext';
import AuthScreen from '../screens/AuthScreen';
import ExploreScreen from '../screens/ExploreScreen';
import ChessGameScreen from '../screens/games/ChessGameScreen';
import CrosswordGameScreen from '../screens/games/CrosswordGameScreen';
import GameSelectionScreen from '../screens/games/GameSelectionScreen';
import HomeScreen from '../screens/HomeScreen';
import RewardsScreen from '../screens/RewardsScreen';
import SocialScreen from '../screens/SocialScreen';
import { colors } from '../theme';
import type { HomeStackParamList, TabParamList } from './types';

const Tab = createMaterialTopTabNavigator<TabParamList>();
const Stack = createNativeStackNavigator<HomeStackParamList>();

const ICON_SIZE = 22;

// ===== Navegador apilado de "Inicio" (Home -> Juegos) =====
function HomeStackNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: colors.white,
        headerTitleStyle: { fontSize: 20, fontWeight: '700' },
        headerBackTitle: 'Atrás',
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="Home" component={HomeScreen} options={{ headerShown: false }} />
      <Stack.Screen name="GameSelection" component={GameSelectionScreen} options={{ title: 'Juegos Diarios' }} />
      <Stack.Screen name="ChessGame" component={ChessGameScreen} options={{ title: 'Desafío Ajedrez' }} />
      <Stack.Screen name="CrosswordGame" component={CrosswordGameScreen} options={{ title: 'Mini Crucigrama' }} />
    </Stack.Navigator>
  );
}
// ===== Fin HomeStackNavigator =====

// ===== Navegación principal: sesión -> pestañas inferiores con deslizamiento =====
export default function RootNavigator() {
  const { status } = useApp();

  if (status === 'loading') {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }
  return status === 'signedIn' ? <MainTabs /> : <AuthScreen />;
}

function MainTabs() {
  const insets = useSafeAreaInsets();

  return (
    <Tab.Navigator
      initialRouteName="Inicio"
      tabBarPosition="bottom"
      screenOptions={{
        lazy: true,
        tabBarShowIcon: true,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarPressColor: colors.accentLight,
        tabBarIndicatorStyle: { backgroundColor: colors.accent, height: 3, top: 0 },
        tabBarStyle: {
          backgroundColor: colors.white,
          paddingBottom: insets.bottom,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          elevation: 0,
          shadowOpacity: 0,
        },
        tabBarLabelStyle: { fontSize: 13, fontWeight: '600', textTransform: 'none' },
        tabBarIconStyle: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
      }}
    >
      <Tab.Screen
        name="MisPuntos"
        component={RewardsScreen}
        options={{
          tabBarLabel: 'Mis puntos',
          tabBarIcon: ({ color }) => <FontAwesome5 name="coins" size={ICON_SIZE} color={color} />,
        }}
      />
      <Tab.Screen
        name="Inicio"
        component={HomeStackNavigator}
        options={({ route }) => ({
          tabBarLabel: 'Inicio',
          tabBarIcon: ({ color }) => <Ionicons name="home" size={ICON_SIZE} color={color} />,
          // Dentro de los juegos se desactiva el swipe para no chocar con el tablero/crucigrama.
          swipeEnabled: (getFocusedRouteNameFromRoute(route) ?? 'Home') === 'Home',
        })}
      />
      <Tab.Screen
        name="Explorar"
        component={ExploreScreen}
        options={{
          tabBarLabel: 'Explorar',
          tabBarIcon: ({ color }) => <Ionicons name="compass" size={ICON_SIZE} color={color} />,
          // El mapa necesita los gestos de arrastre.
          swipeEnabled: false,
        }}
      />
      <Tab.Screen
        name="Social"
        component={SocialScreen}
        options={{
          tabBarLabel: 'Social',
          tabBarIcon: ({ color }) => <Ionicons name="people" size={ICON_SIZE} color={color} />,
        }}
      />
    </Tab.Navigator>
  );
}
// ===== Fin RootNavigator =====

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
});
