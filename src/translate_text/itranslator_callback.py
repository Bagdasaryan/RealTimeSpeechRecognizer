from abc import ABC, abstractmethod

class ITranslatorCallback(ABC):
    @abstractmethod
    def do_on_text_translated(self, translated_text: str):
        """Callback для переведенного текста"""
        pass