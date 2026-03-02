import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { resolve } from 'path';
import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';
import tailwindcss from 'tailwindcss';
// @ts-expect-error - vite-plugin-eslint has module resolution issues
import eslint from 'vite-plugin-eslint';

export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';

  return {
    plugins: [
      react(),
      eslint({
        include: ['**/*.{ts,tsx}'],
        exclude: ['node_modules/**', 'dist/**'],
      }),
    ],

    resolve: {
      alias: {
        '@': resolve(__dirname, '.'),
        '@components': resolve(__dirname, 'components'),
        '@services': resolve(__dirname, 'services'),
        '@contexts': resolve(__dirname, 'contexts'),
      },
    },

    server: {
      port: 3000,
      host: '0.0.0.0',
      strictPort: true,
      proxy: {
        '/api': {
          target: process.env.VITE_API_BASE_URL || 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        },
        '/auth/api': {
          target: process.env.VITE_API_BASE_URL || 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        },
      },
    },

    build: {
      target: 'esnext',
      minify: isProduction,
      sourcemap: !isProduction,
      cssMinify: isProduction,
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom'],
            vendor: ['axios', 'lucide-react'],
          },
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
        },
      },
      chunkSizeWarningLimit: 1000,
    },

    optimizeDeps: {
      include: ['react', 'react-dom'],
    },

    css: {
      devSourcemap: !isProduction,
      postcss: {
        plugins: [
          tailwindcss(),
          autoprefixer(),
          cssnano({
            preset: 'default',
          }),
        ],
      },
    },

    define: {
      __DEV__: !isProduction,
    },

    preview: {
      port: 4173,
      host: true,
      strictPort: true,
    },
  };
});
