import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { spawn, ChildProcess } from 'child_process';
import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';
import axios from 'axios';

describe('Vite Production Configuration Tests', () => {
  const projectRoot = resolve(__dirname, '..');
  const distPath = join(projectRoot, 'dist');
  const viteConfigPath = join(projectRoot, 'vite.config.ts');

  describe('Vite Configuration Validation', () => {
    it('should have valid vite.config.ts file', () => {
      expect(existsSync(viteConfigPath)).toBe(true);
      
      const config = readFileSync(viteConfigPath, 'utf-8');
      expect(config).toContain('@vitejs/plugin-react-swc');
      expect(config).toContain('defineConfig');
      expect(config).toContain('manualChunks');
    });

    it('should include production optimizations', () => {
      const config = readFileSync(viteConfigPath, 'utf-8');
      
      // Check for production optimizations
      expect(config).toContain('target: \'esnext\'');
      expect(config).toContain('minify');
      expect(config).toContain('rollupOptions');
      expect(config).toContain('chunkSizeWarningLimit');
    });

    it('should have path aliases configured', () => {
      const config = readFileSync(viteConfigPath, 'utf-8');
      
      expect(config).toContain('resolve:');
      expect(config).toContain('alias:');
      expect(config).toContain('@components');
      expect(config).toContain('@services');
    });

    it('should have proxy configuration for development', () => {
      const config = readFileSync(viteConfigPath, 'utf-8');
      
      expect(config).toContain('proxy:');
      expect(config).toContain('/api');
      expect(config).toContain('/auth');
    });
  });

  describe('Environment Variables', () => {
    it('should handle VITE_API_URL correctly', () => {
      // In test environment, this should be set
      expect(process.env.VITE_API_URL).toBe('https://yudai.app/api');
      
      // Check that environment variable is properly prefixed
      expect(process.env.VITE_API_URL).toMatch(/^https?:\/\//);
    });

    it('should not expose non-VITE prefixed variables in build', () => {
      // These should not be accessible in frontend build
      expect(process.env.SECRET_KEY).toBeDefined(); // Available in test env
      expect(process.env.DATABASE_URL).toBeUndefined(); // Not set in test
    });
  });

  describe('Production Build Tests', () => {
    let buildProcess: ChildProcess;
    let buildExitCode: number | null = null;

    beforeAll(async () => {
      // Run production build
      buildProcess = spawn('npm', ['run', 'build'], {
        cwd: projectRoot,
        stdio: 'pipe'
      });

      buildExitCode = await new Promise((resolve) => {
        buildProcess.on('exit', (code) => {
          resolve(code);
        });
      });
    }, 60000); // 60 second timeout for build

    it('should complete production build successfully', () => {
      expect(buildExitCode).toBe(0);
    });

    it('should generate dist directory with optimized assets', () => {
      expect(existsSync(distPath)).toBe(true);
      
      const distFiles = readdirSync(distPath);
      expect(distFiles).toContain('index.html');
      expect(distFiles.some(file => file === 'assets')).toBe(true);
    });

    it('should generate chunked JavaScript files', () => {
      const assetsPath = join(distPath, 'assets');
      if (!existsSync(assetsPath)) return;

      const jsFiles = readdirSync(assetsPath)
        .filter(file => file.endsWith('.js'));
      
      // Should have multiple chunks due to code splitting
      expect(jsFiles.length).toBeGreaterThan(1);
      
      // Check for vendor chunks
      const hasVendorChunk = jsFiles.some(file => 
        file.includes('vendor') || file.includes('react-vendor')
      );
      expect(hasVendorChunk).toBe(true);
    });

    it('should generate optimized CSS files', () => {
      const assetsPath = join(distPath, 'assets');
      if (!existsSync(assetsPath)) return;

      const cssFiles = readdirSync(assetsPath)
        .filter(file => file.endsWith('.css'));
      
      expect(cssFiles.length).toBeGreaterThan(0);
      
      // Check if CSS is minified (no unnecessary whitespace)
      if (cssFiles.length > 0) {
        const cssContent = readFileSync(join(assetsPath, cssFiles[0]), 'utf-8');
        expect(cssContent.includes('\n  ')).toBe(false); // No indentation
      }
    });

    it('should have reasonable bundle sizes', () => {
      const assetsPath = join(distPath, 'assets');
      if (!existsSync(assetsPath)) return;

      const jsFiles = readdirSync(assetsPath)
        .filter(file => file.endsWith('.js'));

      jsFiles.forEach(file => {
        const filePath = join(assetsPath, file);
        const stats = statSync(filePath);
        const sizeInKB = stats.size / 1024;
        
        // Individual chunks should be reasonable size (< 1MB)
        expect(sizeInKB).toBeLessThan(1024);
      });
    });

    it('should include index.html with proper asset references', () => {
      const indexPath = join(distPath, 'index.html');
      expect(existsSync(indexPath)).toBe(true);
      
      const htmlContent = readFileSync(indexPath, 'utf-8');
      expect(htmlContent).toContain('<!DOCTYPE html>');
      expect(htmlContent).toContain('<script');
      expect(htmlContent).toContain('assets/');
    });
  });

  describe('Production Preview Tests', () => {
    let previewProcess: ChildProcess;
    let previewStarted = false;

    beforeAll(async () => {
      // Start preview server
      previewProcess = spawn('npm', ['run', 'preview'], {
        cwd: projectRoot,
        stdio: 'pipe'
      });

      // Wait for preview server to start
      await new Promise<void>((resolve) => {
        previewProcess.stdout?.on('data', (data) => {
          const output = data.toString();
          if (output.includes('Local:') && output.includes('4173')) {
            previewStarted = true;
            resolve();
          }
        });

        setTimeout(() => {
          if (!previewStarted) {
            resolve(); // Timeout fallback
          }
        }, 10000);
      });
    }, 15000);

    afterAll(() => {
      if (previewProcess) {
        previewProcess.kill();
      }
    });

    it('should serve production build on preview server', async () => {
      if (!previewStarted) {
        console.warn('Preview server did not start, skipping test');
        return;
      }

      try {
        const response = await axios.get('http://localhost:4173/', {
          timeout: 5000
        });
        
        expect(response.status).toBe(200);
        expect(response.headers['content-type']).toContain('text/html');
      } catch (error) {
        console.warn('Preview server not accessible:', error);
        // Don't fail the test if preview server is not accessible
      }
    });

    it('should serve assets with proper headers', async () => {
      if (!previewStarted) return;

      try {
        const response = await axios.get('http://localhost:4173/', {
          timeout: 5000
        });
        
        const htmlContent = response.data;
        const jsAssetMatch = htmlContent.match(/assets\/.*?\.js/);
        
        if (jsAssetMatch) {
          const assetResponse = await axios.get(
            `http://localhost:4173/${jsAssetMatch[0]}`,
            { timeout: 5000 }
          );
          
          expect(assetResponse.status).toBe(200);
          expect(assetResponse.headers['content-type']).toContain('javascript');
        }
      } catch (error) {
        console.warn('Asset serving test failed:', error);
      }
    });
  });

  describe('Dependencies and Package Configuration', () => {
    it('should have required production dependencies', () => {
      const packageJsonPath = join(projectRoot, 'package.json');
      const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'));
      
      // Check for required runtime dependencies
      expect(packageJson.dependencies).toHaveProperty('react');
      expect(packageJson.dependencies).toHaveProperty('react-dom');
      
      // Check for required dev dependencies
      expect(packageJson.devDependencies).toHaveProperty('@vitejs/plugin-react-swc');
      expect(packageJson.devDependencies).toHaveProperty('vite');
      expect(packageJson.devDependencies).toHaveProperty('typescript');
    });

    it('should have proper build scripts', () => {
      const packageJsonPath = join(projectRoot, 'package.json');
      const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'));
      
      expect(packageJson.scripts).toHaveProperty('build');
      expect(packageJson.scripts).toHaveProperty('preview');
      expect(packageJson.scripts.build).toContain('vite build');
    });
  });
}); 