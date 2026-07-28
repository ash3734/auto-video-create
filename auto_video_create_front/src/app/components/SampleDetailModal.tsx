"use client";

import { Box, Dialog, IconButton, Typography } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { ConceptSample } from "./SampleCard";

interface SampleDetailModalProps {
  sample: ConceptSample | null;
  onClose: () => void;
}

// 04-ia.md §4 / 05-visual.md §1.2 — input SampleCard "영상 보기" 버튼 전용 트리거.
// select 단계에는 이 모달을 여는 수단이 없다(D9/D10, 04-ia.md).
// X / ESC / 배경클릭 전부 동일하게 모달만 닫고, 선택 상태(concept_sample_id)는 절대 변경하지 않는다.
export default function SampleDetailModal({ sample, onClose }: SampleDetailModalProps) {
  const open = !!sample;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      aria-label={sample ? `${sample.name} 영상 보기` : undefined}
      PaperProps={{
        sx: { bgcolor: "transparent", boxShadow: "none", borderRadius: 0, m: 0 },
      }}
      BackdropProps={{
        sx: { bgcolor: "rgba(0,0,0,0.55)" },
      }}
    >
      {sample && (
        <Box
          sx={{
            width: 240,
            height: 427,
            bgcolor: "#0a0a0a",
            borderRadius: "16px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            boxShadow: "0 16px 40px rgba(0,0,0,0.5)",
            overflow: "hidden",
          }}
        >
          <IconButton
            onClick={onClose}
            aria-label="닫기"
            size="small"
            sx={{
              position: "absolute",
              top: 8,
              right: 8,
              color: "rgba(255,255,255,0.55)",
              zIndex: 2,
              "&:hover": { color: "rgba(255,255,255,0.85)" },
            }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>

          {sample.sample_video_url ? (
            <video
              src={sample.sample_video_url}
              controls
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <>
              <Box
                aria-hidden="true"
                sx={{
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  border: "2px solid rgba(255,255,255,0.25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "rgba(255,255,255,0.3)",
                }}
              >
                <PlayArrowIcon sx={{ fontSize: 26 }} />
              </Box>
              <Typography sx={{ mt: 2, color: "rgba(255,255,255,0.5)", fontSize: 12 }}>
                샘플 영상 준비 중입니다
              </Typography>
            </>
          )}
        </Box>
      )}
    </Dialog>
  );
}
