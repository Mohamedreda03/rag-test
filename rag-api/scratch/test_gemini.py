import asyncio
import sys
from openai import AsyncOpenAI

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Read API key from .env file
api_key = None
try:
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("RAG_GEMINI_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
except Exception as e:
    print("Error reading .env:", e)

if not api_key:
    print("API Key not found in .env")
    sys.exit(1)

print("Found Gemini API Key:", api_key[:10] + "...")

# A valid 1x1 black pixel JPEG bytes
dummy_jpeg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\x27" #\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'

async def test_gemini():
    client = AsyncOpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=api_key
    )
    import base64
    base64_image = base64.b64encode(dummy_jpeg).decode("utf-8")
    
    print("Sending request to Google Gemini OpenAI-compatible endpoint...")
    try:
        response = await client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in one word."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
        )
        print("Response received successfully!")
        print("Content:", response.choices[0].message.content)
    except Exception as e:
        print("Exception occurred during request:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini())
