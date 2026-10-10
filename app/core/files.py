"""Answering a file request, in a way that survives download managers.

Browser extensions such as Internet Download Manager hook the network layer and take over any response that
looks like a download (application/pdf, Content-Disposition: attachment). The web app then receives an empty
204 instead of the file, and a PDF preview or a "Télécharger" button silently produces nothing.

So every file endpoint offers two encodings of the same file:
  raw     the file itself (default): for curl, scripts and direct links
  base64  a small JSON document {filename, content_type, size, content_base64}: this is not a download in the
          eyes of a download manager, so it always arrives. The web app uses this one.
Integrity checks happen before either encoding is produced.
"""
import base64
from pathlib import Path
from typing import Literal

from fastapi.responses import FileResponse, JSONResponse

Encoding = Literal["raw", "base64"]


def file_answer(path: str | Path, media_type: str, filename: str, encoding: Encoding = "raw"):
    if encoding == "base64":
        data = Path(path).read_bytes()
        return JSONResponse({"filename": filename, "content_type": media_type, "size": len(data),
                             "content_base64": base64.b64encode(data).decode("ascii")})
    return FileResponse(path, media_type=media_type, filename=filename)
