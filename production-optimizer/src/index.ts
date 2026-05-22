import express from 'express';
import path from 'path';
import cors from 'cors';
import { attachDemoUser } from './middleware/rbac';
import twinRouter from './routes/twin';
import commercialRouter from './routes/commercial';
import mapRouter from './routes/map';
import agentRouter from './routes/agent';
import shiftRouter from './routes/shift';
import productionRouter from './routes/production';
import genieRouter from './routes/genie';
import supervisorRouter from './routes/supervisor';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors({
  origin: [
    'https://production-optimizer-7474647106303257.aws.databricksapps.com',
    /^https:\/\/.*\.cloud\.databricks\.com$/,
    'http://localhost:5173',
    'http://localhost:3001',
  ],
  credentials: true,
}));

app.use(express.json());
app.use(attachDemoUser);

app.use('/api/twin', twinRouter);
app.use('/api/commercial', commercialRouter);
app.use('/api/map', mapRouter);
app.use('/api/agent', agentRouter);
app.use('/api/shift', shiftRouter);
app.use('/api/production', productionRouter);
app.use('/api/genie', genieRouter);
app.use('/api/supervisor', supervisorRouter);

// Serve UI in production
const uiDist = path.join(__dirname, '..', 'ui', 'dist');
app.use(express.static(uiDist));
app.get('*', (_req, res) => {
  res.sendFile(path.join(uiDist, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`CO2-EOR Twin API running on port ${PORT}`);
});
