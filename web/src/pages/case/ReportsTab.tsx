import { useState } from "react";
import {
  Alert, Box, Button, Card, Chip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, FormControl,
  IconButton, InputLabel, LinearProgress, MenuItem, Select, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import ArticleIcon from "@mui/icons-material/ArticleOutlined";
import DeleteIcon from "@mui/icons-material/DeleteOutline";
import { api, ReportsAnalysis, TechReportIn, TechReportScored } from "../../api";
import { ACTION_TITLE, frenchError } from "../../format";
import { useLoad } from "../../hooks";
import { fonts } from "../../theme/tokens";
import { useTokens } from "../../theme/useTokens";
import ExplainPopover from "../../components/ui/ExplainPopover";
import { EmptyState, SectionTitle, SkeletonCards } from "../../components/ui/Page";
import ScoreRing from "../../components/ui/ScoreRing";
import { useToast } from "../../components/ui/Toast";
import { useCase } from "./CaseLayout";
import { EXAMPLE_TECH_REPORT } from "./examples";

const REPORT_ID = /^[A-Za-z0-9_-]{1,40}$/;
const splitList = (value: string) => value.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean);

function AddReportDialog({ open, onClose, onSaved, analysis }: { open: boolean; onClose: () => void; onSaved: () => void; analysis: ReportsAnalysis | null }) {
  const { data: c } = useCase();
  const toast = useToast();
  const existing = analysis?.rapports.length ?? 0;
  const [id, setId] = useState("");
  const [action, setAction] = useState("analyse_logs");
  const [tools, setTools] = useState("");
  const [results, setResults] = useState("");
  const [proofs, setProofs] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const actions = Object.entries(analysis?.actions_connues ?? ACTION_TITLE);
  const suggestedId = `r${existing + 1}`;
  const effectiveId = id || suggestedId;
  const valid = REPORT_ID.test(effectiveId) && action;

  async function save() {
    setBusy(true);
    setError("");
    const body: TechReportIn = { rapport_id: effectiveId, action, outils: splitList(tools), resultats: results.trim(), preuves: splitList(proofs) };
    try {
      await api.analyzeReports(c.case_id, [body]);
      toast.success(`Rapport ${effectiveId} enregistré et noté.`);
      setId(""); setTools(""); setResults(""); setProofs("");
      onSaved();
    } catch (e) {
      setError(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  function example() {
    setAction(EXAMPLE_TECH_REPORT.action);
    setTools(EXAMPLE_TECH_REPORT.outils.join(", "));
    setResults(EXAMPLE_TECH_REPORT.resultats);
    setProofs(EXAMPLE_TECH_REPORT.preuves.join("\n"));
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="md" aria-labelledby="add-report-title">
      <DialogTitle id="add-report-title">Ajouter un rapport technique</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ pt: 1 }}>
          {error && <Alert severity="error" role="alert">{error}</Alert>}
          <DialogContentText>
            Un rapport technique décrit une action forensique menée : outils, résultats, preuves. Locard le note, puis classe tous les rapports du dossier.
          </DialogContentText>
          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
            <TextField label="Identifiant" value={id} placeholder={suggestedId} onChange={(e) => setId(e.target.value)} sx={{ flex: 1, minWidth: 140 }}
              error={Boolean(id) && !REPORT_ID.test(id)} helperText="Lettres, chiffres, - et _" />
            <FormControl sx={{ flex: 2, minWidth: 220 }}>
              <InputLabel id="action-label">Action menée</InputLabel>
              <Select labelId="action-label" label="Action menée" value={action} onChange={(e) => setAction(e.target.value)}>
                {actions.map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
              </Select>
            </FormControl>
          </Box>
          <TextField label="Outils utilisés" value={tools} onChange={(e) => setTools(e.target.value)} fullWidth helperText="Séparés par des virgules, par exemple Splunk, ELK" />
          <TextField label="Résultats" value={results} onChange={(e) => setResults(e.target.value.slice(0, 5000))} multiline minRows={4} fullWidth
            helperText={`${results.length} / 5000. Plus le texte cite d'éléments vérifiables (empreinte, horodatage, journaux, artefact, signature), mieux il est noté.`} />
          <TextField label="Preuves jointes" value={proofs} onChange={(e) => setProofs(e.target.value)} multiline minRows={2} fullWidth
            helperText="Un nom de fichier par ligne. Trois preuves ou plus donnent la note maximale sur ce critère." />
          <Box><Button onClick={example}>Insérer un exemple de rapport</Button></Box>
          {busy && <LinearProgress />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy}>Annuler</Button>
        <Button variant="contained" onClick={save} disabled={busy || !valid}>Enregistrer et noter</Button>
      </DialogActions>
    </Dialog>
  );
}

function ReportRow({ r, onDelete }: { r: TechReportScored; onDelete: () => void }) {
  const p = useTokens();
  const w = r.weights, b = r.breakdown, d = r.details;
  const color = r.score >= 0.75 ? p.success : r.score >= 0.5 ? p.warning : p.danger;
  return (
    <Card component="article" aria-label={`Rapport ${r.rapport_id}, rang ${r.rank}`} sx={{ p: 2.5 }}>
      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
        <Box aria-hidden="true" sx={{ width: 36, height: 36, borderRadius: 2, display: "grid", placeItems: "center", bgcolor: p.primarySoft, color: p.primarySoftText, fontWeight: 600, flexShrink: 0 }}>{r.rank}</Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mb: 0.5 }}>
            <Typography variant="h4" component="h3">{ACTION_TITLE[r.action] ?? r.action}</Typography>
            <Typography component="code" sx={{ fontFamily: fonts.mono, fontSize: 12, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}`, borderRadius: 1.5, px: 1 }}>{r.rapport_id}</Typography>
            {r.in_chain
              ? <Chip size="small" label="Dans la chaîne optimale" sx={{ bgcolor: p.successSoft, color: p.successText }} />
              : <Chip size="small" label="Hors chaîne (score < 0,50)" sx={{ bgcolor: p.neutralSoft, color: p.neutralText }} />}
          </Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, my: 1.25 }}>
            <Box role="img" aria-label={`Score ${r.score.toFixed(2)} sur 1`} sx={{ flex: 1, height: 10, borderRadius: 5, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}`, overflow: "hidden" }}>
              <Box sx={{ width: `${r.score * 100}%`, height: "100%", bgcolor: color, transition: "width 200ms ease" }} />
            </Box>
            <Typography sx={{ fontWeight: 600, fontVariantNumeric: "tabular-nums", minWidth: 40, textAlign: "right" }}>{r.score.toFixed(2)}</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.25 }}>{r.resultats || "Aucun résultat saisi."}</Typography>
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 1 }}>
            {r.outils.map((o) => <Chip key={o} size="small" variant="outlined" label={o} />)}
            {r.preuves.map((o) => <Chip key={o} size="small" label={o} sx={{ bgcolor: p.neutralSoft, color: p.neutralText, fontFamily: fonts.mono, fontSize: 11 }} />)}
          </Box>
          <ExplainPopover
            label="Pourquoi ce score ?" title={`Pourquoi ${r.score.toFixed(2)} ?`}
            segments={[
              { label: "Complétude des champs", value: b.completude, max: w.completude },
              { label: "Éléments techniques cités", value: b.pertinence, max: w.pertinence },
              { label: "Preuves jointes", value: b.preuves, max: w.preuves },
            ]}
            technical="score = 0,4 × champs remplis/4 + 0,3 × concepts cités/5 + 0,3 × min(preuves/3, 1)"
          >
            {d.champs_manquants.length ? `Champs manquants : ${d.champs_manquants.join(", ")}. ` : "Tous les champs sont remplis. "}
            {d.concepts_trouves.length ? `Éléments cités : ${d.concepts_trouves.join(", ")}. ` : "Aucun élément technique vérifiable n'est cité. "}
            {d.concepts_absents.length ? `Absents : ${d.concepts_absents.join(", ")}. ` : ""}
            {`${d.nb_preuves} preuve(s) jointe(s) sur 3 attendues.`}
          </ExplainPopover>
        </Box>
        <Tooltip title="Supprimer ce rapport">
          <IconButton onClick={onDelete} aria-label={`Supprimer le rapport ${r.rapport_id}`}><DeleteIcon /></IconButton>
        </Tooltip>
      </Box>
    </Card>
  );
}

