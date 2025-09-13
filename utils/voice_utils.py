import os
import io
import requests
from pydub import AudioSegment

class VoiceUtils:
    def __init__(self, app):
        self.enabled = app.config['ENABLE_VOICE']
        self.elevenlabs_api_key = app.config.get('ELEVENLABS_API_KEY')
        self.elevenlabs_voice_id = app.config.get('ELEVENLABS_VOICE_ID')
    
    def text_to_speech(self, text, session_id):
        if not self.elevenlabs_api_key or not self.elevenlabs_voice_id:
            return None
        
        try:
            # Generate audio using ElevenLabs API
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            # Save to file
            filename = f"{session_id}_{hash(text)}.mp3"
            filepath = os.path.join('static', 'audio', filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return f"/static/audio/{filename}"
        
        except Exception as e:
            print(f"Error in TTS: {e}")
            return None
    
    def speech_to_text(self, audio_file):
        # Simple fallback - you'd need to implement proper speech recognition
        # For now, we'll just return a placeholder
        print("Speech-to-text is not fully implemented in this version")
        return "Sorry, speech recognition is not available right now."