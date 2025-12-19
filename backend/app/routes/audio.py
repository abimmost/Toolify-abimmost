from fastapi import APIRouter, HTTPException, Depends, Form
from app.services.audio_service import audio_service
from app.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["Audio"])

@router.post("/generate-tts")
async def generate_tts(
    text: str = Form(...),
    language: str = Form("en"),
    user: dict = Depends(get_current_user)
):
    """Generate text-to-speech audio for a message"""
    try:
        # Generate audio using YarnGPT via audio_service
        audio_url = audio_service.generate_audio(
            text=text,
            tool_name="chat_message",
            user_id=str(user.id)
        )
        
        return {"url": audio_url}
        
    except Exception as e:
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation error: {str(e)}")