/** The optimal resolution chain as a flow: best report first, each step with its score. */
function ResolutionChain({ analysis }: { analysis: ReportsAnalysis }) {
  const p = useTokens();
  const chain = analysis.chaine_optimale;
  if (chain.length === 0) return <Typography color="text.secondary">Aucun rapport n'atteint encore le seuil de 0,50 : la chaîne est vide.</Typography>;
  return (
    <Box component="ol" aria-label="Chaîne optimale de résolution" sx={{ listStyle: "none", m: 0, p: 0, display: "flex", flexWrap: "wrap", alignItems: "stretch", gap: 1 }}>
      {chain.map((s, i) => (
        <Box component="li" key={s.rapport_id} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box sx={{ p: 1.5, minWidth: 150, borderRadius: 2.5, bgcolor: p.primarySoft, border: `1px solid ${p.primary}` }}>
            <Typography variant="caption" sx={{ color: p.primarySoftText }}>Étape {i + 1} · {s.rapport_id}</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, color: p.primarySoftText }}>{ACTION_TITLE[s.action] ?? s.action}</Typography>
            <Typography variant="caption" sx={{ color: p.primarySoftText }}>score {s.score.toFixed(2)}</Typography>
          </Box>
          {i < chain.length - 1 && <ArrowForwardIcon aria-hidden="true" sx={{ color: p.textSecondary }} />}
        </Box>
      ))}
      <Box component="li" sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <ArrowForwardIcon aria-hidden="true" sx={{ color: p.textSecondary }} />
        <Box sx={{ p: 1.5, borderRadius: 2.5, border: `1px dashed ${p.border}` }}><Typography variant="body2" color="text.secondary">Conclusion</Typography></Box>
      </Box>
    </Box>
  );
}

