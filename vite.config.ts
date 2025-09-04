import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { resolve } from 'path';
import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';
import tailwindcss from 'tailwindcss';
// @ts-expect-error - vite-plugin-eslint has module resolution issues
import eslint from 'vite-plugin-eslint';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';
  
  return {
    plugins: [
      react(),
      eslint({
        include: ['src/**/*.{ts,tsx}'],
        exclude: ['node_modules/**', 'dist/**'],
      }),
    ],
    
    // Path aliases for cleaner imports
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@components': resolve(__dirname, 'src/components'),
        '@services': resolve(__dirname, 'src/services'),
        '@contexts': resolve(__dirname, 'src/contexts'),
      },
    },

    // Development server configuration
    server: {
      port: 3000,
      host: '0.0.0.0',
      strictPort: true,
      // Proxy for development API calls
      proxy: {
        '/api': {
          target: process.env.VITE_API_BASE_URL || 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        },
        '/auth': {
          target: process.env.VITE_API_BASE_URL || 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        }
      }
    },

    // Build optimization
    build: {
      target: 'esnext',
      minify: isProduction,
      sourcemap: !isProduction,
      cssMinify: isProduction,
      
      // Simplified rollup options
      rollupOptions: {
        output: {
          // Essential chunks only
          manualChunks: {
            'react-vendor': ['react', 'react-dom'],
            'vendor': ['axios', 'lucide-react']
          },
          
          // Clean asset naming
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
        },
      },
      
      chunkSizeWarningLimit: 1000,
    },

    // Dependency optimization
    optimizeDeps: {
      include: ['react', 'react-dom'],
    },

    // CSS configuration with ESM imports
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

    // Environment variables
    define: {
      __DEV__: !isProduction,
    },

    // Preview configuration
    preview: {
      port: 4173,
      host: true,
      strictPort: true,
    },
  };
});
