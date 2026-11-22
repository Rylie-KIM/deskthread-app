// The shapes below mirror contracts/api.py (contract 1.0). The page talks only to the
// backend it was served from, and sends the session token with every call.

export type SourceStatus = "off" | "on" | "locked";
export type OsPermission = "not_needed" | "granted" | "missing" | "unknown";

export interface SourceState {
  source_id: string;
  kind: string;
  label: string;
  status: SourceStatus;
  os_permission: OsPermission;
  allowed_scope_ids: string[];
  items_in_memory: number;
}
export interface FolderInfo { path: string; name: string; files: number; pictures: number; videos: number; other: number }
export interface Scope { scope_id: string; label: string; item_count: number | null }
export interface PermissionRequest {
  source_id: string;
  label: string;
  what_will_be_read: string;
  scopes: Scope[];
  os_permission: OsPermission;
}
export interface Meeting { meeting_id: string; title: string; start: string; person: string }
export interface Citation {
  item_id: string;
  unit: number;
  quote: string;
  source_id: string;
  source_label: string;
  title: string;
  date: string | null;
  undated: boolean;
  read_by_model: boolean;
}
export type PointStatus = "done" | "open" | "changed" | "superseded";
export interface BriefPoint { label: string; status: PointStatus; citations: Citation[]; note: string; matched: string[] }
export interface Coverage {
  accessible: number;
  searched: number;
  unsupported: number;
  given_to_model: number;
  cited: number;
  by_source: Record<string, number>;
  not_accessible: Record<string, number | null>;
}
export interface GateResult { gate: string; outcome: "pass" | "warn" | "fail" | "skipped"; detail: string }
export interface Answer {
  kind: "brief" | "not_found" | "no_sources" | "stopped";
  question: string;
  points: BriefPoint[];
  message: string;
  coverage: Coverage;
  gate_trace: GateResult[];
  given_item_ids: string[];
  seconds: number;
  show_status: boolean;
  summary: string[];
  model_name: string;
  left_out: Record<string, number>;
}
export interface Progress { step: string; number: number; of: number; detail: string }
export interface ItemView {
  item_id: string;
  source_label: string;
  kind: string;
  title: string;
  date: string | null;
  location: string;
  units: { number: number; text: string }[];
  read_by_model: boolean;
  has_image: boolean;
  origin: "file" | "app" | "";
}
export interface ProcessInfo { name: string; pid: number; memory_mb: number }
export interface MemoryState {
  items_held: number;
  items_by_source: Record<string, number>;
  image_readings_held: number;
  model_loaded: boolean;
  processes: ProcessInfo[];
  mac_memory_mb: number;
  mac_free_mb: number;
}
export interface Connection { process: string; pid: number; remote: string; local_only: boolean }
export interface ConnectionCheck { command: string; output: string; connections: Connection[]; all_local: boolean; ran_at: string }
export interface FileChange { name: string; what: "added" | "changed" | "removed"; when: string | null; owner: string }
export interface FolderHash { label: string; files: number; before: string; now: string; unchanged: boolean; changes: FileChange[]; changes_total: number }
export interface AuditLine { at: string; action: string; source_id: string; count: number }
export interface Proof {
  sampled_at: string;
  connections: Connection[];
  all_local: boolean;
  folders: FolderHash[];
  files_written_by_app: number;
  telemetry_off: Record<string, boolean>;
  audit: AuditLine[];
  limits: string;
}
export interface Receipt {
  items_read: number;
  items_given_to_model: number;
  questions: number;
  memory_cleared: boolean;
  model_unloaded: boolean;
  files_written_by_app: number;
  all_connections_local: boolean;
  folders: FolderHash[];
  limits: string;
  read_by_source: Record<string, number>;
  given_by_source: Record<string, number>;
}
export interface SessionInfo {
  app: string;
  contract_version: string;
  model_tag: string;
  model_digest: string;
  prompt_version: string;
  now: string;
  demo_folder: string;
}

