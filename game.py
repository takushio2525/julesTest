import pygame
import pretty_midi
import os
import pyaudio
import numpy as np
import librosa

# --- 定数 ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WINDOW_TITLE = "カラオケゲーム"
FPS = 60

# 色の定義
COLOR_BACKGROUND = (20, 20, 40) # 少し青みがかった背景
COLOR_PITCH_BAR_AREA = (40, 40, 60) # 音程バーエリアの背景色
COLOR_NOTE_GUIDE = (100, 200, 255)  # お手本ノートの色 (明るい青)
COLOR_PLAYER_PITCH = (255, 130, 130) # プレイヤーの音程のデフォルト色 (明るいサーモンピンク)
COLOR_PLAYER_PITCH_MATCH = (130, 255, 130) # 音程一致時のプレイヤー音程の色 (明るい緑)
COLOR_PLAYHEAD = (255, 50, 50) # 再生ヘッドの色 (明るい赤)
COLOR_TEXT = (230, 230, 230) # 一般テキストの色
COLOR_SCORE_TEXT = (255, 255, 100) # スコアの色 (黄色)
COLOR_HELP_TEXT = (180, 180, 180) # 操作説明のテキスト色

# 音程バーエリア設定
PITCH_BAR_AREA_X = 60
PITCH_BAR_AREA_Y = 120 # スコアとタイトル表示のため少し下げる
PITCH_BAR_AREA_WIDTH = SCREEN_WIDTH - 120
PITCH_BAR_AREA_HEIGHT = SCREEN_HEIGHT - 300 # 下部にも操作説明等のスペース

# MIDIノートの音域と画面Y座標のマッピング用
MIDI_NOTE_MIN = pretty_midi.note_name_to_number('C3')
MIDI_NOTE_MAX = pretty_midi.note_name_to_number('A5') # 少し高音域も表示
PIXELS_PER_SECOND = 120 # スクロール速度を少し上げる

# プレイヤー音程表示用
PLAYER_PITCH_MARKER_WIDTH = 15 # マーカーの横幅 (バー形式)
PLAYER_PITCH_MARKER_THICKNESS = 6 # マーカーの縦の太さ

# 採点ロジック用
PITCH_MATCH_THRESHOLD = 0.75
SCORE_PER_NOTE = 100 # 1ノート完全に歌えた場合の基本スコア
MIN_VOICED_PROB_THRESHOLD = 0.65 # 音程分析で採用する最小の有声確率
MIN_NOTE_DURATION_FOR_SCORING = 0.2 # この秒数より短いノートは採点対象外とする（オプション）

# --- マイク入力設定 ---
MIC_SAMPLE_RATE = 44100
MIC_CHANNELS = 1
MIC_CHUNK_SIZE = 2048 # FFTのサイズにも影響
MIC_FORMAT = pyaudio.paInt16
PYAUDIO_INPUT_DEVICE_INDEX = None

F0_FMIN = librosa.note_to_hz('C2')
F0_FMAX = librosa.note_to_hz('C7')


# --- テスト用ファイルパス ---
SONG_NAME = "test_video"
ACCOMPANIMENT_PATH = os.path.join("outData", SONG_NAME, "accompaniment.wav")
VOCAL_MIDI_PATH = os.path.join("outData", SONG_NAME, f"{SONG_NAME}_vocals.mid")

