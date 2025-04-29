from abc import ABC, abstractmethod

class IStreamCallback(ABC):
    """Callback interface for handling audio stream events.
    
    Implement this interface to receive notifications when audio segments are detected
    and saved during stream processing.
    """

    @abstractmethod
    def do_on_audio_stream_playing(self, filename: str) -> None:
        """Called when a complete audio segment is detected and saved.
        
        Args:
            filename: Path to the saved WAV file containing the detected audio segment.
                     The segment will meet minimum duration requirements and have
                     proper silence padding based on configuration.
        
        Note:
            This method is typically invoked after the system detects natural speech
            boundaries (periods of silence) and saves the preceding audio to disk.
            Implementations should process the file quickly to avoid blocking the
            audio stream processing thread.
        """
        pass
