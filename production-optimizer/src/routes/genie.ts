/**
 * Genie client + Express routes (Node-native, no Python sidecar).
 *
 * Endpoints:
 *   POST /api/genie/ask     — start or continue conversation, return shaped result
 *   GET  /api/genie/space   — Space metadata
 *
 * Auth: uses Databricks Apps OAuth client_credentials flow against the SP env vars
 *   DATABRICKS_HOST, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET.
 */
import { Router, Request, Response } from 'express';
import https from 'https';
import { URL } from 'url';

const router = Router();

const GENIE_SPACE_ID = process.env.GENIE_SPACE_ID || '';
const RAW_HOST = (process.env.DATABRICKS_HOST || '').replace(/\/$/, '');
const HOST = RAW_HOST && !RAW_HOST.startsWith('http') ? `https://${RAW_HOST}` : RAW_HOST;
const CLIENT_ID = process.env.DATABRICKS_CLIENT_ID || '';
const CLIENT_SECRET = process.env.DATABRICKS_CLIENT_SECRET || '';

// ── Token cache ──────────────────────────────────────────────
let _token = '';
let _tokenExpires = 0;

async function getToken(): Promise<string> {
  if (_token && Date.now() < _tokenExpires - 60_000) return _token;
  if (!HOST || !CLIENT_ID || !CLIENT_SECRET) {
    throw new Error('Apps OAuth env not set (DATABRICKS_HOST/CLIENT_ID/CLIENT_SECRET)');
  }
  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    scope: 'all-apis',
  });
  const auth = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString('base64');
  const resp = await fetchJson(`${HOST}/oidc/v1/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: `Basic ${auth}`,
    },
    body: body.toString(),
  });
  if (!resp.access_token) throw new Error(`token fetch failed: ${JSON.stringify(resp).slice(0, 200)}`);
  _token = resp.access_token as string;
  _tokenExpires = Date.now() + (Number(resp.expires_in || 3600) * 1000);
  return _token;
}

// ── HTTP helpers ────────────────────────────────────────────
interface FetchOpts { method?: string; headers?: Record<string, string>; body?: string }

function fetchJson(url: string, opts: FetchOpts = {}): Promise<any> {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = https.request({
      hostname: u.hostname,
      port: u.port || 443,
      path: u.pathname + u.search,
      method: opts.method || 'GET',
      headers: opts.headers || {},
    }, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        if (res.statusCode && res.statusCode >= 400) {
          return reject(new Error(`HTTP ${res.statusCode}: ${text.slice(0, 300)}`));
        }
        try { resolve(text ? JSON.parse(text) : {}); } catch { resolve({ _raw: text }); }
      });
    });
    req.on('error', reject);
    if (opts.body) req.write(opts.body);
    req.end();
  });
}

async function dbxApi(path: string, opts: FetchOpts = {}): Promise<any> {
  const token = await getToken();
  return fetchJson(`${HOST}${path}`, {
    ...opts,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
}

// ── Genie API ────────────────────────────────────────────────

interface GenieMessage {
  message_id: string;
  conversation_id: string;
  status?: string;
  content?: string;
  attachments?: any[];
}

async function startConversation(question: string): Promise<GenieMessage> {
  const r = await dbxApi(`/api/2.0/genie/spaces/${GENIE_SPACE_ID}/start-conversation`, {
    method: 'POST',
    body: JSON.stringify({ content: question }),
  });
  // SDK shape: { message_id, conversation_id, message: {...} }
  return {
    message_id: r.message_id || r.message?.id,
    conversation_id: r.conversation_id,
    status: r.message?.status,
  };
}

async function createMessage(convId: string, question: string): Promise<GenieMessage> {
  const r = await dbxApi(`/api/2.0/genie/spaces/${GENIE_SPACE_ID}/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content: question }),
  });
  return {
    message_id: r.id || r.message_id,
    conversation_id: convId,
    status: r.status,
  };
}

