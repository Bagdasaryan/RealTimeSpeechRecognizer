import pyaudio
import wave
import numpy as np
import time
from audio_stream_reader.istream_callback import IStreamCallback
from pathlib import Path
from collections import deque


class BaseAudioStreamReceiver:
    def __init__(self, device_name: str = "Stereo Mix (Realtek(R) Audio)"):
        self._callback = None
        self._is_recording = False
        self._sample_rate = 16000
        self._chunk_size = 480
        self._device_name = device_name
        self._input_device_index = self._get_device_index_by_name(self._device_name)

        # Для RMS-анализа
        self._frames = []
        self._rms_history = deque(maxlen=50)  # 50 фреймов по ~30-40 мс ≈ 1.5–2 секунды
        self._silence_frame_count = 0
        self._silence_threshold_factor = 0.5  # тишина — если RMS < среднее * 0.5
        self._silence_required = 13  # сколько подряд "тихих" фреймов — считать тишиной

        # Параметры минимальной и максимальной продолжительности записи (в секундах)
        self._min_duration_seconds = 3
        self._max_duration_seconds = 8

        # Время последней записи
        self._last_save_time = None

        # Путь к результатам
        self.project_root = Path(__file__).parent.parent
        self.result_dir = self.project_root / "result"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.result_dir / "data.txt"

        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write("=== Начало записи аудиофрагментов ===\n")

    def _get_device_index_by_name(self, target_name: str):
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            name = info.get('name')
            if target_name.lower() in name.lower() and info.get('maxInputChannels', 0) > 0:
                print(f"🎧 Выбрано устройство: [{i}] {name}")
                return i
        p.terminate()
        raise ValueError(f"Устройство ввода '{target_name}' не найдено")

    def list_input_devices(self):
        p = pyaudio.PyAudio()
        print("🎤 Доступные входные устройства:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                print(f"[{i}] {info['name']}")
        p.terminate()

    def set_audio_stream_listener(self, callback: IStreamCallback):
        if not isinstance(callback, IStreamCallback):
            raise TypeError("Callback должен реализовывать IStreamCallback")
        self._callback = callback
        self._start_recording()

    def _start_recording(self):
        self._is_recording = True
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            input=True,
            input_device_index=self._input_device_index,
            frames_per_buffer=self._chunk_size,
            stream_callback=self._audio_callback
        )

    def stop_audio_stream_receiving(self):
        self._is_recording = False
        if hasattr(self, '_stream'):
            self._stream.stop_stream()
            self._stream.close()
        if hasattr(self, '_audio'):
            self._audio.terminate()

        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write("=== Запись завершена ===\n")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if self._is_recording:
            self._frames.append(in_data)
            self._process_audio_buffer(in_data)
        return (in_data, pyaudio.paContinue)

    def _process_audio_buffer(self, in_data):
        audio_array = np.frombuffer(in_data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        self._rms_history.append(rms)

        avg_rms = np.mean(self._rms_history) if self._rms_history else 1
        silence_threshold = avg_rms * self._silence_threshold_factor

        if rms < silence_threshold:
            self._silence_frame_count += 1
        else:
            self._silence_frame_count = 0

        # Если тишина держится несколько кадров — записываем
        if self._silence_frame_count >= self._silence_required:
            # print(f"📉 Тихо (RMS {rms:.2f} < порога {silence_threshold:.2f}), проверяем время")
            self._save_frames_to_wav()
            # Массив фреймов очищается только после успешного сохранения
            if self._last_save_time is None or (time.time() - self._last_save_time) >= self._min_duration_seconds:
                self._frames.clear()  # Очищаем только после успешного сохранения
            self._silence_frame_count = 0
            self._rms_history.clear()

        # Обрезаем по максимуму
        max_buffer_seconds = 15
        max_frames = int(self._sample_rate * max_buffer_seconds / self._chunk_size)
        if len(self._frames) > max_frames:
            self._frames = self._frames[-max_frames:]

    def _save_frames_to_wav(self):
        # Проверяем продолжительность записи
        num_frames = len(self._frames)
        duration_seconds = num_frames * self._chunk_size / self._sample_rate

        # Если запись слишком короткая и прошло меньше 3 секунд с предыдущего сохранения, пропускаем
        if duration_seconds < self._min_duration_seconds:
            if self._last_save_time is None or (time.time() - self._last_save_time) < self._min_duration_seconds:
                # print(f"⏳ Запись слишком короткая ({duration_seconds:.2f} сек), продолжаем накопление данных")
                return  # Пропускаем сохранение, но продолжаем запись

        # Если запись слишком длинная — обрезаем
        if duration_seconds > self._max_duration_seconds:
            # print(f"⏳ Запись слишком длинная ({duration_seconds:.2f} сек), обрезаем")
            self._frames = self._frames[:int(self._sample_rate * self._max_duration_seconds / self._chunk_size)]

        # Сохраняем файл
        timestamp = int(time.time() * 1000)
        filename = f"rec_{timestamp}.wav"
        full_path = self.result_dir / filename
        wav_data = b''.join(self._frames)

        with wave.open(str(full_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(wav_data)

        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write(f"{time.ctime()} | {filename} | {len(wav_data)} байт\n")

        # Обновляем время последней записи
        self._last_save_time = time.time()

        # После успешной записи очищаем массив фреймов
        self._frames.clear()

        if self._callback:
            self._callback.do_on_audio_stream_playing(str(full_path))
