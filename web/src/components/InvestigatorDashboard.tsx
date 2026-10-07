import { useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, FormControl, InputLabel, LinearProgress, MenuItem, Paper, Select,
  Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from "@mui/material";
import { api, CASE_TYPE_LABEL, errorMessage, Mission, STATUS_LABEL } from "../api";

const STATUS_COLOR = { en_attente: "warning", en_cours: "info", termine: "success" } as const;

interface Props {
  onOpen: (id: string) => void;
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Paper sx={{ p: 2, flex: 1, minWidth: 140 }}>
      <Typography variant="h4" sx={{ fontWeight: 800, color: color ?? "primary.main" }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Paper>
  );
}

export default function InvestigatorDashboard({ onOpen }: Props) {
  const [all, setAll] = useState<Mission[] | null>(null);
  const [expertFilter, setExpertFilter] = useState<number | "all">("all");
  const [error, setError] = useState("");

  useEffect(() => {
    api.missions().then(setAll).catch((e) => setError(errorMessage(e)));
  }, []);

  const experts = useMemo(() => {
    const seen = new Map<number, string>();
    (all ?? []).forEach((m) => seen.set(m.expert.id, m.expert.nom));
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [all]);

  const missions = useMemo(
    () => (all ?? []).filter((m) => expertFilter === "all" || m.expert.id === expertFilter),
    [all, expertFilter],
  );

  const totals = useMemo(
    () => ({
      missions: missions.length,
      pvs: missions.reduce((n, m) => n + m.pv_count, 0),
      incoherences: missions.reduce((n, m) => n + m.incoherence_count, 0),
      high: missions.reduce((n, m) => n + m.high_severity_count, 0),
    }),
    [missions],
  );

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, gap: 2, flexWrap: "wrap" }}>
        <Typography variant="h5" color="primary" sx={{ fontWeight: 700 }}>
          Mes missions
        </Typography>
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel id="expert-filter">Investigateur</InputLabel>
          <Select
            labelId="expert-filter"
            label="Investigateur"
            value={expertFilter}
            onChange={(e) => setExpertFilter(e.target.value as number | "all")}
          >
            <MenuItem value="all">Tous les investigateurs</MenuItem>
            {experts.map(([id, nom]) => (
              <MenuItem key={id} value={id}>
                {nom}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}
      {!all && !error && <CircularProgress />}
      {all && all.length === 0 && (
        <Alert severity="info">
          Aucune mission pour le moment. Une mission apparait ici des qu'un mandataire retient un expert pour un mandat.
        </Alert>
      )}

      {all && all.length > 0 && (
        <>
          <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
            <Stat label="Missions" value={totals.missions} />
            <Stat label="PV analyses" value={totals.pvs} />
            <Stat label="Incoherences" value={totals.incoherences} color="#ED6C02" />
            <Stat label="Severite haute" value={totals.high} color="#D32F2F" />
          </Box>
          <Paper>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Dossier</TableCell>
                  <TableCell>Investigateur</TableCell>
                  <TableCell>Statut</TableCell>
                  <TableCell align="right">PV</TableCell>
                  <TableCell align="right">Incoherences</TableCell>
                  <TableCell sx={{ minWidth: 130 }}>Coherence</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {missions.map((m) => (
                  <TableRow key={m.case_id} hover sx={{ cursor: "pointer" }} onClick={() => onOpen(m.case_id)}>
                    <TableCell>
                      {CASE_TYPE_LABEL[m.case_type]}
                      <Typography variant="caption" display="block" color="text.secondary">
                        Priorite {m.priority} - {new Date(m.created_at).toLocaleDateString("fr-FR")}
                      </Typography>
                    </TableCell>
                    <TableCell>{m.expert.nom}</TableCell>
                    <TableCell>
                      <Chip size="small" color={STATUS_COLOR[m.status]} label={STATUS_LABEL[m.status]} />
                    </TableCell>
                    <TableCell align="right">{m.pv_count}</TableCell>
                    <TableCell align="right">
                      {m.incoherence_count > 0 ? (
                        <Chip
                          size="small"
                          color={m.high_severity_count > 0 ? "error" : "warning"}
                          label={m.incoherence_count}
                        />
                      ) : (
                        m.incoherence_count
                      )}
                    </TableCell>
                    <TableCell>
                      {m.score_coherence === null ? (
                        <Typography variant="caption" color="text.secondary">
                          Aucun PV
                        </Typography>
                      ) : (
                        <Box>
                          <LinearProgress
                            variant="determinate"
                            value={m.score_coherence * 100}
                            color={m.score_coherence >= 0.8 ? "success" : m.score_coherence >= 0.6 ? "warning" : "error"}
                          />
                          <Typography variant="caption">{Math.round(m.score_coherence * 100)} %</Typography>
                        </Box>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {missions.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>Aucune mission pour cet investigateur.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </>
      )}
    </Box>
  );
}
