import { ChangeEvent, useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Card, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, LinearProgress, Stack,
  Switch, Tab, Tabs, TextField, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DescriptionIcon from "@mui/icons-material/DescriptionOutlined";
import UploadFileIcon from "@mui/icons-material/UploadFileOutlined";
import { api, Incoherence, PvDetail } from "../../api";
import { formatDateTime, frenchError, INCOHERENCE_LABEL } from "../../format";
import { useLoad } from "../../hooks";
import { useSettings } from "../../settings";
import { useTokens } from "../../theme/useTokens";
import EntityHighlighter from "../../components/ui/EntityHighlighter";
import ExplainPopover from "../../components/ui/ExplainPopover";
import HashBadge from "../../components/ui/HashBadge";
import { EmptyState, SectionTitle, SkeletonCards } from "../../components/ui/Page";
import ScoreRing from "../../components/ui/ScoreRing";
import SeverityChip from "../../components/ui/SeverityChip";
import { useToast } from "../../components/ui/Toast";
import { useCase } from "./CaseLayout";
import { EXAMPLE_PVS } from "./examples";

const MAX_FILE_BYTES = 1_000_000;
const PV_ID = /^[A-Za-z0-9_-]{1,40}$/;

function Excerpt({ pv, text }: { pv: string; text: string }) {
  const p = useTokens();
  return (
    <Box sx={{ flex: 1, minWidth: 0, p: 1.5, borderRadius: 2, bgcolor: p.surfaceAlt, border: `1px solid ${p.border}` }}>
      <Chip size="small" label={`PV ${pv}`} sx={{ mb: 1, bgcolor: p.primarySoft, color: p.primarySoftText }} />
      <Typography variant="body2" component="blockquote" sx={{ m: 0, fontStyle: "italic", wordBreak: "break-word" }}>« {text} »</Typography>
    </Box>
  );
}

/** One detected inconsistency: the two conflicting excerpts side by side, and a plain-language reason. */
function IncoherenceCard({ inc }: { inc: Incoherence }) {
  const p = useTokens();
  const accent = { haute: p.danger, moyenne: p.warning, basse: p.textSecondary }[inc.severity];
  return (
    <Card component="article" sx={{ p: 2.5, borderLeft: `4px solid ${accent}` }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, flexWrap: "wrap", mb: 1 }}>
        <Typography variant="h4" component="h3">{INCOHERENCE_LABEL[inc.type]}</Typography>
        <SeverityChip severity={inc.severity} />
      </Box>
      <Typography variant="body2" sx={{ mb: 2 }}>{inc.description}</Typography>
      <Box sx={{ display: "flex", gap: 1.5, flexDirection: { xs: "column", sm: "row" }, mb: 1.5 }}>
        {inc.evidence.map((e, i) => <Excerpt key={i} pv={e.pv_id} text={e.excerpt} />)}
      </Box>
      <ExplainPopover title="Pourquoi cette incohérence ?" technical={`règle : ${inc.rule}`}>{inc.why}</ExplainPopover>
    </Card>
  );
}

function AddPvDialog({ open, onClose, onAdded, existing }: { open: boolean; onClose: () => void; onAdded: (id: string) => void; existing: number }) {
  const { data: c } = useCase();
  const toast = useToast();
  const [witness, setWitness] = useState("");
  const [pvId, setPvId] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) setPvId(`pv-${String(existing + 1).padStart(3, "0")}`);
  }, [open, existing]);

  const valid = witness.trim().length >= 2 && PV_ID.test(pvId) && text.trim().length >= 20;

  function insertExample() {
    const list = EXAMPLE_PVS[c.case_type];
    const ex = list[existing % list.length];
    setWitness(ex.witness);
    setText(ex.text);
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (f.size > MAX_FILE_BYTES) return setError("Fichier trop volumineux (1 Mo maximum).");
    setError("");
    setText(await f.text());
  }

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const r = await api.analyzePv({ case_id: c.case_id, pv_id: pvId.trim(), pv_text: text, witness_name: witness.trim(), pseudonymize: false });
      const n = r.incoherences.length;
      toast.success(n === 0 ? "PV analysé : aucune incohérence détectée." : `PV analysé : ${n} incohérence(s) détectée(s).`);
      setText("");
      setWitness("");
      onAdded(r.pv_id);
    } catch (e) {
      setError(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="md" aria-labelledby="add-pv-title">
      <DialogTitle id="add-pv-title">Ajouter un procès-verbal</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ pt: 1 }}>
          {error && <Alert severity="error" role="alert">{error}</Alert>}
          <Typography variant="body2" color="text.secondary">
            Collez le texte du PV ou importez un fichier .txt. Locard l'enregistre, calcule son empreinte SHA-256 immédiatement,
            puis le compare aux autres PV du dossier.
          </Typography>
          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
            <TextField label="Témoin ou suspect" value={witness} onChange={(e) => setWitness(e.target.value)} sx={{ flex: 2, minWidth: 220 }} required />
            <TextField label="Identifiant du PV" value={pvId} onChange={(e) => setPvId(e.target.value)} sx={{ flex: 1, minWidth: 140 }}
              error={pvId !== "" && !PV_ID.test(pvId)} helperText="Lettres, chiffres, - et _" />
          </Box>
          <TextField label="Texte du PV" value={text} onChange={(e) => setText(e.target.value)} multiline minRows={8} maxRows={18} fullWidth required
            helperText={`${text.trim() ? text.trim().split(/\s+/).length : 0} mots (20 caractères minimum)`} />
          <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
            <input ref={file} type="file" accept=".txt,text/plain" hidden onChange={onFile} />
            <Button variant="outlined" startIcon={<UploadFileIcon />} onClick={() => file.current?.click()}>Importer un fichier .txt</Button>
            <Button onClick={insertExample}>Insérer un exemple de PV</Button>
          </Box>
          {busy && <LinearProgress />}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy}>Annuler</Button>
        <Button variant="contained" onClick={submit} disabled={busy || !valid}>{busy ? "Analyse en cours…" : "Analyser le PV"}</Button>
      </DialogActions>
    </Dialog>
  );
}

