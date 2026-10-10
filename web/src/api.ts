import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { getSession, Session, setSession } from "./session";

export const http = axios.create({ baseURL: "/api/v1" });

http.interceptors.request.use((config) => {
  const session = getSession();
  if (session) config.headers.Authorization = `Bearer ${session.access_token}`;
  return config;
});

// One refresh at a time: several requests failing together must not each spend the single-use refresh token.
let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  const session = getSession();
  if (!session) return Promise.resolve(false);
  refreshing ??= axios
    .post<Session>("/api/v1/auth/refresh", { refresh_token: session.refresh_token })
    .then((r) => {
      setSession(r.data);
      return true;
    })
    .catch(() => {
      setSession(null);
      return false;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

http.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
  const isAuthCall = config?.url?.startsWith("/auth/");
  if (error.response?.status === 401 && config && !config._retried && !isAuthCall && getSession()) {
    config._retried = true;
    if (await refreshSession()) return http(config);
  }
  return Promise.reject(error);
});

/** A protected file as a Blob. A plain link cannot carry the Authorization header, so files are fetched. */
export async function fetchFile(url: string): Promise<Blob> {
  const response = await http.get<Blob>(url.replace(/^\/api\/v1/, ""), { responseType: "blob" });
  return response.data;
}

function saveBlob(blob: Blob, filename: string): void {
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(href);
}

export async function downloadFile(url: string, filename: string): Promise<void> {
  saveBlob(await fetchFile(url), filename);
}

/**
 * A protected PDF as a Blob, fetched as base64 inside JSON. Download managers (Internet Download Manager and
 * the like) swallow anything that looks like a PDF download and hand the page an empty 204, which blanks the
 * preview and makes "Télécharger" save an empty file. A JSON answer is not a download, so it always arrives.
 */
export async function fetchPdf(url: string): Promise<Blob> {
  const { data } = await http.get<{ content_base64: string; content_type: string }>(
    url.replace(/^\/api\/v1/, ""), { params: { encoding: "base64" } },
  );
  const bytes = Uint8Array.from(atob(data.content_base64), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: data.content_type });
}

export async function downloadPdf(url: string, filename: string): Promise<void> {
  saveBlob(await fetchPdf(url), filename);
}

// ------------------------------------------------------------------ types

export type CaseType = "fraude_bancaire" | "intrusion_reseau" | "malware";
export type Priority = "basse" | "moyenne" | "haute";
export type CaseStatus = "en_attente" | "en_cours" | "termine";
export type SolStatus = "pending" | "accepted" | "refused" | "chosen";
export type StageKey = "mandat" | "experts" | "contrat" | "preparation" | "analyse" | "rapport";

export interface Stage {
  key: StageKey;
  label: string;
  done: boolean;
  current: boolean;
}

export interface CaseData {
  case_id: string;
  case_type: CaseType;
  description: string;
  priority: Priority;
  status: CaseStatus;
  created_at: string;
  mandataire: { nom: string; fonction: string };
  chosen_expert_id: number | null;
  signed: boolean;
  stages: Stage[];
  progress: number;
  last_activity: string;
  solicitations: { total: number; pending: number; accepted: number; refused: number };
}

export interface NewCase {
  case_type: CaseType;
  description: string;
  priority: Priority;
  mandataire: { nom: string; fonction: string };
}

export interface Expert {
  id: number;
  nom: string;
  competences: string[];
  bio: string;
  annees_experience: number;
  disponibilite: boolean;
  score: number;
  justification: string;
  weights: { text: number; dispo: number; exp: number };
  breakdown: { text_score: number; dispo_score: number; exp_score: number };
}

export interface Solicitation {
  id: number;
  case_id: string;
  expert_id: number;
  expert_nom: string | null;
  expert_competences: string[];
  status: SolStatus;
  reason: string | null;
  responded_at: string | null;
}

export interface Request {
  id: number;
  case_id: string;
  expert_id: number;
  status: SolStatus;
  reason: string | null;
  responded_at: string | null;
  case: { case_id: string; case_type: CaseType; priority: Priority; description: string; created_at: string };
}

export interface Contract {
  contract_id: string;
  pdf_url: string;
  hash_sha256: string;
  generated_at: string;
}

export interface MissionPrep {
  questions: string[];
  suggested_witnesses: string[];
  checklist: string[];
  guide_pdf_url: string;
}

