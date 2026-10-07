import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, FormControlLabel, LinearProgress,
  List, ListItem, ListItemText, Paper, Stack, Switch, TextField, Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
  api, CASE_TYPE_LABEL, CaseData, Entities, errorMessage, Incoherence, INCOHERENCE_LABEL, Mission,
  MissionPrep, PvAnalysis, PvReport,
} from "../api";

const SEVERITY_COLOR = { haute: "error", moyenne: "warning", basse: "default" } as const;
const MAX_FILE_BYTES = 1_000_000;

function EntityChips({ entities }: { entities: Entities }) {
  const groups: [string, string[]][] = [
    ["Personnes", entities.personnes],
    ["Lieux", entities.lieux],
    ["Dates", entities.dates],
    ["Montants", entities.montants],
    ["Heures", entities.heures],
  ];
  return (
    <Stack spacing={1}>
      {groups.map(([label, items]) => (
        <Box key={label} sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
          <Typography variant="body2" sx={{ width: 90, fontWeight: 600 }}>
            {label}
          </Typography>
          {items.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              aucun
            </Typography>
          )}
          {items.map((x) => (
            <Chip key={x} size="small" variant="outlined" label={x} />
          ))}
        </Box>
      ))}
    </Stack>
  );
}

function IncoherenceCard({ inc }: { inc: Incoherence }) {
  return (
    <Card variant="outlined" sx={{ borderLeft: 4, borderLeftColor: `${SEVERITY_COLOR[inc.severity]}.main` }}>
      <CardContent>
        <Box sx={{ display: "flex", gap: 1, mb: 1, flexWrap: "wrap" }}>
          <Chip size="small" color={SEVERITY_COLOR[inc.severity]} label={`Severite ${inc.severity}`} />
          <Chip size="small" label={INCOHERENCE_LABEL[inc.type]} />
          {inc.pv_references.map((r) => (
            <Chip key={r} size="small" variant="outlined" label={r} />
          ))}
        </Box>
        <Typography variant="body2" sx={{ mb: 1 }}>
          {inc.description}
        </Typography>
        {inc.evidence.map((e, i) => (
          <Typography key={i} variant="caption" display="block" color="text.secondary" sx={{ fontStyle: "italic" }}>
            [{e.pv_id}] "{e.excerpt}"
          </Typography>
        ))}
      </CardContent>
    </Card>
  );
}

interface Props {
  id: string;
  onBack: () => void;
}

