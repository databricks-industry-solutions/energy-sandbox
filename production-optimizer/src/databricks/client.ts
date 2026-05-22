/**
 * Databricks client — wires Lakehouse (SQL Warehouse) and Lakebase (PostgreSQL).
 */

import { executeQuery } from './sql';

export interface DatabricksConfig {
  host: string;
  token: string;
  warehouseId: string;
  lakebaseConfig?: {
    host: string;
    port: number;
    database: string;
  };
}

/** Execute SQL against Databricks SQL Warehouse (Lakehouse / Delta tables). */
export async function queryLakehouse(config: DatabricksConfig, sql: string): Promise<any[]> {
  return executeQuery(sql);
}

/** Execute SQL against Lakebase (managed PostgreSQL). */
export async function queryLakebase(config: DatabricksConfig, sql: string): Promise<any[]> {
  // Lakebase connectivity requires the `pg` package.
  // In Databricks Apps, PG* env vars are injected by the runtime.
  const pgHost = process.env.PGHOST;
  const pgUser = process.env.PGUSER;
  const pgDatabase = process.env.PGDATABASE || 'databricks_postgres';
  const pgPort = parseInt(process.env.PGPORT || '5432', 10);

  if (!pgHost || !pgUser) {
    console.log(`[Lakebase] No PG env vars. SQL: ${sql.slice(0, 100)}`);
    return [];
  }

  try {
    // Dynamic import — pg may not be installed in all environments
    const { Pool } = require('pg');

    // Get OAuth token for password
    const host = process.env.DATABRICKS_HOST || '';
    const tokenResp = await fetch(`${host}/oidc/v1/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `grant_type=client_credentials&scope=all-apis&client_id=${process.env.DATABRICKS_CLIENT_ID || ''}&client_secret=${process.env.DATABRICKS_CLIENT_SECRET || ''}`,
    });
    const tokenData = await tokenResp.json();

    const pool = new Pool({
      host: pgHost, database: pgDatabase, user: pgUser, port: pgPort,
      password: tokenData.access_token,
      ssl: { rejectUnauthorized: false },
      max: 3,
    });

    const result = await pool.query(sql);
    await pool.end();
    return result.rows;
  } catch (err: any) {
    console.error('[Lakebase] Query error:', err?.message);
    return [];
  }
}
