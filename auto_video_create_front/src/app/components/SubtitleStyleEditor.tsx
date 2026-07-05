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

interface FontItem {
  family: string;
  category: string;
  slug: string;
}

// ── Constants ──────────────────────────────────────────────────────────────

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

function authFetch(url: string, options: RequestInit = {}) {
  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  return fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), "X-USER-ID": userId ?? "" },
  });
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

// ── SubtitleStyleEditor (Main) ────────────────────────────────────────────

interface SubtitleStyleEditorProps {
  onSettingsChange: (settings: SubtitleSettings) => void;
}

export default function SubtitleStyleEditor({ onSettingsChange }: SubtitleStyleEditorProps) {
  const [expanded, setExpanded] = useState(false);
  const [settings, setSettings] = useState<SubtitleSettings>(DEFAULT_SETTINGS);
  const [fonts, setFonts] = useState<FontItem[]>([]);
  const [fontsLoading, setFontsLoading] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<"title" | "subtitle">("title");
  const [toastOpen, setToastOpen] = useState(false);
  const [hasChanged, setHasChanged] = useState(false);

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDefaultSettings = useCallback((s: SubtitleSettings) => {
    return (
      s.title.font_family === DEFAULT_SETTINGS.title.font_family &&
      s.title.font_size === DEFAULT_SETTINGS.title.font_size &&
      s.title.fill_color === DEFAULT_SETTINGS.title.fill_color &&
      s.subtitle.font_family === DEFAULT_SETTINGS.subtitle.font_family &&
      s.subtitle.font_size === DEFAULT_SETTINGS.subtitle.font_size &&
      s.subtitle.fill_color === DEFAULT_SETTINGS.subtitle.fill_color
    );
  }, []);

  // Load settings on mount
  useEffect(() => {
    const load = async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/blog/subtitle-settings`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.settings) {
          const loaded: SubtitleSettings = {
            title: {
              font_family: data.settings.title?.font_family ?? DEFAULT_SETTINGS.title.font_family,
              font_size: (data.settings.title?.font_size as "S" | "M" | "L") ?? "M",
              fill_color: data.settings.title?.fill_color ?? DEFAULT_SETTINGS.title.fill_color,
            },
            subtitle: {
              font_family: data.settings.subtitle?.font_family ?? DEFAULT_SETTINGS.subtitle.font_family,
              font_size: (data.settings.subtitle?.font_size as "S" | "M" | "L") ?? "M",
              fill_color: data.settings.subtitle?.fill_color ?? DEFAULT_SETTINGS.subtitle.fill_color,
            },
          };
          setSettings(loaded);
          onSettingsChange(loaded);
          setHasChanged(!isDefaultSettings(loaded));
        }
      } catch {
        // silently fall back to defaults
      }
    };
    load();
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

  const debouncedSave = useCallback((newSettings: SubtitleSettings) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/blog/subtitle-settings`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newSettings),
        });
        if (res.ok) setToastOpen(true);
      } catch {
        // ignore save errors silently
      }
    }, 500);
  }, []);

  const updateSection = useCallback(
    (section: "title" | "subtitle", patch: Partial<StyleSetting>) => {
      setSettings((prev) => {
        const next = {
          ...prev,
          [section]: { ...prev[section], ...patch },
        };
        onSettingsChange(next);
        setHasChanged(!isDefaultSettings(next));
        debouncedSave(next);
        return next;
      });
    },
    [onSettingsChange, isDefaultSettings, debouncedSave]
  );

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    onSettingsChange(DEFAULT_SETTINGS);
    setHasChanged(false);
    debouncedSave(DEFAULT_SETTINGS);
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

              {/* Reset button */}
              {hasChanged && (
                <Box sx={{ mt: 3 }}>
                  <Typography
                    onClick={handleReset}
                    sx={{
                      fontSize: 13,
                      color: "text.secondary",
                      cursor: "pointer",
                      textDecoration: "underline",
                      display: "inline",
                      "&:hover": { color: "#1976d2" },
                    }}
                  >
                    기본값으로 초기화
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

      {/* Save toast */}
      <Snackbar
        open={toastOpen}
        autoHideDuration={1500}
        onClose={() => setToastOpen(false)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => setToastOpen(false)}
          severity="success"
          sx={{ width: "100%" }}
        >
          저장됐어요
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
