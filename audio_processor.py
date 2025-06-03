import os
import numpy as np
import librosa
import pretty_midi
from moviepy.editor import VideoFileClip
from spleeter.separator import Separator
# from spleeter.audio.adapter import AudioAdapter # Spleeter 2.xでは不要な場合が多い

# 出力ディレクトリ名
OUTPUT_DIR = "outData"

def extract_audio_from_mp4(mp4_path: str) -> str | None:
    """
    MP4ファイルから音声を抽出し、WAVファイルとして保存する。

    Args:
        mp4_path: MP4ファイルのパス。

    Returns:
        抽出されたWAVファイルのパス。エラーの場合はNone。
    """
    if not os.path.exists(mp4_path):
        print(f"エラー: ファイルが見つかりません - {mp4_path}")
        return None
    if not mp4_path.lower().endswith(".mp4"):
        print(f"エラー: MP4ファイルではありません - {mp4_path}")
        return None

    try:
        print(f"MP4ファイルからの音声抽出を開始します: {mp4_path}")
        video_clip = VideoFileClip(mp4_path)
        base_name = os.path.splitext(os.path.basename(mp4_path))[0]
        # MP4と同じディレクトリにWAVファイルを作成
        wav_path = os.path.join(os.path.dirname(mp4_path), f"{base_name}.wav")

        video_clip.audio.write_audiofile(wav_path, codec='pcm_s16le')
        video_clip.close()
        print(f"音声ファイルを抽出しました: {wav_path}")
        return wav_path
    except Exception as e:
        print(f"エラー: 音声抽出中に問題が発生しました - {e}")
        return None

