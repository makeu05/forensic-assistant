import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import { CASE_TYPE_LABEL } from "./format";

export interface Notice {
  id: string;
  text: string;
  to: string;
}

const REFRESH_MS = 60_000;

/**
 * What needs the user's attention, worked out from data the app already has:
 * an investigator sees pending requests; a mandataire sees experts who answered.
 */
export function useNotices(): { notices: Notice[]; pendingRequests: number } {
  const { user } = useAuth();
  const [notices, setNotices] = useState<Notice[]>([]);
  const [pendingRequests, setPendingRequests] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function load() {
      try {
        if (user?.role === "investigateur") {
          const requests = (await api.myRequests()).filter((r) => r.status === "pending");
          if (cancelled) return;
          setPendingRequests(requests.length);
          setNotices(requests.map((r) => ({
            id: `req-${r.id}`, to: "/demandes",
            text: `Nouvelle demande de mission : ${CASE_TYPE_LABEL[r.case.case_type]}`,
          })));
        } else {
          const cases = await api.listCases();
          if (cancelled) return;
          const list: Notice[] = [];
          for (const c of cases) {
            const label = CASE_TYPE_LABEL[c.case_type];
            const s = c.solicitations;
            if (c.chosen_expert_id === null && s.accepted > 0) {
              list.push({ id: `acc-${c.case_id}`, to: `/cases/${c.case_id}/experts`, text: `${label} : un expert a accepté. Choisissez-le.` });
            } else if (c.chosen_expert_id === null && s.total > 0 && s.refused === s.total) {
              list.push({ id: `ref-${c.case_id}`, to: `/cases/${c.case_id}/experts`, text: `${label} : tous les experts ont refusé.` });
            }
          }
          setPendingRequests(0);
          setNotices(list);
        }
      } catch {
        /* a failed refresh keeps the previous notices */
      }
    }

    void load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [user]);

  return { notices, pendingRequests };
}
