# This is the main file for the Karaoke app.
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import librosa
import numpy as np
import pretty_midi
import soundfile as sf
import pygame
import time

# --- Pygame Mixerのダミー実装 (前回と同様) ---


class DummyPygameMixer:
    def __init__(self): print("INFO: Initializing DummyPygameMixer.")
    def init(self, *args, **kwargs): print("DummyPygameMixer: init called.")

    class music:
        _is_playing = False
        _is_paused = False
        _load_filepath = None
        _playback_start_sim_time = 0
        _paused_sim_pos = 0

        @staticmethod
        def load(filepath): print(
            f"DummyPygameMixer.music: load('{filepath}') called."); DummyPygameMixer.music._load_filepath = filepath

        @staticmethod
        def play(loops=0):
            print(f"DummyPygameMixer.music: play(loops={loops}) called.")
            DummyPygameMixer.music._is_playing = True
            DummyPygameMixer.music._is_paused = False
            DummyPygameMixer.music._playback_start_sim_time = time.time()
            DummyPygameMixer.music._paused_sim_pos = 0

        @staticmethod
        def pause():
            print("DummyPygameMixer.music: pause() called.")
            if DummyPygameMixer.music._is_playing and not DummyPygameMixer.music._is_paused:
                DummyPygameMixer.music._paused_sim_pos = time.time(
                ) - DummyPygameMixer.music._playback_start_sim_time
                DummyPygameMixer.music._is_paused = True

        @staticmethod
        def unpause():
            print("DummyPygameMixer.music: unpause() called.")
            if DummyPygameMixer.music._is_playing and DummyPygameMixer.music._is_paused:
                DummyPygameMixer.music._playback_start_sim_time += (time.time(
                ) - DummyPygameMixer.music._playback_start_sim_time) - DummyPygameMixer.music._paused_sim_pos
                DummyPygameMixer.music._is_paused = False

        @staticmethod
        def stop():
            print("DummyPygameMixer.music: stop() called.")
            DummyPygameMixer.music._is_playing = False
            DummyPygameMixer.music._is_paused = False
            DummyPygameMixer.music._playback_start_sim_time = 0
            DummyPygameMixer.music._paused_sim_pos = 0

        @staticmethod
        def get_pos():
            if DummyPygameMixer.music._is_playing:
                if DummyPygameMixer.music._is_paused:
                    return int(DummyPygameMixer.music._paused_sim_pos * 1000)
                else:
                    return int((time.time() - DummyPygameMixer.music._playback_start_sim_time) * 1000)
            return -1

        @staticmethod
        def get_busy(): return DummyPygameMixer.music._is_playing and not DummyPygameMixer.music._is_paused


use_dummy_mixer = False
try:
    pygame.mixer.init()
    print("INFO: Pygame mixer initialized successfully.")
except Exception as e:
    print(f"WARNING: Failed to initialize pygame.mixer: {type(e).__name__} - {e}. Using dummy mixer.")
    # pygame.mixer = DummyPygameMixer() # ダミーへの差し替えを解除
    # use_dummy_mixer = True # このフラグはmixer初期化の成否で判断する
    pass # try-exceptの構造を維持するため何かしら必要

# --- Tkinterダミークラス拡張 (前回と同様) ---
# これらのダミークラス定義は残すが、if __name__ == "__main__": での差し替えは行わない
class DummyMaster:
    def __init__(self): self.title_val = ""; self._windowingsystem = 'x11'; self.after_ids = {
    }; self.last_after_id = 0

    def title(self, val): self.title_val = val
    def cget(self, option): return self.title_val if option == "title" else ""
    def pack(self, **kwargs): print(f"DummyMaster: pack({kwargs}) called.")
    def winfo_exists(self): return True
    def lift(self): print("DummyMaster: lift() called")
    def protocol(self, name, func): print(
        f"DummyMaster: protocol({name}) set with {func}.")

    def destroy(self): print("DummyMaster: destroy() called.")

    def after(self, ms, func, *args):
        self.last_after_id += 1
        print(
            f"DummyMaster: after(id={self.last_after_id}, ms={ms}, func={func.__name__}) scheduled.")
        self.after_ids[self.last_after_id] = func
        return self.last_after_id

    def after_cancel(self, id_):
        if id_ in self.after_ids:
            print(
                f"DummyMaster: after_cancel(id={id_}, func={self.after_ids.pop(id_).__name__}) called.")
        else:
            print(
                f"DummyMaster: after_cancel(id={id_}) called, but ID not found.")