export interface Entities {
  personnes: string[];
  lieux: string[];
  dates: string[];
  dates_iso: string[];
  montants: string[];
  montants_valeurs: number[];
  heures: string[];
}

export type IncoherenceType = "temporelle" | "geographique" | "factuelle";
export type Severity = "haute" | "moyenne" | "basse";

export interface Incoherence {
  type: IncoherenceType;
  severity: Severity;
  description: string;
  rule: string;
  why: string;
  pv_references: string[];
  evidence: { pv_id: string; excerpt: string }[];
}

export type EntityLabel = "personne" | "lieu" | "date" | "montant" | "heure";
export interface Segment {
  text: string;
  label: EntityLabel | null;
}

export interface PvAnalysis {
  pv_id: string;
  entities: Entities;
  incoherences: Incoherence[];
  score_coherence: number;
  sha256: string;
  analyzed_at: string;
  duration_ms: number;
}

export interface PvDetail {
  pv_id: string;
  witness_name: string;
  sha256: string;
  verified: boolean;
  analyzed_at: string;
  entities: Entities;
  incoherences: Incoherence[];
  score_coherence: number;
  word_count: number;
  segments: Segment[];
}

export interface PvListItem {
  pv_id: string;
  witness_name: string;
  sha256: string;
  analyzed_at: string;
}

export interface PvReport {
  case_id: string;
  pvs: { pv_id: string; witness_name: string; sha256: string; entities: Entities }[];
  incoherences: Incoherence[];
  score_coherence: number;
}

export interface Mission {
  case_id: string;
  case_type: CaseType;
  priority: Priority;
  status: CaseStatus;
  created_at: string;
  expert: { id: number; nom: string };
  pv_count: number;
  incoherence_count: number;
  high_severity_count: number;
  score_coherence: number | null;
  last_pv_at: string | null;
}

export interface Hypothesis {
  id: string;
  label: string;
  actions: string[];
  origin: "type_dossier" | "incoherence";
  basis: string;
  pv_references: string[];
}

export interface PlanStep {
  priority: number;
  action: string;
  label: string;
  outils: string[];
  description: string;
  duree_min: number;
  duree_max: number;
  duree_estimee: string;
  justified_by: string[];
  why: string;
}

export interface Methodology {
  case_id: string;
  hypotheses: Hypothesis[];
  plan: PlanStep[];
  duree_totale_min: number;
  duree_totale_max: number;
  duree_totale_estimee: string;
}

export interface TechReportIn {
  rapport_id: string;
  action: string;
  outils: string[];
  resultats: string;
  preuves: string[];
}

export interface TechReportScored extends TechReportIn {
  score: number;
  rank: number;
  in_chain: boolean;
  breakdown: { completude: number; pertinence: number; preuves: number };
  weights: { completude: number; pertinence: number; preuves: number };
  details: { champs_manquants: string[]; concepts_trouves: string[]; concepts_absents: string[]; nb_preuves: number };
}

export interface ReportsAnalysis {
  case_id: string;
  rapports: TechReportScored[];
  chaine_optimale: { rapport_id: string; action: string; score: number; preuves_cles: string[] }[];
  score_global: number | null;
  recommandations: string[];
  actions_connues: Record<string, string>;
}

export interface OutlineSection {
  key: string;
  title: string;
  points: string[];
}

export interface FinalReport {
  report_id: string;
  case_id: string;
  version: number;
  sha256: string;
  generated_at: string;
  generated_by: string;
  pseudonymized: boolean;
  pdf_url: string;
  outline: OutlineSection[];
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  module: string;
  action: string;
  case_id: string | null;
  user: string | null;
  payload: Record<string, unknown>;
  file: string | null;
  hash: string | null;
  entry_hash: string;
  prev_hash: string;
}

export interface AuditPage {
  case_id: string;
  total: number;
  modules: string[];
  logs: AuditEntry[];
}

