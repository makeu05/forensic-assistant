import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, Stack, TextField, Typography,
} from "@mui/material";
import InboxIcon from "@mui/icons-material/MailOutline";
import { api, Request } from "../api";
import { CASE_TYPE_LABEL, formatDate, frenchError, relativeTime } from "../format";
import { useLoad } from "../hooks";
import { EmptyState, PageHeader, SkeletonCards } from "../components/ui/Page";
import StatusChip from "../components/ui/StatusChip";
import { useToast } from "../components/ui/Toast";
import { PriorityChip } from "./Home";

const REASONS = ["Indisponible sur cette période", "Conflit d'intérêts", "Hors de mon domaine de compétence"];

export function RefuseDialog({ request, onClose, onDone }: { request: { id: number } | null; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function confirm() {
    if (!request) return;
    setBusy(true);
    try {
      await api.respond(request.id, "refused", reason.trim() || undefined);
      toast.success("Votre refus a été transmis au mandataire.");
      setReason("");
      onDone();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={Boolean(request)} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm" aria-labelledby="refuse-title">
      <DialogTitle id="refuse-title">Refuser cette mission</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          Le mandataire sera informé. Un motif l'aide à choisir un autre expert, il reste facultatif. Cette réponse est définitive.
        </DialogContentText>
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 2 }}>
          {REASONS.map((r) => <Chip key={r} label={r} clickable onClick={() => setReason(r)} variant={reason === r ? "filled" : "outlined"} color={reason === r ? "primary" : "default"} />)}
        </Box>
        <TextField label="Motif (facultatif)" value={reason} onChange={(e) => setReason(e.target.value)} fullWidth multiline minRows={2} inputProps={{ maxLength: 300 }} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={busy}>Annuler</Button>
        <Button onClick={confirm} variant="contained" color="error" disabled={busy}>Refuser la mission</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function RequestsPage() {
  const toast = useToast();
  const requests = useLoad(() => api.myRequests(), []);
  const [refusing, setRefusing] = useState<Request | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function accept(r: Request) {
    setBusyId(r.id);
    try {
      await api.respond(r.id, "accepted");
      toast.success("Mission acceptée. Le mandataire peut maintenant vous choisir.");
      await requests.reload();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusyId(null);
    }
  }

  const list = requests.data ?? [];
  return (
    <>
      <PageHeader title="Demandes de mission" subtitle="Les mandataires qui vous ont sollicité. Répondez pour être pris en compte." />
      {requests.error && <Alert severity="error">{requests.error}</Alert>}
      {requests.loading && !requests.data && <SkeletonCards count={2} height={160} />}
      {requests.data && list.length === 0 && (
        <EmptyState icon={<InboxIcon fontSize="large" />} title="Aucune demande" text="Quand un mandataire vous sollicite pour un dossier, la demande apparaît ici et vous recevez un e-mail." />
      )}
      <Stack spacing={2}>
        {list.map((r) => (
          <Card key={r.id}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap", mb: 1 }}>
                <Box>
                  <Typography variant="h3" component="h2">{CASE_TYPE_LABEL[r.case.case_type]}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Demande du {formatDate(r.case.created_at)} · {relativeTime(r.case.created_at)}
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
                  <PriorityChip priority={r.case.priority} />
                  <StatusChip status={r.status} />
                </Box>
              </Box>
              <Typography sx={{ my: 2, whiteSpace: "pre-wrap" }}>{r.case.description}</Typography>
              {r.reason && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Votre motif : {r.reason}</Typography>}
              <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
                {r.status === "pending" && (
                  <>
                    <Button variant="contained" onClick={() => accept(r)} disabled={busyId === r.id}>Accepter la mission</Button>
                    <Button variant="outlined" color="error" onClick={() => setRefusing(r)} disabled={busyId === r.id}>Refuser</Button>
                  </>
                )}
                {r.status === "accepted" && <Typography variant="body2" color="text.secondary">En attente du choix du mandataire.</Typography>}
                {r.status === "chosen" && <Button component={RouterLink} to={`/cases/${r.case_id}/preparation`} variant="contained">Ouvrir la mission</Button>}
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>
      <RefuseDialog request={refusing} onClose={() => setRefusing(null)} onDone={() => { setRefusing(null); void requests.reload(); }} />
    </>
  );
}
