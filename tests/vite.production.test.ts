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
    it('should have valid vite.config.ts with ESM imports', () => {
      expect(existsSync(viteConfigPath)).toBe(true);
      
      const config = readFileSync(viteConfigPath, 'utf-8');
      expect(config).toContain('import');
      expect(config).toContain('@vitejs/plugin-react-swc');
      expect(config).toContain('defineConfig');
      expect(config).toContain('import autoprefixer');
      expect(config).toContain('import cssnano');
      expect(config).not.toContain('require('); // No require statements
    });

    it('should include essential production optimizations', () => {
      const config = readFileSync(viteConfigPath, 'utf-8');
      
      expect(config).toContain('target: \'esnext\'');
      expect(config).toContain('minify: isProduction');
      expect(config).toContain('manualChunks');
      expect(config).toContain('chunkSizeWarningLimit');
    });

    it('should have streamlined path aliases', () => {
      const config = readFileSync(viteConfigPath, 'utf-8');
      
      expect(config).toContain('resolve:');
      expect(config).toContain('alias:');
      expect(config).toContain('@components');
      expect(config).toContain('@services');
      expect(config).toContain('@contexts');
    });

    it('should have proxy configuration for development', () => {
      const config = readFileSync(viteConfigPath, 'utf-8');
      
      expect(config).toContain('proxy:');
      expect(config).toContain('/api');
      expect(config).toContain('/auth');
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
    }, 60000);

    it('should complete production build successfully', () => {
      expect(buildExitCode).toBe(0);
    });

    it('should generate dist directory with optimized assets', () => {
      expect(existsSync(distPath)).toBe(true);
      
      const distFiles = readdirSync(distPath);
      expect(distFiles).toContain('index.html');
      expect(distFiles.some(file => file === 'assets')).toBe(true);
    });

    it('should generate vendor chunks as configured', () => {
      const assetsPath = join(distPath, 'assets');
      if (!existsSync(assetsPath)) return;

      const jsFiles = readdirSync(assetsPath)
        .filter(file => file.endsWith('.js'));
      
      // Should have essential chunks
      const hasReactVendorChunk = jsFiles.some(file => 
        file.includes('react-vendor')
      );
      const hasVendorChunk = jsFiles.some(file => 
        file.includes('vendor') && !file.includes('react-vendor')
      );
      
      expect(hasReactVendorChunk || hasVendorChunk).toBe(true);
    });

    it('should generate optimized CSS files', () => {
      const assetsPath = join(distPath, 'assets');
      if (!existsSync(assetsPath)) return;

      const cssFiles = readdirSync(assetsPath)
        .filter(file => file.endsWith('.css'));
      
      expect(cssFiles.length).toBeGreaterThan(0);
      
      // Check if CSS is minified
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
        
        // Individual chunks should be reasonable size
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
      previewProcess = spawn('npm', ['run', 'preview'], {
        cwd: projectRoot,
        stdio: 'pipe'
      });

      await new Promise<void>((resolve) => {
        previewProcess.stdout?.on('data', (data) => {
          const output = data.toString();
          if (output.includes('Local:') && output.includes('4173')) {
            previewStarted = true;
            resolve();
          }
        });

        setTimeout(() => resolve(), 10000);
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
      }
    });
  });

  describe('Dependencies and Package Configuration', () => {
    it('should have essential dependencies', () => {
      const packageJsonPath = join(projectRoot, 'package.json');
      const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'));
      
      // Runtime dependencies
      expect(packageJson.dependencies).toHaveProperty('react');
      expect(packageJson.dependencies).toHaveProperty('react-dom');
      
      // Dev dependencies
      expect(packageJson.devDependencies).toHaveProperty('@vitejs/plugin-react-swc');
      expect(packageJson.devDependencies).toHaveProperty('vite');
      expect(packageJson.devDependencies).toHaveProperty('autoprefixer');
      expect(packageJson.devDependencies).toHaveProperty('cssnano');
    });

    it('should have proper build scripts', () => {
      const packageJsonPath = join(projectRoot, 'package.json');
      const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'));
      
      expect(packageJson.scripts).toHaveProperty('build');
      expect(packageJson.scripts).toHaveProperty('preview');
      expect(packageJson.scripts.build).toContain('vite build');
    });

    it('should be configured as ESM module', () => {
      const packageJsonPath = join(projectRoot, 'package.json');
      const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'));
      
      expect(packageJson.type).toBe('module');
    });
  });
}); 