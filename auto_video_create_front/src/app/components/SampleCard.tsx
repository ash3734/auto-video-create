"use client";

import { Box, Typography } from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";

// sprint-4: 컨셉 영상 샘플 4종. BE 응답(GET /api/blog/concept-samples) 스키마 — api-contract.md 확정
export interface ConceptSample {
  concept_sample_id: string;
  name: string;
  is_default: boolean;
  scene_count: number;
  hero_still_url: string | null;
  sample_video_url: string | null;
}

// 05-visual.md §4.2 팔레트(방향값) — 실제 결과물 색이 아니라 "카드 4장 구분용" placeholder.
// hero_still_url 확보 후에는 이 색조 자체가 폐기 대상(§0-1).
const SAMPLE_GRADIENTS: Record<string, string> = {
  sample_1: "linear-gradient(135deg, #90A4C0 0%, #64789C 100%)", // Cool Slate (기본)
  sample_2: "linear-gradient(135deg, #F0B268 0%, #D98A3D 100%)", // Warm Amber
  sample_3: "linear-gradient(135deg, #8FBF9F 0%, #5E9E76 100%)", // Sage Green
  sample_4: "linear-gradient(135deg, #B08FC7 0%, #8B63A8 100%)", // Muted Violet
};
const FALLBACK_GRADIENT = "linear-gradient(135deg, #c8d2e0 0%, #a9b4c6 100%)";

interface SampleCardProps {
  sample: ConceptSample;
  selected: boolean;
  disabled?: boolean;
  onSelect: () => void;
  onViewVideo: () => void;
}

export default function SampleCard({ sample, selected, disabled, onSelect, onViewVideo }: SampleCardProps) {
  const gradient = SAMPLE_GRADIENTS[sample.concept_sample_id] ?? FALLBACK_GRADIENT;

  const handleSelectKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect();
    }
  };

  return (
    <Box
      sx={{
        width: 124,
        flexShrink: 0,
        border: selected ? "2px solid #1976d2" : "1.5px solid #e3e6ef",
        borderRadius: "10px",
        p: 1,
        bgcolor: selected ? "rgba(25, 118, 210, 0.06)" : "#fff",
        position: "relative",
        textAlign: "center",
        opacity: disabled ? 0.5 : 1,
        transition: "border-color 0.15s, background-color 0.15s",
      }}
    >
      {selected && (
        <Box
          sx={{
            position: "absolute",
            top: -7,
            left: -7,
            width: 18,
            height: 18,
            borderRadius: "50%",
            bgcolor: "#1976d2",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 2,
          }}
        >
          <CheckIcon sx={{ fontSize: 12 }} />
        </Box>
      )}

      {/* 선택 hit-area — 대표 스틸 (05-visual.md §1.1 "대") */}
      <Box
        role="radio"
        aria-checked={selected}
        aria-label={`${sample.name}, ${sample.scene_count}장면 선택`}
        tabIndex={disabled ? -1 : 0}
        onClick={disabled ? undefined : onSelect}
        onKeyDown={handleSelectKeyDown}
        sx={{
          width: 96,
          height: 170,
          borderRadius: "6px",
          margin: "0 auto",
          position: "relative",
          overflow: "hidden",
          cursor: disabled ? "default" : "pointer",
          outline: "none",
          "&:hover": disabled ? {} : { boxShadow: "0 0 0 2px rgba(25,118,210,0.35)" },
          "&:focus-visible": { boxShadow: "0 0 0 2px #1976d2" },
        }}
      >
        {sample.hero_still_url ? (
          <Box
            component="img"
            src={sample.hero_still_url}
            alt={`${sample.name} 대표 장면`}
            sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        ) : (
          <>
            <Box sx={{ position: "absolute", inset: 0, background: gradient }} aria-hidden="true" />
            <Typography
              sx={{
                position: "absolute",
                bottom: 4,
                left: 0,
                width: "100%",
                textAlign: "center",
                fontSize: 8,
                color: "rgba(255,255,255,0.85)",
                letterSpacing: 0.3,
              }}
            >
              {sample.name} placeholder
            </Typography>
          </>
        )}
      </Box>

      <Typography sx={{ fontSize: 12, fontWeight: 700, mt: 1 }}>{sample.name}</Typography>
      <Box
        sx={{
          display: "inline-block",
          fontSize: 10,
          color: "#888",
          bgcolor: "#f0f4f8",
          borderRadius: 999,
          px: 1,
          py: "1px",
          mt: 0.5,
        }}
      >
        {sample.scene_count}장면
      </Box>

      {/* 조회(view) hit-area — 선택 hit-area와 물리적으로 분리(구분선 + ≥32px 밴드) */}
      <Box sx={{ mt: 1, pt: 0.75, borderTop: "1px dashed #e3e6ef" }}>
        <Box
          component="button"
          type="button"
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            onViewVideo();
          }}
          aria-label={`${sample.name} 영상 보기`}
          sx={{
            display: "block",
            width: "100%",
            minHeight: 32,
            fontSize: 11,
            fontWeight: 600,
            color: "#1976d2",
            bgcolor: "#eaf2fc",
            border: "1px solid #bcdcf7",
            borderRadius: "6px",
            py: 0.5,
            cursor: disabled ? "default" : "pointer",
            fontFamily: "inherit",
            "&:hover": disabled ? {} : { bgcolor: "#dcebfa" },
          }}
        >
          영상 보기
        </Box>
      </Box>
    </Box>
  );
}
