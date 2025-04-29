from abc import ABC, abstractmethod

class ITranslatorCallback(ABC):
    """Callback interface for receiving translated text notifications.
    
    Implement this interface to receive notifications when text translation completes.
    """

    @abstractmethod
    def do_on_text_translated(self, translated_text: str) -> None:
        """Called when text translation is successfully completed.
        
        Args:
            translated_text: The resulting translated text. 
                           Guaranteed to be non-empty when this callback is invoked.
                           
        Note:
            This method should handle the translated text efficiently as it's called
            synchronously during the translation process. For long-running operations,
            implementations should consider using background processing.
        """
        pass