class NoteVisual:
    def __init__(self, pitch: int, start_time: float, end_time: float, velocity: int = 100):
        self.pitch = pitch
        self.start_time = start_time
        self.end_time = end_time
        self.duration = end_time - start_time
        self.velocity = velocity
        self.is_scored = False

    def get_rect(self, current_time: float, pitch_bar_rect: pygame.Rect) -> pygame.Rect | None:
        note_range = MIDI_NOTE_MAX - MIDI_NOTE_MIN
        if note_range <= 0: note_range = 1

        if not (MIDI_NOTE_MIN <= self.pitch <= MIDI_NOTE_MAX + 1): # +1で最高音も表示
            return None

        y_per_pitch = pitch_bar_rect.height / note_range
        relative_pitch = self.pitch - MIDI_NOTE_MIN
        # Y座標は上が高音、下が低音になるように (一般的なピアノロール表示)
        note_y = pitch_bar_rect.top + (note_range - relative_pitch - 1) * y_per_pitch
        note_height = max(2, y_per_pitch * 0.8) # ノートの太さ、少し隙間を開ける

        playhead_x_offset = pitch_bar_rect.width // 3 # 再生ヘッドの相対位置を少し右に
        note_start_x_on_timeline = self.start_time * PIXELS_PER_SECOND
        current_timeline_x = current_time * PIXELS_PER_SECOND

        note_x = pitch_bar_rect.left + playhead_x_offset + (note_start_x_on_timeline - current_timeline_x)
        note_width = self.duration * PIXELS_PER_SECOND

        if note_x + note_width < pitch_bar_rect.left or note_x > pitch_bar_rect.right:
            return None

        visible_note_x = max(note_x, pitch_bar_rect.left)
        visible_note_width = min(note_x + note_width, pitch_bar_rect.right) - visible_note_x
        if visible_note_width <= 1: # 幅が非常に小さい場合は描画しない
            return None

        return pygame.Rect(int(visible_note_x), int(note_y), int(visible_note_width), int(note_height))

def initialize_pygame():
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    # フォントの指定 (システムフォントが見つからない場合のフォールバックも考慮)
    try:
        title_font = pygame.font.SysFont("arial", 48)
        score_font = pygame.font.SysFont("sans", 36)
        help_font = pygame.font.SysFont("sans", 24)
    except:
        title_font = pygame.font.Font(None, 52)
        score_font = pygame.font.Font(None, 40)
        help_font = pygame.font.Font(None, 28)
    return screen, clock, title_font, score_font, help_font

def load_audio_for_playback(audio_path):
    if not os.path.exists(audio_path):
        print(f"エラー: 伴奏ファイルが見つかりません - {audio_path}")
        return False
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(audio_path)
        print(f"伴奏ファイルをロードしました: {audio_path}")
        return True
    except pygame.error as e:
        print(f"エラー: 伴奏ファイルの読み込みエラー - {e}")
        return False

def load_midi_notes(midi_path) -> list[NoteVisual]:
    notes_visual_list = []
    if not os.path.exists(midi_path):
        print(f"エラー: MIDIファイルが見つかりません - {midi_path}")
        return notes_visual_list
    try:
        midi_data = pretty_midi.PrettyMIDI(midi_path)
        if not midi_data.instruments:
            print("MIDIファイルに楽器情報が含まれていません。")
            return notes_visual_list
        instrument = midi_data.instruments[0]
        for note in instrument.notes:
            if note.duration >= MIN_NOTE_DURATION_FOR_SCORING: # 短すぎるノートは無視 (オプション)
                notes_visual_list.append(NoteVisual(note.pitch, note.start, note.end, note.velocity))
        print(f"MIDIファイルをロードし、{len(notes_visual_list)}個のノートを準備しました: {midi_path}")
    except Exception as e:
        print(f"エラー: MIDIファイルの読み込みまたは解析中にエラー - {e}")
    return notes_visual_list

def initialize_microphone_stream():
    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(format=MIC_FORMAT, channels=MIC_CHANNELS, rate=MIC_SAMPLE_RATE,
                         input=True, frames_per_buffer=MIC_CHUNK_SIZE,
                         input_device_index=PYAUDIO_INPUT_DEVICE_INDEX)
        print("マイク入力ストリームを開きました。")
        return pa, stream
    except Exception as e:
        print(f"エラー: マイク入力ストリームの初期化に失敗 - {e}")
        if pa: pa.terminate()
        return None, None

