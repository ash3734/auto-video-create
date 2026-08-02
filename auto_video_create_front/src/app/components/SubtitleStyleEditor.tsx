"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Typography,
  Collapse,
  ToggleButtonGroup,
  ToggleButton,
  Snackbar,
  Alert,
  Button,
  TextField,
  CircularProgress,
} from "@mui/material";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import FontPickerModal from "./FontPickerModal";

// ── Types ──────────────────────────────────────────────────────────────────

export interface StyleSetting {
  font_family: string;
  font_size: "S" | "M" | "L";
  fill_color: string;
}

export interface SubtitleSettings {
  title: StyleSetting;
  subtitle: StyleSetting;
}

// VOC: 폰트/색상을 이름 붙여 최대 5개까지 저장·재사용하는 스타일 템플릿
export interface SubtitleTemplate {
  id: string;
  name: string;
  title: StyleSetting;
  subtitle: StyleSetting;
}

interface FontItem {
  family: string;
  category: string;
  slug: string;
}

// ── Constants ──────────────────────────────────────────────────────────────

const MAX_TEMPLATES = 5;

const DEFAULT_SETTINGS: SubtitleSettings = {
  title: { font_family: "Black Han Sans", font_size: "M", fill_color: "#fff100" },
  subtitle: { font_family: "Noto Sans KR", font_size: "M", fill_color: "#ffffff" },
};

// CSS px values for the 9:16 preview frame (240px wide)
const SIZE_PX: Record<"S" | "M" | "L", { title: number; subtitle: number }> = {
  S: { title: 20, subtitle: 14 },
  M: { title: 26, subtitle: 18 },
  L: { title: 34, subtitle: 24 },
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const TEMPLATES_URL = `${API_BASE_URL}/api/blog/subtitle-templates`;

function authFetch(url: string, options: RequestInit = {}) {
  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  return fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), "X-USER-ID": userId ?? "" },
  });
}

// ── Helpers: normalize server payloads defensively ─────────────────────────

function normalizeStyleSetting(raw: unknown, fallback: StyleSetting): StyleSetting {
  const r = (raw ?? {}) as Partial<StyleSetting>;
  return {
    font_family: r.font_family ?? fallback.font_family,
    font_size: (r.font_size as "S" | "M" | "L") ?? fallback.font_size,
    fill_color: r.fill_color ?? fallback.fill_color,
  };
}

function normalizeTemplate(raw: unknown): SubtitleTemplate | null {
  const r = raw as { id?: string | number; name?: string; title?: unknown; subtitle?: unknown } | null;
  if (!r || r.id === undefined || r.id === null) return null;
  return {
    id: String(r.id),
    name: r.name ?? "",
    title: normalizeStyleSetting(r.title, DEFAULT_SETTINGS.title),
    subtitle: normalizeStyleSetting(r.subtitle, DEFAULT_SETTINGS.subtitle),
  };
}

// POST/PUT 응답이 { template: {...} } 또는 {...} 그대로 올 수 있어 방어적으로 파싱
function extractTemplate(data: unknown): SubtitleTemplate | null {
  const wrapped = (data as { template?: unknown } | null)?.template ?? data;
  return normalizeTemplate(wrapped);
}

// BE 에러 응답 형식이 두 가지로 섞여 있음: 5개 초과는 { error_code, message } 최상위,
// 그 외 400/404 는 FastAPI 기본 { detail: "문자열" }. 가능한 한 서버 메시지를 그대로 보여준다.
function extractErrorMessage(data: unknown, fallback: string): string {
  const d = data as { error_code?: string; message?: string; detail?: string } | null;
  if (d?.error_code === "template_limit_reached") {
    return "템플릿은 최대 5개까지 저장할 수 있어요";
  }
  if (typeof d?.detail === "string" && d.detail.trim()) return d.detail;
  if (typeof d?.message === "string" && d.message.trim()) return d.message;
  return fallback;
}

