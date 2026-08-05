"use client";
import { Box, Button, TextField, Typography, CircularProgress, LinearProgress, Snackbar, Alert, Paper, Dialog, IconButton, ImageListItem } from "@mui/material";
import { useState, useEffect } from "react";
import Image from "next/image";
import { useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import Link from "next/link";
import Confetti from 'react-confetti';
import CloseIcon from '@mui/icons-material/Close';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import EditIcon from '@mui/icons-material/Edit';
import AuthGuard from "../components/AuthGuard";
import LogoutButton from "../components/LogoutButton";
import ChangePasswordButton from "../components/ChangePasswordButton";
import SubtitleStyleEditor, { SubtitleSettings } from "./components/SubtitleStyleEditor";

interface MediaList {
  images: string[];
  videos: string[];
  scripts?: { script: string }[] | string[];
  // cycle-2: 일반 블로그 지원 — BE 가 응답에 포함. FE 는 default_slot_count 만 사용.
  category?: 'restaurant' | 'general';
  platform?: 'naver' | 'tistory' | 'brunch';
  default_slot_count?: number;
}

// 섹션별 미디어 타입과 선택된 URL을 관리하는 인터페이스
interface SectionMedia {
  type: 'image' | 'video' | 'default';
  url: string | null;
  // cycle-2: type='default' 일 때 BE 가 generate-video 시점에 AI 배경 생성
  isDefaultBackground?: boolean;
}

// VOC-2: extract-all 응답의 suggested_sections 원소 타입 (BE 계약)
type SuggestedSection = { type: 'image'; url: string } | { type: 'default'; url: null };

// VOC-2: BE 응답의 suggested_sections 를 방어적으로 파싱한다.
// 형식이 계약과 조금이라도 다르면(구버전 BE 포함) null 을 반환해 기존 동작(빈 슬롯)으로 폴백한다.
function parseSuggestedSections(raw: unknown, expectedLength: number): SuggestedSection[] | null {
  if (!Array.isArray(raw) || expectedLength <= 0 || raw.length !== expectedLength) return null;
  const parsed: SuggestedSection[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") return null;
    const { type, url } = item as { type?: unknown; url?: unknown };
    if (type === "image" && typeof url === "string" && url.length > 0) {
      parsed.push({ type: "image", url });
    } else if (type === "default" && (url === null || url === undefined)) {
      parsed.push({ type: "default", url: null });
    } else {
      return null;
    }
  }
  return parsed;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

// 영상 생성이 실패했을 때 사용자가 다음에 뭘 해야 할지 알려준다.
// (외부 서비스 장애·결제 문제 등은 사용자가 스스로 해결할 수 없으므로 관리자 문의로 안내)
const ADMIN_CONTACT_GUIDE = "잠시 후 다시 시도해보시고, 계속 안 되면 관리자에게 문의해주세요.";
const withContactGuide = (message?: string | null) =>
  `${(message || "").trim() || "영상 생성에 실패했어요."} ${ADMIN_CONTACT_GUIDE}`;

const getProxiedImageUrl = (url: string) => `/api/image-proxy?url=${encodeURIComponent(url)}`;

// 공통 fetch wrapper 함수 추가
function authFetch(url: string, options: RequestInit = {}) {
  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  const headers = {
    ...(options.headers || {}),
    "X-USER-ID": userId ?? "",
  };
  return fetch(url, { ...options, headers });
}

export default function Home() {
  const [blogUrl, setBlogUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [media, setMedia] = useState<MediaList & { scripts?: string[], title?: string } | null>(null);
  const [scripts, setScripts] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState<string>("");
  const [step, setStep] = useState<'input' | 'select' | 'generating' | 'done'>('input');
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMsg, setSnackbarMsg] = useState("");
  const [zoomImg, setZoomImg] = useState<string | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const theme = useTheme();
  const isPc = useMediaQuery(theme.breakpoints.up('md'));
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  // sectionMedia: 길이 5, 각 원소는 SectionMedia 또는 null
  const [sectionMedia, setSectionMedia] = useState<(SectionMedia|null)[]>([null, null, null, null, null]);
  // 장면 수 선택 (4~8). 스크립트/이미지 슬롯 개수가 이 값을 따른다. 기본 5 = 기존 동작.
  const [sceneCount, setSceneCount] = useState<number>(5);
  const [availableSceneCounts, setAvailableSceneCounts] = useState<{ scene_count: number; available: boolean }[]>([]);

  // VOC-2: extract-all 응답의 suggested_sections 로 자동 채워진 이미지 슬롯 수.
  // 1개 이상일 때만 select 진입 안내 문구를 노출한다.
  const [autoFilledImageCount, setAutoFilledImageCount] = useState(0);

  // GPT가 생성한 스크립트 수정 상태 (수정 중인 카드 인덱스 + 임시 텍스트)
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");

  // cycle-3: 자막 스타일 설정
  const [subtitleSettings, setSubtitleSettings] = useState<SubtitleSettings>({
    title: { font_family: "Black Han Sans", font_size: "M", fill_color: "#fff100" },
    subtitle: { font_family: "Noto Sans KR", font_size: "M", fill_color: "#ffffff" },
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsLoggedIn(!!localStorage.getItem("user_id"));
    }
  }, []);

  // 선택 가능한 장면 수 목록 로드 (실패 시 5만 선택 가능하게 폴백)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/blog/scene-counts`);
        const data = await res.json();
        if (!cancelled && Array.isArray(data?.scene_counts)) {
          setAvailableSceneCounts(data.scene_counts);
          if (typeof data.default_scene_count === "number") {
            setSceneCount(data.default_scene_count);
          }
        }
      } catch {
        if (!cancelled) setAvailableSceneCounts([]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // 미디어 클릭 핸들러
  const handleMediaClick = (type: 'image' | 'video', url: string) => {
    console.log(`[handleMediaClick] Fired for type: ${type}, url: ${url}`);
    setSectionMedia(prev => {
      const updated = [...prev];
      const idx = updated.findIndex(m => m && m.url === url);

      if (idx !== -1) {
        // 이미 선택된 미디어 → 해제
        updated[idx] = null;
      } else {
        // cycle-2 (BUG-002 fix): 빈 슬롯 우선, 없으면 첫 default 슬롯에 직접 교체.
        // 이전 동작: null 슬롯만 채워서 default 슬롯이 뒤에 있는데도 앞 null 슬롯이 먼저 채워져 순서 어긋남.
        const emptyIdx = updated.findIndex(m => m === null);
        if (emptyIdx !== -1) {
          updated[emptyIdx] = { type, url };
        } else {
          const defaultIdx = updated.findIndex(m => m && m.type === 'default');
          if (defaultIdx !== -1) {
            updated[defaultIdx] = { type, url };
          } else {
            console.log('[handleMediaClick] No empty / default slot available.');
          }
        }
      }
      return updated;
    });
  };

  // cycle-2.2: 외부 이미지가 404/차단 등으로 로드 실패 시 해당 갤러리/슬롯을 hide 한다.
  // BUG-008 (네이버 OGQ 스티커) 같은 pre-existing + 미래 외부 호스트 변경 대비 안전망.
  // 시각 회귀로 사용자가 깨진 이미지를 클릭하지 않도록 wrapper 자체 hide.
  const handleImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const wrapper = img.closest('li') || img.parentElement;
    if (wrapper instanceof HTMLElement) {
      wrapper.style.display = 'none';
    } else {
      img.style.display = 'none';
    }
  };

  // 스크립트 수정 시작/저장/취소 핸들러
  const handleScriptEditStart = (idx: number) => {
    setEditingIdx(idx);
    setEditingText(scripts[idx] ?? "");
  };

  const handleScriptEditSave = () => {
    if (editingIdx === null) return;
    const trimmed = editingText.trim();
    if (!trimmed) return;
    setScripts(prev => prev.map((s, i) => (i === editingIdx ? trimmed : s)));
    setEditingIdx(null);
    setEditingText("");
  };

  const handleScriptEditCancel = () => {
    setEditingIdx(null);
    setEditingText("");
  };

  // ── 드래그 앤 드롭 ──────────────────────────────────────────────────────
  // 갤러리에서 스크립트 카드로 끌어다 놓으면 그 슬롯에 정확히 배정된다.
  // (클릭 방식은 폴백으로 유지 — 모바일은 HTML5 드래그가 동작하지 않음)
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  type DragPayload =
    | { kind: 'gallery'; type: 'image' | 'video'; url: string }
    | { kind: 'slot'; from: number };

  const handleDragStartMedia = (e: React.DragEvent, type: 'image' | 'video', url: string) => {
    const payload: DragPayload = { kind: 'gallery', type, url };
    e.dataTransfer.setData('application/json', JSON.stringify(payload));
    e.dataTransfer.effectAllowed = 'copyMove';
  };

  const handleDragStartSlot = (e: React.DragEvent, from: number) => {
    const payload: DragPayload = { kind: 'slot', from };
    e.dataTransfer.setData('application/json', JSON.stringify(payload));
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDropOnSlot = (e: React.DragEvent, targetIdx: number) => {
    e.preventDefault();
    setDragOverIdx(null);
    let payload: DragPayload;
    try {
      payload = JSON.parse(e.dataTransfer.getData('application/json')) as DragPayload;
    } catch {
      return;
    }
    setSectionMedia(prev => {
      const updated = [...prev];
      if (payload.kind === 'slot') {
        // 슬롯끼리 자리 바꾸기 (순서 조정)
        if (payload.from === targetIdx) return prev;
        const tmp = updated[targetIdx];
        updated[targetIdx] = updated[payload.from];
        updated[payload.from] = tmp;
        return updated;
      }
      // 갤러리 → 슬롯. 이미 다른 슬롯에 있던 미디어면 그 슬롯은 비운다 (중복 방지).
      const existingIdx = updated.findIndex(m => m && m.url === payload.url);
      updated[targetIdx] = { type: payload.type, url: payload.url };
      if (existingIdx !== -1 && existingIdx !== targetIdx) {
        updated[existingIdx] = null;
      }
      return updated;
    });
  };

  // 스크립트 슬롯에 배정된 이미지가 로드 실패했을 때 그 슬롯을 비운다.
  // 자동 배정(VOC-2)이 깨진 이미지 URL(404 등)을 고르면, 이전에는 미리보기 영역만
  // 숨겨져서 "파란색으로 선택된 것처럼 보이는데 이미지도 없고 해제 버튼(X)도 없는"
  // 막다른 상태가 됐다. 슬롯을 비워 사용자가 직접 다시 고를 수 있게 한다.
  const handleSectionImageError = (idx: number) => {
    setSectionMedia(prev => {
      if (!prev[idx]) return prev;
      const updated = [...prev];
      updated[idx] = null;
      return updated;
    });
    setAutoFilledImageCount(prev => (prev > 0 ? prev - 1 : 0));
  };

  // 섹션 미디어 해제 핸들러 (스크립트별 미리보기에서 X 클릭)
  const handleSectionMediaDeselect = (idx: number) => {
    setSectionMedia(prev => {
      const updated = [...prev]; // 배열을 복사하여 새로운 참조를 만듭니다.
      updated[idx] = null; // 해당 인덱스를 null로 설정합니다.
      return updated; // 수정된 새 배열을 반환합니다.
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMedia(null);
    setScripts([]);
    setTitle("");
    setStep('input');
    setVideoUrl(null);
    setGenerateError(null);
    setSectionMedia(Array(sceneCount).fill(null));
    setAutoFilledImageCount(0);
    setEditingIdx(null);
    setEditingText("");
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000); // 3분
    try {
      const res = await authFetch(`${API_BASE_URL}/api/blog/extract-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blog_url: blogUrl, scene_count: sceneCount }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const data = await res.json();
      if (data.status === "success") {
        setMedia({ images: data.images, videos: data.videos, scripts: data.scripts, title: data.title });
        const scriptList: string[] = (data.scripts || []).map((s: { script: string } | string) => typeof s === 'string' ? s : s.script);
        setScripts(scriptList);
        setTitle(data.title || "");

        // VOC-2: extract-all 응답의 suggested_sections 로 sectionMedia 초기값을 자동 채움 (default 제안, 강제 아님).
        // 형식이 계약과 다르면(필드 없음/구버전 BE 포함) null 반환 → 기존 default_slot_count 폴백 동작 유지.
        // 장면 수는 BE 응답을 신뢰 소스로 (없으면 요청값 → 스크립트 길이 순)
        const effectiveCount: number =
          typeof data.scene_count === 'number' ? data.scene_count : (scriptList.length || sceneCount);
        setSceneCount(effectiveCount);

        const suggested = parseSuggestedSections(data.suggested_sections, scriptList.length);
        if (suggested) {
          const filled: (SectionMedia | null)[] = Array(effectiveCount).fill(null);
          let imageCount = 0;
          suggested.forEach((item, i) => {
            if (i >= filled.length) return;
            if (item.type === 'image') {
              filled[i] = { type: 'image', url: item.url };
              imageCount++;
            } else {
              filled[i] = { type: 'default', url: null, isDefaultBackground: true };
            }
          });
          setSectionMedia(filled);
          setAutoFilledImageCount(imageCount);
        } else {
          setAutoFilledImageCount(0);
          // cycle-2: BE 가 default_slot_count 만큼 부족 슬롯을 알려주면 후반부를 AI 기본 배경으로 채움
          const defaultCount: number = typeof data.default_slot_count === 'number' ? data.default_slot_count : 0;
          const base: (SectionMedia | null)[] = Array(effectiveCount).fill(null);
          if (defaultCount > 0) {
            const start = Math.max(0, effectiveCount - defaultCount);
            for (let i = start; i < effectiveCount; i++) {
              base[i] = { type: 'default', url: null, isDefaultBackground: true };
            }
          }
          setSectionMedia(base);
        }
        setStep('select');
      } else {
        setError(data.message || "이미지/영상/스크립트 추출에 실패했습니다.");
      }
    } catch {
      setError(withContactGuide("서버 요청 중 오류가 생겼어요."));
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateVideo = async () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    setStep('generating');
    setGenerateError(null);
    setVideoUrl(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000); // 3분
    try {
      const res = await authFetch(`${API_BASE_URL}/api/blog/generate-video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          scripts,
          sections: sectionMedia,
          subtitle_settings: subtitleSettings,
          scene_count: sceneCount,
        }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const data = await res.json();
      if (data.status === "started" && data.render_id) {
        // Creatomate polling via backend proxy
        let pollCount = 0;
        let videoUrl = null;
        while (pollCount < 60) { // 최대 3분(3초 * 60)
          const pollController = new AbortController();
          const pollTimeoutId = setTimeout(() => pollController.abort(), 180000); // 3분
          const pollRes = await authFetch(`${API_BASE_URL}/api/blog/poll-video?render_id=${data.render_id}`, { signal: pollController.signal });
          clearTimeout(pollTimeoutId);
          const pollData = await pollRes.json();
          if (pollData.status === "succeeded" && pollData.url) {
            videoUrl = pollData.url;
            break;
          } else if (pollData.status === "failed") {
            setGenerateError(withContactGuide("영상 합성 중 문제가 생겼어요."));
            setStep('select');
            return;
          }
          await new Promise(r => setTimeout(r, 3000)); // 3초 대기
          pollCount++;
        }
        if (videoUrl) {
          setVideoUrl(videoUrl);
          setStep('done');
        } else {
          setGenerateError(withContactGuide("영상 생성이 제한 시간 내에 끝나지 않았어요."));
          setStep('select');
        }
      } else {
        // BE 가 내려준 사유(예: 음성 생성 실패, 템플릿 미설정)를 그대로 보여주고
        // 사용자가 할 수 있는 다음 행동을 덧붙인다.
        setGenerateError(withContactGuide(data.message));
        setStep('select');
      }
    } catch {
      setGenerateError(withContactGuide("서버 요청 중 오류가 생겼어요."));
      setStep('select');
    }
  };

  const handleReset = () => {
    setBlogUrl("");
    setLoading(false);
    setError(null);
    setMedia(null);
    setScripts([]);
    setTitle("");
    setStep('input');
    setVideoUrl(null);
    setGenerateError(null);
    setSectionMedia(Array(sceneCount).fill(null));
    setAutoFilledImageCount(0);
    setEditingIdx(null);
    setEditingText("");
  };

  const handleBetaAlert = (msg: string) => {
    setSnackbarMsg(msg);
    setSnackbarOpen(true);
  };

  useEffect(() => {
    if (step === 'done' && videoUrl) {
      setShowConfetti(true);
      const timer = setTimeout(() => setShowConfetti(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [step, videoUrl]);

  return (
    <AuthGuard>
      <Box sx={{ minHeight: "100vh", bgcolor: "#fff", display: "flex", flexDirection: "column" }}>
        {/* 헤더 */}
        <Box sx={{ width: "100%", height: 64, display: "flex", alignItems: "center", justifyContent: "space-between", px: 4, borderBottom: "1px solid #eee", position: "sticky", top: 0, zIndex: 10 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Link href="/" passHref legacyBehavior>
              <Box
                component="a"
                sx={{
                  width: 120,
                  height: 48,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-start',
                  position: 'relative',
                  cursor: 'pointer',
                  textDecoration: 'none',
                  color: 'inherit',
                  marginRight: 2 // theme.spacing(2) = 16px
                }}
                onClick={e => { e.preventDefault(); window.location.href = '/'; }}
              >
                <Image
                  src="/logo.png"
                  alt="logo"
                  fill
                  style={{ objectFit: "contain" }}
                  sizes="120px"
                  priority
                />
              </Box>
            </Link>
          </Box>
          <Box sx={{ display: "flex", gap: 1, alignItems: 'center' }}>
            {isLoggedIn ? (
              <>
                <ChangePasswordButton />
                <LogoutButton />
              </>
            ) : (
              <>
                <Button variant="outlined" color="inherit" size="small" sx={{ fontWeight: 600 }} onClick={() => handleBetaAlert("Beta 버전에서는 로그인 기능이 지원되지 않습니다.")}>로그인</Button>
                <Button
                  variant="contained"
                  color="primary"
                  size="small"
                  sx={{ fontWeight: 600, display: { xs: 'none', sm: 'inline-flex' } }}
                  onClick={() => handleBetaAlert("Beta 버전에서는 회원가입 기능이 지원되지 않습니다.")}
                >
                  무료로 회원 가입
                </Button>
              </>
            )}
          </Box>
        </Box>

        {/* 메인 컨텐츠 */}
        <Box sx={{ flex: 1, minHeight: '100vh', display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-start", px: 2 }}>
          {step === 'input' && (
            <Box sx={{ width: "100%", maxWidth: 420, textAlign: "center", mt: 12 }}>
              <Typography variant="h4" fontWeight={700} gutterBottom sx={{ mt: 6 }}>
                내 블로그로 숏폼 영상 만들기
              </Typography>
              <Typography variant="body1" color="text.primary" sx={{ mb: 4, wordBreak: 'keep-all' }}>
                <Box component="span" sx={{ fontWeight: 500 }}>네이버 블로그, 티스토리, 브런치</Box> 주소를 붙여넣으면 숏폼 영상을 자동으로 만들어줘요.
              </Typography>
              <Box component="form" onSubmit={handleSubmit} sx={{ width: "100%", mb: 2 }}>
                <TextField
                  label="블로그 주소"
                  placeholder="https://blog.naver.com/username/123456"
                  variant="outlined"
                  fullWidth
                  value={blogUrl}
                  onChange={e => setBlogUrl(e.target.value)}
                  sx={{ mb: 2, bgcolor: "#fafbfc" }}
                  inputProps={{ inputMode: "url" }}
                  InputLabelProps={{ shrink: true }}
                />

                {/* 장면 수 선택 — 스크립트/이미지 개수가 이 값을 따른다 */}
                <Box sx={{ mb: 2, textAlign: "left" }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5 }}>
                    장면 수
                    <Box component="span" sx={{ fontSize: 11, fontWeight: 500, color: "#888", ml: 1 }}>
                      스크립트와 이미지 개수예요
                    </Box>
                  </Typography>
                  <Box sx={{ display: "flex", gap: 1 }}>
                    {[4, 5, 6, 7, 8].map(n => {
                      const info = availableSceneCounts.find(o => o.scene_count === n);
                      // 목록을 못 받았으면 기본값(5)만 허용 — 미확보 템플릿 선택 방지
                      const enabled = info ? info.available : n === 5;
                      const selected = sceneCount === n;
                      return (
                        <Button
                          key={n}
                          onClick={() => enabled && setSceneCount(n)}
                          disabled={!enabled || loading}
                          variant={selected ? "contained" : "outlined"}
                          sx={{ minWidth: 0, flex: 1, fontWeight: 700, py: 1 }}
                        >
                          {n}
                        </Button>
                      );
                    })}
                  </Box>
                  {availableSceneCounts.some(o => !o.available) && (
                    <Typography sx={{ fontSize: 11, color: "#888", mt: 0.5 }}>
                      비활성 장면 수는 준비 중이에요.
                    </Typography>
                  )}
                </Box>

                <Button type="submit" variant="contained" color="primary" fullWidth size="large" disabled={loading} sx={{ fontWeight: 700, fontSize: 18, height: 48 }}>
                  {loading ? <CircularProgress size={24} color="inherit" /> : "숏폼 만들기"}
                </Button>
              </Box>
              {error && <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>}
            </Box>
          )}
          {step === 'select' && media && scripts.length > 0 && (
            isPc ? (
              <>
                <Box
                  sx={{
                    width: '100%',
                    maxWidth: 1000,
                    mx: 'auto',
                    mt: 4,
                    mb: 4,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: '#fff',
                    borderRadius: 3,
                    boxShadow: '0 2px 12px rgba(25,118,210,0.07)',
                    px: 4,
                    py: 2.5,
                    border: '1.5px solid #f2f4f8',
                  }}
                >
                  {/* 왼쪽: 타이틀+안내문구 */}
                  <Box>
                    <Typography variant="h5" fontWeight={700} sx={{ color: '#222', letterSpacing: -1, mb: 0.5 }}>
                      생성된 스크립트에 알맞는 이미지를 선택해 주세요.
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#666' }}>
                      자막 스타일을 미리 설정하고 이미지를 선택하면 영상이 생성됩니다.
                    </Typography>
                  </Box>
                  {/* 오른쪽: 액션 버튼 2개 */}
                  <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <Button
                      variant="outlined"
                      color="primary"
                      onClick={handleReset}
                      sx={{ fontWeight: 600, minWidth: 100 }}
                    >
                      다시하기
                    </Button>
                    <Button
                      variant="contained"
                      color="primary"
                      size="large"
                      sx={{ fontWeight: 700, minWidth: 140 }}
                      onClick={handleGenerateVideo}
                      disabled={sectionMedia.filter(m => m !== null).length !== sceneCount || loading || editingIdx !== null || !title.trim() || scripts.some(s => !s.trim())}
                    >
                      {loading ? <CircularProgress size={24} color="inherit" /> : "숏폼 만들기"}
                    </Button>
                  </Box>
                </Box>
                {/* 영상 생성 실패 안내 (PC).
                    기존에는 이 배너가 모바일 분기에만 있어, PC 에서는 실패해도
                    아무 설명 없이 select 화면으로 돌아와 "반응 없음"처럼 보였다. */}
                {generateError && (
                  <Box sx={{ width: '100%', maxWidth: 1200, mx: 'auto', px: 4, mt: 2 }}>
                    <Alert severity="error" onClose={() => setGenerateError(null)}>
                      {generateError}
                    </Alert>
                  </Box>
                )}
                {/* cycle-3: 자막 스타일 설정 (Row 1 — 접힘 기본) */}
                <Box sx={{ width: '100%', maxWidth: 1200, mx: 'auto', px: 4, mt: 2 }}>
                  <SubtitleStyleEditor onSettingsChange={setSubtitleSettings} />
                  {/* Row 경계 시선 유도 */}
                  <Typography
                    variant="body2"
                    sx={{ color: '#666', mb: 2, fontSize: 13 }}
                  >
                    이미지를 선택해 주세요 — 5개를 모두 고르면 영상 생성하기가 활성화됩니다.
                  </Typography>
                  {/* VOC-2: suggested_sections 로 자동 채워진 슬롯이 있을 때만 안내 */}
                  {autoFilledImageCount > 0 && (
                    <Typography
                      variant="body2"
                      sx={{ color: '#666', mb: 0.5, fontSize: 13, wordBreak: 'keep-all' }}
                    >
                      글 내용에 맞춰 이미지를 자동으로 넣어드렸어요.
                    </Typography>
                  )}
                  <Typography
                    variant="body2"
                    sx={{ color: '#666', mb: 2, fontSize: 13, wordBreak: 'keep-all' }}
                  >
                    오른쪽 이미지를 원하는 스크립트로 끌어다 놓아 보세요. 스크립트끼리 끌어서 순서도 바꿀 수 있어요.
                  </Typography>
                </Box>
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'row', justifyContent: 'center', alignItems: 'flex-start', gap: 4, px: 4, py: 2, maxWidth: 1200, mx: 'auto', width: '100%' }}>
                  {/* 왼쪽: 스크립트 */}
                  <Paper elevation={3} sx={{ flex: 1, p: 4, borderRadius: 4, minWidth: 340, maxWidth: 480, bgcolor: '#fafbfc', boxShadow: '0 4px 24px rgba(0,0,0,0.04)' }}>
                    <Typography variant="h6" fontWeight={700} gutterBottom>생성된 스크립트</Typography>
                    <TextField
                      label="영상 제목"
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                      fullWidth
                      size="small"
                      sx={{ mb: 2, bgcolor: '#fff' }}
                      inputProps={{ maxLength: 30 }}
                      helperText="GPT가 생성한 제목이에요. 자유롭게 수정할 수 있어요."
                    />
                    {scripts.map((script, idx) => {
                      const section = sectionMedia[idx];
                      // cycle-2: 사용자가 직접 고른 슬롯만 강조. AI 기본 배경 슬롯은 강조 X.
                      const isUserSelected = !!section && section.type !== 'default';
                      const isDragOver = dragOverIdx === idx;
                      return (
                        <Paper
                          key={idx}
                          onDragOver={e => { e.preventDefault(); if (dragOverIdx !== idx) setDragOverIdx(idx); }}
                          onDragLeave={() => setDragOverIdx(prev => (prev === idx ? null : prev))}
                          onDrop={e => handleDropOnSlot(e, idx)}
                          sx={{
                            mb: 2,
                            p: 2,
                            borderRadius: 2,
                            boxShadow: isDragOver
                              ? '0 0 0 3px #43a047, 0 2px 8px rgba(0,0,0,0.06)'
                              : isUserSelected ? '0 0 0 3px #1976d2, 0 2px 8px rgba(0,0,0,0.06)' : '0 2px 8px rgba(0,0,0,0.03)',
                            border: isDragOver
                              ? '2px dashed #43a047'
                              : isUserSelected ? '2px solid #1976d2' : '1.5px solid #e3e6ef',
                            bgcolor: isDragOver
                              ? 'rgba(67, 160, 71, 0.08)'
                              : isUserSelected ? 'rgba(25, 118, 210, 0.07)' : '#fff',
                            transition: 'all 0.2s',
                          }}
                        >
                          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 0.5 }}>스크립트 {idx + 1}</Typography>
                          {editingIdx === idx ? (
                            <Box sx={{ mb: 2 }}>
                              <TextField
                                value={editingText}
                                onChange={e => setEditingText(e.target.value)}
                                multiline
                                fullWidth
                                size="small"
                                autoFocus
                                inputProps={{ maxLength: 100 }}
                                helperText={`${editingText.length}/100자`}
                              />
                              <Box sx={{ display: 'flex', gap: 1, mt: 1, justifyContent: 'flex-end' }}>
                                <Button size="small" onClick={handleScriptEditCancel}>취소</Button>
                                <Button size="small" variant="contained" onClick={handleScriptEditSave} disabled={!editingText.trim()}>저장</Button>
                              </Box>
                            </Box>
                          ) : (
                            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                              <Typography variant="body1" sx={{ flex: 1, whiteSpace: 'pre-line' }}>{script}</Typography>
                              <IconButton size="small" onClick={() => handleScriptEditStart(idx)} aria-label={`스크립트 ${idx + 1} 수정`}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          )}
                          {/* 미디어 미리보기 — 다른 스크립트 카드로 끌어다 놓으면 자리 바꾸기 */}
                          {section && (
                            <Box
                              draggable
                              onDragStart={e => handleDragStartSlot(e, idx)}
                              sx={{ mt: 2, position: 'relative', cursor: 'grab' }}
                            >
                              {section.type === 'default' ? (
                                <>
                                  <Box sx={{
                                    width: '100%',
                                    height: 200,
                                    borderRadius: 2,
                                    background: 'linear-gradient(135deg, #e8f0fe 0%, #f3f4f6 100%)',
                                  }} />
                                  <Box sx={{
                                    position: 'absolute',
                                    top: 8,
                                    left: 8,
                                    bgcolor: 'rgba(25, 118, 210, 0.85)',
                                    color: '#fff',
                                    fontSize: 12,
                                    fontWeight: 500,
                                    px: 1.25,
                                    py: 0.5,
                                    borderRadius: 999,
                                    letterSpacing: 0.2,
                                  }}>AI 기본 배경</Box>
                                </>
                              ) : section.type === 'image' ? (
                                <img
                                  src={getProxiedImageUrl(section.url as string)}
                                  alt={`스크립트 ${idx + 1} 이미지`}
                                  onError={() => handleSectionImageError(idx)}
                                  style={{ width: '100%', height: 200, objectFit: 'cover', borderRadius: 8 }}
                                />
                              ) : (
                                <video
                                  src={section.url as string}
                                  style={{ width: '100%', height: 200, objectFit: 'cover', borderRadius: 8 }}
                                  controls
                                />
                              )}
                              <IconButton
                                size="small"
                                onClick={() => handleSectionMediaDeselect(idx)}
                                sx={{
                                  position: 'absolute',
                                  top: 8,
                                  right: 8,
                                  bgcolor: 'rgba(0,0,0,0.5)',
                                  '&:hover': { bgcolor: 'rgba(0,0,0,0.7)' },
                                }}
                              >
                                <CloseIcon sx={{ color: 'white' }} />
                              </IconButton>
                            </Box>
                          )}
                          {section?.type === 'default' && (
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, wordBreak: 'keep-all' }}>
                              AI가 어울리는 배경을 채워뒀어요. 오른쪽에서 직접 바꿀 수 있어요.
                            </Typography>
                          )}
                        </Paper>
                      );
                    })}
                  </Paper>
                  {/* 오른쪽: 이미지/영상 선택 */}
                  <Paper elevation={3} sx={{ flex: 1, p: 4, borderRadius: 4, minWidth: 340, maxWidth: 600, bgcolor: '#fff', boxShadow: '0 4px 24px rgba(0,0,0,0.04)' }}>
                    <Typography variant="h6" fontWeight={700} gutterBottom>이미지 선택</Typography>
                    <Box
                      sx={{
                        maxHeight: 400,
                        overflowY: 'scroll',
                        pr: 1,
                        mb: 2,
                        position: 'relative',
                        border: '1px solid #eee',
                        borderRadius: 2,
                        background: 'linear-gradient(to bottom, #fff 90%, rgba(255,255,255,0)), linear-gradient(to top, #fff 90%, rgba(255,255,255,0))',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '100% 20px',
                        backgroundPosition: 'top, bottom',
                        scrollbarGutter: 'stable',
                        '&::-webkit-scrollbar': {
                          width: '10px',
                          background: '#f2f4f8',
                        },
                        '&::-webkit-scrollbar-thumb': {
                          background: '#d1d5db',
                          borderRadius: 8,
                        },
                        '&::-webkit-scrollbar-corner': {
                          background: '#f2f4f8',
                        },
                      }}
                    >
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                        {media.images.map((url) => {
                          const selectedIdx = sectionMedia.findIndex(section => section && section.url === url);
                          return (
                            <ImageListItem key={url} sx={{ position: 'relative', cursor: 'grab', transition: 'opacity 0.2s' }}>
                              <img
                                onClick={() => handleMediaClick('image', url)}
                                draggable
                                onDragStart={e => handleDragStartMedia(e, 'image', url)}
                                src={getProxiedImageUrl(url)}
                                alt=""
                                loading="lazy"
                                onError={handleImgError}
                                style={{ width: '100%', height: 140, objectFit: 'cover', borderRadius: 8, border: selectedIdx !== -1 ? '2px solid #1976d2' : '2px solid transparent' }}
                              />
                              <IconButton
                                size="small"
                                sx={{ position: 'absolute', top: 8, right: 8, bgcolor: 'rgba(0,0,0,0.5)', '&:hover': { bgcolor: 'rgba(0,0,0,0.7)' } }}
                                onClick={e => { e.stopPropagation(); setZoomImg(url); }}
                              >
                                <ZoomInIcon sx={{ color: 'white' }} />
                              </IconButton>
                              {selectedIdx !== -1 && (
                                <Box sx={{ position: "absolute", bottom: 0, left: 0, width: "100%", height: 28, bgcolor: "rgba(25, 118, 210, 0.7)", display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" }} />
                              )}
                            </ImageListItem>
                          );
                        })}
                      </Box>
                    </Box>
                    <Typography variant="h6" fontWeight={700} gutterBottom sx={{ mt: 4 }}>영상 선택</Typography>
                    <Box sx={{ maxHeight: 400, overflowY: 'scroll', pr: 1, mb: 2, scrollbarGutter: 'stable', '&::-webkit-scrollbar': { width: '10px', background: '#f2f4f8' }, '&::-webkit-scrollbar-thumb': { background: '#d1d5db', borderRadius: 8 }, '&::-webkit-scrollbar-corner': { background: '#f2f4f8' } }}>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                        {media.videos.map((url) => {
                          const selectedIdx = sectionMedia.findIndex(section => section && section.url === url);
                          return (
                            <Box key={url} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                              <video
                                onClick={() => handleMediaClick('video', url)}
                                draggable
                                onDragStart={e => handleDragStartMedia(e, 'video', url)}
                                src={url}
                                style={{ width: '100%', height: 350, objectFit: 'contain', borderRadius: 8, border: selectedIdx !== -1 ? '2px solid #1976d2' : '2px solid transparent', cursor: 'grab' }}
                                controls
                              />
                            </Box>
                          );
                        })}
                      </Box>
                    </Box>
                  </Paper>
                </Box>
              </>
            ) : (
              <Box sx={{ width: "100%", mb: 4 }}>
                <Typography variant="h6" gutterBottom>생성된 스크립트</Typography>
                {/* VOC-2: suggested_sections 로 자동 채워진 슬롯이 있을 때만 안내 */}
                {autoFilledImageCount > 0 && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2, wordBreak: 'keep-all' }}>
                    글 내용에 맞춰 이미지를 자동으로 넣어드렸어요. 눌러서 바꿀 수 있어요.
                  </Typography>
                )}
                <TextField
                  label="영상 제목"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  fullWidth
                  size="small"
                  sx={{ mb: 2 }}
                  inputProps={{ maxLength: 30 }}
                  helperText="GPT가 생성한 제목이에요. 자유롭게 수정할 수 있어요."
                />
                {scripts.map((script, idx) => {
                  const section = sectionMedia[idx];
                  return (
                    <Box key={idx} sx={{ mb: 1, p: 1, border: '1px solid #eee', borderRadius: 2 }}>
                      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 0.5 }}>스크립트 {idx + 1}</Typography>
                      {editingIdx === idx ? (
                        <Box>
                          <TextField
                            value={editingText}
                            onChange={e => setEditingText(e.target.value)}
                            multiline
                            fullWidth
                            size="small"
                            autoFocus
                            inputProps={{ maxLength: 100 }}
                            helperText={`${editingText.length}/100자`}
                          />
                          <Box sx={{ display: 'flex', gap: 1, mt: 1, justifyContent: 'flex-end' }}>
                            <Button size="small" onClick={handleScriptEditCancel}>취소</Button>
                            <Button size="small" variant="contained" onClick={handleScriptEditSave} disabled={!editingText.trim()}>저장</Button>
                          </Box>
                        </Box>
                      ) : (
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                          <Typography variant="body1" sx={{ flex: 1, whiteSpace: 'pre-line' }}>{script}</Typography>
                          <IconButton size="small" onClick={() => handleScriptEditStart(idx)} aria-label={`스크립트 ${idx + 1} 수정`}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Box>
                      )}
                      {/* cycle-2: AI 기본 배경 슬롯은 모바일에서도 안내 카피 + 그라디언트 패널 표시 */}
                      {section?.type === 'default' && (
                        <>
                          <Box sx={{ mt: 1, position: 'relative' }}>
                            <Box sx={{
                              width: '100%',
                              height: 120,
                              borderRadius: 2,
                              background: 'linear-gradient(135deg, #e8f0fe 0%, #f3f4f6 100%)',
                            }} />
                            <Box sx={{
                              position: 'absolute',
                              top: 6,
                              left: 6,
                              bgcolor: 'rgba(25, 118, 210, 0.85)',
                              color: '#fff',
                              fontSize: 11,
                              fontWeight: 500,
                              px: 1,
                              py: 0.25,
                              borderRadius: 999,
                            }}>AI 기본 배경</Box>
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, wordBreak: 'keep-all' }}>
                            AI가 어울리는 배경을 채워뒀어요. 아래에서 직접 바꿀 수 있어요.
                          </Typography>
                        </>
                      )}
                      {idx === scripts.length - 1 && (
                        <Typography variant="body2" color="secondary" sx={{ mt: 1 }}>
                          이 스크립트에는 영상을 선택해 주세요.
                        </Typography>
                      )}
                    </Box>
                  );
                })}
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'center', mb: 2 }}>
                  {media.images.length === 0 && <Typography color="text.secondary">이미지가 없습니다.</Typography>}
                  {media.images.map((url) => {
                    const selectedIdx = sectionMedia.findIndex(section => section && section.url === url);
                    
                    return (
                      <Box
                        key={url}
                        sx={{
                          position: "relative",
                          cursor: "pointer",
                          borderRadius: 2,
                          overflow: "hidden",
                          border: selectedIdx !== -1 ? "2px solid #1976d2" : "2px solid transparent",
                          boxShadow: selectedIdx !== -1 ? "0 0 0 2px #1976d2" : "none",
                        }}
                        onClick={() => handleMediaClick('image', url)}
                      >
                        <img
                          src={getProxiedImageUrl(url)}
                          alt=""
                          loading="lazy"
                          onError={handleImgError}
                          style={{
                            width: '100%',
                            height: 120,
                            objectFit: 'cover',
                            borderRadius: 8,
                            border: selectedIdx !== -1 ? '2px solid #1976d2' : '2px solid transparent'
                          }}
                        />
                        {selectedIdx !== -1 && (
                          <Box
                            sx={{
                              position: "absolute",
                              top: 0,
                              left: 0,
                              width: "100%",
                              height: "100%",
                              bgcolor: "rgba(25, 118, 210, 0.3)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              pointerEvents: "none",
                            }}
                          >
                            <Typography variant="h6" color="#fff" fontWeight={700}>
                              {selectedIdx + 1}번
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    );
                  })}
                </Box>
                {media && media.videos && media.videos.length > 0 && (
                  <Box sx={{ width: "100%", mb: 4 }}>
                    <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>영상 선택</Typography>
                    <Box
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: 3,
                        justifyItems: 'center',
                        alignItems: 'center',
                        mb: 2,
                      }}
                    >
                      {media.videos.map((url) => {
                        const selectedIdx = sectionMedia.findIndex(section => section && section.url === url);

                        return (
                          <Box 
                            key={url} 
                            sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}
                          >
                            <video
                              onClick={() => handleMediaClick('video', url)}
                              src={url}
                              style={{ 
                                width: '100%',
                                height: 120,
                                objectFit: 'cover',
                                borderRadius: 8,
                                border: selectedIdx !== -1 ? '2px solid #1976d2' : '2px solid transparent',
                              }}
                              controls
                            />
                          </Box>
                        );
                      })}
                    </Box>
                  </Box>
                )}
                <Button
                  variant="contained"
                  color="primary"
                  fullWidth
                  size="large"
                  sx={{ mt: 3, mb: 2 }}
                  disabled={sectionMedia.filter(m => m !== null).length !== sceneCount || loading || editingIdx !== null || !title.trim() || scripts.some(s => !s.trim())}
                  onClick={handleGenerateVideo}
                >
                  최종 영상 생성하기
                </Button>
                {generateError && (
                  <Alert severity="error" sx={{ mb: 2 }} onClose={() => setGenerateError(null)}>
                    {generateError}
                  </Alert>
                )}
              </Box>
            )
          )}
          {step === 'generating' && (
            <Box sx={{ width: '100%', mt: 6, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Typography variant="h6" align="center" sx={{ mb: 2 }}>
                최종 영상을 생성 중입니다...
              </Typography>
              <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 4 }}>
                최대 5분 정도 소요될 수 있습니다. 잠시만 기다려 주세요.
              </Typography>
              <Box sx={{ width: 300, maxWidth: '90%' }}>
                <LinearProgress color="primary" sx={{ height: 4, borderRadius: 2 }} />
              </Box>
            </Box>
          )}
          {step === 'done' && videoUrl && (
            <>
              {showConfetti && <Confetti style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 2000 }} />}
              <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', mt: 6 }}>
                <Typography variant="h6" align="center" sx={{ mb: 3 }}>
                  최종 영상이 생성되었습니다!
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: 360, height: 640, maxWidth: '90vw', maxHeight: '70vh', bgcolor: '#f5f5f5', borderRadius: 3, boxShadow: 2, mb: 2 }}>
                  <video
                    src={videoUrl}
                    controls
                    style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 12, background: '#000' }}
                  />
                </Box>
                <Box sx={{ width: '100%', maxWidth: 1000, mx: 'auto', mt: 4, mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button
                    variant="outlined"
                    color="primary"
                    onClick={handleReset}
                    sx={{ fontWeight: 600, minWidth: 100 }}
                  >
                    다시하기
                  </Button>
                </Box>
              </Box>
            </>
          )}
        </Box>

        {/* 하단 Beta 안내 */}
        <Box sx={{ width: "100%", textAlign: "center", py: 2, bgcolor: "#f8fafd", borderTop: "1px solid #eee", fontSize: 14, color: "#888" }}>
          사용중 문의사항이 있으면 mukghost2025@gmail.com 또는 오픈 채팅방으로 문의해주세요.
        </Box>

        {/* Snackbar for Beta 알림 */}
        <Snackbar open={snackbarOpen} autoHideDuration={2500} onClose={() => setSnackbarOpen(false)} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
          <Alert onClose={() => setSnackbarOpen(false)} severity="info" sx={{ width: '100%' }}>
            {snackbarMsg}
          </Alert>
        </Snackbar>

        {/* 이미지 확대 모달 */}
        <Dialog open={!!zoomImg} onClose={() => setZoomImg(null)} maxWidth="md" PaperProps={{ sx: { borderRadius: 3, p: 2, bgcolor: '#fff' } }}>
          {zoomImg && (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', p: 2 }}>
              <Image
                src={getProxiedImageUrl(zoomImg)}
                alt="확대 이미지"
                width={480}
                height={360}
                style={{ objectFit: 'contain', maxWidth: 600, maxHeight: 500, borderRadius: 8 }}
                unoptimized
              />
            </Box>
          )}
        </Dialog>
      </Box>
    </AuthGuard>
  );
}
