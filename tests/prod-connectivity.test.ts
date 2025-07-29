import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import axios from 'axios';

// Production environment configuration
const PROD_CONFIG = {
  mainDomain: 'https://yudai.app',
  apiSubdomain: 'https://api.yudai.app',
  timeout: 10000, // 10 seconds
};

// Test data
const testEndpoints = [
  { path: '/health', method: 'GET', description: 'Health check' },
  { path: '/docs', method: 'GET', description: 'API documentation' },
  { path: '/', method: 'GET', description: 'Root endpoint' },
];

describe('Production Environment Connectivity Tests', () => {
  let mainDomainClient: any;
  let apiSubdomainClient: any;

  beforeAll(() => {
    // Create axios instances with proper configuration
    mainDomainClient = axios.create({
      baseURL: PROD_CONFIG.mainDomain,
      timeout: PROD_CONFIG.timeout,
      validateStatus: (status) => status < 500, // Don't throw on 4xx errors
    });

    apiSubdomainClient = axios.create({
      baseURL: PROD_CONFIG.apiSubdomain,
      timeout: PROD_CONFIG.timeout,
      validateStatus: (status) => status < 500,
    });

    // Add request/response interceptors for debugging
    [mainDomainClient, apiSubdomainClient].forEach(client => {
      client.interceptors.request.use((config: any) => {
        console.log(`🚀 ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      });

      client.interceptors.response.use(
        (response: any) => {
          console.log(`✅ ${response.status} ${response.config.method?.toUpperCase()} ${response.config.url}`);
          return response;
        },
        (error: any) => {
          console.log(`❌ ${error.response?.status || 'NETWORK'} ${error.config?.method?.toUpperCase()} ${error.config?.url}`);
          return Promise.reject(error);
        }
      );
    });
  });

  describe('Main Domain (yudai.app) - Frontend Tests', () => {
    it('should serve the frontend application', async () => {
      const response = await mainDomainClient.get('/');
      
      expect(response.status).toBe(200);
      expect(response.headers['content-type']).toMatch(/text\/html/);
      expect(response.data).toContain('<!DOCTYPE html>');
    });

    it('should have proper security headers', async () => {
      const response = await mainDomainClient.get('/');
      
      expect(response.headers['strict-transport-security']).toBeDefined();
      expect(response.headers['x-frame-options']).toBeDefined();
      expect(response.headers['x-content-type-options']).toBeDefined();
    });

    it('should redirect HTTP to HTTPS', async () => {
      try {
        const httpClient = axios.create({
          baseURL: 'http://yudai.app',
          timeout: PROD_CONFIG.timeout,
          maxRedirects: 0, // Don't follow redirects
        });
        
        await httpClient.get('/');
      } catch (error: any) {
        expect(error.response?.status).toBe(301);
        expect(error.response?.headers?.location).toMatch(/^https:\/\//);
      }
    });
  });

  describe('Main Domain (yudai.app) - API Proxy Tests', () => {
    testEndpoints.forEach(({ path, method, description }) => {
      it(`should proxy ${description} via /api${path}`, async () => {
        const response = await mainDomainClient.request({
          method,
          url: `/api${path}`,
        });
        
        expect(response.status).toBeLessThan(500);
        
        // For health check, expect specific response
        if (path === '/health') {
          expect(response.status).toBe(200);
        }
      });
    });

    it('should handle CORS preflight requests', async () => {
      const response = await mainDomainClient.options('/api/health', {
        headers: {
          'Origin': 'https://yudai.app',
          'Access-Control-Request-Method': 'GET',
          'Access-Control-Request-Headers': 'Content-Type',
        },
      });
      
      expect(response.status).toBe(204);
      expect(response.headers['access-control-allow-origin']).toBe('https://yudai.app');
    });
  });

  describe('API Subdomain (api.yudai.app) - Direct Backend Tests', () => {
    testEndpoints.forEach(({ path, method, description }) => {
      it(`should serve ${description} directly`, async () => {
        const response = await apiSubdomainClient.request({
          method,
          url: path,
        });
        
        expect(response.status).toBeLessThan(500);
        
        // For health check, expect specific response
        if (path === '/health') {
          expect(response.status).toBe(200);
        }
      });
    });

    it('should have proper CORS headers for main domain', async () => {
      const response = await apiSubdomainClient.get('/health', {
        headers: {
          'Origin': 'https://yudai.app',
        },
      });
      
      expect(response.status).toBe(200);
      expect(response.headers['access-control-allow-origin']).toBe('https://yudai.app');
    });

    it('should handle CORS preflight requests', async () => {
      const response = await apiSubdomainClient.options('/', {
        headers: {
          'Origin': 'https://yudai.app',
          'Access-Control-Request-Method': 'GET',
          'Access-Control-Request-Headers': 'Content-Type',
        },
      });
      
      expect(response.status).toBe(204);
      expect(response.headers['access-control-allow-origin']).toBe('https://yudai.app');
    });
  });

  describe('Backend Health and Functionality Tests', () => {
    it('should have a working health endpoint', async () => {
      const response = await apiSubdomainClient.get('/health');
      
      expect(response.status).toBe(200);
      expect(response.data).toMatch(/healthy|ok/i);
    });

    it('should serve API documentation', async () => {
      const response = await apiSubdomainClient.get('/docs');
      
      expect(response.status).toBe(200);
      expect(response.headers['content-type']).toMatch(/text\/html/);
    });

    it('should have proper response times', async () => {
      const startTime = Date.now();
      await apiSubdomainClient.get('/health');
      const endTime = Date.now();
      
      const responseTime = endTime - startTime;
      expect(responseTime).toBeLessThan(2000); // Should respond within 2 seconds
    });
  });

  describe('Error Handling Tests', () => {
    it('should handle 404 errors gracefully', async () => {
      try {
        await apiSubdomainClient.get('/nonexistent-endpoint');
      } catch (error: any) {
        expect(error.response?.status).toBe(404);
      }
    });

    it('should handle malformed requests', async () => {
      try {
        await apiSubdomainClient.post('/health', 'invalid json', {
          headers: { 'Content-Type': 'application/json' },
        });
      } catch (error: any) {
        expect(error.response?.status).toBeGreaterThanOrEqual(400);
        expect(error.response?.status).toBeLessThan(500);
      }
    });
  });

  describe('SSL/TLS Configuration Tests', () => {
    it('should use HTTPS with proper SSL configuration', async () => {
      const response = await mainDomainClient.get('/');
      
      expect(response.config.url).toMatch(/^https:\/\//);
      expect(response.headers['strict-transport-security']).toBeDefined();
    });

    it('should have proper SSL headers', async () => {
      const response = await mainDomainClient.get('/');
      
      const hstsHeader = response.headers['strict-transport-security'];
      expect(hstsHeader).toContain('max-age=');
      expect(hstsHeader).toContain('includeSubDomains');
    });
  });

  describe('Load Balancing and Performance Tests', () => {
    it('should handle multiple concurrent requests', async () => {
      const concurrentRequests = 5;
      const promises = Array(concurrentRequests).fill(null).map(() => 
        apiSubdomainClient.get('/health')
      );
      
      const responses = await Promise.all(promises);
      
      responses.forEach(response => {
        expect(response.status).toBe(200);
      });
    });

    it('should maintain consistent response times under load', async () => {
      const requests = 10;
      const responseTimes: number[] = [];
      
      for (let i = 0; i < requests; i++) {
        const startTime = Date.now();
        await apiSubdomainClient.get('/health');
        const endTime = Date.now();
        responseTimes.push(endTime - startTime);
      }
      
      const avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
      expect(avgResponseTime).toBeLessThan(1000); // Average should be under 1 second
    });
  });

  afterAll(() => {
    console.log('\n🎉 Production connectivity tests completed!');
  });
}); 