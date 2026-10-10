import { useEffect, useState } from "react";
import { Alert, Box, Skeleton } from "@mui/material";
import { fetchPdf } from "../../api";
import { frenchError } from "../../format";

interface Props {
  /** API path of the PDF, e.g. /api/v1/contracts/…/download */
  url: string;
  title: string;
  height?: number | string;
  /** Called with true when the server delivered the file after re-checking its hash, false if it refused (409). */
  onVerified?: (ok: boolean) => void;
}

/** Shows a protected PDF. The file is fetched with the user's token, then displayed from memory. */
export default function PdfViewer({ url, title, height = 560, onVerified }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null);
    setError("");
    fetchPdf(url)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
        onVerified?.(true);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(frenchError(e));
        onVerified?.(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // onVerified is deliberately left out: callers pass a new function every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!src) return <Skeleton variant="rounded" height={height} animation="wave" aria-label="Chargement du document" />;
  return (
    <Box
      component="iframe"
      src={src}
      title={title}
      sx={{ width: "100%", height, border: 1, borderColor: "divider", borderRadius: 2.5, bgcolor: "background.paper" }}
    />
  );
}
