/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where the API lives. Defaults to http://localhost:8000; "" uses the proxy. */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
