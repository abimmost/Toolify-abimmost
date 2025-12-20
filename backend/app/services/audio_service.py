import os
import tempfile
import requests
from google import genai
from datetime import datetime
from app.config import settings

# Initialize Gemini Client
client = genai.Client(api_key=settings.google_api_key)

# YarnGPT API Configuration
YARNGPT_API_URL = "https://yarngpt.ai/api/v1/tts"

class AudioService:
    """Service for handling audio operations: TTS and STT"""
    
    def __init__(self):
        pass
    
    def clean_text_for_tts(self, text: str) -> str:
        """
        Cleans text for TTS generation by removing markdown and normalizing whitespace.
        """
        import re
        
        # Remove bold/italic markers (* or _)
        text = re.sub(r'[\*_]{1,3}', '', text)
        
        # Remove headers (### Title -> Title)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # Remove links ([text](url) -> text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove code blocks (```code``` -> code)
        text = re.sub(r'```[\w]*', '', text)
        
        # Remove inline code (`code` -> code)
        text = re.sub(r'`', '', text)
        
        # Remove list bullets (* Item -> Item, - Item -> Item)
        text = re.sub(r'^[\*\-]\s+', '', text, flags=re.MULTILINE)
        
        # Normalize newlines: replace literal \n with actual newline if needed
        text = text.replace('\\n', '\n')
        
        # Collapse multiple newlines to max 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def generate_audio(self, text, tool_name, user_id):
        """
        Generate audio file from text using YarnGPT and upload to Supabase.
        """
        try:
            # Clean text before processing
            text = self.clean_text_for_tts(text)
            
            # Prepare headers
            if not settings.yarngpt_api_key:
                pass
            
            headers = {
                "Authorization": f"Bearer {settings.yarngpt_api_key}",
                "Content-Type": "application/json"
            }

            # Prepare request to YarnGPT
            payload = {
                "text": text,
                "voice": "Idera", # Default voice
            }
            
            response = requests.post(YARNGPT_API_URL, json=payload, headers=headers, stream=True)
            
            if response.status_code != 200:
                raise Exception(f"YarnGPT API failed: {response.text}")
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() else "_" for c in tool_name)
            filename = f"{safe_name}_{timestamp}.mp3"
            
            # Stream to memory
            import io
            audio_buffer = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                audio_buffer.write(chunk)
            
            audio_content = audio_buffer.getvalue()

            # Upload to Supabase Storage
            from app.config import supabase
            storage_path = f"{user_id}/{filename}"
            bucket_name = "tool-audio"
            
            supabase.storage.from_(bucket_name).upload(
                file=audio_content,
                path=storage_path,
                file_options={"content-type": "audio/mp3"}
            )
            
            # Get Public URL
            public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
            
            return public_url
            
        except Exception as e:

            raise Exception(f"Audio generation error: {str(e)}")


    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
        """
        Transcribes audio using the Gemini API.

        Args:
            audio_bytes: The audio file content.
            mime_type: The mime type of the audio file.

        Returns:
            The transcribed text.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        temp_audio_path = None
        uploaded_file_name = None
        
        try:
            # Log input details
            audio_size = len(audio_bytes)
            logger.info(f"[TRANSCRIBE] Starting transcription - Audio size: {audio_size} bytes, MIME type: {mime_type}")
            print(f"[TRANSCRIBE] Starting transcription - Audio size: {audio_size} bytes, MIME type: {mime_type}")
            
            if audio_size == 0:
                logger.error("[TRANSCRIBE] Audio bytes are empty!")
                print("[TRANSCRIBE] Error: Audio bytes are empty!")
                return ""
            
            # Determine extension from mime_type
            ext = ".mp3"
            if "wav" in mime_type:
                ext = ".wav"
            elif "ogg" in mime_type:
                ext = ".ogg"
            elif "m4a" in mime_type or "mp4" in mime_type:
                ext = ".m4a"
            elif "aac" in mime_type:
                ext = ".aac"
            elif "webm" in mime_type:
                ext = ".webm"
            
            logger.info(f"[TRANSCRIBE] Determined file extension: {ext}")
            print(f"[TRANSCRIBE] Determined file extension: {ext}")
            
            # Create a temporary file to store the audio
            logger.info("[TRANSCRIBE] Creating temporary file...")
            print("[TRANSCRIBE] Creating temporary file...")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio_path = temp_audio.name
            
            logger.info(f"[TRANSCRIBE] Temporary file created at: {temp_audio_path}")
            print(f"[TRANSCRIBE] Temporary file created at: {temp_audio_path}")
            
            # Verify file was written correctly
            if not os.path.exists(temp_audio_path):
                logger.error(f"[TRANSCRIBE] Temporary file does not exist after creation: {temp_audio_path}")
                print(f"[TRANSCRIBE] Error: Temporary file does not exist after creation: {temp_audio_path}")
                return ""
            
            file_size = os.path.getsize(temp_audio_path)
            logger.info(f"[TRANSCRIBE] Temporary file size: {file_size} bytes")
            print(f"[TRANSCRIBE] Temporary file size: {file_size} bytes")

            # Upload the file to Gemini
            logger.info("[TRANSCRIBE] Uploading file to Gemini API...")
            print("[TRANSCRIBE] Uploading file to Gemini API...")
            
            try:
                uploaded_file = client.files.upload(file=temp_audio_path)
                uploaded_file_name = uploaded_file.name
                logger.info(f"[TRANSCRIBE] File uploaded successfully. Name: {uploaded_file_name}, State: {uploaded_file.state.name}")
                print(f"[TRANSCRIBE] File uploaded successfully. Name: {uploaded_file_name}, State: {uploaded_file.state.name}")
            except Exception as upload_error:
                logger.error(f"[TRANSCRIBE] File upload failed: {type(upload_error).__name__}: {str(upload_error)}")
                print(f"[TRANSCRIBE] File upload failed: {type(upload_error).__name__}: {str(upload_error)}")
                raise
            
            # Wait for file to be processed (ACTIVE state)
            import time
            max_wait = 60  # Increased to 60 seconds
            wait_time = 0
            poll_interval = 1
            
            logger.info(f"[TRANSCRIBE] Waiting for file to reach ACTIVE state (current: {uploaded_file.state.name})...")
            print(f"[TRANSCRIBE] Waiting for file to reach ACTIVE state (current: {uploaded_file.state.name})...")
            
            while uploaded_file.state.name != "ACTIVE":
                if wait_time >= max_wait:
                    error_msg = f"File processing timeout after {max_wait}s. Final state: {uploaded_file.state.name}"
                    logger.error(f"[TRANSCRIBE] {error_msg}")
                    print(f"[TRANSCRIBE] Error: {error_msg}")
                    raise Exception(error_msg)
                
                time.sleep(poll_interval)
                wait_time += poll_interval
                
                # Robust polling with retries for the GET call
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        uploaded_file = client.files.get(name=uploaded_file.name)
                        break # Success
                    except Exception as poll_error:
                        is_last_attempt = (attempt == max_retries - 1)
                        error_type = type(poll_error).__name__
                        logger.warning(f"[TRANSCRIBE] Polling attempt {attempt+1} failed: {error_type}: {str(poll_error)}")
                        print(f"[TRANSCRIBE] Warning: Polling attempt {attempt+1} failed: {error_type}")
                        
                        if is_last_attempt:
                            logger.error("[TRANSCRIBE] All polling retries failed.")
                            raise # Re-raise the last error if all retries fail
                        
                        # Exponential backoff for the retry itself
                        time.sleep(2 ** attempt) 
                
                if wait_time % 5 == 0:  # Log every 5 seconds
                    logger.info(f"[TRANSCRIBE] Still waiting... ({wait_time}s elapsed, state: {uploaded_file.state.name})")
                    print(f"[TRANSCRIBE] Still waiting... ({wait_time}s elapsed, state: {uploaded_file.state.name})")
            
            logger.info(f"[TRANSCRIBE] File is ACTIVE after {wait_time}s")
            print(f"[TRANSCRIBE] File is ACTIVE after {wait_time}s")
            
            prompt = "Transcribe the following audio exactly as spoken. Do not translate. Return only the transcription."
            
            logger.info(f"[TRANSCRIBE] Sending transcription request to Gemini (model: {settings.gemini_model})...")
            print(f"[TRANSCRIBE] Sending transcription request to Gemini (model: {settings.gemini_model})...")
            
            # Robust generation with retries
            max_gen_retries = 3
            response = None
            for attempt in range(max_gen_retries):
                try:
                    response = client.models.generate_content(
                        model=settings.gemini_model,
                        contents=[prompt, uploaded_file]
                    )
                    logger.info(f"[TRANSCRIBE] Received response from Gemini API")
                    print(f"[TRANSCRIBE] Received response from Gemini API")
                    break # Success
                except Exception as api_error:
                    is_last_attempt = (attempt == max_gen_retries - 1)
                    error_type = type(api_error).__name__
                    logger.warning(f"[TRANSCRIBE] Generation attempt {attempt+1} failed: {error_type}: {str(api_error)}")
                    print(f"[TRANSCRIBE] Warning: Generation attempt {attempt+1} failed: {error_type}")
                    
                    if is_last_attempt:
                        logger.error("[TRANSCRIBE] All generation retries failed.")
                        raise # Re-raise if all retries fail
                    
                    time.sleep(2 ** attempt) # Exponential backoff
            
            # Log response structure for debugging
            if response:
                logger.info(f"[TRANSCRIBE] Response type: {type(response)}")
                logger.info(f"[TRANSCRIBE] Response attributes: {dir(response)}")
                print(f"[TRANSCRIBE] Response type: {type(response)}")
                print(f"[TRANSCRIBE] Response has 'text' attr: {hasattr(response, 'text')}")
                print(f"[TRANSCRIBE] Response has 'candidates' attr: {hasattr(response, 'candidates')}")
            
            # Check if response has text
            try:
                if hasattr(response, 'text') and response.text:
                    transcribed_text = response.text.strip()
                    logger.info(f"[TRANSCRIBE] Successfully extracted text (length: {len(transcribed_text)} chars)")
                    print(f"[TRANSCRIBE] Successfully extracted text (length: {len(transcribed_text)} chars)")
                    print(f"[TRANSCRIBE] Transcribed text preview: {transcribed_text[:100]}...")
                    return transcribed_text
                else:
                    logger.warning(f"[TRANSCRIBE] No text in response. Response: {response}")
                    print(f"[TRANSCRIBE] Warning: No text in response")
                    return ""
            except Exception as text_error:
                logger.error(f"[TRANSCRIBE] Error accessing response.text: {type(text_error).__name__}: {str(text_error)}")
                print(f"[TRANSCRIBE] Error accessing response.text: {type(text_error).__name__}: {str(text_error)}")
                
                # Try accessing via candidates if available
                try:
                    if hasattr(response, 'candidates') and response.candidates:
                        logger.info("[TRANSCRIBE] Attempting to extract text from candidates...")
                        print("[TRANSCRIBE] Attempting to extract text from candidates...")
                        
                        candidate_text = response.candidates[0].content.parts[0].text.strip()
                        logger.info(f"[TRANSCRIBE] Successfully extracted from candidates (length: {len(candidate_text)} chars)")
                        print(f"[TRANSCRIBE] Successfully extracted from candidates (length: {len(candidate_text)} chars)")
                        return candidate_text
                    else:
                        logger.warning("[TRANSCRIBE] No candidates available in response")
                        print("[TRANSCRIBE] Warning: No candidates available in response")
                except Exception as candidate_error:
                    logger.error(f"[TRANSCRIBE] Error accessing candidates: {type(candidate_error).__name__}: {str(candidate_error)}")
                    print(f"[TRANSCRIBE] Error accessing candidates: {type(candidate_error).__name__}: {str(candidate_error)}")
                
                return ""
            
        except Exception as e:
            logger.error(f"[TRANSCRIBE] Fatal error: {type(e).__name__}: {str(e)}")
            print(f"[TRANSCRIBE] Fatal error: {type(e).__name__}: {str(e)}")
            
            # Log stack trace for debugging
            import traceback
            stack_trace = traceback.format_exc()
            logger.error(f"[TRANSCRIBE] Stack trace:\n{stack_trace}")
            print(f"[TRANSCRIBE] Stack trace:\n{stack_trace}")
            
            return ""
        finally:
            # Clean up uploaded file from Gemini if exists
            if uploaded_file_name:
                try:
                    logger.info(f"[TRANSCRIBE] Cleaning up uploaded file: {uploaded_file_name}")
                    print(f"[TRANSCRIBE] Cleaning up uploaded file: {uploaded_file_name}")
                    client.files.delete(name=uploaded_file_name)
                    logger.info("[TRANSCRIBE] Uploaded file deleted successfully")
                    print("[TRANSCRIBE] Uploaded file deleted successfully")
                except Exception as delete_error:
                    logger.warning(f"[TRANSCRIBE] Failed to delete uploaded file: {delete_error}")
                    print(f"[TRANSCRIBE] Warning: Failed to delete uploaded file: {delete_error}")
            
            # Clean up local temp file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                    logger.info(f"[TRANSCRIBE] Temporary file deleted: {temp_audio_path}")
                    print(f"[TRANSCRIBE] Temporary file deleted: {temp_audio_path}")
                except Exception as unlink_error:
                    logger.warning(f"[TRANSCRIBE] Failed to delete temp file: {unlink_error}")
                    print(f"[TRANSCRIBE] Warning: Failed to delete temp file: {unlink_error}")

audio_service = AudioService()
