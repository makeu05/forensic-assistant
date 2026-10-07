import type { CaseType, TechReportIn } from "../../api";

export interface ExamplePv {
  witness: string;
  text: string;
}

/**
 * Sample statements from the project's test dataset, so the analysis can be tried without real data.
 * Each case type has two statements that contradict each other.
 */
export const EXAMPLE_PVS: Record<CaseType, ExamplePv[]> = {
  fraude_bancaire: [
    {
      witness: "Pierre Lambert",
      text: "PROCÈS-VERBAL D'AUDITION\nDate : 12/10/2025\nTémoin : Pierre Lambert\n\nDÉCLARATION :\nJe m'appelle Pierre Lambert, responsable comptable de la société Alpha à Lyon. J'ai autorisé le virement de 50 000 euros le 10/10/2025 à 14h. Le bénéficiaire était une société basée à Marseille. Mme Sophie Girard m'avait transmis la demande.",
    },
    {
      witness: "Claire Morel",
      text: "Le compte de la société a été compromis le 05/10/2025 selon la banque. M. Hugo Perrin, du service informatique, a découvert l'intrusion à Paris. Les pertes s'élèvent à 50 000 euros.",
    },
  ],
  intrusion_reseau: [
    {
      witness: "Marc Leroy",
      text: "Le 14 octobre 2025, la session SSH du compte de M. Antoine Bernard est ouverte depuis 192.168.1.50 à 03:42. Environ 2 GB de données ont été exfiltrés. Le serveur se trouve au siège social de Bordeaux.",
    },
    {
      witness: "Antoine Bernard",
      text: "Je suis en vacances à Paris depuis le 10 octobre 2025. Je n'ai pas accès au réseau de l'entreprise. Ma collègue Julie Moreau peut confirmer que j'ai quitté Bordeaux le 9 octobre.",
    },
  ],
  malware: [
    {
      witness: "Nadia Fofana",
      text: "J'ai cliqué sur la pièce jointe mardi matin. Mon poste s'est mis à chiffrer les fichiers vers 10h30. J'ai prévenu M. Olivier Garnier, le responsable informatique, à Nantes.",
    },
    {
      witness: "Olivier Garnier",
      text: "Selon les journaux du serveur de messagerie, l'e-mail contenant la pièce jointe a été reçu mercredi à 08h12. La rançon demandée est de 15 000 euros en bitcoin. Les sauvegardes du 1er octobre 2025 sont intactes.",
    },
  ],
};

export const EXAMPLE_TECH_REPORT: Omit<TechReportIn, "rapport_id"> = {
  action: "analyse_logs",
  outils: ["Splunk", "ELK"],
  resultats:
    "Les journaux de la banque, corrélés avec l'horodatage des connexions, montrent une session ouverte depuis une adresse inhabituelle. L'empreinte hash des fichiers extraits a été relevée et l'artefact de session conservé.",
  preuves: ["extrait_journaux.txt", "export_session.csv", "capture_ecran.png"],
};