class DummyFrame(DummyMaster):
    def __init__(self, master, **kwargs): super().__init__()
    def pack(self, **kwargs): print(f"DummyFrame: pack({kwargs}) called.")
    def grid(self, **kwargs): print(f"DummyFrame: grid({kwargs}) called.")


class DummyWidget(DummyMaster):
    def __init__(self, master, text="", width=0, height=0, bg="", command=None, **kwargs):
        super().__init__()
        self._text = text
        self._command = command
        self._master = master
        self._kwargs = kwargs  # Store all kwargs for potential reference in logs
        log_cmd = f", command={command.__name__}" if command else ""
        # More detailed creation log, including the type of widget if possible
        widget_type = self.__class__.__name__ if self.__class__.__name__ != "DummyWidget" else "Widget"
        print(
            f"DummyWidget: {widget_type} created for master {type(master).__name__} with text='{text}'{log_cmd} (kwargs={kwargs})")

    def config(self, text="", **kwargs):
        if text:
            self._text = text
        # Log all config changes, not just text
        print(
            f"DummyWidget ({self._kwargs.get('text', self._text)}): config(text='{self._text}', new_kwargs={kwargs}) called.")

    # Simplified cget
    def cget(self, option): return self._text if option == "text" else ""

    def pack(self, **kwargs): print(
        f"DummyWidget ({self._kwargs.get('text', self._text)}): pack({kwargs}) called.")

    def grid(self, **kwargs): print(
        f"DummyWidget ({self._kwargs.get('text', self._text)}): grid({kwargs}) called.")

    def delete(self, item): print(
        f"DummyCanvas ({self._kwargs.get('bg', 'canvas')}): delete('{item}') called.")

    def create_rectangle(self, *args, **kwargs): print(
        f"DummyCanvas ({self._kwargs.get('bg', 'canvas')}): create_rectangle({args}, {kwargs}) called.")
    def create_line(self, *args, **kwargs): print(
        f"DummyCanvas ({self._kwargs.get('bg', 'canvas')}): create_line({args}, {kwargs}) called.")

# --- KaraokeAppクラス (前回から変更なしの部分はコメントで省略) ---


