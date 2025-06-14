"use client";
import { Box, Button, Container, TextField, Typography, CircularProgress, LinearProgress } from "@mui/material";
import { useState } from "react";
import Image from "next/image";

interface MediaList {
  images: string[];
  videos: string[];
  scripts?: { script: string }[] | string[];
}

export default function Home() {
  const [blogUrl, setBlogUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [media, setMedia] = useState<MediaList & { scripts?: string[], title?: string } | null>(null);
  const [scripts, setScripts] = useState<string[]>([]);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState<string>("");
  const [step, setStep] = useState<'input' | 'select' | 'generating' | 'done'>('input');
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMedia(null);
    setSelectedImages([]);
    setSelectedVideo(null);
    setScripts([]);
    setTitle("");
    setStep('input');
    setVideoUrl(null);
    setGenerateError(null);
    try {
      const res = await fetch("/api/blog/extract-all", {
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

  const handleImageClick = (url: string) => {
    setSelectedImages(prev => {
      const idx = prev.indexOf(url);
      if (idx === -1) {
        if (prev.length < 4) {
          return [...prev, url];
        } else {
          return prev;
        }
      } else if (idx === prev.length - 1) {
        return prev.slice(0, -1);
      } else {
        return prev;
      }
    });
  };

  const getImageOrder = (url: string) => {
    const idx = selectedImages.indexOf(url);
    return idx !== -1 ? idx + 1 : null;
  };

  const handleVideoSelect = (url: string) => {
    setSelectedVideo(prev => prev === url ? null : url);
  };

  const handleGenerateVideo = async () => {
    setStep('generating');
    setGenerateError(null);
    setVideoUrl(null);
    try {
      const res = await fetch("/api/blog/generate-video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          scripts,
          images: selectedImages,
          video: selectedVideo,
        }),
      });
      const data = await res.json();
      if (data.status === "success" && data.video_url) {
        setVideoUrl(data.video_url);
        setStep('done');
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
    setSelectedImages([]);
    setSelectedVideo(null);
    setScripts([]);
    setTitle("");
    setStep('input');
    setVideoUrl(null);
    setGenerateError(null);
  };

  return (
    <Container maxWidth="sm" sx={{ minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", p: 2 }}>
      <Box sx={{ width: "100%", textAlign: "center", mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          블로그 주소로 쇼츠 만들기
        </Typography>
        <Typography variant="body1" color="text.secondary">
          네이버 블로그 주소를 입력하면 자동으로 쇼츠 영상을 만들어줍니다.
        </Typography>
        {title && (
          <Typography variant="h5" color="primary" fontWeight={700} sx={{ mt: 2, mb: 2 }}>
            영상 제목: {title}
          </Typography>
        )}
      </Box>
      <Box component="form" onSubmit={handleSubmit} sx={{ width: "100%", mb: 4 }}>
        <TextField
          label="네이버 블로그 주소!!!"
          variant="outlined"
          fullWidth
          value={blogUrl}
          onChange={e => setBlogUrl(e.target.value)}
          sx={{ mb: 2 }}
          inputProps={{ inputMode: "url" }}
        />
        <Button type="submit" variant="contained" color="primary" fullWidth size="large" disabled={loading}>
          {loading ? <CircularProgress size={24} color="inherit" /> : "쇼츠 만들기"}
        </Button>
      </Box>
      {error && <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>}
      {step === 'select' && media && scripts.length > 0 && (
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
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 2 }}>
            이미지를 클릭하면 선택 순서대로 각 스크립트에 할당됩니다.<br />
            선택을 취소하려면 마지막에 선택한 이미지를 다시 클릭하세요.<br />
            (최대 4개까지 선택할 수 있습니다)
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'center', mb: 2 }}>
            {media.images.length === 0 && <Typography color="text.secondary">이미지가 없습니다.</Typography>}
            {media.images.map((url, idx) => {
              const order = getImageOrder(url);
              return (
                <Box
                  key={url}
                  sx={{
                    position: "relative",
                    cursor: order === null && selectedImages.length < 4 ? "pointer" : order !== null ? "pointer" : "not-allowed",
                    borderRadius: 2,
                    overflow: "hidden",
                    border: order !== null ? "2px solid #1976d2" : "2px solid transparent",
                    boxShadow: order !== null ? "0 0 0 2px #1976d2" : "none",
                    opacity: order === null && selectedImages.length >= 4 ? 0.5 : 1,
                  }}
                  onClick={() => handleImageClick(url)}
                >
                  <Image
                    src={`/api/image-proxy?url=${encodeURIComponent(url)}`}
                    alt={`img${idx}`}
                    width={80}
                    height={80}
                    style={{
                      objectFit: "cover",
                      display: "block",
                      filter: order !== null ? "brightness(0.6)" : "none",
                      transition: "filter 0.2s, box-shadow 0.2s",
                    }}
                    unoptimized
                  />
                  {order !== null && (
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
                        {order}번 선택됨
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
                {media.videos.map((url) => (
                  <Box key={url} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 220 }}>
                    <video
                      src={url}
                      style={{ width: 200, height: 140, borderRadius: 8, border: selectedVideo === url ? '3px solid #1976d2' : '2px solid #eee', marginBottom: 8, background: '#000' }}
                      controls
                    />
                    <Button
                      variant={selectedVideo === url ? 'contained' : 'outlined'}
                      color={selectedVideo === url ? 'primary' : 'inherit'}
                      size="small"
                      onClick={() => handleVideoSelect(url)}
                      sx={{ width: 180 }}
                    >
                      {selectedVideo === url ? '선택됨' : '이 영상 선택'}
                    </Button>
                  </Box>
                ))}
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                영상을 1개만 선택할 수 있습니다. 선택을 취소하려면 다시 클릭하세요.
              </Typography>
            </Box>
          )}
          <Button
            variant="contained"
            color="primary"
            fullWidth
            size="large"
            sx={{ mt: 3, mb: 2 }}
            disabled={selectedImages.length !== 4 || !selectedVideo}
            onClick={handleGenerateVideo}
          >
            최종 영상 생성하기
          </Button>
          {generateError && <Typography color="error" sx={{ mb: 2 }}>{generateError}</Typography>}
        </Box>
      )}
      {step === 'generating' && (
        <Box sx={{ width: "100%", textAlign: "center", mt: 8 }}>
          <Typography variant="h6" gutterBottom>최종 영상을 생성 중입니다...</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            최대 1분 정도 소요될 수 있습니다. 잠시만 기다려 주세요.
          </Typography>
          <Box sx={{ width: '100%', mt: 4 }}>
            <LinearProgress />
          </Box>
        </Box>
      )}
      {step === 'done' && videoUrl && (
        <Box sx={{ width: "100%", textAlign: "center", mt: 8 }}>
          <Typography variant="h6" gutterBottom>최종 영상이 생성되었습니다!</Typography>
          <video src={videoUrl} controls style={{ width: '100%', maxHeight: 400, borderRadius: 8, margin: '24px 0' }} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            다시하기를 누르면 이 영상은 더 이상 다운로드할 수 없습니다.
          </Typography>
          <Button variant="outlined" color="primary" onClick={handleReset} sx={{ mt: 2 }}>
            다시하기
          </Button>
        </Box>
      )}
    </Container>
  );
}
