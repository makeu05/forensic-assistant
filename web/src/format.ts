import axios from "axios";
import type { CaseType, IncoherenceType, Priority } from "./api";

export const CASE_TYPE_LABEL: Record<CaseType, string> = {
  fraude_bancaire: "Fraude bancaire",
  intrusion_reseau: "Intrusion réseau",
  malware: "Logiciel malveillant",
};

export const CASE_TYPE_HELP: Record<CaseType, string> = {
  fraude_bancaire: "Virements suspects, comptes compromis, détournement de fonds.",
  intrusion_reseau: "Accès non autorisé à un système d'information, exfiltration de données.",
  malware: "Rançongiciel, code malveillant, poste ou serveur infecté.",
};

export const PRIORITY_LABEL: Record<Priority, string> = { basse: "Basse", moyenne: "Moyenne", haute: "Haute" };

export const INCOHERENCE_LABEL: Record<IncoherenceType, string> = {
  temporelle: "Incohérence temporelle",
  geographique: "Incohérence géographique",
  factuelle: "Incohérence factuelle",
};

export const ACTION_TITLE: Record<string, string> = {
  analyse_logs: "Analyse des journaux",
  analyse_reseau: "Analyse du trafic réseau",
  analyse_disque: "Analyse de disque",
  malware_analysis: "Analyse de code malveillant",
};

export const MODULE_LABEL: Record<string, string> = {
  A: "Mandat", B: "Experts", C: "Contrat", D: "Acceptation", E: "Préparation", F: "Analyse des PV",
  G: "Méthodologie", H: "Rapports techniques", I: "Rapport final", AUTH: "Compte",
};

export const AUDIT_ACTION: Record<string, string> = {
  create_case: "Mandat créé",
  sign_mandate: "Mandat signé",
  match_experts: "Experts proposés",
  solicit_experts: "Experts sollicités",
  invite_expert: "Invitation envoyée à un expert",
  notify_expert: "Expert notifié d'une demande",
  expert_accepted: "Mission acceptée par l'expert",
  expert_refused: "Mission refusée par l'expert",
  select_expert: "Expert choisi",
  generate_contract: "Contrat généré",
  generate_contract_failed: "Échec de génération du contrat",
  prepare_mission: "Mission préparée",
  analyze_pv: "PV analysé",
  analyze_reports: "Rapports techniques analysés",
  delete_report: "Rapport technique supprimé",
  generate_report: "Rapport final généré",
  generate_report_failed: "Échec de génération du rapport",
  register: "Compte créé",
  login: "Connexion",
  activate_account: "Compte expert activé",
  account_locked: "Compte verrouillé après plusieurs échecs",
  refresh_reuse_detected: "Réutilisation d'un jeton détectée",
};

export const auditActionLabel = (action: string) => AUDIT_ACTION[action] ?? action.replaceAll("_", " ");

const dateFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
});

export const formatDate = (iso: string) => dateFmt.format(new Date(iso));
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso));

const rtf = new Intl.RelativeTimeFormat("fr", { numeric: "auto" });

export function relativeTime(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return "à l'instant";
}

export const shortHash = (hash: string, head = 12, tail = 6) =>
  hash.length > head + tail + 1 ? `${hash.slice(0, head)}…${hash.slice(-tail)}` : hash;

export const percent = (value: number) => `${Math.round(value * 100)} %`;

const KNOWN: [RegExp, string][] = [
  [/must be signed/i, "Le mandat doit d'abord être signé."],
  [/no expert has been selected/i, "Choisissez d'abord un expert pour ce dossier."],
  [/already chosen/i, "Un expert a déjà été choisi pour ce dossier."],
  [/invalid transition/i, "Cette réponse a déjà été enregistrée et ne peut plus être modifiée."],
  [/integrity check failed/i, "Contrôle d'intégrité échoué : le fichier stocké a été modifié."],
  [/already exists/i, "Un compte existe déjà avec cette adresse e-mail."],
  [/invalid or expired invitation/i, "Ce lien d'invitation est invalide ou a expiré."],
  [/too many failed/i, "Trop de tentatives échouées. Réessayez dans quelques minutes."],
  [/not solicited/i, "Cet expert n'a pas été sollicité pour ce dossier."],
];

/** A friendly French message for any error from the API. */
export function frenchError(e: unknown, context: "login" | "default" = "default"): string {
  if (!axios.isAxiosError(e)) return "Une erreur inattendue s'est produite.";
  if (!e.response) return "Impossible de joindre le serveur. Vérifiez votre connexion et réessayez.";
  const { status, data } = e.response;
  const detail = typeof data?.detail === "string" ? data.detail : "";
  const known = KNOWN.find(([rx]) => rx.test(detail));
  if (known) return known[1];
  if (status === 401) {
    return context === "login" ? "Adresse e-mail ou mot de passe incorrect." : "Votre session a expiré. Reconnectez-vous.";
  }
  if (status === 403) return "Cette action n'est pas disponible pour votre rôle.";
  if (status === 404) return "Élément introuvable ou inaccessible.";
  if (status === 409) return detail && /[éèàê]/.test(detail) ? detail : "Action impossible dans l'état actuel du dossier.";
  if (status === 422) return "Certains champs sont invalides. Vérifiez votre saisie.";
  if (status === 429) return "Trop de tentatives. Réessayez dans quelques minutes.";
  if (status >= 500) return "Le serveur a rencontré un problème. Réessayez dans un instant.";
  return "Une erreur s'est produite. Réessayez.";
}
