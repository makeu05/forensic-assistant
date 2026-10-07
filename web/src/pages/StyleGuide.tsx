import { ReactNode, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert, Box, Button, Card, Chip, Container, FormControlLabel, Switch, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/FileDownloadOutlined";
import { AuditEntry, Segment, Stage } from "../api";
import { useSettings } from "../settings";
import { brand, fonts, palette, scale } from "../theme/tokens";
import { useTokens } from "../theme/useTokens";
import AuditTimeline from "../components/ui/AuditTimeline";
import EntityHighlighter from "../components/ui/EntityHighlighter";
import ExplainPopover from "../components/ui/ExplainPopover";
import HashBadge from "../components/ui/HashBadge";
import ScoreBreakdownBar from "../components/ui/ScoreBreakdownBar";
import ScoreRing from "../components/ui/ScoreRing";
import SeverityChip from "../components/ui/SeverityChip";
import StatusChip, { Status } from "../components/ui/StatusChip";
import { useToast } from "../components/ui/Toast";
import WorkflowStepper from "../components/ui/WorkflowStepper";
import { PriorityChip } from "./Home";

function luminance(hex: string) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const ratio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <Box component="section" aria-labelledby={id} sx={{ mb: 7 }}>
      <Typography id={id} variant="h2" component="h2" sx={{ mb: 3 }}>{title}</Typography>
      {children}
    </Box>
  );
}

function Swatch({ name, hex, usage }: { name: string; hex: string; on?: string; usage: string }) {
  // label colour: whichever of white or ink reads better on this swatch
  const on = ratio(hex, "#FFFFFF") >= ratio(hex, "#101828") ? "#FFFFFF" : "#101828";
  return (
    <Box sx={{ border: 1, borderColor: "divider", borderRadius: 2.5, overflow: "hidden", bgcolor: "background.paper" }}>
      <Box sx={{ bgcolor: hex, height: 72, display: "flex", alignItems: "flex-end", p: 1.5 }}>
        <Typography variant="caption" sx={{ color: on, fontWeight: 600 }}>Aa {ratio(hex, on).toFixed(1)} : 1</Typography>
      </Box>
      <Box sx={{ p: 1.5 }}>
        <Typography variant="subtitle2">{name}</Typography>
        <Typography variant="caption" sx={{ fontFamily: fonts.mono, display: "block" }}>{hex}</Typography>
        <Typography variant="caption" color="text.secondary">{usage}</Typography>
      </Box>
    </Box>
  );
}

const SAMPLE_SEGMENTS: Segment[] = [
  { text: "J'ai autorisé le virement de ", label: null }, { text: "50 000 euros", label: "montant" }, { text: " le ", label: null },
  { text: "10/10/2025", label: "date" }, { text: " à ", label: null }, { text: "14h", label: "heure" }, { text: " depuis ", label: null },
  { text: "Lyon", label: "lieu" }, { text: ", sur demande de ", label: null }, { text: "Mme Sophie Girard", label: "personne" }, { text: ".", label: null },
];

const SAMPLE_STAGES: Stage[] = [
  { key: "mandat", label: "Mandat", done: true, current: false }, { key: "experts", label: "Experts", done: true, current: false },
  { key: "contrat", label: "Contrat", done: true, current: false }, { key: "preparation", label: "Préparation", done: false, current: true },
  { key: "analyse", label: "Analyse", done: false, current: false }, { key: "rapport", label: "Rapport", done: false, current: false },
];

const HASH = "a3f5e8d2c1b94e7f60a1d3c5b7e9f2a4c6d8e0f1a2b3c4d5e6f708192a3b4c5d";
const SAMPLE_AUDIT: AuditEntry[] = [
  { id: 3, timestamp: "2025-10-16T14:40:00Z", module: "C", action: "generate_contract", case_id: "x", user: "juge.dupont@tribunal.fr", payload: { version: 1 }, file: "contracts/c7d4f0a1/mandat.pdf", hash: HASH, entry_hash: HASH, prev_hash: HASH.split("").reverse().join("") },
  { id: 2, timestamp: "2025-10-16T14:35:12Z", module: "B", action: "match_experts", case_id: "x", user: "juge.dupont@tribunal.fr", payload: { expert_ids: [42, 18, 7] }, file: null, hash: null, entry_hash: HASH, prev_hash: HASH },
  { id: 1, timestamp: "2025-10-16T14:32:00Z", module: "A", action: "create_case", case_id: "x", user: "juge.dupont@tribunal.fr", payload: {}, file: null, hash: null, entry_hash: HASH, prev_hash: "0".repeat(64) },
];

