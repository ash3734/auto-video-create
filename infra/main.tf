terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # 최신 안정 버전
    }
  }
}

provider "aws" {
  region = "ap-northeast-2"
}

resource "aws_s3_bucket" "my_bucket" {
  bucket = "auto-video-tts-files" # 실제 AWS에 생성된 버킷 이름과 일치시킴
  force_destroy = true # 버킷 비우고 삭제 허용(테스트/개발용)
}

resource "aws_s3_bucket_public_access_block" "public_access" {
  bucket = aws_s3_bucket.my_bucket.id

  block_public_acls   = false
  block_public_policy = false
  ignore_public_acls  = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "public_read" {
  bucket = aws_s3_bucket.my_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = "*"
        Action = "s3:GetObject"
        Resource = "${aws_s3_bucket.my_bucket.arn}/*"
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

data "aws_caller_identity" "current" {}

# 업로드/삭제는 AWS IAM 인증 사용자만 가능 (별도 정책 필요 없음) 