async function getMessage(convId: string, msgId: string): Promise<any> {
  return dbxApi(`/api/2.0/genie/spaces/${GENIE_SPACE_ID}/conversations/${convId}/messages/${msgId}`);
}

async function getQueryResult(convId: string, msgId: string): Promise<any> {
  try {
    return await dbxApi(`/api/2.0/genie/spaces/${GENIE_SPACE_ID}/conversations/${convId}/messages/${msgId}/query-result`);
  } catch {
    return null;
  }
}

const POLL = [350, 350, 350, 700, 700, 700, 1200, 1200, 1200, 1800, 1800, 2500, 2500, 3000, 3000, 3000, 3000, 3000, 3000];

function isTerminal(status?: string): boolean {
  const s = (status || '').toUpperCase();
  return s.includes('COMPLETED') || s.includes('FAILED') || s.includes('CANCELLED');
}

async function askSync(question: string, conversationId?: string): Promise<any> {
  if (!GENIE_SPACE_ID) return { error: 'GENIE_SPACE_ID not configured' };

  let m: GenieMessage;
  if (conversationId) {
    m = await createMessage(conversationId, question);
  } else {
    m = await startConversation(question);
  }
  const convId = m.conversation_id;
  const msgId = m.message_id;
  if (!convId || !msgId) throw new Error(`Genie returned no ids: ${JSON.stringify(m)}`);

  // Poll
  let final: any = m;
  for (const delay of POLL) {
    const fresh = await getMessage(convId, msgId);
    final = fresh;
    if (isTerminal(fresh.status)) break;
    await new Promise(r => setTimeout(r, delay));
  }

  return shape(convId, msgId, final);
}

async function shape(convId: string, msgId: string, m: any): Promise<any> {
  // Genie returns the user's content under `content` and the answer under attachments.
  // We deliberately ignore m.content (it's the question) and only use attachment text.
  let text = '';
  let sql: string | null = null;
  let cols: string[] = [];
  let rows: any[][] = [];
  const status = m?.status || '';

  for (const att of (m?.attachments || [])) {
    if (att.text?.content) text = att.text.content;
    if (att.query?.query) {
      sql = att.query.query;
      const qr = await getQueryResult(convId, msgId);
      const sr = qr?.statement_response;
      if (sr) {
        const schema = sr.manifest?.schema?.columns;
        if (schema) cols = schema.map((c: any) => c.name);
        const data = sr.result?.data_array;
        if (Array.isArray(data)) rows = data.slice(0, 200);
      }
    }
  }

  // Fallback diagnostic: surface why no text came back so the UI shows something useful.
  if (!text) {
    const attCount = (m?.attachments || []).length;
    text = `_(Genie status: **${status || 'unknown'}** · ${attCount} attachment(s) · no NL text returned. ` +
           `Try rephrasing the question more specifically against the table columns.)_`;
    if (status && !/COMPLETED/i.test(status)) {
      text = `_(Genie did not finish within the polling window. Last status: **${status}**. Try again.)_`;
    }
  }

  return {
    conversation_id: convId,
    message_id: msgId,
    text,
    sql,
    columns: cols,
    rows,
  };
}

// Exported for the supervisor specialist
export const genieClient = { askSync };

// ── Express routes ───────────────────────────────────────────

router.post('/ask', async (req: Request, res: Response) => {
  try {
    const { question, conversation_id } = req.body || {};
    if (!question) return res.status(400).json({ error: 'question is required' });
    const out = await askSync(question, conversation_id);
    res.json(out);
  } catch (e: any) {
    console.error('[genie.ask] error:', e?.message || e);
    res.json({ error: String(e?.message || e) });
  }
});

router.get('/space', (_req, res) => {
  res.json({
    space_id: GENIE_SPACE_ID,
    configured: !!GENIE_SPACE_ID,
    name: 'Production Optimizer — Field Operations',
  });
});

export default router;
