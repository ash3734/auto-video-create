"use client";
import * as React from "react";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Box from "@mui/material/Box";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import Typography from "@mui/material/Typography";
import Container from "@mui/material/Container";
import Alert from "@mui/material/Alert";
import { useRouter } from "next/navigation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

// 공통 fetch wrapper 함수 추가 (로그인 요청 제외)
function authFetch(url: string, options: RequestInit = {}) {
  const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
  const headers = {
    ...(options.headers || {}),
    "X-USER-ID": userId ?? "",
  };
  return fetch(url, { ...options, headers });
}

export default function LoginPage() {
  const [id, setId] = React.useState("");
  const [pw, setPw] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const router = useRouter();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    const res = await fetch(`${API_BASE_URL}/api/account/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, pw }),
    });
    const data = await res.json();
    setLoading(false);
    if (data.status === "success") {
      localStorage.setItem("user_id", data.id);
      router.push("/");
    } else {
      setError("로그인 실패: " + (data.reason || ""));
    }
  };

  return (
    <Container component="main" maxWidth="xs">
      <Box
        sx={{
          marginTop: 8,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <Avatar sx={{ m: 1, bgcolor: "secondary.main" }}>
          <LockOutlinedIcon />
        </Avatar>
        <Typography component="h1" variant="h5">
          로그인
        </Typography>
        <Box component="form" onSubmit={handleSubmit} noValidate sx={{ mt: 1 }}>
          <TextField
            margin="normal"
            required
            fullWidth
            id="id"
            label="ID"
            name="id"
            autoComplete="username"
            autoFocus
            value={id}
            onChange={e => setId(e.target.value)}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="pw"
            label="Password"
            type="password"
            id="pw"
            autoComplete="current-password"
            value={pw}
            onChange={e => setPw(e.target.value)}
          />
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
            disabled={loading}
          >
            {loading ? "로그인 중..." : "로그인"}
          </Button>
        </Box>
      </Box>
    </Container>
  );
} 