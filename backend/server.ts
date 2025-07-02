import express from 'express';
import { runYudaiCLI } from './utils/runYudaiCLI.js';

const app = express();
app.use(express.json());

app.post('/api/run-cli', async (req, res) => {
  const { args = [] } = req.body || {};
  try {
    const result = await runYudaiCLI(Array.isArray(args) ? args : []);
    res.json(result);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    res.status(500).json({ error: message });
  }
});

const port = process.env.PORT ? Number(process.env.PORT) : 5174;
app.listen(port, () => {
  console.log(`Backend server listening on http://localhost:${port}`);
});
