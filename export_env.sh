#!/bin/bash
# 프로젝트 루트(.env가 있는 곳) 기준으로 환경변수 export

ENV_PATH="$(cd "$(dirname "$0")" && pwd)/.env"

if [ ! -f "$ENV_PATH" ]; then
  echo ".env 파일이 $ENV_PATH 에 없습니다."
  exit 1
fi

export $(grep -v '^#' "$ENV_PATH" | xargs)
echo "환경변수가 성공적으로 export 되었습니다."

terraform force-unlock 845d1880-fe76-8386-62c5-5e2528b69a1c 