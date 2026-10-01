import * as Location from 'expo-location';
import React, { useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import MapView from 'react-native-maps';

import { DEFAULT_REGION } from '../data/mockData';

// ===== Pantalla: Explorar (ExploreScreen) =====
// Usa el proveedor por defecto (Google Maps en Android, Apple Maps en iOS).
// Para builds de Android fuera de Expo Go, define la API key en app.json
// (android.config.googleMaps.apiKey).
export default function ExploreScreen() {
  const mapRef = useRef<MapView>(null);

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status !== 'granted') return; // Se queda en la coordenada de respaldo.

        const { coords } = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        if (!active) return;

        mapRef.current?.animateToRegion(
          {
            latitude: coords.latitude,
            longitude: coords.longitude,
            latitudeDelta: 0.01,
            longitudeDelta: 0.01,
          },
          800,
        );
      } catch {
        // Sin ubicación: se mantiene DEFAULT_REGION.
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        initialRegion={DEFAULT_REGION}
        showsUserLocation
        showsMyLocationButton
      />
    </View>
  );
}
// ===== Fin ExploreScreen =====

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
