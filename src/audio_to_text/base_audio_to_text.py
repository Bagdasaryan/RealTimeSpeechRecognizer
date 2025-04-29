import json
import os
from pathlib import Path
from vosk import Model, KaldiRecognizer, SetLogLevel
from pydub import AudioSegment
from abc import ABC, abstractmethod
from audio_to_text.iaudio_to_text_callback import IAudioToTextCallback

# Disables Vosk logging output
SetLogLevel(-1)

class BaseAudioToText:
    """Base class for converting audio to text using Vosk speech recognition"""
    
    def __init__(self, model_path: str):
        """
        Initializes the audio-to-text converter with specified Vosk model
        
        Args:
            model_path: Relative path to the Vosk language model directory
        """
        self.model_path = model_path
        self.model = None  # Vosk model instance
        self.rec = None    # Vosk recognizer instance
        self.listener = None  # Callback for recognition results

        self._initialize_model()

    def _initialize_model(self):
        """Initializes Vosk speech recognition model from specified path"""
        try:
            # Construct absolute path relative to project root
            project_root = Path(__file__).parent.parent.parent
            model_absolute_path = project_root / self.model_path

            if not model_absolute_path.exists():
                raise FileNotFoundError(f"Model not found at path {model_absolute_path}")

            self.model = Model(str(model_absolute_path))
            self.rec = KaldiRecognizer(self.model, 16000)
            print(f"Vosk model successfully loaded from: {model_absolute_path}")
        except Exception as e:
            print(f"Model initialization error: {e}")
            exit(1)

    def set_audio_to_text_listener(self, listener: IAudioToTextCallback):
        """
        Sets the callback for receiving recognition results
        
        Args:
            listener: Implementation of IAudioToTextCallback interface
        """
        self.listener = listener

    def process_audio_file(self, audio_file_name: str):
        """
        Processes audio file and returns text through registered callback
        
        Args:
            audio_file_name: Name of the audio file in the results directory
            
        Raises:
            FileNotFoundError: If specified audio file doesn't exist
            Exception: For any errors during audio processing
        """
        try:
            # Construct absolute path to audio file
            project_root = Path(__file__).parent.parent.parent
            audio_file_path = project_root / "src" / "result" / audio_file_name

            if not audio_file_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

            # Load and prepare audio file
            audio = AudioSegment.from_wav(str(audio_file_path))
            audio = audio.set_channels(1).set_frame_rate(16000)

            # Perform speech recognition
            self.rec.AcceptWaveform(audio.raw_data)
            result = json.loads(self.rec.Result())
            text = result.get("text", "").strip()

            if not text:
                print("Warning: No speech recognized in audio file")
                text = "[text not recognized]"

            # Notify listener with recognition result
            if self.listener:
                self.listener.do_on_audio_to_text(text)

        except Exception as e:
            print(f"Audio processing error: {e}")
            raise
