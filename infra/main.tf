terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0" # 최신 안정 버전
    }
  }
  backend "s3" {
    bucket = "ash3734-terraform-state-bucket"
    key    = "state/terraform.tfstate"
    region = "ap-northeast-2"
  }
}

provider "aws" {
  region = "ap-northeast-2"
}

resource "aws_s3_bucket" "my_bucket" {
  bucket        = "auto-video-tts-files" # 실제 AWS에 생성된 버킷 이름과 일치시킴
  force_destroy = true                   # 버킷 비우고 삭제 허용(테스트/개발용)
}

resource "aws_s3_bucket_public_access_block" "public_access" {
  bucket = aws_s3_bucket.my_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "public_read" {
  bucket = aws_s3_bucket.my_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.my_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/Admin",
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/admin"
          ]
        }
        Action = [
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:PutObjectAcl",
          "s3:DeleteObjectVersion"
        ]
        Resource = "${aws_s3_bucket.my_bucket.arn}/*"
      }
    ]
  })
}

resource "aws_s3_bucket" "test" {
  bucket        = "ash3734-terraform-action-test-bucket"
  force_destroy = true
}

# cycle-2: AI 배경 생성(DALL-E) 실패 시 사용하는 fallback 이미지.
# services/ai_background.py 가 이 객체를 참조한다.
resource "aws_s3_object" "default_bg" {
  bucket       = aws_s3_bucket.my_bucket.id
  key          = "static/default-bg.png"
  source       = "${path.module}/files/default-bg.png"
  etag         = filemd5("${path.module}/files/default-bg.png")
  content_type = "image/png"
}

data "aws_caller_identity" "current" {}

# 업로드/삭제는 AWS IAM 인증 사용자만 가능 (별도 정책 필요 없음)

resource "aws_iam_role" "lambda_exec" {
  name = "lambda_exec_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "fastapi" {
  function_name    = "my-fastapi-backend"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "main.handler"
  runtime          = "python3.11"
  filename         = "${path.module}/../auto_video_create_server/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../auto_video_create_server/lambda.zip")

  environment {
    variables = {
      ENV = "production"
      # cycle-3: 한글 폰트 목록 조회용 Google Fonts Developer API 키.
      # 실제 값은 infra/terraform.tfvars (gitignore) 또는 GitHub Secrets → terraform plan -var 로 주입.
      # PO 운영 작업: Google Cloud Console에서 키 발급 후 아래 두 곳에 등록 필요.
      #   1) infra/terraform.tfvars: google_fonts_api_key = "AIza..."
      #   2) GitHub Secrets: GOOGLE_FONTS_API_KEY (terraform.yml 의 -var 플래그로 전달)
      GOOGLE_FONTS_API_KEY = var.google_fonts_api_key
      # security-hotfix (cycle-3, 2026-06-01): OPENAI_API_KEY 를 terraform 관리로 이관.
      # 배경: 이전에는 AWS 콘솔에서 수동 등록돼 있어 terraform plan 이 AWS 상태 refresh 시
      #        해당 키 실값을 "삭제 예정" diff 로 평문 출력 → PR 코멘트로 공개 노출됨 (PR #40, #45).
      # 해결: terraform 이 키를 var 로 알면 plan 이 drift 없이 인식 → 평문 실값 diff 미발생.
      # 실제 값은 아래 중 하나로 주입 (실값 커밋 절대 금지):
      #   1) infra/terraform.tfvars (gitignore): openai_api_key = "sk-..."
      #   2) GitHub Secrets: OPENAI_API_KEY → terraform.yml 의 -var="openai_api_key=$OPENAI_API_KEY" 로 전달
      # PO 운영 작업: 유출된 키 2개 폐기+재발급 후 GitHub Secrets + AWS Lambda(test/prod) 에 새 키 등록.
      OPENAI_API_KEY = var.openai_api_key
    }
  }
  timeout     = 30
  memory_size = 512
}

resource "aws_apigatewayv2_api" "api" {
  name          = "fastapi-http-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.fastapi.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "prod"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fastapi.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

output "api_endpoint" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

variable "github_token" {
  description = "GitHub Personal Access Token for Amplify"
  type        = string
}

# cycle-3: Google Fonts Developer API 키 (한글 폰트 목록 조회).
# 실값은 infra/terraform.tfvars (gitignore) 또는 GitHub Secrets 로 주입.
# 발급: https://console.cloud.google.com → API 및 서비스 → 사용자 인증 정보 → API 키 생성
#       → Web Fonts 제한 권장.
variable "google_fonts_api_key" {
  description = "Google Fonts Developer API Key for Korean font subset listing (GET /api/blog/fonts)"
  type        = string
  sensitive   = true
}

# security-hotfix (cycle-3, 2026-06-01): OPENAI_API_KEY terraform 관리 이관.
# 배경: AWS 콘솔 수동 등록 → terraform plan refresh 시 실값 평문 노출 (PR #40, #45).
# 실값은 infra/terraform.tfvars (gitignore) 또는 GitHub Secrets 로 주입 (실값 커밋 금지).
# PO 운영 작업:
#   1) OpenAI 대시보드에서 유출 키 2개 폐기 + 새 키 발급 (OpenAI 가 이미 1개 비활성화함 — 나머지 1개도 즉시 폐기)
#   2) 새 키를 GitHub Secrets OPENAI_API_KEY 에 등록
#   3) AWS Lambda my-fastapi-backend (test/prod) 콘솔에서 OPENAI_API_KEY 환경변수 업데이트
#   4) GitHub secret scanning 알림 2건 resolve
variable "openai_api_key" {
  description = "OpenAI API Key for video script generation and DALL-E background generation"
  type        = string
  sensitive   = true
}

resource "aws_amplify_app" "frontend" {
  name        = "auto-video-frontend"
  repository  = "https://github.com/ash3734/auto-video-create"
  oauth_token = var.github_token
  platform    = "WEB"
  build_spec  = file("../amplify.yml")

  environment_variables = {
    NEXT_PUBLIC_API_URL = "https://your-backend-api-url" # 필요시 수정
  }
}

resource "aws_amplify_branch" "main" {
  app_id            = aws_amplify_app.frontend.id
  branch_name       = "main"
  stage             = "PRODUCTION"
  enable_auto_build = true
} 