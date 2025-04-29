import requests
from typing import Optional
from translate_text.itranslator_callback import ITranslatorCallback

class BaseTranslateText:
    """Provides text translation functionality using Yandex Cloud Translation API."""
    
    # Suppored languages
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'ru': 'Russian',
        'hy': 'Armenian'
    }

    def __init__(self, 
                 oauth_token: Optional[str] = None, 
                 folder_id: Optional[str] = None,
                 default_source_lang: str = 'en',
                 default_target_lang: str = 'hy'):
        """
        :param oauth_token: Yandex Cloud OAuth token (None for dummy mode)
        :param folder_id: Yandex Cloud Folder ID
        :param default_source_lang: Default source language code
        :param default_target_lang: Default target language code
        """
        self.oauth_token = oauth_token
        self.folder_id = folder_id
        self.default_source_lang = default_source_lang
        self.default_target_lang = default_target_lang
        self._listener = None
        self.api_endpoint = "https://translate.api.cloud.yandex.net/translate/v2/translate"

    def set_text_translator_listener(self, listener: ITranslatorCallback):
        """Sets callback handler for translation results"""
        if not isinstance(listener, ITranslatorCallback):
            raise TypeError("Listener must implement ITranslatorCallback")
        self._listener = listener

    def translate(self, 
                 text: str, 
                 source_lang: Optional[str] = None,
                 target_lang: Optional[str] = None) -> Optional[str]:
        """
        Performs synchronous text translation
        
        Args:
            text: Text to translate
            source_lang: Source language code (uses default if None)
            target_lang: Target language code (uses default if None)
            
        Returns:
            Translated text if successful, None otherwise
        """
        # Validate language codes
        src_lang = source_lang if source_lang else self.default_source_lang
        trg_lang = target_lang if target_lang else self.default_target_lang
        
        if src_lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported source language: {src_lang}")
        if trg_lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported target language: {trg_lang}")

        translated_text = self._translate_text(text, src_lang, trg_lang)
        
        if self._listener and translated_text is not None:
            self._listener.do_on_text_translated(translated_text)
            
        return translated_text

    def _translate_text(self, 
                       text: str, 
                       source_lang: str, 
                       target_lang: str) -> Optional[str]:
        """Internal translation logic"""
        if not self.oauth_token or not self.folder_id:
            print("Yandex credentials not configured. Using dummy translation.")
            return f"[{source_lang}→{target_lang}] {text}"

        try:
            response = requests.post(
                self.api_endpoint,
                headers={
                    "Authorization": f"Api-Key {self.oauth_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "folderId": self.folder_id,
                    "texts": [text],
                    "sourceLanguageCode": source_lang,
                    "targetLanguageCode": target_lang,
                    "format": "PLAIN_TEXT"
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()["translations"][0]["text"]
        except requests.exceptions.RequestException as e:
            print(f"Translation API error: {str(e)}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Response parsing error: {str(e)}")
            return None

    def set_default_languages(self, source_lang: str, target_lang: str):
        """Updates default source and target languages"""
        if source_lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported source language: {source_lang}")
        if target_lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported target language: {target_lang}")
            
        self.default_source_lang = source_lang
        self.default_target_lang = target_lang
