import { useTheme } from "@mui/material/styles";
import { palette, Palette } from "./tokens";

/** The colour tokens of the current mode, for components that need tinted backgrounds. */
export function useTokens(): Palette {
  return palette[useTheme().palette.mode];
}
