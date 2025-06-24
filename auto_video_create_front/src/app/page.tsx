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

interface MediaList {
  images: string[];
  videos: string[];
  scripts?: { script: string }[] | string[];
}

// 섹션별 미디어 타입과 선택된 URL을 관리하는 인터페이스
interface SectionMedia {
  type: 'image' | 'video';
  url: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

const getProxiedImageUrl = (url: string) => `/api/image-proxy?url=${encodeURIComponent(url)}`;

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

  // sectionMedia: 길이 5, 각 원소는 SectionMedia 또는 null
  const [sectionMedia, setSectionMedia] = useState<(SectionMedia|null)[]>([null, null, null, null, null]);

  console.log("--- Component Re-rendering ---");
  console.log("Current sectionMedia state:", JSON.stringify(sectionMedia, null, 2));

  // 미디어 클릭 핸들러
  const handleMediaClick = (type: 'image' | 'video', url: string) => {
    console.log(`[handleMediaClick] Fired for type: ${type}, url: ${url}`);
    setSectionMedia(prev => {
      const updated = [...prev];
      const idx = updated.findIndex(m => m && m.url === url);
      
      if (idx !== -1) {
        updated[idx] = null;
      } else {
        const emptyIdx = updated.findIndex(m => m === null);
        if (emptyIdx !== -1) {
          updated[emptyIdx] = { type, url };
        } else {
          console.log('[handleMediaClick] No empty slot available.');
        }
      }
      return updated;
    });
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
    setSectionMedia([null, null, null, null, null]);
    try {
      const res = await fetch(`${API_BASE_URL}/api/blog/extract-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blog_url: blogUrl }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setMedia({ images: data.images, videos: data.videos, scripts: data.scripts, title: data.title });
        setScripts((data.scripts || []).map((s: { script: string } | string) => typeof s === 'string' ? s : s.script));
        setTitle(data.title || "");
        setStep('select');
      } else {
        setError(data.message || "이미지/영상/스크립트 추출에 실패했습니다.");
      }
    } catch {
      setError("서버 요청 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateVideo = async () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    setStep('generating');
    setGenerateError(null);
    setVideoUrl(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/blog/generate-video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          scripts,
          sections: sectionMedia,
        }),
      });
      const data = await res.json();
      if (data.status === "started" && data.render_id) {
        // Creatomate polling via backend proxy
        let pollCount = 0;
        let videoUrl = null;
        while (pollCount < 60) { // 최대 3분(3초 * 60)
          const pollRes = await fetch(`${API_BASE_URL}/api/blog/poll-video?render_id=${data.render_id}`);
          const pollData = await pollRes.json();
          if (pollData.status === "succeeded" && pollData.url) {
            videoUrl = pollData.url;
            break;
          } else if (pollData.status === "failed") {
            setGenerateError("영상 생성에 실패했습니다.");
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
          setGenerateError("영상 생성이 제한 시간 내에 완료되지 않았습니다.");
          setStep('select');
        }
      } else {
        setGenerateError(data.message || "영상 생성에 실패했습니다.");
        setStep('select');
      }
    } catch {
      setGenerateError("서버 요청 중 오류가 발생했습니다.");
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
    setSectionMedia([null, null, null, null, null]);
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
    <>
      <Box sx={{ minHeight: "100vh", bgcolor: "#fff", display: "flex", flexDirection: "column" }}>
        {/* 헤더 */}
        <Box sx={{ width: "100%", height: 64, display: "flex", alignItems: "center", justifyContent: "space-between", px: 4, borderBottom: "1px solid #eee", position: "sticky", top: 0, zIndex: 10 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Link href="/" passHref legacyBehavior>
              <Box
                component="a"
                sx={{ fontWeight: 700, fontSize: 22, letterSpacing: -1, cursor: 'pointer', textDecoration: 'none', color: 'inherit' }}
                onClick={e => { e.preventDefault(); window.location.href = '/'; }}
              >
                Blog Shorts
              </Box>
            </Link>
            <Box sx={{ bgcolor: "#1976d2", color: "#fff", fontSize: 12, fontWeight: 700, borderRadius: 1, px: 1.2, py: 0.3, ml: 1 }}>BETA</Box>
          </Box>
          <Box sx={{ display: "flex", gap: 1, alignItems: 'center' }}>
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
          </Box>
        </Box>

        {/* 다시하기 버튼: 헤더 바로 아래, step !== 'input'일 때만 */}
        {step !== 'input' && (
          <Box sx={{ width: '100%', display: 'flex', justifyContent: 'flex-end', px: 4, mt: 2 }}>
            <Button variant="outlined" color="primary" onClick={handleReset} sx={{ fontWeight: 600 }}>
              다시하기
            </Button>
          </Box>
        )}

        {/* 메인 컨텐츠 */}
        <Box sx={{ flex: 1, minHeight: '100vh', display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-start", px: 2 }}>
          {step === 'input' && (
            <Box sx={{ width: "100%", maxWidth: 420, textAlign: "center", mt: 12 }}>
              <Typography variant="h4" fontWeight={700} gutterBottom sx={{ mt: 6 }}>
                블로그 주소로 쇼츠 만들기
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                네이버 블로그 주소를 입력하면 쇼츠 영상을 만들어줍니다.
              </Typography>
              <Box component="form" onSubmit={handleSubmit} sx={{ width: "100%", mb: 2 }}>
                <TextField
                  label="네이버 블로그 주소"
                  variant="outlined"
                  fullWidth
                  value={blogUrl}
                  onChange={e => setBlogUrl(e.target.value)}
                  sx={{ mb: 2, bgcolor: "#fafbfc" }}
                  inputProps={{ inputMode: "url" }}
                />
                <Button type="submit" variant="contained" color="primary" fullWidth size="large" disabled={loading} sx={{ fontWeight: 700, fontSize: 18, height: 48 }}>
                  {loading ? <CircularProgress size={24} color="inherit" /> : "쇼츠 만들기"}
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
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: '#f8fbff',
                    border: '1.5px solid #1976d2',
                    borderRadius: 2,
                    px: 3,
                    py: 2,
                    mb: 4,
                    boxShadow: '0 2px 8px rgba(25,118,210,0.07)',
                  }}
                >
                  {/* 안내문구 */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box sx={{ fontSize: 24, color: 'primary.main', mr: 1 }}>💡</Box>
                    <Typography
                      variant="subtitle1"
                      sx={{ fontWeight: 700, color: 'primary.main', fontSize: 18 }}
                    >
                      생성된 스크립트에 알맞는 이미지를 순서대로 선택해 주세요.
                    </Typography>
                  </Box>
                  {/* 버튼 영역 */}
                  <Box sx={{ display: 'flex', gap: 1 }}>
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
                      disabled={sectionMedia.filter(m => m !== null).length !== 5 || loading}
                    >
                      {loading ? <CircularProgress size={24} color="inherit" /> : "쇼츠 만들기"}
                    </Button>
                  </Box>
                </Box>
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'row', justifyContent: 'center', alignItems: 'flex-start', gap: 4, px: 4, py: 6, maxWidth: 1200, mx: 'auto', width: '100%' }}>
                  {/* 왼쪽: 스크립트 */}
                  <Paper elevation={3} sx={{ flex: 1, p: 4, borderRadius: 4, minWidth: 340, maxWidth: 480, bgcolor: '#fafbfc', boxShadow: '0 4px 24px rgba(0,0,0,0.04)' }}>
                    <Typography variant="h6" fontWeight={700} gutterBottom>생성된 스크립트</Typography>
                    {scripts.map((script, idx) => {
                      const section = sectionMedia[idx];
                      return (
                        <Paper
                          key={idx}
                          sx={{
                            mb: 2,
                            p: 2,
                            borderRadius: 2,
                            boxShadow: section ? '0 0 0 3px #1976d2, 0 2px 8px rgba(0,0,0,0.06)' : '0 2px 8px rgba(0,0,0,0.03)',
                            border: section ? '2px solid #1976d2' : '1.5px solid #e3e6ef',
                            bgcolor: section ? 'rgba(25, 118, 210, 0.07)' : '#fff',
                            transition: 'all 0.2s',
                          }}
                        >
                          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 0.5 }}>스크립트 {idx + 1}</Typography>
                          <Typography variant="body1" sx={{ mb: 2 }}>{script}</Typography>
                          {/* 미디어 미리보기 */}
                          {section && (
                            <Box sx={{ mt: 2, position: 'relative' }}>
                              {section.type === 'image' ? (
                                <img 
                                  src={getProxiedImageUrl(section.url)} 
                                  alt={`스크립트 ${idx + 1} 이미지`}
                                  style={{ width: '100%', height: 200, objectFit: 'cover', borderRadius: 8 }}
                                />
                              ) : (
                                <video
                                  src={section.url}
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
                      }}
                    >
                      <Box sx={{ textAlign: 'center', fontSize: 12, color: '#888', mb: 1 }}>
                        ⬇️ 아래로 스크롤하여 더 많은 이미지를 확인하세요
                      </Box>
                      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                        {media.images.map((url) => {
                          const selectedIdx = sectionMedia.findIndex(section => section && section.url === url);
                          return (
                            <ImageListItem key={url} sx={{ position: 'relative', cursor: 'pointer', transition: 'opacity 0.2s' }}>
                              <img
                                onClick={() => handleMediaClick('image', url)}
                                src={getProxiedImageUrl(url)}
                                alt=""
                                loading="lazy"
                                style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 8, border: selectedIdx !== -1 ? '2px solid #1976d2' : '2px solid transparent' }}
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
                    <Box sx={{ maxHeight: 400, overflowY: 'auto', pr: 1, mb: 2 }}>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                        {media.videos.map((url) => {
                          const selectedIdx = sectionMedia.findIndex(section => section && section.url === url);
                          return (
                            <Box key={url} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                              <video
                                onClick={() => handleMediaClick('video', url)}
                                src={url}
                                style={{ width: '100%', height: 200, objectFit: 'cover', borderRadius: 8, border: selectedIdx !== -1 ? '2px solid #1976d2' : '2px solid transparent' }}
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
                {scripts.map((script, idx) => (
                  <Box key={idx} sx={{ mb: 1, p: 1, border: '1px solid #eee', borderRadius: 2 }}>
                    <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 0.5 }}>스크립트 {idx + 1}</Typography>
                    <Typography variant="body1">{script}</Typography>
                    {idx === scripts.length - 1 && (
                      <Typography variant="body2" color="secondary" sx={{ mt: 1 }}>
                        이 스크립트에는 영상을 선택해 주세요.
                      </Typography>
                    )}
                  </Box>
                ))}
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
                  disabled={sectionMedia.filter(m => m !== null).length !== 5 || loading}
                  onClick={handleGenerateVideo}
                >
                  최종 영상 생성하기
                </Button>
                {generateError && <Typography color="error" sx={{ mb: 2 }}>{generateError}</Typography>}
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
              </Box>
            </>
          )}
        </Box>

        {/* 하단 Beta 안내 */}
        <Box sx={{ width: "100%", textAlign: "center", py: 2, bgcolor: "#f8fafd", borderTop: "1px solid #eee", fontSize: 14, color: "#888" }}>
          <b>BETA</b> 버전입니다. 서비스는 테스트 중이며, 기능 및 데이터는 예고 없이 변경될 수 있습니다.
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
    </>
  );
}