/** Screen 9: technical reports ranked by score, with the optimal resolution chain. */
export default function ReportsTab() {
  const { data: c, reload: reloadCase } = useCase();
  const toast = useToast();
  const analysis = useLoad(() => api.reportsAnalysis(c.case_id), [c.case_id]);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const data = analysis.data;

  async function remove() {
    if (!deleting) return;
    try {
      await api.deleteTechReport(c.case_id, deleting);
      toast.success(`Rapport ${deleting} supprimé.`);
      setDeleting(null);
      await analysis.reload();
    } catch (e) {
      toast.error(frenchError(e));
    }
  }

  if (analysis.loading && !data) return <SkeletonCards count={3} height={150} />;
  return (
    <>
      <SectionTitle action={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setAdding(true)}>Ajouter un rapport technique</Button>}>
        Rapports techniques
      </SectionTitle>
      {analysis.error && <Alert severity="error" sx={{ mb: 2 }}>{analysis.error}</Alert>}
      {data && data.rapports.length === 0 && (
        <EmptyState icon={<ArticleIcon fontSize="large" />} title="Aucun rapport technique"
          text="Chaque action forensique (analyse de journaux, de trafic, de disque) donne lieu à un rapport. Locard les note et propose la chaîne de résolution la plus solide."
          action={{ label: "Ajouter un premier rapport", onClick: () => setAdding(true) }} />
      )}
      {data && data.rapports.length > 0 && (
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 3fr) minmax(280px, 1fr)" }, alignItems: "start" }}>
          <Stack spacing={2}>
            <Card sx={{ p: 2.5 }}>
              <Typography variant="h4" component="h3" sx={{ mb: 0.5 }}>Chaîne optimale de résolution</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Les rapports notés 0,50 ou plus, du plus utile au moins utile.
              </Typography>
              <ResolutionChain analysis={data} />
            </Card>
            {data.rapports.map((r) => <ReportRow key={r.rapport_id} r={r} onDelete={() => setDeleting(r.rapport_id)} />)}
          </Stack>
          <Stack spacing={2}>
            <Card sx={{ p: 2.5, display: "flex", gap: 2, alignItems: "center" }}>
              <ScoreRing value={data.score_global ?? 0} size={84} label="Score global des rapports" caption="global" />
              <Box>
                <Typography variant="h4" component="h3">Score global</Typography>
                <Typography variant="body2" color="text.secondary">Moyenne des notes des {data.rapports.length} rapport(s).</Typography>
              </Box>
            </Card>
            {data.recommandations.length > 0 && (
              <Card sx={{ p: 2.5 }}>
                <Typography variant="h4" component="h3" sx={{ mb: 1 }}>Recommandations</Typography>
                <Box component="ul" sx={{ m: 0, pl: 2.5, display: "grid", gap: 1 }}>
                  {data.recommandations.map((t) => <Typography component="li" variant="body2" key={t}>{t}</Typography>)}
                </Box>
              </Card>
            )}
          </Stack>
        </Box>
      )}
      <AddReportDialog open={adding} onClose={() => setAdding(false)} analysis={data} onSaved={() => { setAdding(false); void analysis.reload(); void reloadCase(); }} />
      <Dialog open={Boolean(deleting)} onClose={() => setDeleting(null)} aria-labelledby="delete-report-title">
        <DialogTitle id="delete-report-title">Supprimer le rapport {deleting} ?</DialogTitle>
        <DialogContent><DialogContentText>Le classement et la chaîne optimale seront recalculés. La suppression est enregistrée dans le journal d'audit.</DialogContentText></DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleting(null)}>Annuler</Button>
          <Button color="error" variant="contained" onClick={remove}>Supprimer</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
