module.exports = function (api) {
  api.cache(true);
  // babel-preset-expo (SDK 54+) ya incluye el plugin de Reanimated/Worklets.
  return {
    presets: ['babel-preset-expo'],
  };
};
