from abc import ABC, abstractmethod

class IAudioToTextCallback(ABC):
    """Абстрактный класс (интерфейс) для callback-обработчика распознавания текста из аудио."""
    
    @abstractmethod
    def do_on_audio_to_text(self, translation_res: str):
        """Метод для обработки результата распознавания речи."""
        pass
