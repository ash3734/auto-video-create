"""
AI를 이용해 틀린그림(원본, 변형본) 이미지 쌍을 생성하는 함수/클래스 템플릿
"""

import openai
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 이미지 저장 경로
DATA_DIR = "auto_video_create_server/data/find_difference"
os.makedirs(DATA_DIR, exist_ok=True)

def generate_difference_image(prompt, diff_level=1):
    """
    prompt: 생성할 이미지 주제(예: '카페 내부', '강아지와 고양이')
    diff_level: 난이도(1=3개, 2=4개, 3=5개 차이)
    return: 한 장의 이미지 웹 URL (왼쪽: 원본, 오른쪽: n개만 다르게)
    """
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    diff_instruction = {
        1: ("3 clear and easy-to-spot differences"),
        2: ("4 clear and obvious differences"),
        3: ("5 clear and very noticeable differences")
    }[diff_level]
    full_prompt = (
        f"Create a single image for a 'find the difference' puzzle. "
        f"The image should be split into two parts: the left side is the original, and the right side is almost identical but with {diff_instruction}. "
        f"The differences must be ONLY in the color, position, number, or presence/absence of objects. "
        f"Do NOT change the background, style, or overall composition. "
        f"Do NOT add any titles, text, numbers, logos, or watermarks. "
        f"Do NOT add any text or marks about the number of differences, answers, solutions, 'spot the difference', 'answer', 'solution', 'difference', '정답', '문제', '차이', '틀린그림', or any hints, circles, highlights, or extra images. "
        f"The image must contain ONLY the two pictures (left: original, right: modified). No additional elements. "
        f"Avoid subtle or hard-to-spot differences; make each difference obvious and easy to find. "
        f"Example differences: On the left, there is a red apple; on the right, the apple is blue. Or, on the left, there are three butterflies; on the right, there are two. "
        f"The images should be bright, colorful, and in a child-friendly educational style. "
        f"Theme: {prompt}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": full_prompt}
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "generate_image",
                    "description": "Generate an image based on the text prompt",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "The prompt to generate an image from"},
                            "size": {"type": "string", "enum": ["1024x1024", "1792x1024", "1024x1792"], "description": "The size of the image to generate"}
                        },
                        "required": ["prompt"]
                    }
                }
            }
        ],
        tool_choice="auto"
    )
    tool_call = response.choices[0].message.tool_calls[0]
    image_generation_result = tool_call.function.arguments
    import json
    image_args = json.loads(image_generation_result)
    img_url = image_args["image_url"]
    return img_url 