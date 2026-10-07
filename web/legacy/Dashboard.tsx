import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Table, TableBody, TableCell,
  TableHead, TableRow, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { api, CASE_TYPE_LABEL, CaseData, errorMessage, STATUS_LABEL } from "../api";

const STATUS_COLOR = { en_attente: "warning", en_cours: "info", termine: "success" } as const;

interface Props {
  onNew: () => void;
  onOpen: (id: string) => void;
}

export default function Dashboard({ onNew, onOpen }: Props) {
  const [cases, setCases] = useState<CaseData[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listCases().then((r) => setCases(r.cases)).catch((e) => setError(errorMessage(e)));
  }, []);

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5" color="primary" sx={{ fontWeight: 700 }}>
          Tableau de bord
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={onNew}>
          Nouveau mandat
        </Button>
      </Box>
      {error && <Alert severity="error">{error}</Alert>}
      {!cases && !error && <CircularProgress />}
      {cases && cases.length === 0 && (
        <Alert severity="info">Aucun mandat pour le moment. Creez le premier avec "Nouveau mandat".</Alert>
      )}
      {cases && cases.length > 0 && (
        <Paper>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Priorite</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell>Signe</TableCell>
                <TableCell>Cree le</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cases.map((c) => (
                <TableRow key={c.case_id} hover sx={{ cursor: "pointer" }} onClick={() => onOpen(c.case_id)}>
                  <TableCell>{CASE_TYPE_LABEL[c.case_type]}</TableCell>
                  <TableCell>{c.priority}</TableCell>
                  <TableCell>
                    <Chip size="small" color={STATUS_COLOR[c.status]} label={STATUS_LABEL[c.status]} />
                  </TableCell>
                  <TableCell>{c.signed ? "Oui" : "Non"}</TableCell>
                  <TableCell>{new Date(c.created_at).toLocaleString("fr-FR")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  );
}
