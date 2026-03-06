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

export async function queryLakehouse(config: DatabricksConfig, sql: string): Promise<any[]> {
  // TODO: Wire to Databricks SQL endpoint
  console.log(`[Databricks] Would execute SQL: ${sql}`);
  return [];
}

export async function queryLakebase(config: DatabricksConfig, sql: string): Promise<any[]> {
  // TODO: Wire to Lakebase PostgreSQL
  console.log(`[Lakebase] Would execute SQL: ${sql}`);
  return [];
}
