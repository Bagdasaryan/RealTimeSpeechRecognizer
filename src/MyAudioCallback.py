import threading
import time
import queue
from pathlib import Path
from typing import Optional
from audio_to_text.base_audio_to_text import BaseAudioToText
from audio_to_text.iaudio_to_text_callback import IAudioToTextCallback
from audio_stream_reader.istream_callback import IStreamCallback
from audio_stream_reader.base_audio_stream_receiver import BaseAudioStreamReceiver
from translate_text.base_translate_text import BaseTranslateText
from translate_text.itranslator_callback import ITranslatorCallback


class MyAudioCallback(IAudioToTextCallback, IStreamCallback, ITranslatorCallback):
    def __init__(self):
        # Инициализация модели распознавания речи
        project_root = Path(__file__).parent.parent
        model_path = project_root / "language_models" / "enmodel-small"
        print(f"Инициализация модели распознавания: {model_path}")
        
        self.audio_to_text = BaseAudioToText(model_path=str(model_path))
        self.audio_to_text.set_audio_to_text_listener(self)
        
        # Очередь для аудиофайлов
        self.audio_files_queue = queue.Queue()
        self.audio_processing_thread = None
        self.audio_running = False
        self.currently_processing = False
        self.audio_lock = threading.Lock()
        
        # Инициализация переводчика (синхронная версия)
        self.translator = BaseTranslateText(
            oauth_token="AQVN0Y5y_ENyewZxxU_0CfaPXUlyiBDL8tU19J06",  # None для тестового режима
            folder_id="b1g395ej0iqqcob4b562",
            default_source_lang="en",  # Язык распознанных аудиозаписей
            default_target_lang="hy"   # Язык перевода
        )
        self.translator.set_text_translator_listener(self)

    def do_on_audio_stream_playing(self, filename: str):
        """Обработка нового аудиофайла (вызывается из аудиопотока)"""
        self.audio_files_queue.put(filename)
        self._start_audio_processing()

    def _start_audio_processing(self):
        """Запуск потока обработки аудио"""
        if self.audio_processing_thread is None or not self.audio_processing_thread.is_alive():
            self.audio_running = True
            self.audio_processing_thread = threading.Thread(
                target=self._process_audio_queue,
                daemon=True
            )
            self.audio_processing_thread.start()

    def _process_audio_queue(self):
        """Поток для обработки очереди аудио"""
        while self.audio_running:
            try:
                with self.audio_lock:
                    if self.currently_processing:
                        continue

                    filename = self.audio_files_queue.get(timeout=1)
                    self.currently_processing = True

                # Синхронная обработка файла
                self.audio_to_text.process_audio_file(filename)
                
                # Ожидание завершения через callback
                while True:
                    with self.audio_lock:
                        if not self.currently_processing:
                            break
                    time.sleep(0.1)

                self.audio_files_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Ошибка обработки аудио: {e}")
                with self.audio_lock:
                    self.currently_processing = False

    def do_on_audio_to_text(self, recognized_text: str):
        # Синхронный перевод текста
        self.translator.translate(
            text=recognized_text,
            source_lang="en",  # Явно указываем язык оригинала
            target_lang="hy"    # Язык перевода
        )
        
        with self.audio_lock:
            self.currently_processing = False

    def do_on_text_translated(self, translated_text: str):
        """Обработка переведенного текста (вызывается из BaseTranslateText)"""
        print(f"ПЕРЕВЕДЕНО: {translated_text}")
        # Здесь можно сохранить результат или передать дальше

    def stop(self):
        """Остановка всех процессов"""
        self.audio_running = False
        if self.audio_processing_thread:
            self.audio_processing_thread.join(timeout=1)
        self.translator.set_text_translator_listener(None)
        print("Все процессы остановлены")

def main():
    project_root = Path(__file__).parent.parent
    result_dir = project_root / "result"
    result_dir.mkdir(exist_ok=True)

    callback = MyAudioCallback()
    receiver = BaseAudioStreamReceiver()
    receiver.set_audio_stream_listener(callback)

    try:
        print("Запуск аудио захвата... Нажмите Ctrl+C для остановки")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nПолучен сигнал прерывания")
    finally:
        receiver.stop_audio_stream_receiving()
        callback.stop()
        print("Программа завершена корректно")

if __name__ == "__main__":
    main()