def analyze_pitch_from_mic_data(audio_data_np: np.ndarray, sr: int) -> float | None:
    try:
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio_data_np, fmin=F0_FMIN, fmax=F0_FMAX, sr=sr,
            frame_length=MIC_CHUNK_SIZE, hop_length=MIC_CHUNK_SIZE // 4
        )
        for i in range(len(f0)):
            if voiced_flag[i] and not np.isnan(f0[i]) and voiced_probs[i] > MIN_VOICED_PROB_THRESHOLD:
                return librosa.hz_to_midi(f0[i])
        return None
    except Exception: return None

def game_loop(screen, clock, title_font, score_font, help_font):
    running = True
    accompaniment_loaded = load_audio_for_playback(ACCOMPANIMENT_PATH)
    notes_to_draw = load_midi_notes(VOCAL_MIDI_PATH)

    pitch_bar_rect = pygame.Rect(PITCH_BAR_AREA_X, PITCH_BAR_AREA_Y, PITCH_BAR_AREA_WIDTH, PITCH_BAR_AREA_HEIGHT)
    playhead_screen_x = pitch_bar_rect.left + pitch_bar_rect.width // 3 # 再生ヘッド位置を調整

    pa, mic_stream = initialize_microphone_stream()
    analyzing_mic = True if mic_stream else False
    current_player_midi_note = None
    score = 0

    if mic_stream: print("マイクからの音程分析を開始します...")
    else: print("マイクが利用できないため、音程分析はスキップされます。")

    playing_music = False
    current_playback_time_sec = 0.0
    note_score_awarded_flags = {i: False for i in range(len(notes_to_draw))}

    title_surf = title_font.render(WINDOW_TITLE, True, COLOR_TEXT)
    title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, PITCH_BAR_AREA_Y // 2))

    help_texts = [
        "P: Play/Pause", "S: Stop", "M: Mic ON/OFF", "Q: Quit"
    ]
    help_surfaces = [help_font.render(text, True, COLOR_HELP_TEXT) for text in help_texts]
    help_start_y = SCREEN_HEIGHT - 30 - (len(help_surfaces) * (help_font.get_height() + 5))


    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if accompaniment_loaded and event.key == pygame.K_p:
                    if playing_music:
                        pygame.mixer.music.pause()
                        playing_music = False
                        print("伴奏一時停止")
                    else:
                        if pygame.mixer.music.get_pos() > 0 and not playing_music: # Paused
                            pygame.mixer.music.unpause()
                        else: # Stopped or first play
                            pygame.mixer.music.play()
                            current_playback_time_sec = 0.0 # 再生開始時は時間をリセット
                            note_score_awarded_flags = {i: False for i in range(len(notes_to_draw))}
                            score = 0 # スコアもリセット
                        playing_music = True
                        print("伴奏再生中")
                elif accompaniment_loaded and event.key == pygame.K_s:
                    pygame.mixer.music.stop()
                    playing_music = False
                    current_playback_time_sec = 0.0
                    score = 0
                    note_score_awarded_flags = {i: False for i in range(len(notes_to_draw))}
                    print("伴奏停止")
                elif event.key == pygame.K_m and mic_stream:
                    analyzing_mic = not analyzing_mic
                    print(f"マイク音程分析を {'ON' if analyzing_mic else 'OFF'} にしました。")
                elif event.key == pygame.K_q: running = False

        if playing_music and accompaniment_loaded:
            current_playback_time_ms = pygame.mixer.music.get_pos()
            if current_playback_time_ms == -1: playing_music = False
            else: current_playback_time_sec = current_playback_time_ms / 1000.0

        current_player_midi_note = None
        if mic_stream and analyzing_mic:
            try:
                raw_mic_data = mic_stream.read(MIC_CHUNK_SIZE, exception_on_overflow=False)
                audio_data_np = np.frombuffer(raw_mic_data, dtype=np.int16).astype(np.float32) / 32768.0
                current_player_midi_note = analyze_pitch_from_mic_data(audio_data_np, MIC_SAMPLE_RATE)
            except IOError: pass
            except Exception as e: print(f"マイク処理エラー: {e}")

        player_marker_color = COLOR_PLAYER_PITCH
        if playing_music and current_player_midi_note is not None:
            for i, note_vis in enumerate(notes_to_draw):
                if not note_score_awarded_flags[i] and \
                   note_vis.start_time <= current_playback_time_sec < note_vis.end_time:
                    if abs(current_player_midi_note - note_vis.pitch) <= PITCH_MATCH_THRESHOLD:
                        player_marker_color = COLOR_PLAYER_PITCH_MATCH
                        score += SCORE_PER_NOTE # ノート単位で一度だけ加点
                        note_score_awarded_flags[i] = True
                    break

        screen.fill(COLOR_BACKGROUND)
        pygame.draw.rect(screen, COLOR_PITCH_BAR_AREA, pitch_bar_rect)

        for note_vis in notes_to_draw:
            note_rect = note_vis.get_rect(current_playback_time_sec, pitch_bar_rect)
            if note_rect:
                pygame.draw.rect(screen, COLOR_NOTE_GUIDE, note_rect)

        if current_player_midi_note is not None and MIDI_NOTE_MIN <= current_player_midi_note <= MIDI_NOTE_MAX +1 :
            note_range = MIDI_NOTE_MAX - MIDI_NOTE_MIN
            if note_range <= 0: note_range = 1
            y_per_pitch = pitch_bar_rect.height / note_range
            relative_pitch = current_player_midi_note - MIDI_NOTE_MIN
            player_pitch_y = pitch_bar_rect.top + (note_range - relative_pitch - 1) * y_per_pitch

            player_pitch_marker_rect = pygame.Rect(
                playhead_screen_x - PLAYER_PITCH_MARKER_WIDTH // 2,
                int(player_pitch_y + (y_per_pitch - PLAYER_PITCH_MARKER_THICKNESS)/2), # バーのY中心を合わせる
                PLAYER_PITCH_MARKER_WIDTH,
                PLAYER_PITCH_MARKER_THICKNESS
            )
            pygame.draw.rect(screen, player_marker_color, player_pitch_marker_rect, border_radius=3)

        pygame.draw.line(screen, COLOR_PLAYHEAD, (playhead_screen_x, pitch_bar_rect.top), (playhead_screen_x, pitch_bar_rect.bottom), 3)

        screen.blit(title_surf, title_rect)
        score_surf = score_font.render(f"Score: {score}", True, COLOR_SCORE_TEXT)
        screen.blit(score_surf, (SCREEN_WIDTH - score_surf.get_width() - 20, 20))

        for i, help_surf in enumerate(help_surfaces):
            help_rect = help_surf.get_rect(center=(SCREEN_WIDTH // 2, help_start_y + i * (help_font.get_height() + 5)))
            screen.blit(help_surf, help_rect)

        pygame.display.flip()
        clock.tick(FPS)

    if mic_stream: mic_stream.stop_stream(); mic_stream.close()
    if pa: pa.terminate()
    pygame.quit()

if __name__ == '__main__':
    print("ゲームを開始します...")
    print(f"使用する伴奏ファイル: {ACCOMPANIMENT_PATH}")
    print(f"使用するMIDIファイル: {VOCAL_MIDI_PATH}")

    if not os.path.exists(ACCOMPANIMENT_PATH):
        print(f"警告: 伴奏ファイルが見つかりません。 ({ACCOMPANIMENT_PATH})")
    if not os.path.exists(VOCAL_MIDI_PATH):
        print(f"警告: MIDIファイルが見つかりません。 ({VOCAL_MIDI_PATH})")

    if os.path.exists(ACCOMPANIMENT_PATH) and os.path.exists(VOCAL_MIDI_PATH):
        main_screen, main_clock, title_f, score_f, help_f = initialize_pygame()
        game_loop(main_screen, main_clock, title_f, score_f, help_f)
    else:
        print("必要な伴奏ファイルまたはMIDIファイルが不足しているため、ゲームの主要機能を実行できません。")
        print("audio_processor.py を実行して、テスト用の音声・MIDIファイルを生成してください。")

    print("ゲームを終了しました。")

```
