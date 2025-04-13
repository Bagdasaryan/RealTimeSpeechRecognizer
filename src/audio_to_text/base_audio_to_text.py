import json
import os
from pathlib import Path
from vosk import Model, KaldiRecognizer, SetLogLevel
from pydub import AudioSegment
from abc import ABC, abstractmethod
from audio_to_text.iaudio_to_text_callback import IAudioToTextCallback

# Устанавливаем уровень логирования для Vosk (отключаем логи)
SetLogLevel(-1)

class BaseAudioToText:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.rec = None
        self.listener = None

        self._initialize_model()

    def _initialize_model(self):
        """Инициализация модели Vosk для распознавания речи"""
        try:
            # Используем абсолютный путь для модели относительно корня проекта
            project_root = Path(__file__).parent.parent.parent  # Корень проекта (на два уровня выше)
            model_absolute_path = project_root / self.model_path

            # Проверяем, что модель существует
            if not model_absolute_path.exists():
                print(f"Ошибка: Модель не найдена по пути {model_absolute_path}")
                exit(1)

            self.model = Model(str(model_absolute_path))
            self.rec = KaldiRecognizer(self.model, 16000)
            print(f"Модель Vosk успешно загружена с пути: {model_absolute_path}")
        except Exception as e:
            print(f"Ошибка инициализации модели: {e}")
            exit(1)

    def set_audio_to_text_listener(self, listener: IAudioToTextCallback):
        """Устанавливаем слушателя (callback) для получения результата распознавания"""
        self.listener = listener

    def process_audio_file(self, audio_file_name: str):
        """Обработка аудиофайла и вызов callback с результатом распознавания"""
        try:
            # Получаем путь к аудиофайлу
            project_root = Path(__file__).parent.parent.parent  # Корень проекта (на два уровня выше)
            audio_file_path = project_root / "src" / "result" / audio_file_name

            if not audio_file_path.exists():
                print(f"Ошибка: файл {audio_file_path} не найден.")
                return

            # print(f"Обработка аудиофайла: {audio_file_path}")

            # Загружаем аудио с помощью pydub
            audio = AudioSegment.from_wav(str(audio_file_path))
            audio = audio.set_channels(1).set_frame_rate(16000)

            # Запускаем распознавание
            self.rec.AcceptWaveform(audio.raw_data)
            result = json.loads(self.rec.Result())
            text = result.get("text", "").strip()

            if not text:
                print("Предупреждение: текст не распознан")
                text = "[Текст не распознан]"

            # Передаем распознанный текст через callback
            if self.listener:
                self.listener.do_on_audio_to_text(text)

        except Exception as e:
            print(f"Ошибка обработки аудио: {e}")
            return