export interface AuditFilters {
  module?: string;
  actor?: string;
  action?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface Invitation {
  expert_name: string;
  email: string;
}

// -------------------------------------------------------------------- calls

export const api = {
  // auth
  login: (email: string, password: string) => http.post<Session>("/auth/login", { email, password }).then((r) => r.data),
  register: (email: string, display_name: string, password: string) =>
    http.post<Session>("/auth/register", { email, display_name, password }).then((r) => r.data),
  invitation: (token: string) => http.get<Invitation>("/auth/invitation", { params: { token } }).then((r) => r.data),
  activate: (token: string, password: string, display_name?: string) =>
    http.post<Session>("/auth/activate", { token, password, display_name }).then((r) => r.data),
  logout: (refresh_token: string) => http.post("/auth/logout", { refresh_token }),

  // cases (A) and experts (B)
  listCases: () => http.get<{ total: number; cases: CaseData[] }>("/cases?limit=50").then((r) => r.data.cases),
  getCase: (id: string) => http.get<CaseData>(`/cases/${id}`).then((r) => r.data),
  createCase: (body: NewCase) => http.post<{ case_id: string }>("/cases", body).then((r) => r.data),
  experts: (id: string) => http.get<{ experts: Expert[] }>(`/cases/${id}/experts`).then((r) => r.data.experts),
  sign: (id: string, signatory_name: string) => http.post(`/cases/${id}/sign`, { signatory_name }),

  // acceptance workflow (D)
  solicit: (case_id: string, expert_ids: number[]) => http.post("/solicitations", { case_id, expert_ids }),
  solicitations: (id: string) =>
    http.get<{ solicitations: Solicitation[] }>(`/solicitations?case_id=${id}`).then((r) => r.data.solicitations),
  myRequests: () => http.get<{ solicitations: Request[] }>("/solicitations/mine").then((r) => r.data.solicitations),
  respond: (sid: number, status: "accepted" | "refused", reason?: string) =>
    http.put(`/solicitations/${sid}/respond`, { status, reason }),
  select: (case_id: string, expert_id: number) => http.post("/solicitations/select", { case_id, expert_id }),

  // contract (C)
  generateContract: (case_id: string) => http.post<Contract>("/contracts/generate", { case_id }).then((r) => r.data),
  contract: (case_id: string) =>
    http
      .get<Contract>(`/contracts?case_id=${case_id}`)
      .then((r) => r.data)
      .catch((e) => {
        if (axios.isAxiosError(e) && e.response?.status === 404) return null;
        throw e;
      }),

  // mission preparation (E)
  prepareMission: (body: { case_id: string; questions?: string[]; suggested_witnesses?: string[]; checklist?: string[] }) =>
    http.post<MissionPrep>("/mission/prepare", body).then((r) => r.data),

  // PV analysis (F)
  missions: () => http.get<{ total: number; missions: Mission[] }>("/pv/missions").then((r) => r.data.missions),
  analyzePv: (body: { case_id: string; pv_id: string; pv_text: string; witness_name: string; pseudonymize: boolean }) =>
    http.post<PvAnalysis>("/pv/analyze", body).then((r) => r.data),
  listPvs: (case_id: string) => http.get<{ pvs: PvListItem[] }>("/pv", { params: { case_id } }).then((r) => r.data.pvs),
  pvDetail: (case_id: string, pv_id: string, pseudonymize: boolean) =>
    http.get<PvDetail>(`/pv/${pv_id}`, { params: { case_id, pseudonymize } }).then((r) => r.data),
  pvReport: (case_id: string, pseudonymize: boolean) =>
    http.get<PvReport>("/pv/report", { params: { case_id, pseudonymize } }).then((r) => r.data),

  // methodology (G), technical reports (H), final report (I)
  methodology: (case_id: string) => http.get<Methodology>("/methodology", { params: { case_id } }).then((r) => r.data),
  analyzeReports: (case_id: string, rapports: TechReportIn[]) =>
    http.post<ReportsAnalysis>("/reports/analyze", { case_id, rapports }).then((r) => r.data),
  reportsAnalysis: (case_id: string) =>
    http.get<ReportsAnalysis>("/reports/analysis", { params: { case_id } }).then((r) => r.data),
  deleteTechReport: (case_id: string, rapport_id: string) => http.delete(`/reports/${rapport_id}`, { params: { case_id } }),
  generateReport: (body: { case_id: string; conclusion: string; pseudonymize: boolean }) =>
    http.post<FinalReport>("/reports/generate", body).then((r) => r.data),
  finalReports: (case_id: string) =>
    http.get<{ reports: FinalReport[] }>("/reports", { params: { case_id } }).then((r) => r.data.reports),

  // audit (J)
  auditLogs: (case_id: string, filters: AuditFilters = {}) =>
    http.get<AuditPage>("/audit/logs", { params: { case_id, ...filters } }).then((r) => r.data),
  verifyChain: () =>
    http.get<{ valid: boolean; entries: number; broken_at: number | null }>("/audit/chain/verify").then((r) => r.data),
};
