import { FormEvent, useState } from "react";
import { Alert, Box, Button, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { api, CASE_TYPE_LABEL, CaseType, errorMessage, Priority } from "../api";

interface Props {
  onCancel: () => void;
  onCreated: (id: string) => void;
}

export default function CaseForm({ onCancel, onCreated }: Props) {
  const [caseType, setCaseType] = useState<CaseType>("fraude_bancaire");
  const [priority, setPriority] = useState<Priority>("moyenne");
  const [description, setDescription] = useState("");
  const [nom, setNom] = useState("");
  const [fonction, setFonction] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // mirrors backend validation (description >= 10 chars, names required)
  const descTooShort = description.trim().length < 10;
  const valid = !descTooShort && nom.trim() !== "" && fonction.trim() !== "";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError("");
    try {
      const { case_id } = await api.createCase({
        case_type: caseType,
        description: description.trim(),
        priority,
        mandataire: { nom: nom.trim(), fonction: fonction.trim() },
      });
      onCreated(case_id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Paper sx={{ p: 3 }} component="form" onSubmit={submit}>
      <Typography variant="h5" color="primary" sx={{ fontWeight: 700, mb: 2 }}>
        Nouveau mandat
      </Typography>
      <Stack spacing={2}>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField select label="Type de cas" value={caseType} onChange={(e) => setCaseType(e.target.value as CaseType)}>
          {Object.entries(CASE_TYPE_LABEL).map(([k, v]) => (
            <MenuItem key={k} value={k}>{v}</MenuItem>
          ))}
        </TextField>
        <TextField select label="Priorite" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
          <MenuItem value="basse">Basse</MenuItem>
          <MenuItem value="moyenne">Moyenne</MenuItem>
          <MenuItem value="haute">Haute</MenuItem>
        </TextField>
        <TextField
          label="Description des faits"
          multiline
          minRows={4}
          required
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          error={description !== "" && descTooShort}
          helperText={description !== "" && descTooShort ? "10 caracteres minimum" : " "}
        />
        <Box sx={{ display: "flex", gap: 2 }}>
          <TextField fullWidth required label="Nom du mandataire" value={nom} onChange={(e) => setNom(e.target.value)} />
          <TextField fullWidth required label="Fonction" value={fonction} onChange={(e) => setFonction(e.target.value)} />
        </Box>
        <Box sx={{ display: "flex", gap: 1, justifyContent: "flex-end" }}>
          <Button onClick={onCancel} disabled={busy}>Annuler</Button>
          <Button type="submit" variant="contained" disabled={!valid || busy}>
            Creer le mandat
          </Button>
        </Box>
      </Stack>
    </Paper>
  );
}
