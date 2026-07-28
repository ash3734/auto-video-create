"use client";

import { Box, Typography } from "@mui/material";
import SampleCard, { ConceptSample } from "./SampleCard";

interface SampleSelectorProps {
  samples: ConceptSample[];
  selectedId: string;
  disabled?: boolean;
  onSelect: (conceptSampleId: string) => void;
  onViewVideo: (sample: ConceptSample) => void;
}

// 04-ia.md §3 — "컨셉 샘플" 카드 4장, radiogroup, 샘플1 pre-selected.
// 목록이 아직 로드되지 않았으면 렌더링하지 않음(input 화면은 카드 없이도 기존과 동일하게 동작 — "무시하는 유저" 경로 A).
export default function SampleSelector({ samples, selectedId, disabled, onSelect, onViewVideo }: SampleSelectorProps) {
  if (samples.length === 0) return null;

  return (
    <Box sx={{ mb: 2.75 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 1, mb: 1.25 }}>
        <Typography sx={{ fontSize: 13, fontWeight: 700 }}>컨셉 샘플</Typography>
        <Box
          sx={{
            fontSize: 10,
            color: "#888",
            bgcolor: "#f0f4f8",
            border: "1px solid #e3e6ef",
            borderRadius: 999,
            px: 1,
            py: "2px",
            fontWeight: 500,
          }}
        >
          선택 사항
        </Box>
      </Box>
      <Typography sx={{ fontSize: 12, color: "#888", mb: 1.5 }}>
        영상 보기로 미리 확인할 수 있어요
      </Typography>
      <Box
        role="radiogroup"
        aria-label="컨셉 샘플 선택 (선택 사항)"
        sx={{ display: "flex", flexWrap: "nowrap", gap: 1.5, justifyContent: "center" }}
      >
        {samples.map((sample) => (
          <SampleCard
            key={sample.concept_sample_id}
            sample={sample}
            selected={sample.concept_sample_id === selectedId}
            disabled={disabled}
            onSelect={() => onSelect(sample.concept_sample_id)}
            onViewVideo={() => onViewVideo(sample)}
          />
        ))}
      </Box>
    </Box>
  );
}