class KaraokeApp:
    NOTE_HEIGHT = 10
    SECONDS_PER_SCREEN = 10
    PIXELS_PER_SECOND = 60
    CURSOR_X_POSITION = 150
    CURSOR_COLOR = "red"
    NOTE_COLOR = "blue"
    FUTURE_NOTE_COLOR = "cyan"
    PAST_NOTE_COLOR = "gray"
    MIN_MIDI_PITCH = 40
    MAX_MIDI_PITCH = 84
    PITCH_RANGE = MAX_MIDI_PITCH - MIN_MIDI_PITCH + 1
    REFRESH_INTERVAL_MS = 30

    def __init__(self, master):
        self.master = master
        master.title("カラオケアプリ")
        self.prepared_vocal_wav = os.path.join("outData", "vocal.wav")
        self.prepared_accompaniment_wav = os.path.join(
            "outData", "accompaniment.wav")
        self.vocal_midi_filepath = os.path.join("outData", "vocal.mid")
        self.midi_data = None
        self.notes = []
        self.is_playing = False
        self.is_paused = False
        self.current_note_index = 0
        self.playback_start_time = 0
        self.paused_position = 0
        self.update_loop_id = None
        # GUI要素の初期化 (ダミーwidgetが使われる)
        self.main_status_label = tk.Label(
            self.master, text="初期状態")  # masterを渡す
        self.main_status_label.pack()
        self.karaoke_window = None
        self.play_pause_button_karaoke = None
        self.pitch_canvas = None
        print("INFO: KaraokeApp initialized.")

    # --- dummy_audio_selection_and_preparation (テスト用に簡略化または削除、テストケース側で準備) ---
    def select_and_prepare_files(self, vocal_src_path, acc_src_path):
        print(
            f"INFO: Preparing files: vocal='{vocal_src_path}', acc='{acc_src_path}'")
        os.makedirs("outData", exist_ok=True)
        if vocal_src_path and os.path.exists(vocal_src_path):
            shutil.copy(vocal_src_path, self.prepared_vocal_wav)
            print(
                f"INFO: Copied {vocal_src_path} to {self.prepared_vocal_wav}")
        else:
            print(
                f"WARNING: Vocal source '{vocal_src_path}' not found or not provided.")
        if acc_src_path and os.path.exists(acc_src_path):
            shutil.copy(acc_src_path, self.prepared_accompaniment_wav)
            print(
                f"INFO: Copied {acc_src_path} to {self.prepared_accompaniment_wav}")
        else:
            print(
                f"WARNING: Accompaniment source '{acc_src_path}' not found or not provided.")
        self.main_status_label.config(text="ファイル準備完了（シミュレート）。")

    def convert_vocal_to_midi(self):  # _wrapper と _logic を統合
        print("INFO: --- Running Vocal to MIDI Conversion ---")
        if not os.path.exists(self.prepared_vocal_wav):
            self.main_status_label.config(
                text=f"エラー: {self.prepared_vocal_wav} が見つかりません。")
            print(
                f"ERROR: {self.prepared_vocal_wav} not found for MIDI conversion.")
            return False  # 失敗を示す
        try:
            y, sr = librosa.load(self.prepared_vocal_wav, sr=None)
            if len(y) == 0:
                self.main_status_label.config(text="エラー: 音声ファイルが空です。")
                return False
            hop_length = int(sr * 0.01)
            fmin = librosa.note_to_hz('C2')
            fmax = librosa.note_to_hz('C6')
            pitches, magnitudes = librosa.piptrack(
                y=y, sr=sr, hop_length=hop_length, fmin=fmin, fmax=fmax, threshold=0.1)
            notes_for_midi = []  # ... (ノート抽出ロジック - 前回と同様、ここでは簡略化のため省略しない)
            frame_duration = hop_length / float(sr)
            active_note_midi = None
            active_note_start_time = 0
            active_note_velocities = []
            for t_idx in range(pitches.shape[1]):
                max_mag_idx = np.argmax(magnitudes[:, t_idx])
                pitch_hz = pitches[max_mag_idx, t_idx]
                current_time = t_idx * frame_duration
                if pitch_hz > 0:
                    current_midi_note = round(librosa.hz_to_midi(pitch_hz))
                    velocity_value = np.clip(
                        magnitudes[max_mag_idx, t_idx] * 200, 30, 127)
                    if active_note_midi is None:
                        active_note_midi = current_midi_note
                        active_note_start_time = current_time
                        active_note_velocities = [velocity_value]
                    elif active_note_midi != current_midi_note:
                        if active_note_velocities:
                            notes_for_midi.append(pretty_midi.Note(velocity=int(np.mean(active_note_velocities)), pitch=int(
                                active_note_midi), start=active_note_start_time, end=current_time))
                        active_note_midi = current_midi_note
                        active_note_start_time = current_time
                        active_note_velocities = [velocity_value]
                    else:
                        active_note_velocities.append(velocity_value)
                elif active_note_midi is not None:
                    if active_note_velocities:
                        notes_for_midi.append(pretty_midi.Note(velocity=int(np.mean(active_note_velocities)), pitch=int(
                            active_note_midi), start=active_note_start_time, end=current_time))
                    active_note_midi = None
                    active_note_velocities = []
            if active_note_midi is not None and active_note_velocities:
                notes_for_midi.append(pretty_midi.Note(velocity=int(np.mean(active_note_velocities)), pitch=int(
                    active_note_midi), start=active_note_start_time, end=current_time + frame_duration))

            midi_data_obj = pretty_midi.PrettyMIDI(
                initial_tempo=librosa.beat.tempo(y=y, sr=sr)[0])
            instrument = pretty_midi.Instrument(program=0)
            instrument.notes.extend(notes_for_midi)
            midi_data_obj.instruments.append(instrument)
            midi_data_obj.write(self.vocal_midi_filepath)
            print(
                f"SUCCESS: MIDI file created: {self.vocal_midi_filepath} with {len(notes_for_midi)} notes.")
            self.main_status_label.config(
                text=f"MIDI変換完了: {os.path.basename(self.vocal_midi_filepath)}。")
            return True  # 成功
        except Exception as e:
            print(
                f"ERROR: MIDI conversion logic failed: {type(e).__name__} - {str(e)}")
            self.main_status_label.config(
                text=f"エラー: MIDI変換失敗 ({type(e).__name__})。")
            return False  # 失敗

    def show_karaoke_window(self):  # _wrapper と _ui を統合
        print("INFO: --- Opening Karaoke Window ---")
        if not os.path.exists(self.prepared_accompaniment_wav):
            print(
                f"ERROR: Accompaniment file {self.prepared_accompaniment_wav} not found.")
            self.main_status_label.config(text="エラー: 伴奏音源が見つかりません。")
            return False
        if not os.path.exists(self.vocal_midi_filepath):
            print(
                f"ERROR: Vocal MIDI file {self.vocal_midi_filepath} not found.")
            self.main_status_label.config(text="エラー: ボーカルMIDIファイルが見つかりません。")
            return False

        try:
            self.midi_data = pretty_midi.PrettyMIDI(self.vocal_midi_filepath)
            self.notes = []
            if self.midi_data.instruments and self.midi_data.instruments[0].notes:
                for note in self.midi_data.instruments[0].notes:
                    self.notes.append(
                        {"start": note.start, "end": note.end, "pitch": note.pitch, "velocity": note.velocity})
                self.notes.sort(key=lambda x: x["start"])
            else:
                print("WARNING: MIDI file contains no notes or no instruments.")
            print(f"INFO: Loaded {len(self.notes)} notes from MIDI.")
            pygame.mixer.music.load(self.prepared_accompaniment_wav)
            print("INFO: Accompaniment audio loaded.")
            self.main_status_label.config(text="カラオケの準備完了。")
        except Exception as e:
            print(
                f"ERROR: Failed to load MIDI/audio for karaoke: {type(e).__name__} - {str(e)}")
            self.main_status_label.config(
                text=f"エラー: カラオケ準備失敗 ({type(e).__name__})。")
            return False

        if self.karaoke_window and self.karaoke_window.winfo_exists():
            self.karaoke_window.lift()
            return True

        self.karaoke_window = tk.Toplevel(self.master) if not isinstance(
            self.master, DummyMaster) else DummyMaster()  # masterを渡す
        self.karaoke_window.title("カラオケゲーム")

        top_f = tk.Frame(self.karaoke_window)
        top_f.pack(side="top", fill="x", padx=5, pady=2)
        tk.Label(top_f, text=f"伴奏: {os.path.basename(self.prepared_accompaniment_wav)}").pack(
            side="left")
        tk.Label(top_f, text=f"MIDI: {os.path.basename(self.vocal_midi_filepath)}").pack(
            side="left", padx=10)
        self.pitch_canvas_height = (
            self.MAX_MIDI_PITCH - self.MIN_MIDI_PITCH + 1) * self.NOTE_HEIGHT
        self.pitch_canvas = tk.Canvas(
            self.karaoke_window, width=600, height=self.pitch_canvas_height, bg="white")
        self.pitch_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        bottom_f = tk.Frame(self.karaoke_window)
        bottom_f.pack(side="bottom", fill="x", padx=5, pady=5)
        self.play_pause_button_karaoke = tk.Button(
            bottom_f, text="再生", command=self.toggle_play_pause)
        self.play_pause_button_karaoke.pack(side="left", padx=5)
        tk.Button(bottom_f, text="停止", command=self.stop_music).pack(
            side="left", padx=5)
        if hasattr(self.karaoke_window, 'protocol'):
            self.karaoke_window.protocol(
                "WM_DELETE_WINDOW", self.on_karaoke_window_close)
        print("INFO: Karaoke UI elements defined for karaoke window.")
        return True

    def toggle_play_pause(self):
        # (前回と同様のロジック)
        print(
            f"INFO: toggle_play_pause. Playing={self.is_playing}, Paused={self.is_paused}")
        if not self.is_playing:
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
            self.playback_start_time = time.time()
            self.simulated_playback_time_sec = 0.0
            self.current_note_index = 0
            if self.play_pause_button_karaoke:
                self.play_pause_button_karaoke.config(text="一時停止")
            self.update_display_loop()
            print("INFO: Music playing, display loop started.")
        elif self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.paused_position = pygame.mixer.music.get_pos() / 1000.0  # get_pos はダミー対応済み
            if self.play_pause_button_karaoke:
                self.play_pause_button_karaoke.config(text="再生")
            if self.update_loop_id:
                self.master.after_cancel(self.update_loop_id)
                self.update_loop_id = None
            print("INFO: Music paused, display loop stopped.")
        elif self.is_playing and self.is_paused:
            if use_dummy_mixer:
                DummyPygameMixer.music.unpause()  # ダミーのunpauseを呼ぶ
            else:
                pygame.mixer.music.unpause()
            self.is_paused = False
            # 正しい再生開始時刻の調整 (一時停止時間を考慮)
            self.playback_start_time = time.time() - self.paused_position
            if self.play_pause_button_karaoke:
                self.play_pause_button_karaoke.config(text="一時停止")
            self.update_display_loop()
            print("INFO: Music unpaused, display loop resumed.")
        self.main_status_label.config(
            text=f"再生状態: Playing={self.is_playing}, Paused={self.is_paused}")

    def stop_music(self):
        # (前回と同様のロジック)
        print("INFO: stop_music called.")
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.simulated_playback_time_sec = 0.0
        self.current_note_index = 0
        if self.play_pause_button_karaoke:
            self.play_pause_button_karaoke.config(text="再生")
        if self.update_loop_id:
            if hasattr(self.master, 'after_cancel'):
                self.master.after_cancel(self.update_loop_id)
            self.update_loop_id = None
        if self.pitch_canvas:
            self.pitch_canvas.delete("all")
        print("INFO: Music stopped and display loop cancelled, canvas cleared.")
        self.main_status_label.config(text="再生停止。")

    def update_display_loop(self):
        # (前回と同様のロジック)
        if not self.is_playing or self.is_paused:
            if self.update_loop_id:
                if hasattr(self.master, 'after_cancel'):
                    self.master.after_cancel(self.update_loop_id)
                self.update_loop_id = None
            return
        current_playback_time_sec = pygame.mixer.music.get_pos() / 1000.0
        if current_playback_time_sec < 0 and self.is_playing and not use_dummy_mixer:  # get_posが-1を返し、かつ再生中なら終了とみなす
            print("INFO: Playback finished (get_pos is -1). Stopping music.")
            self.stop_music()
            return
        self.draw_pitch_bars(current_playback_time_sec)
        if hasattr(self.master, 'after'):
            self.update_loop_id = self.master.after(
                self.REFRESH_INTERVAL_MS, self.update_display_loop)

    def draw_pitch_bars(self, current_time_sec):
        # (前回と同様のロジック)
        if not self.pitch_canvas:
            return
        self.pitch_canvas.delete("all")
        canvas_width = 600
        canvas_height = self.pitch_canvas_height  # ダミー用に固定値も考慮
        # Check if canvas is valid
        if hasattr(self.pitch_canvas, 'winfo_width') and self.pitch_canvas.winfo_exists():
            canvas_width = self.pitch_canvas.winfo_width()
            canvas_height = self.pitch_canvas.winfo_height()

        cursor_x = self.CURSOR_X_POSITION
        self.pitch_canvas.create_line(
            cursor_x, 0, cursor_x, canvas_height, fill=self.CURSOR_COLOR, width=2)
        view_start_time = current_time_sec - \
            (cursor_x / self.PIXELS_PER_SECOND)
        view_end_time = current_time_sec + \
            ((canvas_width - cursor_x) / self.PIXELS_PER_SECOND)
        for note in self.notes:
            if note["end"] < view_start_time or note["start"] > view_end_time:
                continue
            x1 = (note["start"] - current_time_sec) * \
                self.PIXELS_PER_SECOND + cursor_x
            x2 = (note["end"] - current_time_sec) * \
                self.PIXELS_PER_SECOND + cursor_x
            y_center = canvas_height - \
                ((note["pitch"] - self.MIN_MIDI_PITCH) *
                 self.NOTE_HEIGHT + self.NOTE_HEIGHT / 2)
            y1 = y_center - self.NOTE_HEIGHT / 2
            y2 = y_center + self.NOTE_HEIGHT / 2
            color = self.PAST_NOTE_COLOR if note["end"] < current_time_sec else self.NOTE_COLOR
            self.pitch_canvas.create_rectangle(
                x1, y1, x2, y2, fill=color, outline="black")

    def on_karaoke_window_close(self):
        # (前回と同様のロジック)
        print("INFO: Karaoke window close requested.")
        self.stop_music()
        if self.karaoke_window:
            if hasattr(self.karaoke_window, 'destroy'):
                self.karaoke_window.destroy()
            self.karaoke_window = None
            print("INFO: Karaoke window destroyed.")


if __name__ == "__main__":
    print("INFO: main.py successfully parsed.")
    print("INFO: Dummy class definitions remain but are not globally aliased to tk or pygame.mixer.")
    print("INFO: KaraokeApp class will now use actual tkinter and pygame.mixer (if available).")
    print("INFO: To run the application GUI, create a root Tk window, instantiate KaraokeApp, and run root.mainloop().")

    # --- Example of how to run the actual application ---
    # root = tk.Tk()
    # app = KaraokeApp(root)
    # # Perform any initial file setup here if needed for the app to start
    # # e.g., app.select_and_prepare_files("path/to/vocal.wav", "path/to/acc.wav")
    # # app.convert_vocal_to_midi()
    # root.mainloop()
