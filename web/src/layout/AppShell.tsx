import { ReactNode, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar, Autocomplete, Avatar, Badge, BottomNavigation, BottomNavigationAction, Box, Divider, IconButton, InputAdornment,
  List, ListItemButton, ListItemIcon, ListItemText, Menu, MenuItem, Paper, TextField, Toolbar, Tooltip, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/AddCircleOutline";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import DarkModeIcon from "@mui/icons-material/DarkModeOutlined";
import FingerprintIcon from "@mui/icons-material/Fingerprint";
import FolderIcon from "@mui/icons-material/FolderOpenOutlined";
import HistoryIcon from "@mui/icons-material/HistoryOutlined";
import InboxIcon from "@mui/icons-material/MailOutline";
import LightModeIcon from "@mui/icons-material/LightModeOutlined";
import LogoutIcon from "@mui/icons-material/LogoutOutlined";
import NotificationsIcon from "@mui/icons-material/NotificationsNone";
import SearchIcon from "@mui/icons-material/Search";
import SettingsIcon from "@mui/icons-material/SettingsOutlined";
import SpaceDashboardIcon from "@mui/icons-material/SpaceDashboardOutlined";
import { api, CaseData } from "../api";
import { useAuth } from "../auth";
import { CASE_TYPE_LABEL } from "../format";
import { useStored } from "../hooks";
import { useNotices } from "../notifications";
import { useSettings } from "../settings";
import { brand } from "../theme/tokens";

const SIDEBAR_WIDTH = 264;
const SIDEBAR_COLLAPSED = 76;
const ON_NAVY = "#C7D3E5"; // secondary text on the navy sidebar (checked by scripts/check-contrast.mjs)

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
  badge?: number;
}

function useNavItems(pendingRequests: number): NavItem[] {
  const { user } = useAuth();
  const common: NavItem[] = [
    { to: "/audit", label: "Journal d'audit", icon: <HistoryIcon /> },
    { to: "/options", label: "Options", icon: <SettingsIcon /> },
  ];
  if (user?.role === "investigateur") {
    return [
      { to: "/", label: "Mes missions", icon: <FolderIcon />, end: true },
      { to: "/demandes", label: "Demandes", icon: <InboxIcon />, badge: pendingRequests },
      ...common,
    ];
  }
  return [
    { to: "/", label: "Tableau de bord", icon: <SpaceDashboardIcon />, end: true },
    { to: "/cases/new", label: "Nouveau mandat", icon: <AddIcon /> },
    ...common,
  ];
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 2.5, height: 64 }}>
      <FingerprintIcon aria-hidden="true" sx={{ color: brand.cyan, fontSize: 30 }} />
      {!collapsed && (
        <Box>
          <Typography sx={{ color: "#FFFFFF", fontSize: 20, fontWeight: 600, lineHeight: 1.1 }}>Locard</Typography>
          <Typography sx={{ color: ON_NAVY, fontSize: 12, lineHeight: 1.2 }}>Investigation numérique</Typography>
        </Box>
      )}
    </Box>
  );
}

