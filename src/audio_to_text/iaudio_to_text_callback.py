from abc import ABC, abstractmethod

class IAudioToTextCallback(ABC):
    """
    Abstract base class defining the callback interface for audio-to-text conversion results.
    
    Implement this interface to receive speech recognition results from BaseAudioToText.
    """

    @abstractmethod
    def do_on_audio_to_text(self, recognized_text: str) -> None:
        """
        Callback method invoked when speech recognition completes.
        
        Args:
            recognized_text: The text result from speech recognition.
                           Returns "[text not recognized]" if recognition failed.
                           
        Note:
            This method should be implemented to handle the recognition result.
            The method should not block for extended periods as it's called
            during the recognition process.
        """
        pass
