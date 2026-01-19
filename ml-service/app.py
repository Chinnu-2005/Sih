import os
import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import uvicorn
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
import io

# Load environment variables from the parent directory .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = FastAPI(title="Civic Issue ML Classifier (Gemini Powered)", version="3.0.0")

# Configure Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)

# Use Gemini 1.5 Flash for speed and cost-effectiveness
# Use Gemini 1.5 Flash (Standard)
MODEL_NAME = "gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

class ClassificationRequest(BaseModel):
    text: Optional[str] = None
    image_url: Optional[str] = None
    # Audio URL support is limited in direct API, usually requires file upload or distinct handling
    # For compatibility, we'll keep the field but might need to fetch it if provided.
    audio_url: Optional[str] = None 

# Predefined Labels (for prompt context)
SEVERITY_LEVELS = ["Minor issue", "Moderate issue", "Severe issue"]
DEPARTMENTS = [
    "Sanitation and Waste Management",
    "Roads and Transport",
    "Electricity and Streetlights",
    "Water Supply and Drainage",
    "Public Health",
    "Environment",
    "Public Safety"
]

MAPPED_SEVERITY = {
    "Minor issue": "LOW",
    "Moderate issue": "MEDIUM",
    "Severe issue": "HIGH"
}

MAPPED_DEPARTMENTS = {
    "Sanitation and Waste Management": "Sanitation",
    "Roads and Transport": "Roads",
    "Electricity and Streetlights": "Electricity",
    "Water Supply and Drainage": "Water",
    "Public Health": "Health",
    "Environment": "Environment",
    "Public Safety": "Safety"
}

SYSTEM_PROMPT = f"""
You are an AI assistant for a civic issue reporting system. 
Your task is to analyze inputs (text, images, or audio) and classify them based on the municipality's needs.

### Classification Rules
1. **Department:** Choose strictly from: {json.dumps(DEPARTMENTS)}
2. **Severity:** Choose strictly from: {json.dumps(SEVERITY_LEVELS)}
3. **Title:** Generate a concise, professional title (max 5 words).
4. **Reasoning:** Provide a 1-sentence explanation for the classification.

### Output Format
You must output a single, valid JSON object. 
- DO NOT use Markdown formatting (no ```json or ```).
- DO NOT include any introductory or concluding text.
- The output must be parseable by `json.loads()` directly.

### JSON Schema
{{
  "department": "string",
  "severity": "string",
  "title": "string",
  "reasoning": "string"
}}
"""

def parse_gemini_response(response_text):
    try:
        # cleanup markdown if present
        text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response_text}")
        return None

@app.post("/classify")
async def classify_issue(
    text: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server configuration error: Gemini API Key missing.")

    inputs = []
    
    # 1. Handle Text
    if text:
        inputs.append(f"Complaint Description: {text}")

    # 2. Handle Image (File Upload) - Priority
    if image:
        try:
            content = await image.read()
            image_bytes = io.BytesIO(content)
            pil_image = Image.open(image_bytes)
            inputs.append(pil_image)
        except Exception as e:
            print(f"Failed to process uploaded image: {e}")
            inputs.append(f"[System Note: User uploaded an image but it failed to process. Error: {str(e)}]")

    # 3. Handle Image URL (Fallback if no file)
    elif image_url:
        try:
            import requests
            print(f"Fetching image from: {image_url}")
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            image_bytes = io.BytesIO(img_response.content)
            pil_image = Image.open(image_bytes)
            inputs.append(pil_image)
        except Exception as e:
            print(f"Failed to load image from URL: {e}")
            inputs.append(f"[System Note: User provided image URL {image_url} but it could not be accessed.]")

    if not inputs:
         raise HTTPException(status_code=400, detail="No valid input provided (text or image).")

    try:
        # Add system instruction via content
        full_prompt = [SYSTEM_PROMPT] + inputs
        
        response = model.generate_content(full_prompt)
        result = parse_gemini_response(response.text)

        if not result:
             raise HTTPException(status_code=500, detail="Failed to parse AI response")

        # Map to internal format
        raw_dept = result.get("department", "Other")
        raw_sev = result.get("severity", "Moderate issue")
        
        mapped_dept = MAPPED_DEPARTMENTS.get(raw_dept, "Other")
        mapped_sev = MAPPED_SEVERITY.get(raw_sev, "MEDIUM")

        return {
            "severity": mapped_sev,
            "department": mapped_dept,
            "title": result.get("title", "Civic Issue"),
            "confidence": {
                "severity": 0.9, # Placeholder as Gemini doesn't always give confidence scores easily
                "department": 0.9
            },
            "original_analysis": result # Debug info
        }

    except Exception as e:
        print(f"Gemini API Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

@app.post("/classify-audio")
async def classify_audio_file(file: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server configuration error: Gemini API Key missing.")

    try:
        content = await file.read()
        
        # Gemini 1.5 supports audio directly, but via File API usually. 
        # For simplicity in this lightweight script passed as 'blob' parts if supported by library version,
        # or we rely on the library's helpers. 
        # However, sending raw audio bytes directly to generate_content is not always standard for 'audio'.
        # The robust way with google-generativeai is uploading the file using `genai.upload_file` then using it.
        
        # Save temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp:
             temp.write(content)
             temp_path = temp.name
        
        try:
            print("Uploading audio to Gemini...")
            # Upload to Gemini Media
            audio_file = genai.upload_file(path=temp_path)
            
            # Prompt
            prompt = [SYSTEM_PROMPT, "Analyze this audio complaint.", audio_file]
            
            response = model.generate_content(prompt)
            result = parse_gemini_response(response.text)
            
            # Cleanup remote file (optional but good practice)
            # audio_file.delete() # Not available immediately in all SDK versions, but let's assume auto-cleanup or ignore for now
            
        finally:
            # Cleanup local
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        if not result:
             raise HTTPException(status_code=500, detail="Failed to analyze audio")

        raw_dept = result.get("department", "Other")
        raw_sev = result.get("severity", "Moderate issue")
        
        return {
            "severity": MAPPED_SEVERITY.get(raw_sev, "MEDIUM"),
            "department": MAPPED_DEPARTMENTS.get(raw_dept, "Other"),
            "title": result.get("title", "Audio Report"),
            "confidence": {
                 "severity": 0.9,
                 "department": 0.9
            },
            "transcribed_text": result.get("reasoning", "Audio processed directly.") # Gemini implies transcript in reasoning often
        }

    except Exception as e:
        print(f"Audio Error: {e}")
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "gemini-cloud"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)