function Sidebar({ items, collapsed, onToggle }: { items: NavItem[]; collapsed: boolean; onToggle: () => void }) {
  return (
    <Box
      component="aside"
      sx={{
        display: { xs: "none", md: "flex" }, flexDirection: "column", flexShrink: 0, bgcolor: brand.navy900,
        width: collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_WIDTH, transition: "width 200ms ease", position: "sticky", top: 0, height: "100vh",
      }}
    >
      <Brand collapsed={collapsed} />
      <Box component="nav" aria-label="Navigation principale" sx={{ flex: 1, px: 1.5, pt: 1 }}>
        <List disablePadding>
          {items.map((item) => (
            <Box component="li" key={item.to} sx={{ listStyle: "none" }}>
            <Tooltip title={collapsed ? item.label : ""} placement="right">
              <ListItemButton
                component={NavLink} to={item.to} end={item.end}
                sx={{
                  borderRadius: 2, mb: 0.5, minHeight: 44, color: "#FFFFFF", px: 1.5,
                  transition: "background-color 150ms ease",
                  "&:hover": { bgcolor: "rgba(255,255,255,0.08)" },
                  "&.active": { bgcolor: brand.navy700, boxShadow: `inset 3px 0 0 ${brand.cyan}` },
                  "&.Mui-focusVisible, &:focus-visible": { outline: `2px solid ${brand.cyan}`, boxShadow: "none" },
                }}
              >
                <ListItemIcon sx={{ minWidth: collapsed ? 0 : 40, color: "inherit", justifyContent: "center" }}>
                  <Badge color="error" badgeContent={item.badge} invisible={!item.badge}>{item.icon}</Badge>
                </ListItemIcon>
                {!collapsed && <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 14, fontWeight: 500 }} />}
              </ListItemButton>
            </Tooltip>
            </Box>
          ))}
        </List>
      </Box>
      <Divider sx={{ borderColor: "rgba(255,255,255,0.12)" }} />
      <Box sx={{ p: 1.5, display: "flex", justifyContent: collapsed ? "center" : "space-between", alignItems: "center" }}>
        {!collapsed && (
          <Typography component={NavLink} to="/style-guide" sx={{ color: ON_NAVY, fontSize: 12, textDecoration: "none", "&:hover": { textDecoration: "underline" } }}>
            Guide de style
          </Typography>
        )}
        <Tooltip title={collapsed ? "Déplier le menu" : "Replier le menu"}>
          <IconButton onClick={onToggle} aria-label={collapsed ? "Déplier le menu" : "Replier le menu"} sx={{ color: "#FFFFFF" }}>
            {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

function CaseSearch() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseData[]>([]);

  useEffect(() => {
    api.listCases().then(setCases).catch(() => undefined);
  }, []);

  const text = (c: CaseData) => `${CASE_TYPE_LABEL[c.case_type]} ${c.description} ${c.case_id}`.toLowerCase();
  return (
    <Autocomplete<CaseData>
      options={cases}
      value={null}
      blurOnSelect
      clearOnBlur
      noOptionsText="Aucun dossier trouvé"
      getOptionLabel={(c) => CASE_TYPE_LABEL[c.case_type]}
      filterOptions={(options, { inputValue }) => options.filter((c) => text(c).includes(inputValue.trim().toLowerCase()))}
      onChange={(_, c) => c && navigate(`/cases/${c.case_id}`)}
      isOptionEqualToValue={(a, b) => a.case_id === b.case_id}
      sx={{ flex: 1, maxWidth: 440 }}
      renderOption={(props, c) => (
        <li {...props} key={c.case_id}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>{CASE_TYPE_LABEL[c.case_type]}</Typography>
            <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block", maxWidth: 360 }}>
              {c.description}
            </Typography>
          </Box>
        </li>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          size="small"
          placeholder="Rechercher un dossier"
          inputProps={{ ...params.inputProps, "aria-label": "Rechercher un dossier" }}
          InputProps={{
            ...params.InputProps,
            startAdornment: <InputAdornment position="start"><SearchIcon sx={{ color: ON_NAVY }} /></InputAdornment>,
            sx: {
              bgcolor: brand.navy700, color: "#FFFFFF", borderRadius: 2,
              "& fieldset": { borderColor: "rgba(255,255,255,0.18)" },
              "&:hover fieldset": { borderColor: "rgba(255,255,255,0.4)" },
              "& input::placeholder": { color: ON_NAVY, opacity: 1 },
              "& .MuiAutocomplete-clearIndicator": { color: ON_NAVY },
            },
          }}
        />
      )}
    />
  );
}

