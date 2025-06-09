"use client";
import { Box, Button, Container, TextField, Typography, CircularProgress, Checkbox, FormControlLabel, FormGroup } from "@mui/material";
import { useState } from "react";
import Image from "next/image";

interface MediaList {
  images: string[];
  videos: string[];
}

export default function Home() {
  const [blogUrl, setBlogUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [media, setMedia] = useState<MediaList | null>(null);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [selectedVideos, setSelectedVideos] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMedia(null);
    setSelectedImages([]);
    setSelectedVideos([]);
    try {
      const res = await fetch("/api/extract-media", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blog_url: blogUrl }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setMedia({ images: data.images, videos: data.videos });
      } else {
        setError(data.message || "이미지/영상 추출에 실패했습니다.");
      }
    } catch (err) {
      setError("서버 요청 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleImageToggle = (url: string) => {
    setSelectedImages(prev => prev.includes(url) ? prev.filter(u => u !== url) : [...prev, url]);
  };
  const handleVideoToggle = (url: string) => {
    setSelectedVideos(prev => prev.includes(url) ? prev.filter(u => u !== url) : [...prev, url]);
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
      </Box>
      <Box component="form" onSubmit={handleSubmit} sx={{ width: "100%", mb: 4 }}>
        <TextField
          label="네이버 블로그 주소"
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
      {media && (
        <Box sx={{ width: "100%", mb: 4 }}>
          <Typography variant="h6" gutterBottom>이미지 선택</Typography>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 2,
              mb: 2,
            }}
          >
            {media.images.length === 0 && <Typography color="text.secondary">이미지가 없습니다.</Typography>}
            {media.images.map((url, idx) => {
              const selected = selectedImages.includes(url);
              return (
                <Box
                  key={url}
                  sx={{
                    position: "relative",
                    cursor: "pointer",
                    borderRadius: 2,
                    overflow: "hidden",
                    border: selected ? "2px solid #1976d2" : "2px solid transparent",
                    boxShadow: selected ? "0 0 0 2px #1976d2" : "none",
                  }}
                  onClick={() => handleImageToggle(url)}
                >
                  <img
                    src={`/api/image-proxy?url=${encodeURIComponent(url)}`}
                    alt={`img${idx}`}
                    style={{
                      width: "100%",
                      height: 80,
                      objectFit: "cover",
                      display: "block",
                      filter: selected ? "brightness(0.6)" : "none",
                      transition: "filter 0.2s, box-shadow 0.2s",
                    }}
                  />
                  {selected && (
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
                      <Typography variant="h5" color="#fff" fontWeight={700}>
                        선택됨
                      </Typography>
                    </Box>
                  )}
                </Box>
              );
            })}
          </Box>
          <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>영상 선택</Typography>
          <FormGroup>
            {media.videos.length === 0 && <Typography color="text.secondary">영상이 없습니다.</Typography>}
            {media.videos.map((url, idx) => (
              <FormControlLabel
                key={url}
                control={<Checkbox checked={selectedVideos.includes(url)} onChange={() => handleVideoToggle(url)} />}
                label={<video src={url} style={{ maxWidth: 120, maxHeight: 80, marginRight: 8 }} controls />} />
            ))}
          </FormGroup>
        </Box>
      )}
    </Container>
  );
}
