import { Link as RouterLink } from "react-router-dom";
import { Box, Button, Card, Divider, Typography } from "@mui/material";
import EditNoteIcon from "@mui/icons-material/EditNoteOutlined";
import { useAuth } from "../../auth";
import { CASE_TYPE_LABEL, formatDateTime, PRIORITY_LABEL } from "../../format";
import { SectionTitle } from "../../components/ui/Page";
import { useCase } from "./CaseLayout";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography component="div" sx={{ fontWeight: 500 }}>{children}</Typography>
    </Box>
  );
}

/** Step 1. The mandate as it was created, with the next action for the viewer. */
export default function MandateStep() {
  const { data: c } = useCase();
  const { user } = useAuth();
  const mandataire = user?.role !== "investigateur";
  const next = c.stages.find((s) => s.current);

  return (
    <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "minmax(0, 3fr) minmax(260px, 2fr)" }, alignItems: "start" }}>
      <Card sx={{ p: { xs: 2.5, sm: 4 } }}>
        <SectionTitle>Mandat d'investigation</SectionTitle>
        <Typography sx={{ whiteSpace: "pre-wrap", mb: 3 }}>{c.description}</Typography>
        <Divider sx={{ mb: 3 }} />
        <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" } }}>
          <Field label="Type de dossier">{CASE_TYPE_LABEL[c.case_type]}</Field>
          <Field label="Priorité">{PRIORITY_LABEL[c.priority]}</Field>
          <Field label="Mandataire">{c.mandataire.nom}, {c.mandataire.fonction}</Field>
          <Field label="Créé le">{formatDateTime(c.created_at)}</Field>
          <Field label="Signature du mandat">{c.signed ? "Signé" : "Pas encore signé"}</Field>
        </Box>
      </Card>
      <Card sx={{ p: 3 }}>
        <Typography variant="h4" component="h2" sx={{ mb: 1 }}>Prochaine étape</Typography>
        {next ? (
          <>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              {mandataire
                ? ({
                    experts: "Choisissez l'expert qui mènera l'investigation parmi les trois profils proposés.",
                    contrat: c.signed ? "Générez le contrat PDF, avec son empreinte d'intégrité." : "Signez le mandat, puis générez le contrat PDF.",
                    preparation: "L'expert prépare les auditions. Vous serez informé de l'avancement.",
                    analyse: "L'expert analyse les témoignages. Vous serez informé de l'avancement.",
                    rapport: "L'expert rédige le rapport final. Vous pourrez le télécharger dès sa publication.",
                  } as Record<string, string>)[next.key] ?? ""
                : "Ouvrez l'étape en cours pour poursuivre votre travail."}
            </Typography>
            <Button component={RouterLink} to={`/cases/${c.case_id}/${next.key}`} variant="contained" startIcon={<EditNoteIcon />}>
              Aller à l'étape « {next.label} »
            </Button>
          </>
        ) : (
          <Typography color="text.secondary">Toutes les étapes sont terminées. Le rapport final est disponible.</Typography>
        )}
      </Card>
    </Box>
  );
}
