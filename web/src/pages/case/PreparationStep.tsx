import { KeyboardEvent, useState } from "react";
import {
  Alert, Box, Button, Card, Checkbox, Chip, IconButton, LinearProgress, TextField, Tooltip, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/DeleteOutline";
import FileDownloadIcon from "@mui/icons-material/FileDownloadOutlined";
import { api, downloadFile } from "../../api";
import { useAuth } from "../../auth";
import { frenchError } from "../../format";
import { useStored } from "../../hooks";
import { SectionTitle } from "../../components/ui/Page";
import { useToast } from "../../components/ui/Toast";
import { useCase } from "./CaseLayout";

interface Item {
  text: string;
  done: boolean;
}
interface Prep {
  questions: Item[];
  witnesses: string[];
  checklist: Item[];
}

function EditableList({ title, hint, items, onChange, addLabel, doneLabel }: {
  title: string; hint: string; items: Item[]; onChange: (items: Item[]) => void; addLabel: string; doneLabel: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    if (!draft.trim()) return;
    onChange([...items, { text: draft.trim(), done: false }]);
    setDraft("");
  };
  return (
    <Card sx={{ p: 3 }}>
      <Typography variant="h3" component="h3">{title}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{hint}</Typography>
      <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 0.5 }}>
        {items.map((it, i) => (
          <Box component="li" key={i} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <Checkbox
              checked={it.done} inputProps={{ "aria-label": `${doneLabel} : ${it.text}` }}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, done: e.target.checked } : x)))}
            />
            <TextField
              value={it.text} variant="standard" fullWidth multiline inputProps={{ "aria-label": `Modifier : ${it.text}` }}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
              InputProps={{ disableUnderline: false, sx: { textDecoration: it.done ? "line-through" : "none", color: it.done ? "text.secondary" : "text.primary" } }}
            />
            <Tooltip title="Supprimer">
              <IconButton size="small" onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label={`Supprimer : ${it.text}`}><DeleteIcon fontSize="small" /></IconButton>
            </Tooltip>
          </Box>
        ))}
      </Box>
      <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
        <TextField
          size="small" fullWidth placeholder={addLabel} value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e: KeyboardEvent) => e.key === "Enter" && (e.preventDefault(), add())} inputProps={{ "aria-label": addLabel }}
        />
        <Button variant="outlined" startIcon={<AddIcon />} onClick={add} disabled={!draft.trim()}>Ajouter</Button>
      </Box>
    </Card>
  );
}

function Witnesses({ names, onChange }: { names: string[]; onChange: (n: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    if (!draft.trim()) return;
    onChange([...names, draft.trim()]);
    setDraft("");
  };
  return (
    <Card sx={{ p: 3 }}>
      <Typography variant="h3" component="h3">Témoins et suspects</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Locard ne suggère pas encore de personnes à partir du mandat : ajoutez celles que vous souhaitez entendre.
      </Typography>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: names.length ? 2 : 0 }}>
        {names.map((n, i) => <Chip key={`${n}-${i}`} label={n} onDelete={() => onChange(names.filter((_, j) => j !== i))} deleteIcon={<DeleteIcon aria-label={`Retirer ${n}`} />} />)}
      </Box>
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField size="small" fullWidth placeholder="Nom et rôle, par exemple M. Dupont (directeur financier)" value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e: KeyboardEvent) => e.key === "Enter" && (e.preventDefault(), add())} inputProps={{ "aria-label": "Ajouter une personne à entendre" }} />
        <Button variant="outlined" startIcon={<AddIcon />} onClick={add} disabled={!draft.trim()}>Ajouter</Button>
      </Box>
    </Card>
  );
}

/** Step 4. Interview questions as an editable checklist, exported as the methodological guide. */
export default function PreparationStep() {
  const { data: c, reload } = useCase();
  const { user } = useAuth();
  const toast = useToast();
  const [prep, setPrep] = useStored<Prep | null>(`locard.prep.${c.case_id}`, null);
  const [busy, setBusy] = useState(false);
  const stageDone = c.stages.find((s) => s.key === "preparation")?.done;

  if (user?.role !== "investigateur") {
    return (
      <>
        <SectionTitle>Préparation de la mission</SectionTitle>
        <Alert severity={stageDone ? "success" : "info"}>
          {stageDone
            ? "L'expert a préparé les auditions et exporté son guide méthodologique."
            : c.chosen_expert_id === null ? "La préparation commence après le choix de l'expert."
            : "L'expert prépare les questions d'audition. Cette étape ne demande rien de votre part."}
        </Alert>
      </>
    );
  }
  if (c.chosen_expert_id === null) {
    return <Alert severity="info">La préparation est disponible quand le mandataire vous a choisi pour cette mission.</Alert>;
  }

  async function generate() {
    setBusy(true);
    try {
      const r = await api.prepareMission({ case_id: c.case_id });
      setPrep({
        questions: r.questions.map((text) => ({ text, done: false })),
        witnesses: r.suggested_witnesses,
        checklist: r.checklist.map((text) => ({ text, done: false })),
      });
      toast.success("Questions générées. Adaptez-les à votre enquête.");
      await reload();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  async function exportGuide() {
    if (!prep) return;
    setBusy(true);
    try {
      const r = await api.prepareMission({
        case_id: c.case_id, questions: prep.questions.map((q) => q.text), suggested_witnesses: prep.witnesses,
        checklist: prep.checklist.map((q) => q.text),
      });
      await downloadFile(r.guide_pdf_url, "guide_methodologique.pdf");
      toast.success("Guide méthodologique exporté.");
      await reload();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  if (!prep) {
    return (
      <>
        <SectionTitle>Préparation de la mission</SectionTitle>
        <Card sx={{ p: { xs: 2.5, sm: 4 }, maxWidth: 640 }}>
          <Typography variant="h3" component="h2" sx={{ mb: 1 }}>Préparer les auditions</Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Locard génère des questions types selon le type de dossier. Vous pourrez les modifier, en ajouter, puis exporter le guide
            méthodologique en PDF pour mener les auditions.
          </Typography>
          {busy && <LinearProgress sx={{ mb: 2 }} />}
          <Button variant="contained" size="large" onClick={generate} disabled={busy}>
            {stageDone ? "Régénérer les questions" : "Générer les questions d'audition"}
          </Button>
        </Card>
      </>
    );
  }

  return (
    <>
      <SectionTitle action={
        <Button variant="contained" startIcon={<FileDownloadIcon />} onClick={exportGuide} disabled={busy || prep.questions.length === 0}>
          {busy ? "Génération du PDF…" : "Exporter le guide méthodologique (PDF)"}
        </Button>
      }>Préparation de la mission</SectionTitle>
      {busy && <LinearProgress sx={{ mb: 2 }} />}
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Cochez les questions au fur et à mesure des auditions. Vos modifications sont conservées sur cet appareil et incluses dans le guide exporté.
      </Typography>
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "3fr 2fr" }, alignItems: "start" }}>
        <EditableList title="Questions d'audition" hint="Cochez une question une fois posée." items={prep.questions}
          onChange={(questions) => setPrep({ ...prep, questions })} addLabel="Ajouter une question" doneLabel="Question posée" />
        <Box sx={{ display: "grid", gap: 3 }}>
          <Witnesses names={prep.witnesses} onChange={(witnesses) => setPrep({ ...prep, witnesses })} />
          <EditableList title="Check-list de mission" hint="Les étapes à ne pas oublier." items={prep.checklist}
            onChange={(checklist) => setPrep({ ...prep, checklist })} addLabel="Ajouter une étape" doneLabel="Étape faite" />
        </Box>
      </Box>
    </>
  );
}
