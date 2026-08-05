"use client";
import { useState } from "react";
import {
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Typography,
  CircularProgress,
  Snackbar,
  Alert,
} from "@mui/material";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const MIN_PASSWORD_LENGTH = 8;

export default function ChangePasswordButton() {
  const [open, setOpen] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState(false);

  const reset = () => {
    setCurrentPw("");
    setNewPw("");
    setConfirmPw("");
    setError(null);
    setLoading(false);
  };

  const handleClose = () => {
    if (loading) return;
    setOpen(false);
    reset();
  };

  // 서버에 보내기 전 로컬에서 걸러낼 수 있는 것만 검사한다 (현재 비밀번호 검증은 서버 몫).
  const localError = (): string | null => {
    if (!currentPw || !newPw || !confirmPw) return "모든 항목을 입력해주세요.";
    if (newPw.length < MIN_PASSWORD_LENGTH) return `새 비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 해요.`;
    if (newPw !== confirmPw) return "새 비밀번호가 서로 달라요.";
    if (newPw === currentPw) return "새 비밀번호가 현재 비밀번호와 같아요.";
    return null;
  };

  const handleSubmit = async () => {
    const localMsg = localError();
    if (localMsg) {
      setError(localMsg);
      return;
    }
    const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") : null;
    if (!userId) {
      setError("로그인 정보를 찾을 수 없어요. 다시 로그인해주세요.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/account/change-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-USER-ID": userId },
        body: JSON.stringify({ id: userId, current_pw: currentPw, new_pw: newPw }),
      });
      const data = await res.json().catch(() => null);
      if (data?.status === "success") {
        setOpen(false);
        reset();
        setToast(true);
      } else {
        setError(data?.reason || "비밀번호를 변경할 수 없어요.");
        setLoading(false);
      }
    } catch {
      setError("서버 요청 중 오류가 발생했어요.");
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant="outlined"
        color="inherit"
        size="small"
        sx={{ fontWeight: 600, borderRadius: 2, px: 2, py: 0.5 }}
        onClick={() => setOpen(true)}
      >
        비밀번호 변경
      </Button>

      <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700, fontSize: 18 }}>비밀번호 변경</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="현재 비밀번호"
            type="password"
            size="small"
            autoComplete="current-password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
            disabled={loading}
            autoFocus
          />
          <TextField
            label="새 비밀번호"
            type="password"
            size="small"
            autoComplete="new-password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            disabled={loading}
            helperText={`${MIN_PASSWORD_LENGTH}자 이상`}
          />
          <TextField
            label="새 비밀번호 확인"
            type="password"
            size="small"
            autoComplete="new-password"
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !loading) handleSubmit();
            }}
          />
          {error && (
            <Typography sx={{ color: "#d32f2f", fontSize: 13, wordBreak: "keep-all" }}>{error}</Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose} disabled={loading}>
            취소
          </Button>
          <Button variant="contained" onClick={handleSubmit} disabled={loading}>
            {loading ? <CircularProgress size={18} color="inherit" /> : "변경"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={toast}
        autoHideDuration={3000}
        onClose={() => setToast(false)}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert severity="success" onClose={() => setToast(false)}>
          비밀번호를 변경했어요.
        </Alert>
      </Snackbar>
    </>
  );
}
