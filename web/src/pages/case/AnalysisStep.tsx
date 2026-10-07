import { useSearchParams } from "react-router-dom";
import { Alert, Box, Tab, Tabs } from "@mui/material";
import { useAuth } from "../../auth";
import { SectionTitle } from "../../components/ui/Page";
import { useCase } from "./CaseLayout";
import MethodTab from "./MethodTab";
import PvTab from "./PvTab";
import ReportsTab from "./ReportsTab";

const TABS = [
  { key: "pv", label: "Témoignages", panel: PvTab },
  { key: "methode", label: "Hypothèses et méthodologie", panel: MethodTab },
  { key: "rapports", label: "Rapports techniques", panel: ReportsTab },
] as const;

/** Step 5: the investigator's analysis workspace. Tabs are kept in the address (?vue=) so a view can be linked. */
export default function AnalysisStep() {
  const { data: c } = useCase();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();

  if (user?.role !== "investigateur") {
    const done = c.stages.find((s) => s.key === "analyse")?.done;
    return (
      <>
        <SectionTitle>Analyse des preuves</SectionTitle>
        <Alert severity={done ? "success" : "info"}>
          {done ? "L'expert a analysé les témoignages. Les conclusions figureront dans le rapport final."
            : "L'expert analyse les témoignages et mène les actions forensiques. Cette étape ne demande rien de votre part."}
        </Alert>
      </>
    );
  }
  if (c.chosen_expert_id === null) return <Alert severity="info">L'analyse est disponible quand le mandataire vous a choisi pour cette mission.</Alert>;

  const current = TABS.find((t) => t.key === params.get("vue")) ?? TABS[0];
  const Panel = current.panel;
  return (
    <Box>
      <Tabs
        value={current.key} onChange={(_, v) => setParams({ vue: v }, { replace: true })} variant="scrollable" scrollButtons="auto"
        aria-label="Vues de l'analyse" sx={{ mb: 3, borderBottom: 1, borderColor: "divider" }}
      >
        {TABS.map((t) => <Tab key={t.key} value={t.key} label={t.label} id={`tab-${t.key}`} aria-controls={`panel-${t.key}`} />)}
      </Tabs>
      <Box role="tabpanel" id={`panel-${current.key}`} aria-labelledby={`tab-${current.key}`}>
        <Panel />
      </Box>
    </Box>
  );
}