const STATUSES: Status[] = ["en_attente", "en_cours", "termine", "pending", "accepted", "refused", "chosen"];

/** A reference page for the design system: tokens, type, controls and every reusable component. */
export default function StyleGuide() {
  const { mode, setMode } = useSettings();
  const toast = useToast();
  const p = useTokens();
  const light = palette.light;
  const [showError, setShowError] = useState(true);

  const swatches = [
    { name: "Navy 900", hex: brand.navy900, on: "#FFFFFF", usage: "Barre latérale, barre du haut, titres" },
    { name: "Navy 700", hex: brand.navy700, on: "#FFFFFF", usage: "Choix retenu, surfaces sombres" },
    { name: "Bleu d'action", hex: light.primary, on: "#FFFFFF", usage: "Boutons, liens, sélection" },
    { name: "Cyan de marque", hex: brand.cyan, on: brand.navy900, usage: "Focus, icônes sur fond sombre. Jamais du texte sur blanc" },
    { name: "Fond", hex: light.bg, on: light.text, usage: "Arrière-plan des pages" },
    { name: "Surface", hex: light.surface, on: light.text, usage: "Cartes, champs" },
    { name: "Texte principal", hex: light.text, on: "#FFFFFF", usage: "Texte courant" },
    { name: "Texte secondaire", hex: light.textSecondary, on: "#FFFFFF", usage: "Aides, légendes" },
    { name: "Succès", hex: light.success, on: "#FFFFFF", usage: "Validé, vérifié. Texte : #0E6B4C sur fond teinté" },
    { name: "Alerte", hex: light.warning, on: "#FFFFFF", usage: "Icônes et barres. Texte : #8A5A00 (le #B7791F d'origine ne passe pas AA)" },
    { name: "Danger", hex: light.danger, on: "#FFFFFF", usage: "Erreur, refus, sévérité haute" },
    { name: "Information", hex: light.info, on: "#FFFFFF", usage: "Neutre informatif. Texte : #086585 sur fond teinté" },
  ];

  return (
    <Box sx={{ bgcolor: "background.default", minHeight: "100vh", py: 4 }}>
      <Container maxWidth="lg" component="main" id="main">
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2, mb: 4 }}>
          <Button component={RouterLink} to="/" startIcon={<ArrowBackIcon />}>Retour à Locard</Button>
          <ToggleButtonGroup exclusive size="small" value={mode} onChange={(_, v) => v && setMode(v)} aria-label="Thème">
            <ToggleButton value="light">Clair</ToggleButton>
            <ToggleButton value="dark">Sombre</ToggleButton>
          </ToggleButtonGroup>
        </Box>
        <Typography variant="h1" component="h1" sx={{ mb: 1 }}>Guide de style Locard</Typography>
        <Typography color="text.secondary" sx={{ mb: 6, maxWidth: 720 }}>
          Les jetons de couleur, la typographie et les composants de l'interface. Sobre, calme, rigoureux : une plateforme sérieuse,
          jamais tape-à-l'œil. Les rapports de contraste affichés sont calculés en direct sur le mode clair.
        </Typography>

        <Section id="couleurs" title="Couleurs">
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(3, 1fr)", lg: "repeat(4, 1fr)" } }}>
            {swatches.map((s) => <Swatch key={s.name} {...s} />)}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Le contraste minimal AA est de 4,5 : 1 pour le texte et 3 : 1 pour les éléments graphiques. Un script
            (<code>scripts/check-contrast.mjs</code>) contrôle toutes les paires, en mode clair et sombre.
          </Typography>
        </Section>

        <Section id="typo" title="Typographie">
          <Card sx={{ p: 3, display: "grid", gap: 2 }}>
            {([["32", "h1", "Titre de page"], ["24", "h2", "Titre de section"], ["20", "h3", "Titre de carte"], ["16", "body1", "Texte courant des vues mandataire : 16 px, interligne 1,5."], ["14", "body2", "Texte dense des tableaux experts : 14 px."], ["12", "caption", "Légendes et aides : 12 px."]] as const).map(([px, variant, text]) => (
              <Box key={px} sx={{ display: "flex", alignItems: "baseline", gap: 2, flexWrap: "wrap" }}>
                <Typography variant="caption" sx={{ width: 40, fontFamily: fonts.mono }}>{px} px</Typography>
                <Typography variant={variant} component="p" sx={{ m: 0 }}>{text}</Typography>
              </Box>
            ))}
            <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
              <Typography sx={{ fontWeight: 400 }}>Inter 400 Regular</Typography>
              <Typography sx={{ fontWeight: 500 }}>Inter 500 Medium</Typography>
              <Typography sx={{ fontWeight: 600 }}>Inter 600 SemiBold</Typography>
            </Box>
            <Typography sx={{ fontFamily: fonts.mono, fontSize: 14 }}>JetBrains Mono : {HASH.slice(0, 40)} · 7fb0bd10-3e43-4671</Typography>
            <Typography variant="caption" color="text.secondary">Échelle : {Object.values(scale).join(" / ")}. Trois graisses seulement : 400, 500 et 600.</Typography>
          </Card>
        </Section>

        <Section id="boutons" title="Boutons et champs">
          <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
            <Card sx={{ p: 3, display: "grid", gap: 2 }}>
              <Typography variant="h4" component="h3">Boutons</Typography>
              <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
                <Button variant="contained">Action principale</Button>
                <Button variant="outlined">Secondaire</Button>
                <Button>Texte</Button>
                <Button variant="contained" startIcon={<DownloadIcon />}>Avec icône</Button>
                <Button variant="contained" disabled>Désactivé</Button>
                <Button variant="contained" color="error">Destructif</Button>
              </Box>
              <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", flexWrap: "wrap" }}>
                <Button variant="contained" size="small">Petit</Button>
                <Button variant="contained">Moyen</Button>
                <Button variant="contained" size="large">Grand</Button>
              </Box>
              <Typography variant="caption" color="text.secondary">Un seul bouton principal par écran. Au clavier, le focus est un anneau bleu cerclé d'un halo cyan.</Typography>
            </Card>
            <Card sx={{ p: 3, display: "grid", gap: 2 }}>
              <Typography variant="h4" component="h3">Champs</Typography>
              <TextField label="Nom du mandataire" defaultValue="M. Dupont" helperText="Tel qu'il apparaîtra sur le mandat." />
              <TextField label="Adresse e-mail" error={showError} defaultValue="dupont@" helperText={showError ? "Saisissez une adresse valide, par exemple nom@organisation.fr." : " "} />
              <FormControlLabel control={<Switch checked={showError} onChange={(e) => setShowError(e.target.checked)} />} label="Afficher l'état d'erreur" />
            </Card>
          </Box>
        </Section>

        <Section id="pastilles" title="Pastilles d'état et de sévérité">
          <Card sx={{ p: 3, display: "grid", gap: 3 }}>
            <Box><Typography variant="h4" component="h3" sx={{ mb: 1.5 }}>États des dossiers et des sollicitations</Typography>
              <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>{STATUSES.map((s) => <StatusChip key={s} status={s} />)}</Box></Box>
            <Box><Typography variant="h4" component="h3" sx={{ mb: 1.5 }}>Sévérité des incohérences</Typography>
              <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}><SeverityChip severity="haute" /><SeverityChip severity="moyenne" /><SeverityChip severity="basse" /></Box></Box>
            <Box><Typography variant="h4" component="h3" sx={{ mb: 1.5 }}>Priorité</Typography>
              <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}><PriorityChip priority="haute" /><PriorityChip priority="moyenne" /><PriorityChip priority="basse" /></Box></Box>
            <Typography variant="caption" color="text.secondary">Chaque pastille associe une icône et un texte à sa couleur : la couleur seule ne porte jamais le sens.</Typography>
          </Card>
        </Section>

        <Section id="alertes" title="Alertes et confirmations">
          <Box sx={{ display: "grid", gap: 1.5 }}>
            <Alert severity="success">Mandat signé. Vous pouvez générer le contrat.</Alert>
            <Alert severity="info">Les experts ont été sollicités par e-mail.</Alert>
            <Alert severity="warning">Tous les experts ont refusé ce mandat.</Alert>
            <Alert severity="error">Contrôle d'intégrité échoué : le fichier stocké a été modifié.</Alert>
            <Box><Button variant="outlined" onClick={() => toast.success("Empreinte copiée dans le presse-papiers.")}>Afficher une confirmation</Button></Box>
          </Box>
        </Section>

        <Section id="composants" title="Composants réutilisables">
          <Box sx={{ display: "grid", gap: 3 }}>
            <Card sx={{ p: 3 }}>
              <Typography variant="h4" component="h3" sx={{ mb: 2 }}>WorkflowStepper</Typography>
              <WorkflowStepper stages={SAMPLE_STAGES} activeKey="preparation" onSelect={() => undefined} />
            </Card>
            <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
              <Card sx={{ p: 3 }}>
                <Typography variant="h4" component="h3" sx={{ mb: 2 }}>ScoreRing</Typography>
                <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                  <ScoreRing value={0.87} label="Score" /><ScoreRing value={0.62} label="Score" /><ScoreRing value={0.32} label="Score" />
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>Vert à partir de 75, ambre à partir de 50, rouge en dessous. Le nombre est toujours écrit.</Typography>
              </Card>
              <Card sx={{ p: 3 }}>
                <Typography variant="h4" component="h3" sx={{ mb: 2 }}>ScoreBreakdownBar et ExplainPopover</Typography>
                <ScoreBreakdownBar segments={[{ label: "Similarité textuelle", value: 0.43, max: 0.6 }, { label: "Disponibilité", value: 0.2, max: 0.2 }, { label: "Expérience", value: 0.15, max: 0.2 }]} />
                <Box sx={{ mt: 1.5 }}>
                  <ExplainPopover title="Pourquoi ce score ?" technical="score = 0,6 × TF-IDF + 0,2 × disponibilité + 0,2 × min(années / 20, 1)"
                    segments={[{ label: "Similarité textuelle", value: 0.43, max: 0.6 }, { label: "Disponibilité", value: 0.2, max: 0.2 }, { label: "Expérience", value: 0.15, max: 0.2 }]}>
                    Locard compare le mandat aux compétences de l'expert, puis ajoute sa disponibilité et son expérience.
                  </ExplainPopover>
                </Box>
              </Card>
            </Box>
            <Card sx={{ p: 3, display: "grid", gap: 2 }}>
              <Typography variant="h4" component="h3">HashBadge</Typography>
              <HashBadge hash={HASH} verified timestamp="2025-10-16T14:40:00Z" />
              <HashBadge hash={HASH} verified={false} />
              <HashBadge hash={HASH} />
            </Card>
            <Card sx={{ p: 3 }}>
              <Typography variant="h4" component="h3" sx={{ mb: 2 }}>EntityHighlighter</Typography>
              <EntityHighlighter segments={SAMPLE_SEGMENTS} />
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5, color: p.textSecondary }}>
                Couleur et style de soulignement distincts pour chaque type d'entité.
              </Typography>
            </Card>
            <Card sx={{ p: 3 }}>
              <Typography variant="h4" component="h3" sx={{ mb: 2 }}>AuditTimeline</Typography>
              <AuditTimeline entries={SAMPLE_AUDIT} />
            </Card>
          </Box>
        </Section>

        <Section id="cartes" title="Cartes">
          <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
            {[0, 1, 2].map((i) => (
              <Card key={i} sx={{ p: 3 }}>
                <Chip size="small" label={["Rayon 10 px", "Bordure 1 px", "Ombre très douce"][i]} sx={{ mb: 1.5 }} />
                <Typography variant="h3" component="h3">Carte {i + 1}</Typography>
                <Typography variant="body2" color="text.secondary">Grille de 8 px, beaucoup d'espace, une idée par carte.</Typography>
              </Card>
            ))}
          </Box>
        </Section>
      </Container>
    </Box>
  );
}
