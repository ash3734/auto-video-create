"use client";
import { useRouter } from "next/navigation";
import Button from "@mui/material/Button";

export default function LogoutButton() {
  const router = useRouter();
  return (
    <Button
      variant="outlined"
      color="inherit"
      size="small"
      sx={{ fontWeight: 600, borderRadius: 2, px: { xs: 1.25, sm: 2 }, minWidth: 0, py: 0.5, whiteSpace: 'nowrap' }}
      onClick={() => {
        localStorage.removeItem("user_id");
        router.push("/login");
      }}
    >
      로그아웃
    </Button>
  );
} 