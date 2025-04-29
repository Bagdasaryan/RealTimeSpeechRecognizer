import pyaudio
import wave
import numpy as np
import time
from audio_stream_reader.istream_callback import IStreamCallback
from pathlib import Path
from collections import deque


class BaseAudioStreamReceiver:
    """Handles continuous audio stream reception with silence detection and automatic file saving.
    
    Attributes:
        _sample_rate: Audio sampling rate in Hz (default 16000)
        _chunk_size: Number of audio frames per buffer (default 480)
        _silence_threshold_factor: Multiplier for dynamic silence detection
        _min_duration_seconds: Minimum valid recording duration
        _max_duration_seconds: Maximum allowed recording duration
    """

    def __init__(self, device_name: str = "Stereo Mix (Realtek(R) Audio)"):
        """Initializes audio stream receiver with specified input device.
        
        Args:
            device_name: Name of the audio input device to use
        """
        self._callback = None
        self._is_recording = False
        self._sample_rate = 16000
        self._chunk_size = 480
        self._device_name = device_name
        self._input_device_index = self._get_device_index_by_name(self._device_name)

        # RMS analysis parameters
        self._frames = []
        self._rms_history = deque(maxlen=50)  # 50 frames (~1.5-2 seconds at 30-40ms/frame)
        self._silence_frame_count = 0
        self._silence_threshold_factor = 0.5  # Silence when RMS < average * 0.5
        self._silence_required = 13  # Consecutive silent frames to trigger detection

        # Recording duration limits (seconds)
        self._min_duration_seconds = 3
        self._max_duration_seconds = 8

        # Last save timestamp
        self._last_save_time = None

        # Output directory setup
        self.project_root = Path(__file__).parent.parent
        self.result_dir = self.project_root / "result"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.result_dir / "data.txt"

        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write("=== Audio recording session started ===\n")

    def _get_device_index_by_name(self, target_name: str) -> int:
        """Finds audio input device index by name.
        
        Args:
            target_name: Partial or complete device name
            
        Returns:
            Device index if found
            
        Raises:
            ValueError: If specified device is not found
        """
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            name = info.get('name')
            if target_name.lower() in name.lower() and info.get('maxInputChannels', 0) > 0:
                print(f"Selected device: [{i}] {name}")
                return i
        p.terminate()
        raise ValueError(f"Input device '{target_name}' not found")

    def list_input_devices(self) -> None:
        """Prints all available audio input devices."""
        p = pyaudio.PyAudio()
        print("Available input devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                print(f"[{i}] {info['name']}")
        p.terminate()

    def set_audio_stream_listener(self, callback: IStreamCallback) -> None:
        """Sets callback for audio stream events.
        
        Args:
            callback: Implementation of IStreamCallback interface
            
        Raises:
            TypeError: If callback doesn't implement IStreamCallback
        """
        if not isinstance(callback, IStreamCallback):
            raise TypeError("Callback must implement IStreamCallback")
        self._callback = callback
        self._start_recording()

    def _start_recording(self) -> None:
        """Initializes and starts audio stream recording."""
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

    def stop_audio_stream_receiving(self) -> None:
        """Stops audio recording and cleans up resources."""
        self._is_recording = False
        if hasattr(self, '_stream'):
            self._stream.stop_stream()
            self._stream.close()
        if hasattr(self, '_audio'):
            self._audio.terminate()

        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write("=== Recording session ended ===\n")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for processing incoming audio data."""
        if self._is_recording:
            self._frames.append(in_data)
            self._process_audio_buffer(in_data)
        return (in_data, pyaudio.paContinue)

    def _process_audio_buffer(self, in_data: bytes) -> None:
        """Analyzes audio buffer for silence detection and manages recording.
        
        Args:
            in_data: Raw audio data buffer
        """
        audio_array = np.frombuffer(in_data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        self._rms_history.append(rms)

        avg_rms = np.mean(self._rms_history) if self._rms_history else 1
        silence_threshold = avg_rms * self._silence_threshold_factor

        if rms < silence_threshold:
            self._silence_frame_count += 1
        else:
            self._silence_frame_count = 0

        # Trigger save on sustained silence
        if self._silence_frame_count >= self._silence_required:
            self._save_frames_to_wav()
            if self._last_save_time is None or (time.time() - self._last_save_time) >= self._min_duration_seconds:
                self._frames.clear()
            self._silence_frame_count = 0
            self._rms_history.clear()

        # Limit maximum buffer size
        max_buffer_seconds = 15
        max_frames = int(self._sample_rate * max_buffer_seconds / self._chunk_size)
        if len(self._frames) > max_frames:
            self._frames = self._frames[-max_frames:]

    def _save_frames_to_wav(self) -> None:
        """Saves accumulated audio frames to WAV file when conditions are met."""
        num_frames = len(self._frames)
        duration_seconds = num_frames * self._chunk_size / self._sample_rate

        # Skip if recording is too short and recent save exists
        if duration_seconds < self._min_duration_seconds:
            if self._last_save_time is None or (time.time() - self._last_save_time) < self._min_duration_seconds:
                return

        # Trim if recording is too long
        if duration_seconds > self._max_duration_seconds:
            self._frames = self._frames[:int(self._sample_rate * self._max_duration_seconds / self._chunk_size)]

        # Save WAV file
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
            f.write(f"{time.ctime()} | {filename} | {len(wav_data)} bytes\n")

        self._last_save_time = time.time()
        self._frames.clear()

        if self._callback:
            self._callback.do_on_audio_stream_playing(str(full_path))
