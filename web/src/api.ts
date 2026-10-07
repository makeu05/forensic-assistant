import axios from "axios";

export const http = axios.create({ baseURL: "/api/v1" });

export type CaseType = "fraude_bancaire" | "intrusion_reseau" | "malware";
export type Priority = "basse" | "moyenne" | "haute";
export type CaseStatus = "en_attente" | "en_cours" | "termine";

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
}

export interface Expert {
  id: number;
  nom: string;
  competences: string[];
  score: number;
  justification: string;
  breakdown: { text_score: number; dispo_score: number; exp_score: number };
}

export interface Solicitation {
  id: number;
  case_id: string;
  expert_id: number;
  expert_nom: string | null;
  expert_competences: string[];
  status: "pending" | "accepted" | "refused" | "chosen";
  reason: string | null;
  responded_at: string | null;
}

export interface Contract {
  contract_id: string;
  pdf_url: string;
  hash_sha256: string;
  generated_at: string;
}

export interface NewCase {
  case_type: CaseType;
  description: string;
  priority: Priority;
  mandataire: { nom: string; fonction: string };
}

export const CASE_TYPE_LABEL: Record<CaseType, string> = {
  fraude_bancaire: "Fraude bancaire",
  intrusion_reseau: "Intrusion reseau",
  malware: "Malware",
};

export const STATUS_LABEL: Record<CaseStatus, string> = {
  en_attente: "En attente",
  en_cours: "En cours",
  termine: "Termine",
};

/** Readable message from an axios error (FastAPI returns {detail}). */
export function errorMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join(", ");
    return e.message;
  }
  return "Erreur inconnue";
}

export const api = {
  listCases: () => http.get<{ total: number; cases: CaseData[] }>("/cases?limit=50").then((r) => r.data),
  getCase: (id: string) => http.get<CaseData>(`/cases/${id}`).then((r) => r.data),
  createCase: (body: NewCase) => http.post<{ case_id: string }>("/cases", body).then((r) => r.data),
  experts: (id: string) => http.get<{ experts: Expert[] }>(`/cases/${id}/experts`).then((r) => r.data.experts),
  solicit: (case_id: string, expert_ids: number[]) => http.post("/solicitations", { case_id, expert_ids }),
  solicitations: (id: string) =>
    http.get<{ solicitations: Solicitation[] }>(`/solicitations?case_id=${id}`).then((r) => r.data.solicitations),
  respond: (sid: number, status: "accepted" | "refused", reason?: string) =>
    http.put(`/solicitations/${sid}/respond`, { status, reason }),
  select: (case_id: string, expert_id: number) => http.post("/solicitations/select", { case_id, expert_id }),
  sign: (id: string, signatory_name: string) => http.post(`/cases/${id}/sign`, { signatory_name }),
  generateContract: (case_id: string) => http.post<Contract>("/contracts/generate", { case_id }).then((r) => r.data),
  contract: (case_id: string) =>
    http
      .get<Contract>(`/contracts?case_id=${case_id}`)
      .then((r) => r.data)
      .catch((e) => {
        if (axios.isAxiosError(e) && e.response?.status === 404) return null;
        throw e;
      }),
};
