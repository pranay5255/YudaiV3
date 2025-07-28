import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { resolve } from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const isProduction = mode === 'production';
  
  return {
    plugins: [react()],
    
    // Path aliases for cleaner imports
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@components': resolve(__dirname, 'src/components'),
        '@services': resolve(__dirname, 'src/services'),
        '@contexts': resolve(__dirname, 'src/contexts'),
        '@utils': resolve(__dirname, 'src/utils'),
        '@types': resolve(__dirname, 'src/types'),
      },
    },

    // Development server configuration
    server: {
      port: 5173,
      host: true,
      open: false,
      strictPort: true,
      // Proxy for development API calls
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
        '/auth': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        }
      }
    },

    // Build optimization
    build: {
      target: 'esnext',
      minify: isProduction ? 'esbuild' : false,
      sourcemap: !isProduction,
      cssMinify: isProduction,
      
      // Rollup options for production optimization
      rollupOptions: {
        output: {
          // Manual chunks for better caching
          manualChunks(id) {
            // Vendor chunk for node_modules
            if (id.includes('node_modules')) {
              // Separate React vendor chunk
              if (id.includes('react') || id.includes('react-dom')) {
                return 'react-vendor';
              }
              // Other vendor libraries
              return 'vendor';
            }
            
            // Services chunk
            if (id.includes('/src/services/')) {
              return 'services';
            }
            
            // Components chunk (if large)
            if (id.includes('/src/components/') && !id.includes('.css')) {
              return 'components';
            }
          },
          
          // Asset file naming
          assetFileNames: (assetInfo) => {
            const info = assetInfo.name?.split('.') || [];
            let extType = info[info.length - 1];
            
            if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
              extType = 'images';
            } else if (/woff2?|eot|ttf|otf/i.test(extType)) {
              extType = 'fonts';
            }
            
            return `assets/${extType}/[name]-[hash][extname]`;
          },
          
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
        },
      },
      
      // Chunk size warning limit
      chunkSizeWarningLimit: 1000,
    },

    // Dependency optimization
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
      ],
      exclude: ['lucide-react'],
    },

    // CSS configuration
    css: {
      devSourcemap: !isProduction,
      postcss: {
        plugins: isProduction ? [
          require('autoprefixer'),
          require('cssnano')({
            preset: 'default',
          }),
        ] : [],
      },
    },

    // Environment variables
    define: {
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
      __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    },

    // Preview configuration for production testing
    preview: {
      port: 4173,
      host: true,
      strictPort: true,
    },
  };
});
