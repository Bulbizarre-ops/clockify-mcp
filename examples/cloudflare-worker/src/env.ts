export type Env = {
  DEFAULT_ACCESS_MODE?: string;
  DEFAULT_REGION?: string;
  /** Workspace plan gate: free | standard | pro | all (default all when unset in code paths that omit it). */
  DEFAULT_PLAN?: string;
  OAUTH_KV: KVNamespace;
};