export interface ModelInfo {
  tag: string;
  name: string;
  maker: string;
  download_gb: number;
  reads_pictures: boolean;
  good_for: string;
  installed: boolean;
  selected: boolean;
  tested: boolean;
  downloading: number | null;
  failed: boolean;
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

// The token arrives in the address fragment (#t=...), which a browser never sends over the
// network. It is kept in memory only: no cookie, no localStorage.
let token = "";
export function readToken(): string {
  if (!token && typeof window !== "undefined") {
    token = new URLSearchParams(window.location.hash.slice(1)).get("t") ?? "";
  }
  return token;
}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    cache: "no-store",
    credentials: "omit",
    headers: { "X-DeskThread-Token": readToken(), ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = data as { code?: string; message?: string };
    throw new ApiError(err.code ?? "E-999", err.message ?? "The request failed.", response.status);
  }
  return data as T;
}

const id = encodeURIComponent;
export const api = {
  session: () => call<SessionInfo>("GET", "/api/session"),
  sources: () => call<SourceState[]>("GET", "/api/sources"),
  folders: () => call<FolderInfo[]>("GET", "/api/folders"),
  chooseFolder: (path: string) => call<SourceState[]>("POST", "/api/folder", { path }),
  removeFolder: (path: string) => call<SourceState[]>("POST", "/api/folder/remove", { path }),
  request: (sourceId: string) => call<PermissionRequest>("GET", `/api/sources/${id(sourceId)}/request`),
  grant: (sourceId: string, scopeIds: string[], period: { days?: number; since?: string; until?: string } = {}) =>
    call<SourceState>("POST", `/api/sources/${id(sourceId)}/grant`, { scope_ids: scopeIds, days: period.days ?? null, since: period.since ?? null, until: period.until ?? null }),
  iconUrl: (sourceId: string) => `/api/sources/${id(sourceId)}/icon?t=${id(readToken())}`,
  revoke: (sourceId: string) => call<SourceState>("POST", `/api/sources/${id(sourceId)}/revoke`),
  revokeAll: () => call<SourceState[]>("POST", "/api/sources/revoke-all"),
  meetings: () => call<Meeting[]>("GET", "/api/meetings"),
  prepare: (meetingId: string) => call<Answer>("POST", "/api/prepare", { meeting_id: meetingId }),
  ask: (question: string) => call<Answer>("POST", "/api/ask", { question }),
  progress: () => call<Progress>("GET", "/api/progress"),
  cancel: () => call<Progress>("POST", "/api/cancel"),
  item: (itemId: string) => call<ItemView>("GET", `/api/items/${id(itemId)}`),
  reveal: (itemId: string) => call<ItemView>("POST", `/api/items/${id(itemId)}/reveal`),
  imageUrl: (itemId: string) => `/api/items/${id(itemId)}/image?t=${id(readToken())}`,
  models: () => call<ModelInfo[]>("GET", "/api/models"),
  selectModel: (tag: string) => call<ModelInfo[]>("POST", "/api/models/select", { tag }),
  downloadModel: (tag: string) => call<ModelInfo[]>("POST", "/api/models/download", { tag }),
  memory: () => call<MemoryState>("GET", "/api/memory"),
  forget: () => call<MemoryState>("POST", "/api/forget"),
  proof: () => call<Proof>("GET", "/api/proof"),
  checkConnections: () => call<ConnectionCheck>("GET", "/api/proof/connections"),
  endSession: () => call<Receipt>("POST", "/api/end-session"),
};

// What to tell a person when something did not work: plain words, never a code.
export function plain(err: unknown): string {
  if (!(err instanceof ApiError)) return "That did not work. Please try again.";
  const byCode: Record<string, string> = {
    "E-107": "macOS has not allowed DeskThread to read this app yet. Open System Settings, Privacy & Security, Automation, and switch DeskThread on.",
    "E-202": "That app did not answer. Open it once, then try again.",
    "E-301": "The AI on this Mac is not ready. Wait a moment, or choose another AI model.",
    "E-302": "This AI model is not on this Mac yet. Download it first.",
  };
  return byCode[err.code] ?? (err.message ? err.message.charAt(0).toUpperCase() + err.message.slice(1) + "." : "That did not work. Please try again.");
}

// In the Mac window, a small bridge lets the page ask the window for a few things.
type Bridge = { postMessage: (message: string) => void };
export function macWindow(): Bridge | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { webkit?: { messageHandlers?: { deskthread?: Bridge } } };
  return w.webkit?.messageHandlers?.deskthread ?? null;
}

export function day(iso: string | null): string {
  if (!iso) return "undated";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}
