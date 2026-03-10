import { TwinState } from './types';
export interface TwinDataProvider {
    loadState(): Promise<TwinState>;
}
export declare class InMemoryTwinDataProvider implements TwinDataProvider {
    private state;
    private baseline;
    constructor();
    loadState(): Promise<TwinState>;
}
export declare class DatabricksTwinDataProvider implements TwinDataProvider {
    loadState(): Promise<TwinState>;
}