function Notifications() {
  const navigate = useNavigate();
  const { notices } = useNotices();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  return (
    <>
      <Tooltip title="Notifications">
        <IconButton
          onClick={(e) => setAnchor(e.currentTarget)} sx={{ color: "#FFFFFF" }}
          aria-label={notices.length ? `${notices.length} notification(s)` : "Notifications"} aria-haspopup="menu"
        >
          <Badge color="error" badgeContent={notices.length} invisible={!notices.length}><NotificationsIcon /></Badge>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)} slotProps={{ paper: { sx: { width: 340, maxWidth: "calc(100vw - 32px)" } } }}>
        {notices.length === 0 && <MenuItem disabled sx={{ whiteSpace: "normal" }}>Rien de nouveau. Tout est à jour.</MenuItem>}
        {notices.map((n) => (
          <MenuItem key={n.id} onClick={() => { setAnchor(null); navigate(n.to); }} sx={{ whiteSpace: "normal" }}>
            {n.text}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  if (!user) return null;
  const initials = user.display_name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <>
      <Tooltip title="Mon compte">
        <IconButton onClick={(e) => setAnchor(e.currentTarget)} aria-label={`Menu du compte de ${user.display_name}`} aria-haspopup="menu">
          <Avatar sx={{ width: 36, height: 36, bgcolor: brand.cyan, color: brand.navy900, fontSize: 14, fontWeight: 600 }}>{initials}</Avatar>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2">{user.display_name}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{user.email}</Typography>
          <Typography variant="caption" color="text.secondary">
            {user.role === "investigateur" ? "Investigateur" : "Mandataire"}
          </Typography>
        </Box>
        <Divider />
        <MenuItem onClick={() => { setAnchor(null); navigate("/options"); }}>
          <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>Options
        </MenuItem>
        <MenuItem onClick={() => { setAnchor(null); void logout().then(() => navigate("/login")); }}>
          <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>Se déconnecter
        </MenuItem>
      </Menu>
    </>
  );
}

function TopBar() {
  const { mode, setMode } = useSettings();
  return (
    <AppBar position="sticky" elevation={0} sx={{ bgcolor: brand.navy900, borderBottom: "1px solid rgba(255,255,255,0.08)", backgroundImage: "none" }}>
      <Toolbar sx={{ gap: 1.5, minHeight: { xs: 56, md: 64 } }}>
        <Box sx={{ display: { xs: "flex", md: "none" }, alignItems: "center", gap: 1, mr: 0.5 }}>
          <FingerprintIcon aria-hidden="true" sx={{ color: brand.cyan }} />
          <Typography sx={{ color: "#FFFFFF", fontWeight: 600, fontSize: 20 }}>Locard</Typography>
        </Box>
        <CaseSearch />
        <Box sx={{ flex: 1 }} />
        <Tooltip title={mode === "dark" ? "Passer au mode clair" : "Passer au mode sombre"}>
          <IconButton onClick={() => setMode(mode === "dark" ? "light" : "dark")} sx={{ color: "#FFFFFF" }} aria-label={mode === "dark" ? "Activer le mode clair" : "Activer le mode sombre"}>
            {mode === "dark" ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Tooltip>
        <Notifications />
        <UserMenu />
      </Toolbar>
    </AppBar>
  );
}

function BottomNav({ items }: { items: NavItem[] }) {
  const location = useLocation();
  const navigate = useNavigate();
  const current = items.findIndex((i) => (i.end ? location.pathname === i.to : location.pathname.startsWith(i.to)));
  return (
    <Paper component="nav" aria-label="Navigation principale" elevation={3} square sx={{ display: { xs: "block", md: "none" }, position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 1100 }}>
      <BottomNavigation value={current} onChange={(_, i) => navigate(items[i].to)} showLabels>
        {items.map((item) => (
          <BottomNavigationAction
            key={item.to} label={item.label} sx={{ minWidth: 0, px: 0.5, "& .MuiBottomNavigationAction-label": { fontSize: 12 } }}
            icon={<Badge color="error" badgeContent={item.badge} invisible={!item.badge}>{item.icon}</Badge>}
          />
        ))}
      </BottomNavigation>
    </Paper>
  );
}

export default function AppShell() {
  const { pendingRequests } = useNotices();
  const items = useNavItems(pendingRequests);
  const [collapsed, setCollapsed] = useStored("locard.sidebar.collapsed", false);
  const location = useLocation();

  // Move focus to the page title after navigation, so keyboard and screen-reader users start at the top.
  useEffect(() => {
    document.getElementById("main")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <Box
        component="a" href="#main"
        sx={{ position: "absolute", left: -9999, top: 8, zIndex: 2000, bgcolor: "#FFFFFF", color: brand.navy900, px: 2, py: 1, borderRadius: 1, "&:focus": { left: 8 } }}
      >
        Aller au contenu principal
      </Box>
      <Sidebar items={items} collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <Box sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <TopBar />
        <Box component="main" id="main" tabIndex={-1} sx={{ flex: 1, outline: "none", px: { xs: 2, sm: 3, md: 4 }, py: { xs: 3, md: 4 }, pb: { xs: 12, md: 4 }, maxWidth: 1240, width: "100%", mx: "auto" }}>
          <Outlet />
        </Box>
      </Box>
      <BottomNav items={items} />
    </Box>
  );
}

