"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.queryLakehouse = queryLakehouse;
exports.queryLakebase = queryLakebase;
async function queryLakehouse(config, sql) {
    // TODO: Wire to Databricks SQL endpoint
    console.log(`[Databricks] Would execute SQL: ${sql}`);
    return [];
}
async function queryLakebase(config, sql) {
    // TODO: Wire to Lakebase PostgreSQL
    console.log(`[Lakebase] Would execute SQL: ${sql}`);
    return [];
}
