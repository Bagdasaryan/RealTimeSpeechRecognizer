import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk
import os
import time
import threading
import json
from pathlib import Path
from MyAudioCallback import MyAudioCallback

from audio_to_text.base_audio_to_text import BaseAudioToText
from audio_to_text.iaudio_to_text_callback import IAudioToTextCallback
from audio_stream_reader.istream_callback import IStreamCallback
from audio_stream_reader.base_audio_stream_receiver import BaseAudioStreamReceiver
from translate_text.base_translate_text import BaseTranslateText
from translate_text.itranslator_callback import ITranslatorCallback


class TranslatorApp(tk.Tk, ITranslatorCallback):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Загрузка локализации
        with open(Path(self.base_dir) / 'lexemes.json', 'r', encoding='utf-8') as f:
            self.lexemes = json.load(f)
        
        # Настройки по умолчанию
        self.current_lang = "en"
        self.current_theme = "light"
        self.translation_start_time = 0
        
        # Пути для сохранения
        self.translation_dir = Path("C:/translation_res")
        self.translation_dir.mkdir(exist_ok=True)
        self.results_info_file = Path(self.base_dir) / "result" / "info.txt"
        self.results_info_file.parent.mkdir(exist_ok=True)
        self.audio_results_dir = Path(self.base_dir) / "result"
        
        # Настройка окна
        self.title("Translator")
        self.geometry("800x600")
        self.minsize(800, 600)
        self.configure(bg="white")
        
        # Состояние приложения
        self.is_translating = False
        self.audio_callback = None
        self.receiver = None
        self.translation_thread = None
        self.api_available = True
        
        # Элементы интерфейса
        self.icons = {}
        self.nav_buttons = {}
        self.active_screen = None
        self.widgets_to_translate = {}
        
        # Инициализация
        self.load_icons()
        self.create_screens()
        self.create_bottom_nav()
        self.show_screen("Home")
        self.apply_theme()

    def t(self, key):
        """Функция перевода текста"""
        return self.lexemes[key][self.current_lang]

    def load_icons(self):
        icons_dir = os.path.join(self.base_dir, "icons")
        try:
            for name in ["home", "settings", "result"]:
                for state in ["enabled", "disabled"]:
                    path = os.path.join(icons_dir, f"{name}_{state}.png")
                    img = Image.open(path).resize((30, 30))
                    self.icons[f"{name}_{state}"] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading icons: {e}")
            placeholder = ImageTk.PhotoImage(Image.new("RGB", (30, 30), "gray"))
            for name in ["home", "settings", "result"]:
                self.icons[f"{name}_enabled"] = placeholder
                self.icons[f"{name}_disabled"] = placeholder

    def create_screens(self):
        # Экран Home
        self.home_frame = tk.Frame(self, bg="white")
        
        title = tk.Label(self.home_frame, text=self.t("LABEL_HOME"), 
                        font=("Arial", 20, "bold"), bg="white")
        title.pack(pady=(30, 10), anchor="w", padx=60)
        self.widgets_to_translate[title] = "LABEL_HOME"

        # Выбор языка исходного текста
        from_label = tk.Label(self.home_frame, text=self.t("TITLE_LABGUAGE_FROM"), 
                            font=("Arial", 12), bg="white", anchor="w")
        from_label.pack(padx=60, anchor="w")
        self.from_combo = ttk.Combobox(self.home_frame, 
                                     values=[self.t("VALUE_ENG"), self.t("VALUE_ARM")], 
                                     state="readonly", font=("Arial", 12))
        self.from_combo.current(0)  # По умолчанию английский
        self.from_combo.pack(padx=60, pady=(0, 20), anchor="w")
        self.widgets_to_translate[from_label] = "TITLE_LABGUAGE_FROM"
        self.widgets_to_translate[self.from_combo] = ("VALUE_ENG", "VALUE_ARM")

        # Выбор языка перевода
        to_label = tk.Label(self.home_frame, text=self.t("TITLE_LANGUAGE_TO"), 
                           font=("Arial", 12), bg="white", anchor="w")
        to_label.pack(padx=60, anchor="w")
        self.to_combo = ttk.Combobox(self.home_frame, 
                                   values=[self.t("VALUE_ENG"), self.t("VALUE_ARM")], 
                                   state="readonly", font=("Arial", 12))
        self.to_combo.current(1)  # По умолчанию армянский
        self.to_combo.pack(padx=60, pady=(0, 30), anchor="w")
        self.widgets_to_translate[to_label] = "TITLE_LANGUAGE_TO"
        self.widgets_to_translate[self.to_combo] = ("VALUE_ENG", "VALUE_ARM")

        # Кнопка перевода (черная с белым/черным текстом)
        self.translate_btn = tk.Button(
            self.home_frame, 
            text=self.t("BTN_RUN_TRANSLATION"), 
            bg="black", 
            fg="white", 
            font=("Arial", 12),
            width=20,
            height=2,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            command=self.toggle_translation
        )
        self.translate_btn.pack(pady=20)
        self.widgets_to_translate[self.translate_btn] = "BTN_RUN_TRANSLATION"

        # Текстовое поле для вывода
        self.text_area = scrolledtext.ScrolledText(
            self.home_frame, 
            wrap=tk.WORD, 
            font=("Arial", 12),
            padx=20,
            pady=20,
            height=10
        )
        self.text_area.pack(padx=40, pady=(0, 20), fill=tk.BOTH, expand=True)

        # Экран Settings
        self.settings_frame = tk.Frame(self, bg="white")
        settings_title = tk.Label(self.settings_frame, text=self.t("LABEL_SETTINGS"), 
                                font=("Arial", 20, "bold"), bg="white")
        settings_title.pack(pady=(30, 10), anchor="w", padx=60)
        self.widgets_to_translate[settings_title] = "LABEL_SETTINGS"

        # Язык интерфейса
        int_lang_label = tk.Label(self.settings_frame, text=self.t("LABEL_INTERFACE_LANG"), 
                                font=("Arial", 12), bg="white", anchor="w")
        int_lang_label.pack(padx=60, anchor="w")
        self.int_lang_combo = ttk.Combobox(self.settings_frame, 
                                         values=[self.t("VALUE_ENG"), self.t("VALUE_ARM")], 
                                         state="readonly", font=("Arial", 12))
        self.int_lang_combo.current(0)
        self.int_lang_combo.pack(padx=60, pady=(0, 20), anchor="w")
        self.int_lang_combo.bind("<<ComboboxSelected>>", self.change_interface_language)
        self.widgets_to_translate[int_lang_label] = "LABEL_INTERFACE_LANG"
        self.widgets_to_translate[self.int_lang_combo] = ("VALUE_ENG", "VALUE_ARM")

        # Тема
        theme_label = tk.Label(self.settings_frame, text=self.t("LABEL_THEME"), 
                             font=("Arial", 12), bg="white", anchor="w")
        theme_label.pack(padx=60, anchor="w")
        self.theme_combo = ttk.Combobox(self.settings_frame, 
                                      values=[self.t("VALUE_THEME_LIGHT"), self.t("VALUE_THEME_DARK")], 
                                      state="readonly", font=("Arial", 12))
        self.theme_combo.current(0)
        self.theme_combo.pack(padx=60, pady=(0, 20), anchor="w")
        self.theme_combo.bind("<<ComboboxSelected>>", self.change_theme)
        self.widgets_to_translate[theme_label] = "LABEL_THEME"
        self.widgets_to_translate[self.theme_combo] = ("VALUE_THEME_LIGHT", "VALUE_THEME_DARK")

        # Экран Results
        self.result_frame = tk.Frame(self, bg="white")
        result_title = tk.Label(self.result_frame, text=self.t("LABEL_RESULTS"), 
                              font=("Arial", 20, "bold"), bg="white")
        result_title.pack(pady=(30, 10), anchor="w", padx=60)
        self.widgets_to_translate[result_title] = "LABEL_RESULTS"
        
        self.result_text = tk.Text(
            self.result_frame,
            wrap=tk.WORD,
            font=("Arial", 12),
            padx=20,
            pady=20,
            height=15
        )
        self.result_text.pack(padx=40, pady=(0, 20), fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(self.result_frame, bg="white")
        btn_frame.pack(pady=10)
        self.load_results_btn = tk.Button(
            btn_frame,
            text=self.t("LABEL_RESULTS"),
            command=self.load_results,
            bg="black",
            fg="white",
            font=("Arial", 12),
            width=15
        )
        self.load_results_btn.pack(side="left", padx=10)
        self.widgets_to_translate[self.load_results_btn] = "LABEL_RESULTS"

        self.screens = {
            "Home": self.home_frame,
            "Settings": self.settings_frame,
            "Result": self.result_frame
        }

    def create_bottom_nav(self):
        nav_frame = tk.Frame(self, bg="#f5f5f5", height=60)
        nav_frame.pack(side="bottom", fill="x")
        nav_frame.pack_propagate(False)

        nav_items = [
            ("Home", "LABEL_HOME"),
            ("Settings", "LABEL_SETTINGS"),
            ("Result", "LABEL_RESULT")
        ]

        for name, lexeme in nav_items:
            btn_frame = tk.Frame(nav_frame, bg="#f5f5f5")
            btn_frame.pack(side="left", expand=True, fill="both")

            underline = tk.Frame(btn_frame, bg="#f5f5f5", height=3)
            underline.pack(side="bottom", fill="x")

            icon_label = tk.Label(btn_frame, image=self.icons[f"{name.lower()}_disabled"], bg="#f5f5f5")
            icon_label.pack(pady=(5, 0))
            
            text_label = tk.Label(btn_frame, text=self.t(lexeme), font=("Arial", 12), bg="#f5f5f5")
            text_label.pack()

            for widget in [btn_frame, icon_label, text_label]:
                widget.bind("<Button-1>", lambda e, n=name: self.show_screen(n))

            self.nav_buttons[name] = {
                "frame": btn_frame,
                "icon": icon_label,
                "text": text_label,
                "underline": underline,
                "lexeme": lexeme
            }

    def show_screen(self, screen_name):
        if self.active_screen == screen_name:
            return

        if self.active_screen:
            self.screens[self.active_screen].pack_forget()

        self.screens[screen_name].pack(fill="both", expand=True)

        for name, btn in self.nav_buttons.items():
            if name == screen_name:
                btn["icon"].configure(image=self.icons[f"{name.lower()}_enabled"])
                btn["text"].configure(fg="black", font=("Arial", 12, "bold"))
                btn["underline"].configure(bg="black")
            else:
                btn["icon"].configure(image=self.icons[f"{name.lower()}_disabled"])
                btn["text"].configure(fg="black", font=("Arial", 12))
                btn["underline"].configure(bg="#f5f5f5")

        self.active_screen = screen_name

    def toggle_translation(self):
        if not self.is_translating:
            self.start_translation()
        else:
            self.stop_translation()

    def start_translation(self):
        self.is_translating = True
        self.translate_btn.config(text=self.t("BTN_STOP_TRANSLATION"))
        self.from_combo.config(state="disabled")
        self.to_combo.config(state="disabled")
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, "Starting translation...\n")
        
        self.translation_start_time = int(time.time() * 1000)
        source_lang = "en" if self.from_combo.get() == self.t("VALUE_ENG") else "hy"
        target_lang = "en" if self.to_combo.get() == self.t("VALUE_ENG") else "hy"
        
        self.translation_thread = threading.Thread(
            target=self.run_translation,
            args=(source_lang, target_lang),
            daemon=True
        )
        self.translation_thread.start()

    def stop_translation(self):
        self.is_translating = False
        self.translate_btn.config(text=self.t("BTN_RUN_TRANSLATION"))
        self.from_combo.config(state="readonly")
        self.to_combo.config(state="readonly")
        
        # Сохраняем результат перевода
        translation_result = self.text_area.get(1.0, tk.END).strip()
        if translation_result and not translation_result.startswith("Starting translation"):
            self.save_translation_result(translation_result)
        
        # Останавливаем сервисы
        if self.receiver:
            self.receiver.stop_audio_stream_receiving()
        if self.audio_callback:
            try:
                self.audio_callback.stop()
            except Exception as e:
                print(f"Error stopping callback: {e}")
        
        # Удаляем временные файлы
        self.cleanup_audio_files()

    def run_translation(self, source_lang: str, target_lang: str):
        try:
            self.audio_callback = MyAudioCallback()
            self.audio_callback.translator.set_text_translator_listener(self)
            
            try:
                test_result = self.audio_callback.translator.translate("test", source_lang, target_lang)
                if test_result is None:
                    raise ConnectionError("API недоступен")
                self.api_available = True
                self.text_area.insert(tk.END, "Translation started successfully...\n")
            except Exception as api_error:
                self.api_available = False
                self.text_area.insert(tk.END, f"Using offline mode: {api_error}\n")
            
            self.audio_callback.translator.set_default_languages(source_lang, target_lang)
            
            self.receiver = BaseAudioStreamReceiver()
            self.receiver.set_audio_stream_listener(self.audio_callback)
            
            while self.is_translating:
                time.sleep(0.1)
                
        except Exception as e:
            self.text_area.insert(tk.END, f"\nError: {str(e)}\n")
        finally:
            if hasattr(self, 'receiver') and self.receiver:
                self.receiver.stop_audio_stream_receiving()
            if hasattr(self, 'audio_callback') and self.audio_callback:
                try:
                    self.audio_callback.stop()
                except:
                    pass

    def do_on_text_translated(self, text):
        """Callback для переведенного текста"""
        self.text_area.insert(tk.END, f"{text}\n")
        self.text_area.see(tk.END)

    def change_interface_language(self, event):
        selected = self.int_lang_combo.get()
        lang = "en" if selected == self.t("VALUE_ENG") else "hy"
        
        if lang != self.current_lang:
            self.current_lang = lang
            self.update_ui_language()
    
    def update_ui_language(self):
        """Обновляет весь интерфейс при смене языка"""
        # Сохраняем текущие выборы в комбобоксах
        from_val = self.from_combo.get()
        to_val = self.to_combo.get()
        int_lang_val = self.int_lang_combo.get()
        theme_val = self.theme_combo.get()
        
        for widget, lexeme in self.widgets_to_translate.items():
            if isinstance(lexeme, tuple):
                # Обновляем значения комбобоксов
                new_values = [self.t(l) for l in lexeme]
                widget['values'] = new_values
                
                # Восстанавливаем выбор
                if widget == self.from_combo:
                    try:
                        idx = new_values.index(from_val)
                        widget.current(idx)
                    except ValueError:
                        widget.current(0)
                elif widget == self.to_combo:
                    try:
                        idx = new_values.index(to_val)
                        widget.current(idx)
                    except ValueError:
                        widget.current(1)
                elif widget == self.int_lang_combo:
                    try:
                        idx = new_values.index(int_lang_val)
                        widget.current(idx)
                    except ValueError:
                        widget.current(0)
                elif widget == self.theme_combo:
                    try:
                        idx = new_values.index(theme_val)
                        widget.current(idx)
                    except ValueError:
                        widget.current(0)
            else:
                # Обновляем текст виджетов
                if hasattr(widget, 'config'):
                    widget.config(text=self.t(lexeme))
        
        # Обновляем нижнее меню
        for name, btn in self.nav_buttons.items():
            btn["text"].config(text=self.t(btn["lexeme"]))
        
        # Обновляем текст кнопки перевода
        if self.is_translating:
            self.translate_btn.config(text=self.t("BTN_STOP_TRANSLATION"))
        else:
            self.translate_btn.config(text=self.t("BTN_RUN_TRANSLATION"))

    def change_theme(self, event):
        selected = self.theme_combo.get()
        theme = "light" if selected == self.t("VALUE_THEME_LIGHT") else "dark"
        
        if theme != self.current_theme:
            self.current_theme = theme
            self.apply_theme()
    
    def apply_theme(self):
        """Применяет выбранную тему"""
        try:
            if self.current_theme == "dark":
                bg_color = "#2d2d2d"
                fg_color = "#ffffff"
                text_bg = "#3d3d3d"
                btn_bg = "#4d4d4d"
                btn_fg = "#ffffff"  # Белый текст для темной темы
                highlight_color = "#666666"
            else:
                bg_color = "#ffffff"
                fg_color = "#000000"
                text_bg = "#f5f5f5"
                btn_bg = "black"
                btn_fg = "white"  # Белый текст для светлой темы
                highlight_color = "black"
            
            # Основное окно
            self.config(bg=bg_color)
            
            # Функция для безопасного изменения виджетов
            def safe_config(widget, **kwargs):
                if hasattr(widget, 'config'):
                    try:
                        widget.config(**kwargs)
                    except tk.TclError:
                        pass
            
            # Применяем к фреймам
            for frame in [self.home_frame, self.settings_frame, self.result_frame]:
                safe_config(frame, bg=bg_color)
                for widget in frame.winfo_children():
                    if isinstance(widget, (tk.Label, tk.Button)):
                        safe_config(widget, bg=bg_color, fg=fg_color)
                    elif isinstance(widget, tk.Frame):
                        safe_config(widget, bg=bg_color)
                    elif isinstance(widget, (scrolledtext.ScrolledText, tk.Text)):
                        safe_config(widget, bg=text_bg, fg=fg_color, insertbackground=fg_color)
            
            # Кнопка перевода (особый случай)
            safe_config(self.translate_btn, bg=btn_bg, fg=btn_fg)
            
            # Стиль для Combobox
            style = ttk.Style()
            style.theme_use('clam')
            style.configure("TCombobox", 
                          fieldbackground=text_bg,
                          background=text_bg,
                          foreground=fg_color)
            
            # Нижнее меню
            for name, btn in self.nav_buttons.items():
                safe_config(btn["frame"], bg=bg_color)
                safe_config(btn["icon"], bg=bg_color)
                safe_config(btn["text"], bg=bg_color, fg=fg_color)
                
                underline_color = highlight_color if name == self.active_screen else bg_color
                safe_config(btn["underline"], bg=underline_color)
                
                font = ("Arial", 12, "bold") if name == self.active_screen else ("Arial", 12)
                safe_config(btn["text"], font=font)
                
        except Exception as e:
            print(f"Error applying theme: {e}")

    def cleanup_audio_files(self):
        """Удаляет временные аудиофайлы"""
        try:
            if self.audio_results_dir.exists():
                for file in self.audio_results_dir.glob("*.wav"):
                    try:
                        file.unlink()
                    except Exception as e:
                        print(f"Error deleting audio file {file}: {e}")
        except Exception as e:
            print(f"Error cleaning audio files: {e}")

    def save_translation_result(self, result: str):
        """Сохраняет результат перевода"""
        try:
            # Создаем имя файла на основе времени начала перевода
            filename = f"rec_{self.translation_start_time}.txt"
            filepath = self.translation_dir / filename
            
            # Сохраняем перевод
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)
            
            # Добавляем запись в info.txt
            with open(self.results_info_file, 'a', encoding='utf-8') as f:
                f.write(f"{filepath}\n")
                
            self.text_area.insert(tk.END, f"\nResults saved to: {filepath}\n")
        except Exception as e:
            self.text_area.insert(tk.END, f"\nError saving results: {str(e)}\n")

    def load_results(self):
        """Загружает историю переводов"""
        try:
            self.result_text.delete(1.0, tk.END)
            
            if not self.results_info_file.exists():
                self.result_text.insert(tk.END, "No translation history found")
                return
                
            with open(self.results_info_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                
            if not lines:
                self.result_text.insert(tk.END, "Translation history is empty")
                return
            
            for filepath in reversed(lines):
                if not filepath:
                    continue
                
                # Создаем кликабельную ссылку
                path = Path(filepath)
                link = tk.Label(
                    self.result_text,
                    text=path.name,
                    fg="blue",
                    cursor="hand2",
                    font=("Arial", 12, "underline")
                )
                link.bind("<Button-1>", lambda e, p=filepath: self.open_result_file(p))
                self.result_text.window_create(tk.END, window=link)
                self.result_text.insert(tk.END, "\n\n")
                
        except Exception as e:
            self.result_text.insert(tk.END, f"Error loading history: {str(e)}")

    def open_result_file(self, filepath):
        """Открывает файл с результатом перевода"""
        try:
            os.startfile(filepath)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open file: {str(e)}")

    def on_closing(self):
        self.stop_translation()
        self.destroy()

if __name__ == "__main__":
    app = TranslatorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
