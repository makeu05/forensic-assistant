import { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, LinearProgress, Paper, Step,
  StepLabel, Stepper, TextField, Tooltip, Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import {
  api, CASE_TYPE_LABEL, CaseData, Contract, errorMessage, Expert, Solicitation, STATUS_LABEL,
} from "../api";

const STEPS = ["Experts proposes", "Reponses et selection", "Signature", "Mandat PDF"];

const SOL_LABEL = {
  pending: "En attente",
  accepted: "Accepte",
  refused: "Refuse",
  chosen: "Retenu",
} as const;
const SOL_COLOR = { pending: "default", accepted: "success", refused: "error", chosen: "primary" } as const;

interface Props {
  id: string;
  onBack: () => void;
}

export default function CaseDetail({ id, onBack }: Props) {
  const [data, setData] = useState<CaseData | null>(null);
  const [experts, setExperts] = useState<Expert[]>([]);
  const [sols, setSols] = useState<Solicitation[]>([]);
  const [contract, setContract] = useState<Contract | null>(null);
  const [signName, setSignName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [c, s, k] = await Promise.all([api.getCase(id), api.solicitations(id), api.contract(id)]);
      setData(c);
      setSols(s);
      setContract(k);
      setSignName((prev) => prev || c.mandataire.nom);
      if (s.length === 0) setExperts(await api.experts(id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  /** Run an action, then refresh; surfaces backend errors in the banner. */
  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return error ? <Alert severity="error">{error}</Alert> : <CircularProgress />;
  }

  const chosen = data.chosen_expert_id !== null;
  const step = sols.length === 0 ? 0 : !chosen ? 1 : !data.signed ? 2 : !contract ? 3 : 4;
  const allRefused = sols.length > 0 && sols.every((s) => s.status === "refused");

  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2 }}>
        Retour au tableau de bord
      </Button>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
          <Typography variant="h5" color="primary" sx={{ fontWeight: 700 }}>
            {CASE_TYPE_LABEL[data.case_type]}
          </Typography>
          <Box sx={{ display: "flex", gap: 1 }}>
            <Chip label={`Priorite ${data.priority}`} size="small" />
            <Chip label={STATUS_LABEL[data.status]} size="small" color="secondary" />
          </Box>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {data.mandataire.nom} ({data.mandataire.fonction}) - dossier {data.case_id}
        </Typography>
        <Typography sx={{ mt: 2, whiteSpace: "pre-wrap" }}>{data.description}</Typography>
      </Paper>

      <Stepper activeStep={step} alternativeLabel sx={{ mb: 3 }}>
        {STEPS.map((l) => (
          <Step key={l}>
            <StepLabel>{l}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}
      {busy && <LinearProgress sx={{ mb: 2 }} />}

      {step === 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>Les 3 experts proposes</Typography>
          {experts.map((e, i) => (
            <Card key={e.id} sx={{ mb: 1.5 }}>
              <CardContent>
                <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                  <Typography sx={{ fontWeight: 700 }}>{i + 1}. {e.nom}</Typography>
                  <Tooltip title={e.justification}>
                    <Chip color="secondary" label={`Score ${(e.score * 100).toFixed(0)} / 100`} />
                  </Tooltip>
                </Box>
                <Box sx={{ mt: 1, display: "flex", gap: 0.5, flexWrap: "wrap" }}>
                  {e.competences.map((c) => <Chip key={c} size="small" variant="outlined" label={c} />)}
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{e.justification}</Typography>
              </CardContent>
            </Card>
          ))}
          <Button
            variant="contained"
            disabled={busy || experts.length === 0}
            onClick={() => run(() => api.solicit(id, experts.map((e) => e.id)))}
          >
            Solliciter ces experts
          </Button>
        </Box>
      )}

      {step >= 1 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>Experts sollicites</Typography>
          {sols.map((s) => (
            <Card key={s.id} sx={{ mb: 1.5 }}>
              <CardContent sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 2 }}>
                <Box>
                  <Typography sx={{ fontWeight: 700 }}>{s.expert_nom}</Typography>
                  {s.reason && <Typography variant="body2" color="text.secondary">Motif : {s.reason}</Typography>}
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <Chip size="small" color={SOL_COLOR[s.status]} label={SOL_LABEL[s.status]} />
                  {step === 1 && s.status === "pending" && (
                    <>
                      <Button size="small" disabled={busy} onClick={() => run(() => api.respond(s.id, "accepted"))}>
                        Accepter
                      </Button>
                      <Button
                        size="small" color="error" disabled={busy}
                        onClick={() => run(() => api.respond(s.id, "refused", "Indisponible"))}
                      >
                        Refuser
                      </Button>
                    </>
                  )}
                  {step === 1 && s.status === "accepted" && (
                    <Button size="small" variant="contained" disabled={busy}
                            onClick={() => run(() => api.select(id, s.expert_id))}>
                      Choisir
                    </Button>
                  )}
                </Box>
              </CardContent>
            </Card>
          ))}
          {step === 1 && (
            <Typography variant="caption" color="text.secondary">
              Les boutons Accepter / Refuser simulent la reponse de l'expert (interface expert du module D).
            </Typography>
          )}
          {allRefused && <Alert severity="warning" sx={{ mt: 1 }}>Tous les experts ont refuse ce mandat.</Alert>}
        </Box>
      )}

      {step === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>Signature electronique simple</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            En signant, vous confirmez le mandat ci-dessus. La signature est horodatee et enregistree dans le journal d'audit.
          </Typography>
          <Box sx={{ display: "flex", gap: 2 }}>
            <TextField
              fullWidth size="small" label="Nom du signataire"
              value={signName} onChange={(e) => setSignName(e.target.value)}
            />
            <Button
              variant="contained" sx={{ whiteSpace: "nowrap" }}
              disabled={busy || signName.trim().length < 2}
              onClick={() => run(() => api.sign(id, signName))}
            >
              Signer le mandat
            </Button>
          </Box>
        </Paper>
      )}

      {step === 3 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>Mandat signe</Typography>
          <Button variant="contained" disabled={busy} onClick={() => run(() => api.generateContract(id))}>
            Generer le mandat PDF
          </Button>
        </Paper>
      )}

      {step === 4 && contract && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>Mandat pret</Typography>
          <Button
            variant="contained" startIcon={<DownloadIcon />}
            component="a" href={contract.pdf_url} target="_blank" rel="noreferrer"
          >
            Telecharger le mandat PDF
          </Button>
          <Typography variant="caption" sx={{ display: "block", mt: 2, wordBreak: "break-all" }}>
            Empreinte SHA-256 : {contract.hash_sha256}
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