function isSameStyle(a: StyleSetting, b: StyleSetting) {
  return (
    a.font_family === b.font_family &&
    a.font_size === b.font_size &&
    a.fill_color === b.fill_color
  );
}

function isSameSettings(a: SubtitleSettings, b: SubtitleSettings) {
  return isSameStyle(a.title, b.title) && isSameStyle(a.subtitle, b.subtitle);
}

// ── MiniChip ──────────────────────────────────────────────────────────────

function MiniChip({
  label,
  fontFamily,
  color,
}: {
  label: string;
  fontFamily: string;
  color: string;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.25 }}>
      <Typography
        sx={{ fontSize: 9, color: "#aaa", lineHeight: 1, userSelect: "none" }}
      >
        {label}
      </Typography>
      <Box
        sx={{
          bgcolor: "#3a3a3a",
          border: "1px solid rgba(255,255,255,0.15)",
          borderRadius: "6px",
          px: "10px",
          py: "4px",
          minWidth: 48,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Typography
          sx={{
            fontFamily: `'${fontFamily}', sans-serif`,
            color,
            fontSize: 13,
            fontWeight: 700,
            lineHeight: 1,
            userSelect: "none",
          }}
        >
          가나다
        </Typography>
      </Box>
    </Box>
  );
}

// ── ColorSwatch ───────────────────────────────────────────────────────────

function ColorSwatch({
  label,
  color,
  onChange,
}: {
  label: string;
  color: string;
  onChange: (hex: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <Box>
      <Typography sx={{ fontSize: 12, color: "#666", mb: 0.5 }}>{label}</Typography>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          border: "1.5px solid #e3e6ef",
          borderRadius: "7px",
          px: 1.5,
          py: 0.75,
          cursor: "pointer",
          "&:hover": { borderColor: "#1976d2" },
        }}
        onClick={() => inputRef.current?.click()}
      >
        <Box
          sx={{
            width: 24,
            height: 24,
            borderRadius: "4px",
            bgcolor: color,
            border: "1px solid rgba(0,0,0,0.15)",
            flexShrink: 0,
          }}
        />
        <Typography sx={{ fontSize: 13, color: "#444", fontFamily: "monospace" }}>
          {color.toUpperCase()}
        </Typography>
        <input
          ref={inputRef}
          type="color"
          value={color}
          style={{ position: "absolute", opacity: 0, width: 0, height: 0, pointerEvents: "none" }}
          onChange={(e) => onChange(e.target.value)}
        />
      </Box>
    </Box>
  );
}

// ── StyleSection ──────────────────────────────────────────────────────────

