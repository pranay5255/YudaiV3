import { spawn } from 'child_process';
import path from 'path';

export function runYudaiCLI(args: string[]): Promise<{ stdout: string; stderr: string; }> {
  const cliPath = path.join(__dirname, '..', '..', 'YudaiCLI', 'codex-cli', 'bin', 'codex.js');

  return new Promise((resolve, reject) => {
    const proc = spawn('node', [cliPath, ...args], { env: process.env });
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (d) => (stdout += d.toString()));
    proc.stderr.on('data', (d) => (stderr += d.toString()));
    proc.on('error', reject);
    proc.on('close', () => resolve({ stdout, stderr }));
  });
}
