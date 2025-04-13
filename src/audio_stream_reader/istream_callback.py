from abc import ABC, abstractmethod

class IStreamCallback(ABC):
    """Абстрактный класс (интерфейс) для callback-обработчика аудиопотока."""
    @abstractmethod
    def do_on_audio_stream_playing(self, filename: str):
        """Вызывается при обнаружении конца фразы/слова."""
        pass