export default function MissionDetail({ id, onBack }: Props) {
  const [data, setData] = useState<CaseData | null>(null);
  const [mission, setMission] = useState<Mission | null>(null);
  const [prep, setPrep] = useState<MissionPrep | null>(null);
  const [report, setReport] = useState<PvReport | null>(null);
  const [last, setLast] = useState<PvAnalysis | null>(null);
  const [witness, setWitness] = useState("");
  const [pvId, setPvId] = useState("");
  const [text, setText] = useState("");
  const [pseudo, setPseudo] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [c, ms, r] = await Promise.all([api.getCase(id), api.missions(), api.pvReport(id, pseudo)]);
      setData(c);
      setMission(ms.find((m) => m.case_id === id) ?? null);
      setReport(r);
      setPvId((prev) => prev || `pv-${String(r.pvs.length + 1).padStart(3, "0")}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [id, pseudo]);

  useEffect(() => {
    load();
  }, [load]);

  async function prepare() {
    setBusy(true);
    setError("");
    try {
      setPrep(await api.prepareMission(id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setError("Fichier trop volumineux (1 Mo maximum).");
      return;
    }
    setError("");
    setText(await file.text());
  }

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const result = await api.analyzePv({
        case_id: id, pv_id: pvId.trim(), pv_text: text, witness_name: witness.trim(), pseudonymize: pseudo,
      });
      setLast(result);
      setText("");
      setWitness("");
      setPvId("");
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = witness.trim().length >= 2 && /^[A-Za-z0-9_-]{1,40}$/.test(pvId) && text.trim().length >= 20;

  if (!data) return error ? <Alert severity="error">{error}</Alert> : <CircularProgress />;

  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2 }}>
        Mes missions
      </Button>
      <Typography variant="h5" color="primary" sx={{ fontWeight: 700 }}>
        Mission : {CASE_TYPE_LABEL[data.case_type]}
      </Typography>
      <Box sx={{ display: "flex", gap: 1, my: 1, flexWrap: "wrap" }}>
        <Chip size="small" label={`Priorite ${data.priority}`} />
        {mission && <Chip size="small" color="primary" label={`Investigateur : ${mission.expert.nom}`} />}
        <Chip size="small" variant="outlined" label={`Mandataire : ${data.mandataire.nom}`} />
      </Box>
      <Typography variant="body2" sx={{ mb: 2 }}>
        {data.description}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
          {error}
        </Alert>
      )}
      {!mission && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Aucun expert n'est retenu pour ce dossier : la preparation et l'analyse des PV sont indisponibles.
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          1. Preparation de la mission
        </Typography>
        {!prep ? (
          <Button variant="contained" disabled={busy || !mission} onClick={prepare}>
            Generer les questions et le guide
          </Button>
        ) : (
          <Box>
            <Typography variant="subtitle2">Questions d'audition</Typography>
            <List dense>
              {prep.questions.map((q) => (
                <ListItem key={q}>
                  <ListItemText primary={q} />
                </ListItem>
              ))}
            </List>
            <Typography variant="subtitle2">Checklist</Typography>
            <List dense>
              {prep.checklist.map((q) => (
                <ListItem key={q}>
                  <ListItemText primary={q} />
                </ListItem>
              ))}
            </List>
            <Button startIcon={<DownloadIcon />} href={prep.guide_pdf_url} target="_blank" variant="outlined">
              Telecharger le guide (PDF)
            </Button>
          </Box>
        )}
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          2. Ajouter un proces-verbal
        </Typography>
        <Stack spacing={2}>
          <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
            <TextField
              label="Temoin ou suspect" size="small" value={witness} sx={{ flex: 2, minWidth: 220 }}
              onChange={(e) => setWitness(e.target.value)}
            />
            <TextField
              label="Identifiant du PV" size="small" value={pvId} sx={{ flex: 1, minWidth: 140 }}
              error={pvId !== "" && !/^[A-Za-z0-9_-]{1,40}$/.test(pvId)}
              helperText="Lettres, chiffres, - et _"
              onChange={(e) => setPvId(e.target.value)}
            />
          </Box>
          <TextField
            label="Texte du PV" multiline minRows={8} maxRows={20} value={text} fullWidth
            onChange={(e) => setText(e.target.value)}
            helperText={`${text.trim() ? text.trim().split(/\s+/).length : 0} mots (20 caracteres minimum)`}
          />
          <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
            <input ref={fileInput} type="file" accept=".txt,text/plain" hidden onChange={onFile} />
            <Button startIcon={<UploadFileIcon />} variant="outlined" onClick={() => fileInput.current?.click()}>
              Importer un fichier .txt
            </Button>
            <FormControlLabel
              control={<Switch checked={pseudo} onChange={(e) => setPseudo(e.target.checked)} />}
              label="Pseudonymiser les noms (RGPD)"
            />
            <Box sx={{ flex: 1 }} />
            <Button variant="contained" disabled={busy || !canSubmit || !mission} onClick={submit}>
              {busy ? "Analyse..." : "Analyser le PV"}
            </Button>
          </Box>
        </Stack>

        {last && (
          <Box sx={{ mt: 3 }}>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              Resultat : {last.pv_id}
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1, wordBreak: "break-all" }}>
              Analyse en {last.duration_ms} ms - SHA-256 {last.sha256}
            </Typography>
            <EntityChips entities={last.entities} />
            <Stack spacing={1} sx={{ mt: 2 }}>
              {last.incoherences.length === 0 ? (
                <Alert severity="success">Aucune incoherence detectee avec les PV deja enregistres.</Alert>
              ) : (
                last.incoherences.map((inc, i) => <IncoherenceCard key={i} inc={inc} />)
              )}
            </Stack>
          </Box>
        )}
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 1 }}>
          <Typography variant="h6">3. Synthese du dossier</Typography>
          {report && report.pvs.length > 0 && (
            <Chip
              color={report.score_coherence >= 0.8 ? "success" : report.score_coherence >= 0.6 ? "warning" : "error"}
              label={`Coherence ${Math.round(report.score_coherence * 100)} %`}
            />
          )}
        </Box>
        {report && report.pvs.length === 0 && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Aucun PV enregistre. Les incoherences sont detectees en comparant tous les PV d'un meme dossier.
          </Alert>
        )}
        {report && report.pvs.length > 0 && (
          <>
            <Typography variant="subtitle2" sx={{ mt: 2 }}>
              PV enregistres ({report.pvs.length})
            </Typography>
            <List dense>
              {report.pvs.map((p) => (
                <ListItem key={p.pv_id} disableGutters>
                  <ListItemText
                    primary={`${p.pv_id} - ${p.witness_name}`}
                    secondary={`SHA-256 ${p.sha256.slice(0, 16)}...`}
                  />
                </ListItem>
              ))}
            </List>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Incoherences ({report.incoherences.length})
            </Typography>
            <LinearProgress
              variant="determinate" value={report.score_coherence * 100} sx={{ mb: 2 }}
              color={report.score_coherence >= 0.8 ? "success" : report.score_coherence >= 0.6 ? "warning" : "error"}
            />
            <Stack spacing={1}>
              {report.incoherences.length === 0 ? (
                <Alert severity="success">Aucune incoherence detectee.</Alert>
              ) : (
                report.incoherences.map((inc, i) => <IncoherenceCard key={i} inc={inc} />)
              )}
            </Stack>
          </>
        )}
      </Paper>
    </Box>
  );
}