function PvView({ detail }: { detail: PvDetail }) {
  const incs = detail.incoherences;
  return (
    <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 3fr) minmax(320px, 2fr)" }, alignItems: "start" }}>
      <Card sx={{ p: { xs: 2.5, sm: 3.5 } }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap", mb: 2 }}>
          <Box>
            <Typography variant="h3" component="h2">Déclaration de {detail.witness_name}</Typography>
            <Typography variant="body2" color="text.secondary">PV {detail.pv_id} · {detail.word_count} mots · analysé le {formatDateTime(detail.analyzed_at)}</Typography>
          </Box>
        </Box>
        <Box sx={{ mb: 2.5 }}><HashBadge hash={detail.sha256} verified={detail.verified} /></Box>
        <EntityHighlighter segments={detail.segments} />
      </Card>

      <Stack spacing={2}>
        <Card sx={{ p: 2.5, display: "flex", gap: 2.5, alignItems: "center" }}>
          <ScoreRing value={detail.score_coherence} size={88} label="Score de cohérence" caption="cohérence" good={0.8} fair={0.6} />
          <Box>
            <Typography variant="h4" component="h3">Cohérence des témoignages</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              {incs.length === 0 ? "Aucune incohérence avec les autres PV." : `${incs.length} incohérence(s) impliquant ce PV.`}
            </Typography>
            <ExplainPopover title="Comment est calculé ce score ?" technical="score = max(0, 1 − 0,2 × nombre d'incohérences)">
              Le score part de 100 et perd 20 points par incohérence détectée impliquant ce PV. Il résume ce que Locard a trouvé ;
              il ne remplace pas la lecture du PV par l'expert.
            </ExplainPopover>
          </Box>
        </Card>
        {incs.length === 0
          ? <Alert severity="success">Aucune incohérence détectée. Ajoutez d'autres PV pour croiser les déclarations.</Alert>
          : incs.map((inc, i) => <IncoherenceCard key={i} inc={inc} />)}
      </Stack>
    </Box>
  );
}

/** Screen 7: witness statements with entities highlighted, and the inconsistencies found across the case. */
export default function PvTab() {
  const { data: c, reload: reloadCase } = useCase();
  const { pseudonymize, setPseudonymize } = useSettings();
  const pvs = useLoad(() => api.listPvs(c.case_id), [c.case_id]);
  const [selected, setSelected] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const list = pvs.data ?? [];
  const current = selected && list.some((p) => p.pv_id === selected) ? selected : list[0]?.pv_id ?? null;
  const detail = useLoad(() => (current ? api.pvDetail(c.case_id, current, pseudonymize) : Promise.resolve(null)), [c.case_id, current, pseudonymize, list.length]);

  async function added(id: string) {
    setAdding(false);
    await pvs.reload();
    setSelected(id);
    void reloadCase();
  }

  if (pvs.loading && !pvs.data) return <SkeletonCards count={2} height={200} />;
  return (
    <>
      <SectionTitle action={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setAdding(true)}>Ajouter un PV</Button>}>
        Témoignages analysés
      </SectionTitle>
      {pvs.error && <Alert severity="error" sx={{ mb: 2 }}>{pvs.error}</Alert>}
      {list.length === 0 ? (
        <EmptyState icon={<DescriptionIcon fontSize="large" />} title="Aucun procès-verbal"
          text="Ajoutez le texte d'un PV d'audition. Locard repère les personnes, lieux, dates et montants, puis cherche les contradictions entre déclarations."
          action={{ label: "Ajouter un premier PV", onClick: () => setAdding(true) }} />
      ) : (
        <>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 2, flexWrap: "wrap", mb: 2 }}>
            <Tabs value={current} onChange={(_, v) => setSelected(v)} variant="scrollable" scrollButtons="auto" aria-label="Procès-verbaux" sx={{ minWidth: 0 }}>
              {list.map((p) => <Tab key={p.pv_id} value={p.pv_id} label={`${p.pv_id} · ${pseudonymize ? "Personne" : p.witness_name}`} />)}
            </Tabs>
            <FormControlLabel
              control={<Switch checked={pseudonymize} onChange={(e) => setPseudonymize(e.target.checked)} />}
              label="Masquer les noms (RGPD)"
            />
          </Box>
          {detail.error && <Alert severity="error" sx={{ mb: 2 }}>{detail.error}</Alert>}
          {detail.loading && !detail.data && <SkeletonCards count={1} height={300} />}
          {detail.data && <PvView detail={detail.data} />}
        </>
      )}
      <AddPvDialog open={adding} onClose={() => setAdding(false)} onAdded={added} existing={list.length} />
    </>
  );
}
