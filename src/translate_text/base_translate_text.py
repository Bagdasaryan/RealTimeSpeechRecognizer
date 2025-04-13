import requests
from typing import Optional
from translate_text.itranslator_callback import ITranslatorCallback

class BaseTranslateText:
    def __init__(self, 
                 oauth_token: Optional[str] = None, 
                 folder_id: Optional[str] = None,
                 default_source_lang: str = 'en',
                 default_target_lang: str = 'hy'):
        """
        :param oauth_token: Yandex Cloud OAuth токен (None для тестового режима)
        :param folder_id: Yandex Cloud Folder ID
        :param default_source_lang: Язык оригинала по умолчанию
        :param default_target_lang: Язык перевода по умолчанию
        """
        self.oauth_token = oauth_token
        self.folder_id = folder_id
        self.default_source_lang = default_source_lang
        self.default_target_lang = default_target_lang
        self._listener = None
        self.api_endpoint = "https://translate.api.cloud.yandex.net/translate/v2/translate"

    def set_text_translator_listener(self, listener: ITranslatorCallback):
        """Установка callback-обработчика для переведенного текста"""
        if not isinstance(listener, ITranslatorCallback):
            raise TypeError("Listener must implement ITranslatorCallback")
        self._listener = listener

    def translate(self, 
                 text: str, 
                 source_lang: Optional[str] = None,
                 target_lang: Optional[str] = None) -> Optional[str]:
        """
        Синхронный перевод текста
        
        :param text: Текст для перевода
        :param source_lang: Язык оригинала (если None - используется default_source_lang)
        :param target_lang: Язык перевода (если None - используется default_target_lang)
        :return: Переведенный текст (или None при ошибке)
        """
        # Устанавливаем языки по умолчанию если не указаны
        src_lang = source_lang if source_lang else self.default_source_lang
        trg_lang = target_lang if target_lang else self.default_target_lang

        # Выполняем перевод
        translated_text = self._translate_text(text, src_lang, trg_lang)
        
        # Вызываем callback если есть listener и перевод успешен
        if self._listener and translated_text is not None:
            self._listener.do_on_text_translated(translated_text)
            
        return translated_text

    def _translate_text(self, 
                   text: str, 
                   source_lang: str, 
                   target_lang: str) -> Optional[str]:
        """Основная логика перевода"""
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
                    "format": "PLAIN_TEXT"  # Обязательный параметр
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
        """Установка языков по умолчанию"""
        self.default_source_lang = source_lang
        self.default_target_lang = target_lang
