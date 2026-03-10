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
export declare function queryLakehouse(config: DatabricksConfig, sql: string): Promise<any[]>;
export declare function queryLakebase(config: DatabricksConfig, sql: string): Promise<any[]>;
