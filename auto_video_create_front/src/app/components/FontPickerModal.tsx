"use client";

import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import {
  Box,
  Typography,
  Dialog,
  DialogContent,
  IconButton,
  CircularProgress,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import CheckIcon from "@mui/icons-material/Check";
import SearchIcon from "@mui/icons-material/Search";
import { FixedSizeList, ListChildComponentProps } from "react-window";

// ── Types ──────────────────────────────────────────────────────────────────

interface FontItem {
  family: string;
  category: string;
  slug: string;
}

type TabValue = "All" | "serif" | "sans-serif" | "display" | "handwriting" | "monospace";

const TABS: { label: string; value: TabValue }[] = [
  { label: "All", value: "All" },
  { label: "Serif", value: "serif" },
  { label: "Sans serif", value: "sans-serif" },
  { label: "Display", value: "display" },
  { label: "Handwriting", value: "handwriting" },
  { label: "Monospace", value: "monospace" },
];

const ITEM_HEIGHT = 56;
const MODAL_LIST_HEIGHT = 340;

// ── FontRow ────────────────────────────────────────────────────────────────

interface FontRowProps {
  font: FontItem;
  isSelected: boolean;
  onSelect: (family: string) => void;
  onFontLoad: (family: string) => void;
}

const FontRow = React.memo(function FontRow({
  font,
  isSelected,
  onSelect,
  onFontLoad,
}: FontRowProps) {
  const [imgError, setImgError] = useState(false);
  const thumbnailUrl = `https://creatomate.com/files/fonts/${font.slug}.png`;

  // Trigger font load when row becomes visible
  useEffect(() => {
    onFontLoad(font.family);
  }, [font.family, onFontLoad]);

  return (
    <Box
      onClick={() => onSelect(font.family)}
      sx={{
        display: "flex",
        alignItems: "center",
        height: ITEM_HEIGHT,
        px: 2.5,
        cursor: "pointer",
        bgcolor: isSelected ? "rgba(25,118,210,0.07)" : "transparent",
        "&:hover": { bgcolor: isSelected ? "rgba(25,118,210,0.1)" : "#f5f7fa" },
        transition: "background 0.12s",
        gap: 2,
        userSelect: "none",
      }}
    >
      {/* Thumbnail or font text */}
      {!imgError ? (
        <Box
          sx={{
            width: 120,
            height: 36,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            overflow: "hidden",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={thumbnailUrl}
            alt={font.family}
            onError={() => setImgError(true)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              objectPosition: "left center",
            }}
            loading="lazy"
          />
        </Box>
      ) : null}

      {/* Font name */}
      <Typography
        sx={{
          flex: 1,
          fontSize: 14,
          color: "#222",
          fontFamily: `'${font.family}', sans-serif`,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {font.family}
      </Typography>

      {/* Check */}
      {isSelected && (
        <CheckIcon sx={{ color: "#1976d2", fontSize: 18, flexShrink: 0 }} />
      )}
    </Box>
  );
});

// ── Main Modal ─────────────────────────────────────────────────────────────

interface FontPickerModalProps {
  open: boolean;
  fonts: FontItem[];
  loading: boolean;
  selectedFont: string;
  onSelect: (fontFamily: string) => void;
  onClose: () => void;
}

export default function FontPickerModal({
  open,
  fonts,
  loading,
  selectedFont,
  onSelect,
  onClose,
}: FontPickerModalProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<TabValue>("All");
  const listRef = useRef<FixedSizeList>(null);
  const loadedFontsRef = useRef<Set<string>>(new Set());

  // Reset search/tab when modal opens
  useEffect(() => {
    if (open) {
      setSearchQuery("");
      setActiveTab("All");
    }
  }, [open]);

  // Scroll to selected item when fonts load or modal opens
  useEffect(() => {
    if (open && fonts.length > 0 && listRef.current) {
      const idx = fonts.findIndex((f) => f.family === selectedFont);
      if (idx !== -1) {
        listRef.current.scrollToItem(idx, "smart");
      }
    }
  }, [open, fonts, selectedFont]);

  // Filter fonts based on search + tab
  const filteredFonts = useMemo(() => {
    let list = fonts;
    if (activeTab !== "All") {
      list = list.filter((f) => f.category === activeTab);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter((f) => f.family.toLowerCase().includes(q));
    }
    return list;
  }, [fonts, activeTab, searchQuery]);

  // Reset scroll on filter change
  useEffect(() => {
    listRef.current?.scrollTo(0);
  }, [searchQuery, activeTab]);

  const handleFontLoad = useCallback((family: string) => {
    if (loadedFontsRef.current.has(family)) return;
    loadedFontsRef.current.add(family);
    // Dynamically inject font-face for this family
    const linkId = `gfont-${family.replace(/\s+/g, "-").toLowerCase()}`;
    if (!document.getElementById(linkId)) {
      const link = document.createElement("link");
      link.id = linkId;
      link.rel = "stylesheet";
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family).replace(/%20/g, "+")}:wght@400;700&display=swap`;
      document.head.appendChild(link);
    }
  }, []);

  const Row = useCallback(
    ({ index, style }: ListChildComponentProps) => {
      const font = filteredFonts[index];
      return (
        <div style={style}>
          <FontRow
            font={font}
            isSelected={font.family === selectedFont}
            onSelect={onSelect}
            onFontLoad={handleFontLoad}
          />
        </div>
      );
    },
    [filteredFonts, selectedFont, onSelect, handleFontLoad]
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      PaperProps={{
        sx: {
          width: 560,
          maxHeight: "70vh",
          borderRadius: "16px",
          boxShadow: "0 16px 48px rgba(0,0,0,0.20)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        },
      }}
      sx={{
        "& .MuiBackdrop-root": { bgcolor: "rgba(0,0,0,0.45)" },
        zIndex: 300,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2.5,
          height: 56,
          borderBottom: "1px solid #f2f4f8",
          flexShrink: 0,
        }}
      >
        <Typography sx={{ fontSize: 16, fontWeight: 700, color: "#222" }}>
          폰트 선택
        </Typography>
        <IconButton size="small" onClick={onClose} sx={{ color: "#666" }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <DialogContent
        sx={{ p: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}
      >
        {/* Search */}
        <Box sx={{ px: 2.5, pt: 2, pb: 1.5 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              border: "1.5px solid #e3e6ef",
              borderRadius: "8px",
              px: 1.5,
              height: 44,
              gap: 1,
              "&:focus-within": {
                borderColor: "#1976d2",
                boxShadow: "0 0 0 2px rgba(25,118,210,0.12)",
              },
            }}
          >
            <SearchIcon sx={{ color: "#999", fontSize: 18 }} />
            <input
              type="text"
              placeholder="폰트 검색"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontSize: 14,
                color: "#222",
              }}
            />
            {searchQuery && (
              <Box
                onClick={() => setSearchQuery("")}
                sx={{ cursor: "pointer", color: "#999", fontSize: 16, lineHeight: 1 }}
              >
                ×
              </Box>
            )}
          </Box>
        </Box>

        {/* Category tabs */}
        <Box
          sx={{
            display: "flex",
            borderBottom: "1px solid #f2f4f8",
            px: 1,
            flexShrink: 0,
            overflowX: "auto",
          }}
        >
          {TABS.map((tab) => (
            <Box
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              sx={{
                px: 1.5,
                height: 40,
                display: "flex",
                alignItems: "center",
                cursor: "pointer",
                borderBottom:
                  activeTab === tab.value ? "2px solid #1976d2" : "2px solid transparent",
                color: activeTab === tab.value ? "#1976d2" : "#666",
                fontWeight: activeTab === tab.value ? 700 : 400,
                fontSize: 13,
                whiteSpace: "nowrap",
                transition: "color 0.15s",
                userSelect: "none",
              }}
            >
              {tab.label}
            </Box>
          ))}
        </Box>

        {/* Font list */}
        <Box sx={{ flex: 1, overflow: "hidden" }}>
          {loading ? (
            <Box
              sx={{
                height: MODAL_LIST_HEIGHT,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <CircularProgress size={28} />
            </Box>
          ) : filteredFonts.length === 0 ? (
            <Box
              sx={{
                height: MODAL_LIST_HEIGHT,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Typography sx={{ color: "#999", fontSize: 14 }}>
                검색 결과가 없습니다.
              </Typography>
            </Box>
          ) : (
            <FixedSizeList
              ref={listRef}
              height={MODAL_LIST_HEIGHT}
              width="100%"
              itemCount={filteredFonts.length}
              itemSize={ITEM_HEIGHT}
            >
              {Row}
            </FixedSizeList>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
