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
        self.translation_stop_time = 0
        
        # Пути для сохранения
        self.translation_dir = Path(self.base_dir) / "translations"
        self.results_info_file = Path(self.base_dir) / "result" / "res.txt"
        self.audio_results_dir = Path(self.base_dir) / "result"
        
        # Буфер для накопления переведенного текста
        self.translation_buffer = []
        
        # Создаем директории при инициализации
        self._ensure_directories_exist()
        
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
        self.current_selections = {
            "from_lang": 0,
            "to_lang": 1,
            "interface_lang": 0,
            "theme": 0
        }
        
        # Инициализация
        self.load_icons()
        self.create_screens()
        self.create_bottom_nav()
        self.show_screen("Home")
        self.apply_theme()

    def _ensure_directories_exist(self):
        """Создает все необходимые директории, если они не существуют"""
        try:
            self.translation_dir.mkdir(parents=True, exist_ok=True)
            self.results_info_file.parent.mkdir(parents=True, exist_ok=True)
            self.audio_results_dir.mkdir(parents=True, exist_ok=True)
            
            # Создаем файл res.txt, если его нет
            if not self.results_info_file.exists():
                with open(self.results_info_file, 'w', encoding='utf-8') as f:
                    f.write("")
        except Exception as e:
            print(f"Error creating directories: {e}")
            messagebox.showerror("Error", f"Failed to create directories: {str(e)}")

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
        self.from_combo.current(self.current_selections["from_lang"])
        self.from_combo.pack(padx=60, pady=(0, 20), anchor="w")
        self.from_combo.bind("<<ComboboxSelected>>", lambda e: self.update_current_selection("from_lang"))
        self.widgets_to_translate[from_label] = "TITLE_LABGUAGE_FROM"
        self.widgets_to_translate[self.from_combo] = ("VALUE_ENG", "VALUE_ARM")

        # Выбор языка перевода
        to_label = tk.Label(self.home_frame, text=self.t("TITLE_LANGUAGE_TO"), 
                           font=("Arial", 12), bg="white", anchor="w")
        to_label.pack(padx=60, anchor="w")
        self.to_combo = ttk.Combobox(self.home_frame, 
                                   values=[self.t("VALUE_ENG"), self.t("VALUE_ARM")], 
                                   state="readonly", font=("Arial", 12))
        self.to_combo.current(self.current_selections["to_lang"])
        self.to_combo.pack(padx=60, pady=(0, 30), anchor="w")
        self.to_combo.bind("<<ComboboxSelected>>", lambda e: self.update_current_selection("to_lang"))
        self.widgets_to_translate[to_label] = "TITLE_LANGUAGE_TO"
        self.widgets_to_translate[self.to_combo] = ("VALUE_ENG", "VALUE_ARM")

        # Кнопка перевода
        self.translate_btn = tk.Button(
            self.home_frame, 
            text=self.t("BTN_RUN_TRANSLATION"), 
            bg="black", 
            fg="white", 
            font=("Arial", 12),
            width=30,
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
        self.int_lang_combo.current(self.current_selections["interface_lang"])
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
        self.theme_combo.current(self.current_selections["theme"])
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
        
        # Контейнер для списка результатов
        self.results_container = tk.Frame(self.result_frame, bg="white")
        self.results_container.pack(padx=40, pady=(0, 20), fill=tk.BOTH, expand=True)
        
        # Полоса прокрутки
        self.results_canvas = tk.Canvas(self.results_container, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.results_container, orient="vertical", command=self.results_canvas.yview)
        self.scrollable_frame = tk.Frame(self.results_canvas, bg="white")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(
                scrollregion=self.results_canvas.bbox("all")
            )
        )
        
        self.results_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.results_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
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
        
        if screen_name == "Result":
            self.load_results()

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
        
        self.translation_stop_time = int(time.time() * 1000)
        
        # Сохраняем все накопленные переводы в один файл
        if self.translation_buffer:
            self.save_translation_result("\n".join(self.translation_buffer))
            self.translation_buffer = []  # Очищаем буфер
        
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
        # Добавляем текст в буфер вместо сохранения в файл
        self.translation_buffer.append(text)

    def change_interface_language(self, event):
        selected = self.int_lang_combo.get()
        lang = "en" if selected == self.t("VALUE_ENG") else "hy"
        
        if lang != self.current_lang:
            self.current_lang = lang
            self.update_current_selection("interface_lang")
            self.update_ui_language()
    
    def update_current_selection(self, key):
        """Обновляет текущие выбранные значения комбобоксов"""
        if key == "from_lang":
            self.current_selections["from_lang"] = self.from_combo.current()
        elif key == "to_lang":
            self.current_selections["to_lang"] = self.to_combo.current()
        elif key == "interface_lang":
            self.current_selections["interface_lang"] = self.int_lang_combo.current()
        elif key == "theme":
            self.current_selections["theme"] = self.theme_combo.current()
    
    def update_ui_language(self):
        """Обновляет весь интерфейс при смене языка"""
        # Обновляем виджеты
        for widget, lexeme in self.widgets_to_translate.items():
            if isinstance(lexeme, tuple):
                # Обновляем значения комбобоксов
                new_values = [self.t(l) for l in lexeme]
                widget['values'] = new_values
                
                # Восстанавливаем выбор
                if widget == self.from_combo:
                    widget.current(self.current_selections["from_lang"])
                elif widget == self.to_combo:
                    widget.current(self.current_selections["to_lang"])
                elif widget == self.int_lang_combo:
                    widget.current(self.current_selections["interface_lang"])
                elif widget == self.theme_combo:
                    widget.current(self.current_selections["theme"])
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
            self.update_current_selection("theme")
            self.apply_theme()
    
    def apply_theme(self):
        """Применяет выбранную тему"""
        try:
            if self.current_theme == "dark":
                bg_color = "#1e1e1e"
                fg_color = "#e0e0e0"
                text_bg = "#2d2d2d"
                btn_bg = "#3a3a3a"
                btn_fg = "#ffffff"
                highlight_color = "#4d4d4d"
                combobox_bg = "#333333"
                combobox_fg = "#ffffff"
                combobox_border = "#666666"
                nav_bg = "#2a2a2a"
                nav_highlight = "#3a3a3a"
            else:
                bg_color = "#ffffff"
                fg_color = "#000000"
                text_bg = "#f5f5f5"
                btn_bg = "black"
                btn_fg = "white"
                highlight_color = "black"
                combobox_bg = "#ffffff"
                combobox_fg = "#000000"
                combobox_border = "#000000"
                nav_bg = "#f5f5f5"
                nav_highlight = "#e0e0e0"
            
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
            
            # Кнопка перевода
            safe_config(self.translate_btn, bg=btn_bg, fg=btn_fg)
            
            # Стиль для Combobox с рамкой
            style = ttk.Style()
            style.theme_use('clam')
            style.configure("TCombobox", 
                          fieldbackground=combobox_bg,
                          background=combobox_bg,
                          foreground=combobox_fg,
                          bordercolor=combobox_border,
                          lightcolor=combobox_border,
                          darkcolor=combobox_border,
                          arrowsize=15,
                          padding=10,
                          relief="solid",
                          borderwidth=1)
            
            style.map('TCombobox', 
                     fieldbackground=[('readonly', combobox_bg)],
                     background=[('readonly', combobox_bg)],
                     foreground=[('readonly', combobox_fg)],
                     bordercolor=[('readonly', combobox_border)],
                     lightcolor=[('readonly', combobox_border)],
                     darkcolor=[('readonly', combobox_border)])
            
            # Настройка закругленных углов для кнопок
            style.configure("TButton",
                          borderwidth=1,
                          relief="solid",
                          padding=6,
                          bordercolor=btn_bg,
                          background=btn_bg,
                          foreground=btn_fg)
            
            style.map("TButton",
                    background=[('active', btn_bg)],
                    foreground=[('active', btn_fg)])
            
            # Нижнее меню
            nav_frame = self.nav_buttons["Home"]["frame"].master
            safe_config(nav_frame, bg=nav_bg)
            
            # Добавляем прямоугольник с закругленными краями под нижним меню для темной темы
            if hasattr(self, 'nav_highlight_frame'):
                self.nav_highlight_frame.destroy()
            
            if self.current_theme == "dark":
                self.nav_highlight_frame = tk.Frame(
                    self,
                    bg="#3a3a3a",
                    height=62,
                    bd=0,
                    highlightthickness=0
                )
                self.nav_highlight_frame.place(relx=0.5, rely=1.0, anchor="s", relwidth=1.0)
                self.nav_highlight_frame.lower(nav_frame)
                self.nav_highlight_frame.config(highlightbackground="#3a3a3a")
            
            for name, btn in self.nav_buttons.items():
                safe_config(btn["frame"], bg=nav_bg)
                safe_config(btn["icon"], bg=nav_bg)
                safe_config(btn["text"], bg=nav_bg, fg=fg_color)
                
                underline_color = nav_highlight if name == self.active_screen else nav_bg
                safe_config(btn["underline"], bg=underline_color)
                
                font = ("Arial", 12, "bold") if name == self.active_screen else ("Arial", 12)
                safe_config(btn["text"], font=font)
                
            # Настройка скроллируемого фрейма результатов
            if hasattr(self, 'results_container'):
                safe_config(self.results_container, bg=bg_color)
                safe_config(self.results_canvas, bg=bg_color)
                safe_config(self.scrollable_frame, bg=bg_color)
                
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
        """Сохраняет результат перевода в один файл"""
        try:
            # Создаем имя файла на основе времени остановки перевода
            filename = f"translation_{self.translation_stop_time}.txt"
            filepath = self.translation_dir / filename
            
            # Убедимся, что директория существует
            self.translation_dir.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем весь накопленный перевод
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)
            
            # Убедимся, что директория для res.txt существует
            self.results_info_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Добавляем запись в res.txt
            with open(self.results_info_file, 'a', encoding='utf-8') as f:
                f.write(f"{filepath}\n")
                
            self.text_area.insert(tk.END, f"\nAll translations saved to: {filepath}\n")
            print(f"Saved all translations to: {filepath}")
        except Exception as e:
            error_msg = f"\nError saving results: {str(e)}\n"
            self.text_area.insert(tk.END, error_msg)
            print(error_msg)
            messagebox.showerror("Error", f"Failed to save results: {str(e)}")

    def load_results(self):
        """Загружает историю переводов"""
        try:
            # Очищаем предыдущие результаты
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            # Проверяем существование файла и его содержимое
            if not self.results_info_file.exists():
                no_results_label = tk.Label(
                    self.scrollable_frame, 
                    text=self.t("NO_RESULTS_FOUND"),
                    font=("Arial", 12),
                    bg="white" if self.current_theme == "light" else "#1e1e1e",
                    fg="black" if self.current_theme == "light" else "#e0e0e0"
                )
                no_results_label.pack(pady=20)
                return
                
            with open(self.results_info_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                
            if not lines:
                no_results_label = tk.Label(
                    self.scrollable_frame, 
                    text=self.t("NO_RESULTS_FOUND"),
                    font=("Arial", 12),
                    bg="white" if self.current_theme == "light" else "#1e1e1e",
                    fg="black" if self.current_theme == "light" else "#e0e0e0"
                )
                no_results_label.pack(pady=20)
                return
            
            # Отображаем результаты в обратном порядке (новые сверху)
            for filepath in reversed(lines):
                if not filepath:
                    continue
                
                try:
                    # Получаем только имя файла из полного пути
                    filename = Path(filepath).name
                    
                    # Создаем кликабельную кнопку для каждого результата
                    result_frame = tk.Frame(
                        self.scrollable_frame,
                        bg="white" if self.current_theme == "light" else "#2d2d2d"
                    )
                    result_frame.pack(fill="x", pady=2, padx=5)
                    
                    result_btn = tk.Button(
                        result_frame,
                        text=filename,
                        font=("Arial", 12),
                        bg="white" if self.current_theme == "light" else "#2d2d2d",
                        fg="blue",
                        relief="flat",
                        bd=0,
                        anchor="w",
                        padx=10,
                        pady=5,
                        cursor="hand2"
                    )
                    result_btn.bind("<Button-1>", lambda e, p=filepath: self.open_result_file(p))
                    result_btn.pack(fill="x")
                    
                    # Разделитель
                    separator = tk.Frame(
                        result_frame,
                        height=1,
                        bg="#e0e0e0" if self.current_theme == "light" else "#3a3a3a"
                    )
                    separator.pack(fill="x", padx=10)
                    
                except Exception as e:
                    print(f"Error loading result {filepath}: {e}")
                    continue
                
        except Exception as e:
            error_label = tk.Label(
                self.scrollable_frame, 
                text=f"Error loading history: {str(e)}",
                font=("Arial", 12),
                bg="white" if self.current_theme == "light" else "#1e1e1e",
                fg="red"
            )
            error_label.pack(pady=20)

    def open_result_file(self, filepath):
        """Открывает файл с результатом перевода в проводнике"""
        try:
            path = Path(filepath)
            if path.exists():
                os.startfile(path.parent)
            else:
                messagebox.showerror("Error", f"File not found: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open file: {str(e)}")

    def on_closing(self):
        self.stop_translation()
        self.destroy()

if __name__ == "__main__":
    app = TranslatorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
