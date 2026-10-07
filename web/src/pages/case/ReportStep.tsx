import { useState } from "react";
import {
  Alert, Box, Button, Card, Chip, FormControlLabel, LinearProgress, Stack, Switch, Tab, Tabs, TextField, Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/FileDownloadOutlined";
import ArticleIcon from "@mui/icons-material/ArticleOutlined";
import { api, downloadFile, FinalReport } from "../../api";
import { useAuth } from "../../auth";
import { formatDateTime, frenchError } from "../../format";
import { useLoad } from "../../hooks";
import { useSettings } from "../../settings";
import { useTokens } from "../../theme/useTokens";
import HashBadge from "../../components/ui/HashBadge";
import { EmptyState, SectionTitle, SkeletonCards } from "../../components/ui/Page";
import PdfViewer from "../../components/ui/PdfViewer";
import { useToast } from "../../components/ui/Toast";
import { useCase } from "./CaseLayout";

const MAX_CONCLUSION = 6000;

function Outline({ report }: { report: FinalReport }) {
  const p = useTokens();
  return (
    <Box component="ol" aria-label="Structure du rapport" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 1.5 }}>
      {report.outline.map((s, i) => (
        <Box component="li" key={s.key} sx={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 1.25 }}>
          <Box aria-hidden="true" sx={{ width: 28, height: 28, borderRadius: 1.5, display: "grid", placeItems: "center", fontSize: 13, fontWeight: 600, bgcolor: p.primarySoft, color: p.primarySoftText }}>{i + 1}</Box>
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{s.title}</Typography>
            {s.points.map((pt) => <Typography key={pt} variant="caption" color="text.secondary" sx={{ display: "block" }}>{pt}</Typography>)}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

function Generator({ canGenerate, onDone }: { canGenerate: boolean; onDone: () => void }) {
  const { data: c, reload } = useCase();
  const { pseudonymize, setPseudonymize } = useSettings();
  const toast = useToast();
  const [conclusion, setConclusion] = useState("");
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      const r = await api.generateReport({ case_id: c.case_id, conclusion, pseudonymize });
      toast.success(`Rapport version ${r.version} généré.`);
      onDone();
      await reload();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card sx={{ p: { xs: 2.5, sm: 3.5 }, mb: 4 }}>
      <Typography variant="h3" component="h2" sx={{ mb: 0.5 }}>Générer le rapport d'expertise</Typography>
      <Typography color="text.secondary" sx={{ mb: 2.5 }}>
        Locard compile le mandat, les PV, les hypothèses, les rapports techniques et la chaîne de custody. Chaque génération crée une nouvelle version numérotée.
      </Typography>
      {!canGenerate && <Alert severity="info" sx={{ mb: 2 }}>Analysez au moins un PV pour pouvoir générer le rapport.</Alert>}
      <TextField
        label="Conclusion de l'expert" value={conclusion} onChange={(e) => setConclusion(e.target.value.slice(0, MAX_CONCLUSION))}
        multiline minRows={4} fullWidth sx={{ mb: 2 }}
        helperText={`${conclusion.length} / ${MAX_CONCLUSION}. Ce texte devient la section « Conclusion ». Les constats automatiques sont des aides : la conclusion est la vôtre.`}
      />
      <FormControlLabel
        control={<Switch checked={pseudonymize} onChange={(e) => setPseudonymize(e.target.checked)} />}
        label="Remplacer les noms des personnes citées par des identifiants (RGPD)" sx={{ mb: 2, display: "flex" }}
      />
      {busy && (
        <Box role="status" sx={{ mb: 2 }}>
          <LinearProgress />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>Composition du rapport, compilation du PDF et calcul de l'empreinte…</Typography>
        </Box>
      )}
      <Button variant="contained" size="large" onClick={generate} disabled={busy || !canGenerate}>{busy ? "Génération…" : "Générer le rapport (PDF)"}</Button>
    </Card>
  );
}

function ReportView({ reports }: { reports: FinalReport[] }) {
  const toast = useToast();
  const [version, setVersion] = useState(reports[0].version);
  const [verified, setVerified] = useState<boolean | undefined>();
  const r = reports.find((x) => x.version === version) ?? reports[0];

  return (
    <>
      {reports.length > 1 && (
        <Tabs value={r.version} onChange={(_, v) => { setVerified(undefined); setVersion(v); }} aria-label="Versions du rapport" sx={{ mb: 2 }}>
          {reports.map((x) => <Tab key={x.version} value={x.version} label={`Version ${x.version}${x === reports[0] ? " (récente)" : ""}`} />)}
        </Tabs>
      )}
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "minmax(260px, 1fr) minmax(0, 2.2fr)" }, alignItems: "start" }}>
        <Stack spacing={2.5}>
          <Card sx={{ p: 3 }}>
            <Typography variant="h4" component="h3" sx={{ mb: 2 }}>Sections du rapport</Typography>
            <Outline report={r} />
          </Card>
          <Card sx={{ p: 3, display: "grid", gap: 2 }}>
            <Typography variant="h4" component="h3">Intégrité</Typography>
            <HashBadge hash={r.sha256} verified={verified} timestamp={r.generated_at} />
            <Typography variant="body2" color="text.secondary">Version {r.version}, générée par {r.generated_by} le {formatDateTime(r.generated_at)}.</Typography>
            {r.pseudonymized && <Chip size="small" label="Noms pseudonymisés" sx={{ alignSelf: "flex-start" }} />}
            <Button variant="contained" startIcon={<DownloadIcon />} onClick={() => downloadFile(r.pdf_url, `rapport_v${r.version}.pdf`).catch((e) => toast.error(frenchError(e)))}>
              Télécharger le rapport (PDF)
            </Button>
          </Card>
        </Stack>
        <PdfViewer url={r.pdf_url} title={`Rapport d'expertise, version ${r.version}`} height={760} onVerified={setVerified} />
      </Box>
    </>
  );
}

/** Step 6: the final expertise report. Investigators generate it, mandataires read and download it. */
export default function ReportStep() {
  const { data: c } = useCase();
  const { user } = useAuth();
  const reports = useLoad(() => api.finalReports(c.case_id), [c.case_id]);
  const investigator = user?.role === "investigateur";
  const canGenerate = Boolean(c.stages.find((s) => s.key === "analyse")?.done);
  const list = reports.data ?? [];

  if (reports.loading && !reports.data) return <SkeletonCards count={2} height={200} />;
  return (
    <>
      <SectionTitle>Rapport final</SectionTitle>
      {reports.error && <Alert severity="error" sx={{ mb: 2 }}>{reports.error}</Alert>}
      {investigator && c.chosen_expert_id !== null && <Generator canGenerate={canGenerate} onDone={() => void reports.reload()} />}
      {list.length > 0 ? <ReportView reports={list} /> : (
        <EmptyState icon={<ArticleIcon fontSize="large" />} title="Le rapport n'est pas encore publié"
          text={investigator ? "Une fois généré, il apparaît ici avec son aperçu, son empreinte SHA-256 et son téléchargement."
            : "L'expert le publiera à la fin de l'investigation. Vous pourrez alors le lire et le télécharger ici."} />
      )}
    </>
  );
}
