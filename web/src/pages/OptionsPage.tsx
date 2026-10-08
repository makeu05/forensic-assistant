import { useNavigate } from "react-router-dom";
import { Box, Button, Card, FormControlLabel, Switch, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import DarkModeIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeIcon from "@mui/icons-material/LightModeOutlined";
import DownloadIcon from "@mui/icons-material/FileDownloadOutlined";
import LogoutIcon from "@mui/icons-material/LogoutOutlined";
import { downloadFile } from "../api";
import { useAuth } from "../auth";
import { frenchError } from "../format";
import { useSettings } from "../settings";
import { PageHeader } from "../components/ui/Page";
import { useToast } from "../components/ui/Toast";

function Option({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card sx={{ p: { xs: 2.5, sm: 3.5 } }}>
      <Typography variant="h3" component="h2" sx={{ mb: 1.5 }}>{title}</Typography>
      {children}
    </Card>
  );
}

export default function OptionsPage() {
  const { user, logout } = useAuth();
  const { mode, setMode, pseudonymize, setPseudonymize } = useSettings();
  const navigate = useNavigate();
  const toast = useToast();

  return (
    <>
      <PageHeader title="Options" subtitle="Ces réglages sont enregistrés sur cet appareil." />
      <Box sx={{ display: "grid", gap: 3, maxWidth: 760 }}>
        <Option title="Protection des données (RGPD)">
          <FormControlLabel
            control={<Switch checked={pseudonymize} onChange={(e) => { setPseudonymize(e.target.checked); toast.info(e.target.checked ? "Pseudonymisation activée." : "Pseudonymisation désactivée."); }} />}
            label="Pseudonymiser les noms des personnes citées"
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Quand l'option est active, les noms des témoins et personnes citées dans les procès-verbaux sont remplacés par « Personne A », « Personne B »…
            à l'écran et dans les rapports que vous générez. Le même nom reçoit toujours le même identifiant, pour que le raisonnement reste lisible.
            Les procès-verbaux enregistrés ne sont pas modifiés : seul l'affichage et les exports changent.
          </Typography>
        </Option>

        <Option title="Mes données">
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Téléchargez un fichier JSON avec les informations de votre compte, vos dossiers, les demandes qui vous sont adressées
            et la liste de vos actions enregistrées. Les déclarations des témoins et les données des autres utilisateurs n'y figurent pas.
          </Typography>
          <Button variant="outlined" startIcon={<DownloadIcon />}
            onClick={() => downloadFile("/api/v1/privacy/export", "locard-mes-donnees.json")
              .then(() => toast.success("Export téléchargé."))
              .catch((e) => toast.error(frenchError(e)))}>
            Télécharger mes données
          </Button>
        </Option>

        <Option title="Apparence">
          <ToggleButtonGroup exclusive value={mode} onChange={(_, v) => v && setMode(v)} aria-label="Thème de l'interface">
            <ToggleButton value="light" sx={{ gap: 1, px: 2 }}><LightModeIcon fontSize="small" />Clair</ToggleButton>
            <ToggleButton value="dark" sx={{ gap: 1, px: 2 }}><DarkModeIcon fontSize="small" />Sombre</ToggleButton>
          </ToggleButtonGroup>
        </Option>

        <Option title="Mon compte">
          <Box sx={{ display: "grid", gap: 0.5, mb: 2.5 }}>
            <Typography sx={{ fontWeight: 500 }}>{user?.display_name}</Typography>
            <Typography variant="body2" color="text.secondary">{user?.email}</Typography>
            <Typography variant="body2" color="text.secondary">{user?.role === "investigateur" ? "Investigateur" : "Mandataire"}</Typography>
          </Box>
          <Button variant="outlined" startIcon={<LogoutIcon />} onClick={() => void logout().then(() => navigate("/login"))}>Se déconnecter</Button>
        </Option>
      </Box>
    </>
  );
}
