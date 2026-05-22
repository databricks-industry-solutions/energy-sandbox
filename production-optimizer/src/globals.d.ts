declare module 'express' {
  export interface Request { body: any; params: any; query: any; user?: any; }
  export interface Response { json(data: any): any; status(code: number): Response; sendFile(path: string): void; }
  export interface NextFunction { (err?: any): void; }
  export interface Router { get: any; post: any; put: any; delete: any; use: any; }
  function express(): any;
  namespace express {
    function json(): any;
    function static(path: string): any;
    function Router(): Router;
  }
  export = express;
}
declare module 'cors' {
  const cors: any;
  export = cors;
}
declare module 'path' {
  const path: any;
  export = path;
}
declare var process: any;
declare var __dirname: string;
declare var console: any;
declare function require(id: string): any;