def create_midi_from_vocal_audio(vocal_audio_path: str, output_midi_path: str) -> None:
    """
    ボーカル音声WAVファイルからMIDIデータを生成し保存する。

    Args:
        vocal_audio_path: ボーカル音声WAVファイルのパス。
        output_midi_path: 生成されたMIDIファイルの保存パス。
    """
    if not os.path.exists(vocal_audio_path):
        print(f"エラー: ボーカル音声ファイルが見つかりません - {vocal_audio_path}")
        return

    try:
        print(f"ボーカル音声からのMIDI生成を開始します: {vocal_audio_path}")
        y, sr = librosa.load(vocal_audio_path)

        # 基本周波数(f0)の推定 (pyinを使用)
        # fmin, fmaxは一般的なボーカルの範囲に合わせて調整可能
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C6'))

        # 信頼できるf0のみを取得 (voiced_probsが閾値以上のものなど、より高度なフィルタリングも可能)
        # ここでは簡単のため、voiced_flagがTrueのものを採用
        f0_voiced = f0[voiced_flag]

        # f0が存在しない場合は処理を中断
        if len(f0_voiced) == 0:
            print("エラー: 有声区間または有効なピッチが検出できませんでした。MIDIは生成されません。")
            return

        # MIDIノートに変換するための準備
        midi_data = pretty_midi.PrettyMIDI()
        instrument_program = pretty_midi.instrument_name_to_program('Acoustic Grand Piano') # 例としてピアノ
        instrument = pretty_midi.Instrument(program=instrument_program)

        # オンセット（音の立ち上がり）検出
        onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time')

        if len(onsets) == 0:
            print("警告: オンセットが検出できませんでした。MIDIノートの開始タイミングが不正確になる可能性があります。")
            # オンセットがない場合でも、一定間隔でノートを区切るなどの代替処理も考えられるが、ここでは単純化
            # 代わりに、f0が連続する区間をノートとする簡易的な方法を試す

        current_note_start_time = None
        current_note_pitch = None
        # f0の各フレームに対応する時間を計算
        times = librosa.times_like(f0, sr=sr)

        # f0からノートを生成する簡易的なロジック
        # (より洗練されたアルゴリズムが必要な場合がある)
        min_note_duration = 0.1 # 秒: 短すぎるノートを除外
        note_velocity = 100 # 固定ベロシティ

        for i in range(len(f0)):
            if voiced_flag[i] and f0[i] > 0: # f0が0より大きい（無音でない）場合のみ処理
                pitch = int(round(librosa.hz_to_midi(f0[i]))) # MIDIノート番号に変換して丸める
                if current_note_pitch is None: # 新しいノートの開始
                    current_note_start_time = times[i]
                    current_note_pitch = pitch
                elif pitch != current_note_pitch: # ピッチが変わったら前のノートを終了し新しいノートを開始
                    if current_note_start_time is not None and (times[i] - current_note_start_time >= min_note_duration):
                        note = pretty_midi.Note(
                            velocity=note_velocity, pitch=current_note_pitch, start=current_note_start_time, end=times[i]
                        )
                        instrument.notes.append(note)
                    current_note_start_time = times[i]
                    current_note_pitch = pitch
            else: # 無声区間になったらノートを終了
                if current_note_pitch is not None and current_note_start_time is not None and (times[i] - current_note_start_time >= min_note_duration):
                    note = pretty_midi.Note(
                        velocity=note_velocity, pitch=current_note_pitch, start=current_note_start_time, end=times[i]
                    )
                    instrument.notes.append(note)
                current_note_pitch = None
                current_note_start_time = None

        # 最後のノート処理
        if current_note_pitch is not None and current_note_start_time is not None and (times[-1] - current_note_start_time >= min_note_duration):
             note = pretty_midi.Note(
                velocity=note_velocity, pitch=current_note_pitch, start=current_note_start_time, end=times[-1]
            )
             instrument.notes.append(note)


        midi_data.instruments.append(instrument)

        # MIDIファイルとして保存
        output_dir = os.path.dirname(output_midi_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        midi_data.write(output_midi_path)
        print(f"MIDIファイルを生成しました: {output_midi_path}")

    except Exception as e:
        print(f"エラー: MIDI生成中に問題が発生しました - {e}")


def separate_vocals_and_accompaniment(audio_path: str, output_base_path: str = OUTPUT_DIR) -> None:
    """
    音声ファイルからボーカルと伴奏を分離し、ボーカルからMIDIを生成する。
    """
    if not os.path.exists(audio_path):
        print(f"エラー: 音声ファイルが見つかりません - {audio_path}")
        return
    if not audio_path.lower().endswith(".wav"):
        print(f"エラー: WAVファイルではありません - {audio_path}")
        return

    try:
        os.makedirs(output_base_path, exist_ok=True)
        separator = Separator('spleeter:2stems', tensorflow_based=True)

        print(f"'{audio_path}' のボーカルと伴奏の分離を開始します...")
        separator.separate_to_file(audio_path, output_base_path)

        audio_filename_without_ext = os.path.splitext(os.path.basename(audio_path))[0]
        vocals_audio_filename = "vocals.wav" # spleeterのデフォルト出力名

        # Spleeterは <output_base_path>/<audio_filename_without_ext>/vocals.wav に出力する
        separated_vocals_path = os.path.join(output_base_path, audio_filename_without_ext, vocals_audio_filename)
        separated_accompaniment_path = os.path.join(output_base_path, audio_filename_without_ext, "accompaniment.wav")

        if os.path.exists(separated_vocals_path) and os.path.exists(separated_accompaniment_path):
            print(f"分離が完了しました。ボーカル: {separated_vocals_path}, 伴奏: {separated_accompaniment_path}")

            # ボーカル音声からMIDIを生成
            # MIDIファイル名をボーカルファイルと同じディレクトリに <元のファイル名など>_vocals.mid のようにする
            midi_filename = f"{audio_filename_without_ext}_vocals.mid" # または単に "vocals.mid"
            output_midi_path = os.path.join(output_base_path, audio_filename_without_ext, midi_filename)

            create_midi_from_vocal_audio(separated_vocals_path, output_midi_path)
        else:
            print("エラー: 分離ファイルの出力が確認できませんでした。")

    except Exception as e:
        print(f"エラー: spleeterでの分離またはMIDI生成中に問題が発生しました - {e}")

if __name__ == '__main__':
    TEST_MP4_FILENAME = "test_video.mp4"

    # このテストコードは、ローカル環境で test_video.mp4 を用意して実行することを想定しています。
    print(f"テストを実行するには、'{TEST_MP4_FILENAME}' という名前のMP4ファイルを audio_processor.py と同じディレクトリに配置してください。")
    print("または、以下の `test_mp4_path` を実際のMP4ファイルのパスに書き換えてください。")
    print("注意: Spleeterは初回実行時にモデルをダウンロードするため、時間がかかることがあります。")

    test_mp4_path = TEST_MP4_FILENAME

    if os.path.exists(test_mp4_path):
        extracted_wav_path = extract_audio_from_mp4(test_mp4_path)

        if extracted_wav_path:
            print(f"\n抽出されたWAVファイル: {extracted_wav_path}")

            print("\nSpleeterによる分離とMIDI生成テストを開始します...")
            separate_vocals_and_accompaniment(extracted_wav_path) # ここでMIDI生成まで行われる

            # 生成されたファイルの確認 (例)
            audio_filename_no_ext = os.path.splitext(os.path.basename(extracted_wav_path))[0]
            expected_vocals_wav = os.path.join(OUTPUT_DIR, audio_filename_no_ext, "vocals.wav")
            expected_accompaniment_wav = os.path.join(OUTPUT_DIR, audio_filename_no_ext, "accompaniment.wav")
            expected_midi_file = os.path.join(OUTPUT_DIR, audio_filename_no_ext, f"{audio_filename_no_ext}_vocals.mid")

            print("\n--- 生成ファイルチェック ---")
            if os.path.exists(expected_vocals_wav):
                print(f"ボーカルWAV: {expected_vocals_wav} - OK")
            else:
                print(f"ボーカルWAV: {expected_vocals_wav} - NG (見つかりません)")

            if os.path.exists(expected_accompaniment_wav):
                print(f"伴奏WAV: {expected_accompaniment_wav} - OK")
            else:
                print(f"伴奏WAV: {expected_accompaniment_wav} - NG (見つかりません)")

            if os.path.exists(expected_midi_file):
                print(f"ボーカルMIDI: {expected_midi_file} - OK")
            else:
                print(f"ボーカルMIDI: {expected_midi_file} - NG (見つかりません)")
            print("-------------------------")

            # テスト用に作成したWAVファイルを削除 (任意)
            # try:
            #     if os.path.exists(extracted_wav_path):
            #         os.remove(extracted_wav_path)
            #         print(f"\nテスト用WAVファイルを削除しました: {extracted_wav_path}")
            # except OSError as e:
            #     print(f"テスト用WAVファイル削除エラー: {e}")
        else:
            print("MP4からの音声抽出に失敗したため、後続のテストはスキップします。")
    else:
        print(f"テスト用MP4ファイル '{test_mp4_path}' が見つからないため、テストをスキップします。")
