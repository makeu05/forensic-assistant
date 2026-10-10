import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { Alert, Box, Button, Card, Checkbox, FormControlLabel, LinearProgress, TextField, Typography } from "@mui/material";
import DownloadIcon from "@mui/icons-material/FileDownloadOutlined";
import DrawIcon from "@mui/icons-material/DrawOutlined";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdfOutlined";
import { api, downloadPdf } from "../../api";
import { useAuth } from "../../auth";
import { formatDateTime, frenchError } from "../../format";
import { useLoad } from "../../hooks";
import HashBadge from "../../components/ui/HashBadge";
import { SectionTitle, SkeletonCards } from "../../components/ui/Page";
import PdfViewer from "../../components/ui/PdfViewer";
import { useToast } from "../../components/ui/Toast";
import { useCase } from "./CaseLayout";

function SignCard() {
  const { data: c, reload } = useCase();
  const { user } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.display_name ?? "");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);

  async function sign() {
    setBusy(true);
    try {
      await api.sign(c.case_id, name.trim());
      toast.success("Mandat signé. Vous pouvez générer le contrat.");
      await reload();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card sx={{ p: { xs: 2.5, sm: 4 }, maxWidth: 640 }}>
      <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", mb: 1 }}>
        <DrawIcon color="primary" aria-hidden="true" />
        <Typography variant="h3" component="h2">Signer le mandat</Typography>
      </Box>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        La signature électronique simple associe votre nom à l'heure exacte de la signature. Elle est enregistrée dans le journal d'audit.
      </Typography>
      <TextField label="Nom du signataire" value={name} onChange={(e) => setName(e.target.value)} fullWidth sx={{ mb: 1.5 }} error={name.trim().length > 0 && name.trim().length < 2} />
      <FormControlLabel
        control={<Checkbox checked={agree} onChange={(e) => setAgree(e.target.checked)} />}
        label="J'ai relu le mandat et je confirme son contenu."
        sx={{ mb: 2 }}
      />
      <Box><Button variant="contained" size="large" onClick={sign} disabled={busy || !agree || name.trim().length < 2}>Signer le mandat</Button></Box>
    </Card>
  );
}

function GenerateCard({ onDone }: { onDone: () => void }) {
  const { data: c } = useCase();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      await api.generateContract(c.case_id);
      toast.success("Contrat généré et horodaté.");
      onDone();
    } catch (e) {
      toast.error(frenchError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card sx={{ p: { xs: 2.5, sm: 4 }, maxWidth: 640 }}>
      <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", mb: 1 }}>
        <PictureAsPdfIcon color="primary" aria-hidden="true" />
        <Typography variant="h3" component="h2">Générer le contrat</Typography>
      </Box>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Le mandat signé est mis en page en PDF, puis son empreinte SHA-256 est calculée et enregistrée pour garantir qu'il ne sera pas modifié.
      </Typography>
      {busy && (
        <Box role="status" sx={{ mb: 2 }}>
          <LinearProgress />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>Mise en page du document et calcul de l'empreinte…</Typography>
        </Box>
      )}
      <Button variant="contained" size="large" onClick={generate} disabled={busy}>{busy ? "Génération…" : "Générer le contrat PDF"}</Button>
    </Card>
  );
}

/** Step 3. Sign the mandate, generate the contract PDF, read it with its integrity hash. */
export default function ContractStep() {
  const { data: c, reload } = useCase();
  const { user } = useAuth();
  const contract = useLoad(() => api.contract(c.case_id), [c.case_id]);
  const toast = useToast();
  const [verified, setVerified] = useState<boolean | undefined>();
  const mandataire = user?.role !== "investigateur";

  if (contract.loading && !contract.data && !contract.error) return <SkeletonCards count={2} height={160} />;

  if (contract.data) {
    const k = contract.data;
    return (
      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 3fr) minmax(300px, 1fr)" }, alignItems: "start" }}>
        <PdfViewer url={k.pdf_url} title="Aperçu du contrat PDF" onVerified={setVerified} height={620} />
        <Card sx={{ p: 3, display: "grid", gap: 2.5 }}>
          <Typography variant="h3" component="h2">Contrat prêt</Typography>
          <HashBadge hash={k.hash_sha256} verified={verified} timestamp={k.generated_at} />
          <Typography variant="body2" color="text.secondary">
            À chaque affichage ou téléchargement, Locard recalcule l'empreinte du fichier et le refuse s'il a été modifié depuis sa génération.
          </Typography>
          <Button variant="contained" startIcon={<DownloadIcon />} onClick={() => downloadPdf(k.pdf_url, "mandat.pdf").catch((e) => toast.error(frenchError(e)))}>
            Télécharger le contrat (PDF)
          </Button>
          <Typography variant="caption" color="text.secondary">Généré le {formatDateTime(k.generated_at)}</Typography>
        </Card>
      </Box>
    );
  }

  return (
    <>
      <SectionTitle>Contrat</SectionTitle>
      {c.chosen_expert_id === null ? (
        <Alert severity="info" action={mandataire ? <Button component={RouterLink} to={`/cases/${c.case_id}/experts`} color="inherit" size="small">Choisir un expert</Button> : undefined}>
          {mandataire ? "Choisissez d'abord l'expert qui mènera l'investigation. Le contrat est établi pour lui." : "Le contrat sera disponible après le choix de l'expert par le mandataire."}
        </Alert>
      ) : !mandataire ? (
        <Alert severity="info">Le mandataire n'a pas encore généré le contrat. Il sera disponible ici dès sa signature.</Alert>
      ) : !c.signed ? (
        <SignCard />
      ) : (
        <GenerateCard onDone={() => { void contract.reload(); void reload(); }} />
      )}
    </>
  );
}