function StyleSection({
  sectionLabel,
  setting,
  onChange,
  onOpenFontPicker,
}: {
  sectionLabel: string;
  setting: StyleSetting;
  onChange: (patch: Partial<StyleSetting>) => void;
  onOpenFontPicker: () => void;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Typography
        sx={{
          fontSize: 13,
          fontWeight: 700,
          color: "#1976d2",
          letterSpacing: 0.2,
          textTransform: "uppercase",
        }}
      >
        {sectionLabel}
      </Typography>

      {/* 폰트 */}
      <Box>
        <Typography sx={{ fontSize: 12, color: "#666", mb: 0.5 }}>폰트</Typography>
        <Box
          onClick={onOpenFontPicker}
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            border: "1.5px solid #e3e6ef",
            borderRadius: "7px",
            px: 1.5,
            py: 0.75,
            cursor: "pointer",
            bgcolor: "#fff",
            "&:hover": { borderColor: "#1976d2", boxShadow: "0 0 0 2px rgba(25,118,210,0.12)" },
            transition: "all 0.15s",
          }}
        >
          <Typography
            sx={{
              fontFamily: `'${setting.font_family}', sans-serif`,
              fontSize: 14,
              color: "#222",
              flex: 1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {setting.font_family}
          </Typography>
          <Typography sx={{ fontSize: 16, color: "#666", ml: 1, flexShrink: 0 }}>↗</Typography>
        </Box>
      </Box>

      {/* 크기 */}
      <Box>
        <Typography sx={{ fontSize: 12, color: "#666", mb: 0.5 }}>크기</Typography>
        <ToggleButtonGroup
          value={setting.font_size}
          exclusive
          onChange={(_, v) => { if (v) onChange({ font_size: v as "S" | "M" | "L" }); }}
          size="small"
          sx={{ width: "100%" }}
        >
          {(["S", "M", "L"] as const).map((sz) => (
            <ToggleButton
              key={sz}
              value={sz}
              sx={{
                flex: 1,
                fontSize: 13,
                fontWeight: 600,
                border: "1.5px solid #e3e6ef !important",
                borderRadius: "7px !important",
                mx: 0.25,
                "&.Mui-selected": {
                  bgcolor: "#1976d2 !important",
                  color: "#fff !important",
                  borderColor: "#1976d2 !important",
                },
                "&:hover": { borderColor: "#1976d2 !important" },
              }}
            >
              {sz === "S" ? "S 작게" : sz === "M" ? "M 보통" : "L 크게"}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {/* 색상 */}
      <ColorSwatch
        label="색상"
        color={setting.fill_color}
        onChange={(hex) => onChange({ fill_color: hex })}
      />
    </Box>
  );
}

// ── Preview9x16 ───────────────────────────────────────────────────────────

function Preview9x16({ settings }: { settings: SubtitleSettings }) {
  const titlePx = SIZE_PX[settings.title.font_size].title;
  const subtitlePx = SIZE_PX[settings.subtitle.font_size].subtitle;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        position: "sticky",
        top: 80,
      }}
    >
      <Typography
        sx={{ fontSize: 12, color: "#666", fontWeight: 600, mb: 1 }}
      >
        미리보기
      </Typography>

      {/* 9:16 frame */}
      <Box
        sx={{
          width: 240,
          height: 426,
          border: "2px solid #dde1ea",
          borderRadius: "12px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          bgcolor: "#4a4a4a",
          position: "relative",
        }}
      >
        {/* 미리보기 레이블 pill */}
        <Box
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
            bgcolor: "#888",
            color: "#fff",
            fontSize: 10,
            px: 1,
            py: 0.25,
            borderRadius: 999,
            zIndex: 2,
          }}
        >
          미리보기
        </Box>

        {/* 상단: 제목 존 */}
        <Box
          sx={{
            bgcolor: "rgba(0,0,0,0.40)",
            px: 1.5,
            py: 1,
            minHeight: "20%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography
            sx={{
              fontFamily: `'${settings.title.font_family}', sans-serif`,
              fontSize: titlePx,
              color: settings.title.fill_color,
              textAlign: "center",
              wordBreak: "keep-all",
              lineHeight: 1.3,
            }}
          >
            양재역 맛집 소개
          </Typography>
        </Box>

        {/* 중앙: 이미지 placeholder */}
        <Box
          sx={{
            flex: 1,
            bgcolor: "#b0b8c4",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 0.5,
          }}
        >
          <Typography sx={{ fontSize: 20, color: "#888" }}>📷</Typography>
          <Typography
            sx={{
              fontSize: 10,
              color: "#666",
              textAlign: "center",
              px: 1,
              lineHeight: 1.4,
            }}
          >
            이미지를 선택하면
            <br />
            여기에 반영됩니다
          </Typography>
        </Box>

        {/* 하단: 자막 존 */}
        <Box
          sx={{
            bgcolor: "rgba(0,0,0,0.40)",
            px: 1.5,
            py: 1,
            minHeight: "20%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography
            sx={{
              fontFamily: `'${settings.subtitle.font_family}', sans-serif`,
              fontSize: subtitlePx,
              color: settings.subtitle.fill_color,
              textAlign: "center",
              wordBreak: "keep-all",
              lineHeight: 1.3,
            }}
          >
            양계옥 최고 맛집 소개합니다.
          </Typography>
        </Box>
      </Box>

      {/* 미리보기 한계 안내 */}
      <Typography
        sx={{ fontSize: 11, color: "#888", mt: 1, textAlign: "center", maxWidth: 240 }}
      >
        실제 영상과 유사한 미리보기입니다.
        <br />
        렌더링 결과는 차이가 있을 수 있어요.
      </Typography>
    </Box>
  );
}

// ── TemplateChip ──────────────────────────────────────────────────────────

function TemplateChip({
  template,
  selected,
  onClick,
}: {
  template: SubtitleTemplate;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <Box
      onClick={onClick}
      sx={{
        px: 1.5,
        py: 0.6,
        borderRadius: 999,
        border: selected ? "1.5px solid #1976d2" : "1.5px solid #e3e6ef",
        bgcolor: selected ? "#1976d2" : "#fff",
        color: selected ? "#fff" : "#444",
        fontSize: 13,
        fontWeight: selected ? 700 : 500,
        cursor: "pointer",
        whiteSpace: "nowrap",
        userSelect: "none",
        transition: "all 0.15s",
        "&:hover": { borderColor: "#1976d2" },
      }}
    >
      {template.name || "이름 없는 템플릿"}
    </Box>
  );
}

// ── SubtitleStyleEditor (Main) ────────────────────────────────────────────

interface SubtitleStyleEditorProps {
  onSettingsChange: (settings: SubtitleSettings) => void;
}

type NameDialogMode = "create" | "rename" | null;
type ActionKind = "save" | "create" | "rename" | "delete" | null;

export default function SubtitleStyleEditor({ onSettingsChange }: SubtitleStyleEditorProps) {
  const [expanded, setExpanded] = useState(false);

  // 템플릿 목록 + 현재 선택된 템플릿
  const [templates, setTemplates] = useState<SubtitleTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  // 편집 컨트롤(제목/자막)에 반영되는 현재 편집 값 — 선택된 템플릿 값으로 초기화되고,
  // 사용자가 폰트/크기/색을 바꾸면 여기만 바뀐다 (명시적으로 저장하기 전까지 서버 반영 안 됨)
  const [settings, setSettings] = useState<SubtitleSettings>(DEFAULT_SETTINGS);

  const [fonts, setFonts] = useState<FontItem[]>([]);
  const [fontsLoading, setFontsLoading] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<"title" | "subtitle">("title");

  const [nameDialogMode, setNameDialogMode] = useState<NameDialogMode>(null);
  const [nameInput, setNameInput] = useState("");
  const [deleteConfirming, setDeleteConfirming] = useState(false);
  const [actionLoading, setActionLoading] = useState<ActionKind>(null);

  const [toast, setToast] = useState<{ open: boolean; message: string; severity: "success" | "error" }>({
    open: false,
    message: "",
    severity: "success",
  });

  const showToast = useCallback((message: string, severity: "success" | "error" = "success") => {
    setToast({ open: true, message, severity });
  }, []);

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId) ?? null;
  const baselineSettings: SubtitleSettings = selectedTemplate
    ? { title: selectedTemplate.title, subtitle: selectedTemplate.subtitle }
    : DEFAULT_SETTINGS;
  const hasChanged = !isSameSettings(settings, baselineSettings);

  // Load templates on mount (헤더의 미니 칩 + generate-video 초기값이 펼치기 전에도 맞도록)
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setTemplatesLoading(true);
      try {
        const res = await authFetch(TEMPLATES_URL);
        if (!res.ok) {
          if (!cancelled) onSettingsChange(DEFAULT_SETTINGS);
          return;
        }
        const data = await res.json();
        if (cancelled) return;
        const rawList = Array.isArray(data?.templates) ? data.templates : [];
        const list = rawList
          .map((t: unknown) => normalizeTemplate(t))
          .filter((t: SubtitleTemplate | null): t is SubtitleTemplate => t !== null);
        setTemplates(list);
        if (list.length > 0) {
          setSelectedTemplateId(list[0].id);
          const loaded: SubtitleSettings = { title: list[0].title, subtitle: list[0].subtitle };
          setSettings(loaded);
          onSettingsChange(loaded);
        } else {
          onSettingsChange(DEFAULT_SETTINGS);
        }
      } catch {
        // 네트워크 오류 등 — 기본값으로 폴백, generate-video는 그대로 동작
        if (!cancelled) onSettingsChange(DEFAULT_SETTINGS);
      } finally {
        if (!cancelled) setTemplatesLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load fonts when picker is first opened
  const loadFonts = useCallback(async () => {
    if (fonts.length > 0) return;
    setFontsLoading(true);
    try {
      const res = await authFetch(`${API_BASE_URL}/api/blog/fonts`);
      if (!res.ok) throw new Error("fonts API failed");
      const data = await res.json();
      if (Array.isArray(data.fonts)) {
        setFonts(data.fonts);
      }
    } catch {
      // fallback: show empty list; user can still use font name entry
    } finally {
      setFontsLoading(false);
    }
  }, [fonts.length]);

  const updateSection = useCallback(
    (section: "title" | "subtitle", patch: Partial<StyleSetting>) => {
      setSettings((prev) => {
        const next = {
          ...prev,
          [section]: { ...prev[section], ...patch },
        };
        onSettingsChange(next);
        return next;
      });
    },
    [onSettingsChange]
  );

  const handleRevert = () => {
    setSettings(baselineSettings);
    onSettingsChange(baselineSettings);
  };

  const handleOpenPicker = (target: "title" | "subtitle") => {
    setPickerTarget(target);
    setPickerOpen(true);
    loadFonts();
  };

  const handleFontSelect = (fontFamily: string) => {
    updateSection(pickerTarget, { font_family: fontFamily });
    setPickerOpen(false);
  };

  // ── 템플릿 선택 ──────────────────────────────────────────────────────────

  const handleSelectTemplate = (template: SubtitleTemplate) => {
    setSelectedTemplateId(template.id);
    const loaded: SubtitleSettings = { title: template.title, subtitle: template.subtitle };
    setSettings(loaded);
    onSettingsChange(loaded);
    setNameDialogMode(null);
    setDeleteConfirming(false);
  };

  // ── 액션: 현재 편집값 저장 (선택된 템플릿에 PUT) ────────────────────────

  const handleSaveCurrent = async () => {
    if (!selectedTemplateId) return;
    setActionLoading("save");
    try {
      const res = await authFetch(`${TEMPLATES_URL}/${selectedTemplateId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: settings.title, subtitle: settings.subtitle }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => null);
        const updated = extractTemplate(data);
        setTemplates((prev) =>
          prev.map((t) =>
            t.id === selectedTemplateId
              ? updated ?? { ...t, title: settings.title, subtitle: settings.subtitle }
              : t
          )
        );
        showToast("저장했어요");
      } else {
        const data = await res.json().catch(() => null);
        showToast(extractErrorMessage(data, "저장하지 못했어요. 다시 시도해 주세요."), "error");
      }
    } catch {
      showToast("저장하지 못했어요. 다시 시도해 주세요.", "error");
    } finally {
      setActionLoading(null);
    }
  };

  // ── 액션: 새 템플릿으로 저장 (POST) ──────────────────────────────────────

  const openCreate = () => {
    if (templates.length >= MAX_TEMPLATES) return;
    setDeleteConfirming(false);
    setNameDialogMode("create");
    setNameInput(`템플릿 ${templates.length + 1}`);
  };

  const handleCreateConfirm = async () => {
    const name = nameInput.trim();
    if (!name) return;
    setActionLoading("create");
    try {
      const res = await authFetch(TEMPLATES_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, title: settings.title, subtitle: settings.subtitle }),
      });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        const created =
          extractTemplate(data) ??
          ({ id: `local-${Date.now()}`, name, title: settings.title, subtitle: settings.subtitle } as SubtitleTemplate);
        setTemplates((prev) => [...prev, created]);
        setSelectedTemplateId(created.id);
        setNameDialogMode(null);
        showToast("새 템플릿으로 저장했어요");
      } else {
        showToast(extractErrorMessage(data, "저장하지 못했어요. 다시 시도해 주세요."), "error");
      }
    } catch {
      showToast("저장하지 못했어요. 다시 시도해 주세요.", "error");
    } finally {
      setActionLoading(null);
    }
  };

  // ── 액션: 이름 변경 (PUT name) ───────────────────────────────────────────

  const openRename = () => {
    if (!selectedTemplate) return;
    setDeleteConfirming(false);
    setNameDialogMode("rename");
    setNameInput(selectedTemplate.name);
  };

  const handleRenameConfirm = async () => {
    if (!selectedTemplateId) return;
    const name = nameInput.trim();
    if (!name) return;
    setActionLoading("rename");
    try {
      const res = await authFetch(`${TEMPLATES_URL}/${selectedTemplateId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (res.ok) {
        setTemplates((prev) => prev.map((t) => (t.id === selectedTemplateId ? { ...t, name } : t)));
        setNameDialogMode(null);
        showToast("이름을 변경했어요");
      } else {
        const data = await res.json().catch(() => null);
        showToast(extractErrorMessage(data, "이름을 변경하지 못했어요. 다시 시도해 주세요."), "error");
      }
    } catch {
      showToast("이름을 변경하지 못했어요. 다시 시도해 주세요.", "error");
    } finally {
      setActionLoading(null);
    }
  };

  // ── 액션: 삭제 (DELETE, 최소 1개 유지) ───────────────────────────────────

  const handleDelete = async () => {
    if (!selectedTemplateId || templates.length <= 1) return;
    setActionLoading("delete");
    try {
      const res = await authFetch(`${TEMPLATES_URL}/${selectedTemplateId}`, { method: "DELETE" });
      if (res.ok) {
        const remaining = templates.filter((t) => t.id !== selectedTemplateId);
        setTemplates(remaining);
        setDeleteConfirming(false);
        const next = remaining[0] ?? null;
        setSelectedTemplateId(next ? next.id : null);
        const loaded: SubtitleSettings = next
          ? { title: next.title, subtitle: next.subtitle }
          : DEFAULT_SETTINGS;
        setSettings(loaded);
        onSettingsChange(loaded);
        showToast("삭제했어요");
      } else {
        const data = await res.json().catch(() => null);
        showToast(extractErrorMessage(data, "삭제하지 못했어요. 다시 시도해 주세요."), "error");
      }
    } catch {
      showToast("삭제하지 못했어요. 다시 시도해 주세요.", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const cancelNameDialog = () => {
    setNameDialogMode(null);
    setNameInput("");
  };

  return (
    <>
      {/* Collapse card */}
      <Box
        sx={{
          width: "100%",
          maxWidth: 1200,
          mx: "auto",
          mb: 2,
          borderRadius: expanded ? "12px 12px 0 0" : "12px",
          border: "1.5px solid #f2f4f8",
          bgcolor: "#fafbfc",
          boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
          overflow: "hidden",
        }}
      >
        {/* Header (always visible) */}
        <Box
          onClick={() => setExpanded((v) => !v)}
          sx={{
            display: "flex",
            alignItems: "center",
            px: 3,
            height: 56,
            cursor: "pointer",
            userSelect: "none",
            gap: 1.5,
            "&:hover": { bgcolor: "#f0f2f5" },
            transition: "background 0.15s",
          }}
        >
          {/* Label + badge */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexShrink: 0 }}>
            <Typography sx={{ fontSize: 15, fontWeight: 700, color: "#222" }}>
              자막 스타일 설정
            </Typography>
            <Box
              sx={{
                bgcolor: "#f0f4f8",
                border: "1px solid #dde1ea",
                borderRadius: 999,
                px: 1,
                py: 0.125,
              }}
            >
              <Typography sx={{ fontSize: 11, color: "#888", lineHeight: 1.4 }}>
                선택 사항
              </Typography>
            </Box>
          </Box>

          {/* Mini chips */}
          <Box sx={{ display: "flex", gap: 1, flex: 1, justifyContent: "center" }}>
            <MiniChip
              label="제목"
              fontFamily={settings.title.font_family}
              color={settings.title.fill_color}
            />
            <MiniChip
              label="자막"
              fontFamily={settings.subtitle.font_family}
              color={settings.subtitle.fill_color}
            />
          </Box>

          {/* Toggle icon */}
          {expanded ? (
            <KeyboardArrowUpIcon sx={{ color: "#666", fontSize: 20, flexShrink: 0 }} />
          ) : (
            <KeyboardArrowDownIcon sx={{ color: "#666", fontSize: 20, flexShrink: 0 }} />
          )}
        </Box>

        {/* Expanded content */}
        <Collapse in={expanded} timeout={250}>
          {/* 스타일 템플릿 영역 */}
          <Box sx={{ borderTop: "1.5px solid #f2f4f8", px: 3, py: 2.5 }}>
            <Typography
              sx={{
                fontSize: 13,
                fontWeight: 700,
                color: "#1976d2",
                letterSpacing: 0.2,
                textTransform: "uppercase",
                mb: 1,
              }}
            >
              스타일 템플릿
            </Typography>

            {templatesLoading ? (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.5 }}>
                <CircularProgress size={16} />
                <Typography sx={{ fontSize: 12, color: "#888" }}>
                  템플릿을 불러오는 중이에요
                </Typography>
              </Box>
            ) : templates.length === 0 ? (
              <Typography sx={{ fontSize: 12, color: "#888" }}>
                아직 저장된 템플릿이 없어요. 편집 후 &apos;새 템플릿으로 저장&apos;을 눌러보세요.
              </Typography>
            ) : (
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                {templates.map((t) => (
                  <TemplateChip
                    key={t.id}
                    template={t}
                    selected={t.id === selectedTemplateId}
                    onClick={() => handleSelectTemplate(t)}
                  />
                ))}
              </Box>
            )}

            {/* 액션 버튼 또는 이름 입력/삭제 확인 폼 */}
            {nameDialogMode ? (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1.5, flexWrap: "wrap" }}>
                <TextField
                  size="small"
                  autoFocus
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  placeholder="템플릿 이름"
                  inputProps={{ maxLength: 20 }}
                  sx={{ maxWidth: 220 }}
                />
                <Button
                  size="small"
                  variant="contained"
                  disabled={!nameInput.trim() || actionLoading !== null}
                  onClick={nameDialogMode === "create" ? handleCreateConfirm : handleRenameConfirm}
                >
                  {actionLoading === "create" || actionLoading === "rename" ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    "확인"
                  )}
                </Button>
                <Button size="small" onClick={cancelNameDialog} disabled={actionLoading !== null}>
                  취소
                </Button>
              </Box>
            ) : deleteConfirming ? (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1.5, flexWrap: "wrap" }}>
                <Typography sx={{ fontSize: 12.5, color: "#d32f2f" }}>
                  &apos;{selectedTemplate?.name}&apos; 템플릿을 삭제할까요?
                </Typography>
                <Button
                  size="small"
                  variant="contained"
                  color="error"
                  onClick={handleDelete}
                  disabled={actionLoading !== null}
                >
                  {actionLoading === "delete" ? <CircularProgress size={16} color="inherit" /> : "삭제"}
                </Button>
                <Button size="small" onClick={() => setDeleteConfirming(false)} disabled={actionLoading !== null}>
                  취소
                </Button>
              </Box>
            ) : (
              <>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1.5 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={!selectedTemplateId || !hasChanged || actionLoading !== null}
                    onClick={handleSaveCurrent}
                  >
                    {actionLoading === "save" ? <CircularProgress size={16} /> : "현재 편집값 저장"}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={templates.length >= MAX_TEMPLATES || actionLoading !== null}
                    onClick={openCreate}
                  >
                    새 템플릿으로 저장
                  </Button>
                  <Button
                    size="small"
                    variant="text"
                    disabled={!selectedTemplateId || actionLoading !== null}
                    onClick={openRename}
                  >
                    이름 변경
                  </Button>
                  <Button
                    size="small"
                    variant="text"
                    color="error"
                    disabled={!selectedTemplateId || templates.length <= 1 || actionLoading !== null}
                    onClick={() => setDeleteConfirming(true)}
                  >
                    삭제
                  </Button>
                </Box>
                {templates.length >= MAX_TEMPLATES && (
                  <Typography sx={{ fontSize: 11, color: "#d32f2f", mt: 0.5 }}>
                    템플릿은 최대 5개까지 저장할 수 있어요
                  </Typography>
                )}
              </>
            )}
          </Box>

          <Box
            sx={{
              borderTop: "1.5px solid #f2f4f8",
              display: "flex",
              flexDirection: "row",
              gap: 0,
            }}
          >
            {/* Left: 6 controls */}
            <Box
              sx={{
                flex: "0 0 45%",
                minWidth: 360,
                p: 3,
                display: "flex",
                flexDirection: "column",
                gap: 0,
              }}
            >
              {/* 제목 자막 section */}
              <StyleSection
                sectionLabel="제목 자막"
                setting={settings.title}
                onChange={(patch) => updateSection("title", patch)}
                onOpenFontPicker={() => handleOpenPicker("title")}
              />

              {/* Divider */}
              <Box sx={{ borderTop: "1px solid #e3e6ef", my: 3 }} />

              {/* 본문 자막 section */}
              <StyleSection
                sectionLabel="본문 자막"
                setting={settings.subtitle}
                onChange={(patch) => updateSection("subtitle", patch)}
                onOpenFontPicker={() => handleOpenPicker("subtitle")}
              />

              {/* Revert button — 선택된 템플릿(또는 기본값)으로 되돌리기 */}
              {hasChanged && (
                <Box sx={{ mt: 3 }}>
                  <Typography
                    onClick={handleRevert}
                    sx={{
                      fontSize: 13,
                      color: "text.secondary",
                      cursor: "pointer",
                      textDecoration: "underline",
                      display: "inline",
                      "&:hover": { color: "#1976d2" },
                    }}
                  >
                    변경 내용 되돌리기
                  </Typography>
                </Box>
              )}
            </Box>

            {/* Divider vertical */}
            <Box sx={{ width: "1px", bgcolor: "#e3e6ef", my: 3 }} />

            {/* Right: 9:16 preview */}
            <Box sx={{ flex: 1, p: 3, display: "flex", justifyContent: "center" }}>
              <Preview9x16 settings={settings} />
            </Box>
          </Box>
        </Collapse>
      </Box>

      {/* FontPickerModal */}
      <FontPickerModal
        open={pickerOpen}
        fonts={fonts}
        loading={fontsLoading}
        selectedFont={pickerTarget === "title" ? settings.title.font_family : settings.subtitle.font_family}
        onSelect={handleFontSelect}
        onClose={() => setPickerOpen(false)}
      />

      {/* Action toast */}
      <Snackbar
        open={toast.open}
        autoHideDuration={2000}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => setToast((prev) => ({ ...prev, open: false }))}
          severity={toast.severity}
          sx={{ width: "100%" }}
        >
          {toast.message}
        </Alert>
      </Snackbar>

      {/* Load Google Fonts for default fonts */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;700&display=swap');
      `}</style>

      {/* Dynamically load selected fonts */}
      {[settings.title.font_family, settings.subtitle.font_family]
        .filter((f) => f !== "Black Han Sans" && f !== "Noto Sans KR")
        .map((f) => (
          <style key={f}>{`
            @import url('https://fonts.googleapis.com/css2?family=${encodeURIComponent(f).replace(/%20/g, "+")}:wght@400;700&display=swap');
          `}</style>
        ))}

    </>
  );
}
