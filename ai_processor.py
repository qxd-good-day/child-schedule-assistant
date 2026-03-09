import base64
import json
import os
from openai import OpenAI

# Prompt for the AI to extract schedule information
SYSTEM_PROMPT = """
You are a helpful assistant that extracts structured schedule data from images or text.
Please extract the following fields for each course:
- day_of_week (one of: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday)
- start_time (HH:MM format, 24-hour clock)
- end_time (HH:MM format, 24-hour clock)
- course_name (string)
- location (string)
- pickup_time (HH:MM format, 24-hour clock, or empty string if not found)
- notes (string, optional)

Return the result as a JSON object with a key "courses" containing a list of objects.
Example JSON:
{
  "courses": [
    {
      "day_of_week": "Monday",
      "start_time": "16:30",
      "end_time": "17:30",
      "course_name": "Math",
      "location": "Room 101",
      "pickup_time": "17:30",
      "notes": "Bring calculator"
    }
  ]
}
If the input is an image, do your best to read the table or text.
If the input is text, parse it accordingly.
"""

def encode_image(image_file):
    """Encodes a file-like object (from Streamlit) to base64."""
    return base64.b64encode(image_file.read()).decode('utf-8')

def get_ai_client(api_key, base_url=None):
    """
    创建 AI 客户端，支持 OpenAI 和兼容 OpenAI 格式的 API（如阿里云 DashScope）
    """
    if base_url:
        # 使用自定义 base_url（如阿里云 DashScope）
        return OpenAI(api_key=api_key, base_url=base_url)
    else:
        # 默认使用 OpenAI
        return OpenAI(api_key=api_key)

def extract_schedule_from_image(image_file, api_key, base_url=None, model=None):
    """
    Extracts schedule from an image using AI model.
    支持 OpenAI GPT-4o 和阿里云 DashScope Qwen-VL 等模型
    """
    if not api_key:
        return {"error": "No API key provided."}

    try:
        client = get_ai_client(api_key, base_url)
        base64_image = encode_image(image_file)
        
        # 默认模型选择
        if model is None:
            model = "qwen-vl-max-latest" if base_url else "gpt-4o"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the schedule from this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

def extract_schedule_from_text(text, api_key, base_url=None, model=None):
    """
    Extracts schedule from text using AI model.
    支持 OpenAI GPT-4o 和阿里云 DashScope Qwen 等模型
    """
    if not api_key:
        return {"error": "No API key provided."}

    try:
        client = get_ai_client(api_key, base_url)
        
        # 默认模型选择
        if model is None:
            model = "qwen-max-latest" if base_url else "gpt-4o"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Extract the schedule from this text:\n\n{text}"
                }
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}

def mock_extract_schedule():
    """
    Returns a mock schedule for demonstration purposes (matching the user's image).
    """
    return {
        "courses": [
            {"day_of_week": "Monday", "start_time": "16:30", "end_time": "17:30", "course_name": "小主持人", "location": "幼儿园", "pickup_time": "17:30", "notes": ""},
            {"day_of_week": "Tuesday", "start_time": "16:30", "end_time": "17:30", "course_name": "体适能", "location": "中安创谷", "pickup_time": "16:00", "notes": ""},
            {"day_of_week": "Wednesday", "start_time": "16:30", "end_time": "17:30", "course_name": "科学小实验", "location": "幼儿园", "pickup_time": "17:30", "notes": ""},
            {"day_of_week": "Thursday", "start_time": "16:40", "end_time": "17:30", "course_name": "舞蹈", "location": "西子曼城超市", "pickup_time": "16:00", "notes": ""},
            {"day_of_week": "Friday", "start_time": "16:30", "end_time": "17:30", "course_name": "体适能", "location": "中安创谷", "pickup_time": "16:00", "notes": ""},
            {"day_of_week": "Saturday", "start_time": "10:50", "end_time": "11:50", "course_name": "乐高", "location": "高新银泰3楼吉姆", "pickup_time": "", "notes": ""},
            {"day_of_week": "Sunday", "start_time": "10:30", "end_time": "12:00", "course_name": "绘画", "location": "Y15栋201", "pickup_time": "", "notes": ""},
            {"day_of_week": "Sunday", "start_time": "17:40", "end_time": "18:30", "course_name": "舞蹈", "location": "西子曼城超市", "pickup_time": "", "notes": ""}
        ]
    }
