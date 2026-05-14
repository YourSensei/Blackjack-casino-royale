import random
import sys
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import struct
import wave
import math
import tempfile
import atexit

# Try importing playsound3 for music
try:
    from playsound3 import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False

# Try winsound for SFX on Windows
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

# Bestandsnaam voor het Leaderboard
HIGHSCORE_FILE = "blackjack_highscores.txt"

# Casino Constanten
SUITS = ('Hearts ♥', 'Diamonds ♦', 'Spades ♠', 'Clubs ♣')
RANKS = ('Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
         'Jack', 'Queen', 'King', 'Ace')
CARD_VALUES = {
    'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5, 'Six': 6, 'Seven': 7,
    'Eight': 8, 'Nine': 9, 'Ten': 10,
    'Jack': 10, 'Queen': 10, 'King': 10, 'Ace': 11
}

# Luxe Casino Kleurenpalet
COLOR_BG = "#1A1A1A"
COLOR_FELT = "#006633"
COLOR_GOLD = "#D4AF37"
COLOR_TEXT_LIGHT = "#FFFFFF"
COLOR_TEXT_DARK = "#111111"
COLOR_RED_CARD = "#FF3333"
COLOR_BLACK_CARD = "#E0E0E0"


# ─────────────────────────────────────────────
#  MUSIC COMPOSER  (pure Python + numpy/math)
# ─────────────────────────────────────────────

SAMPLE_RATE = 44100


def _sine(freq, duration, volume=0.4, sample_rate=SAMPLE_RATE):
    """Generate a sine-wave tone as a list of float samples."""
    n = int(sample_rate * duration)
    return [volume * math.sin(2 * math.pi * freq * t / sample_rate) for t in range(n)]


def _adsr(samples, attack=0.01, decay=0.05, sustain=0.7, release=0.1, sample_rate=SAMPLE_RATE):
    """Apply a simple ADSR envelope to a sample list."""
    n = len(samples)
    out = []
    a_end = int(attack * sample_rate)
    d_end = a_end + int(decay * sample_rate)
    r_start = n - int(release * sample_rate)

    for i, s in enumerate(samples):
        if i < a_end:
            env = i / max(a_end, 1)
        elif i < d_end:
            env = 1.0 - (1.0 - sustain) * (i - a_end) / max(d_end - a_end, 1)
        elif i < r_start:
            env = sustain
        else:
            env = sustain * (1.0 - (i - r_start) / max(n - r_start, 1))
        out.append(s * env)
    return out


def _mix(tracks):
    """Mix multiple sample lists (zero-pad shorter ones)."""
    if not tracks:
        return []
    length = max(len(t) for t in tracks)
    result = [0.0] * length
    for track in tracks:
        for i, s in enumerate(track):
            result[i] += s
    return result


def _note(freq, duration, volume=0.35):
    return _adsr(_sine(freq, duration, volume))


def _rest(duration):
    return [0.0] * int(SAMPLE_RATE * duration)


# Note frequencies (equal temperament)
NOTE = {
    'C2': 65.41,  'G2': 98.00,  'A2': 110.00, 'Bb2': 116.54, 'B2': 123.47,
    'C3': 130.81, 'D3': 146.83, 'Eb3': 155.56, 'E3': 164.81, 'F3': 174.61,
    'Gb3': 185.00, 'G3': 196.00, 'Ab3': 207.65, 'A3': 220.00, 'Bb3': 233.08, 'B3': 246.94,
    'C4': 261.63, 'Db4': 277.18, 'D4': 293.66, 'Eb4': 311.13, 'E4': 329.63, 'F4': 349.23,
    'Gb4': 369.99, 'G4': 392.00, 'Ab4': 415.30, 'A4': 440.00, 'Bb4': 466.16, 'B4': 493.88,
    'C5': 523.25, 'Db5': 554.37, 'D5': 587.33, 'Eb5': 622.25, 'E5': 659.25,
    'F5': 698.46, 'G5': 783.99, 'Ab5': 830.61, 'A5': 880.00,
}


def compose_casino_music():
    """
    Compose a looping jazz/casino-style melody with bass and chords.
    Returns raw PCM bytes (16-bit stereo).
    """
    # ── MELODY (right hand) ──────────────────────────────────
    melody_pattern = [
        ('E4', 0.25), ('G4', 0.25), ('A4', 0.5),
        ('C5', 0.25), ('B4', 0.25), ('A4', 0.5),
        ('G4', 0.25), ('E4', 0.25), ('D4', 0.25), ('C4', 0.25),
        ('E4', 0.5), (None, 0.5),
        ('A4', 0.25), ('G4', 0.25), ('E4', 0.5),
        ('F4', 0.25), ('E4', 0.25), ('D4', 0.5),
        ('C4', 0.25), ('E4', 0.25), ('G4', 0.25), ('A4', 0.25),
        ('C5', 0.75), (None, 0.25),
    ]

    # ── BASS LINE (left hand) ────────────────────────────────
    bass_pattern = [
        ('A3', 0.5), ('E3', 0.5),
        ('A3', 0.5), ('E3', 0.5),
        ('G3', 0.5), ('D3', 0.5),
        ('C3', 0.5), ('G3', 0.5),
        ('A3', 0.5), ('E3', 0.5),
        ('A3', 0.5), ('E3', 0.5),
        ('F3', 0.5), ('C3', 0.5),
        ('C3', 1.0),
    ]

    # ── CHORD STABS ─────────────────────────────────────────
    chord_pattern = [
        (None, 0.5), (['A3', 'C4', 'E4'], 0.25), (None, 0.25),
        (None, 0.5), (['A3', 'C4', 'E4'], 0.25), (None, 0.25),
        (None, 0.5), (['G3', 'B3', 'D4'], 0.25), (None, 0.25),
        (None, 0.5), (['C3', 'E3', 'G3'], 0.5),
        (None, 0.5), (['A3', 'C4', 'E4'], 0.25), (None, 0.25),
        (None, 0.5), (['F3', 'A3', 'C4'], 0.25), (None, 0.25),
        (None, 0.5), (['C3', 'E3', 'G3'], 0.25), (None, 0.25),
        (None, 0.75), (['C3', 'E3', 'G3'], 0.25),
    ]

    def build_track(pattern, vol=0.35):
        track = []
        for entry, dur in pattern:
            if entry is None:
                track.extend(_rest(dur))
            elif isinstance(entry, list):
                chord = _mix([_note(NOTE[n], dur, vol / len(entry)) for n in entry])
                track.extend(chord)
            else:
                track.extend(_note(NOTE[entry], dur, vol))
        return track

    mel = build_track(melody_pattern, 0.38)
    bass = build_track(bass_pattern, 0.30)
    chords = build_track(chord_pattern, 0.22)

    mixed = _mix([mel, bass, chords])

    # Normalize to avoid clipping
    peak = max(abs(s) for s in mixed) or 1.0
    if peak > 0.9:
        mixed = [s * 0.9 / peak for s in mixed]

    # Convert to 16-bit PCM stereo bytes
    pcm = bytearray()
    for s in mixed:
        val = int(max(-32768, min(32767, s * 32767)))
        packed = struct.pack('<h', val)
        pcm += packed   # left channel
        pcm += packed   # right channel (same → mono feel)

    return bytes(pcm)


def compose_menu_music():
    """
    Grand casino lounge intro track.
    Slow swing feel with a lush walking bass, jazzy chords and a swinging trumpet-style melody.
    """

    # ── Swing helper: returns a long-short pair (dotted 8th + 16th feel) ──
    def sw(freq, long=0.28, short=0.14, vol=0.40):
        return _adsr(_sine(freq, long + short, vol))

    def build_track(pattern, vol=0.35):
        track = []
        for entry, dur in pattern:
            if entry is None:
                track.extend(_rest(dur))
            elif isinstance(entry, list):
                chord = _mix([_note(NOTE[n], dur, vol / len(entry)) for n in entry])
                track.extend(chord)
            else:
                track.extend(_note(NOTE[entry], dur, vol))
        return track

    # ── Trumpet-style melody  (Bb major, slow swing) ──────────────────────
    melody = [
        (None, 0.25),
        ('F4', 0.42), ('Bb4', 0.42), ('D5', 0.84),
        ('C5', 0.42), ('Bb4', 0.42), ('F4', 0.84),
        ('G4', 0.42), ('Bb4', 0.42), ('D5', 0.42), ('F5', 0.42),
        ('Eb5', 1.26), (None, 0.42),
        ('D5', 0.42), ('C5', 0.42), ('Bb4', 0.42), ('Ab4', 0.42),
        ('G4', 0.84), ('F4', 0.84),
        ('Eb4', 0.42), ('F4', 0.42), ('G4', 0.42), ('Bb4', 0.42),
        ('C5', 1.68),
        (None, 0.42),
        ('F4', 0.42), ('Bb4', 0.42), ('D5', 0.84),
        ('Eb5', 0.42), ('D5', 0.42), ('C5', 0.84),
        ('Bb4', 0.42), ('Ab4', 0.42), ('G4', 0.42), ('F4', 0.42),
        ('Bb4', 1.68),
    ]

    # ── Walking bass (quarters) ────────────────────────────────────────────
    bass = [
        ('Bb2', 0.42), ('D3', 0.42), ('F3', 0.42), ('Ab3', 0.42),
        ('G3', 0.42),  ('Eb3', 0.42), ('C3', 0.42), ('G2', 0.42),
        ('F3', 0.42),  ('A2', 0.42),  ('C3', 0.42), ('Eb3', 0.42),
        ('Bb2', 0.84), ('F3', 0.42),  ('G3', 0.42),
        ('Eb3', 0.42), ('G3', 0.42),  ('Bb3', 0.42), ('Db4', 0.42),
        ('C3', 0.42),  ('Eb3', 0.42), ('G3', 0.42),  ('Bb3', 0.42),
        ('F3', 0.42),  ('Ab3', 0.42), ('C4', 0.42),  ('Eb4', 0.42),
        ('Bb2', 1.68),
        ('Bb2', 0.42), ('D3', 0.42),  ('F3', 0.42),  ('Ab3', 0.42),
        ('Eb3', 0.42), ('G3', 0.42),  ('Bb3', 0.42), ('Db4', 0.42),
        ('F3', 0.42),  ('Ab3', 0.42), ('C4', 0.42),  ('Eb4', 0.42),
        ('Bb2', 1.68),
    ]

    # ── Lush jazz chords (piano comping) ──────────────────────────────────
    chords = [
        (['Bb2', 'D3', 'F3', 'Ab3'], 0.84), (None, 0.84),
        (['G3', 'Bb3', 'D4', 'F4'],  0.84), (None, 0.84),
        (['F3', 'A3', 'C4', 'Eb4'],  0.84), (None, 0.84),
        (['Eb3', 'G3', 'Bb3', 'Db4'],0.84), (None, 0.84),
        (['Eb3', 'Gb3','Bb3', 'Db4'],0.84), (None, 0.84),
        (['C3', 'Eb3', 'G3', 'Bb3'], 0.84), (None, 0.84),
        (['F3', 'A3', 'C4', 'Eb4'],  0.84), (None, 0.84),
        (['Bb2', 'D3', 'F3', 'Ab3'], 1.68),
        (['Bb2', 'D3', 'F3', 'Ab3'], 0.84), (None, 0.84),
        (['Eb3', 'G3', 'Bb3', 'Db4'],0.84), (None, 0.84),
        (['F3', 'A3', 'C4', 'Eb4'],  0.84), (None, 0.84),
        (['Bb2', 'D3', 'F3', 'Ab3'], 1.68),
    ]

    # ── Hi-hat pulse (subtle shimmer) ─────────────────────────────────────
    def hihat_track(total_samples):
        hh = []
        step = int(SAMPLE_RATE * 0.21)   # 8th-note pulse
        click_len = int(SAMPLE_RATE * 0.018)
        for i in range(total_samples // step + 1):
            vol = 0.06 if i % 2 == 0 else 0.03
            for _ in range(click_len):
                import random as _r
                hh.append(_r.uniform(-vol, vol))
            hh.extend([0.0] * (step - click_len))
        return hh[:total_samples]

    mel_t   = build_track(melody, 0.42)
    bass_t  = build_track(bass,   0.28)
    chord_t = build_track(chords, 0.18)

    length = max(len(mel_t), len(bass_t), len(chord_t))
    hh_t   = hihat_track(length)

    mixed = _mix([mel_t, bass_t, chord_t, hh_t])

    peak = max(abs(s) for s in mixed) or 1.0
    if peak > 0.9:
        mixed = [s * 0.9 / peak for s in mixed]

    pcm = bytearray()
    for s in mixed:
        val = int(max(-32768, min(32767, s * 32767)))
        packed = struct.pack('<h', val)
        pcm += packed
        pcm += packed
    return bytes(pcm)


def _pcm_to_wav_file(pcm_bytes, channels=2, sampwidth=2, framerate=SAMPLE_RATE):
    """Write raw PCM bytes to a temporary WAV file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(pcm_bytes)
    return tmp.name


# Global music state
_music_wav_path = None   # path to currently loaded WAV
_music_paused   = False  # whether music is paused
_music_track    = None   # "menu" or "game"


def _winsound_play(path):
    """Start looping a WAV file immediately via winsound (Windows async loop)."""
    if WINSOUND_AVAILABLE and path:
        try:
            winsound.PlaySound(
                path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP
            )
        except Exception as e:
            print(f"[Music] winsound play error: {e}")


def _winsound_stop():
    """Stop the currently looping WAV immediately."""
    if WINSOUND_AVAILABLE:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


def start_background_music(track="game"):
    """
    Compose the requested track in a background thread, then start looping it
    immediately via winsound.PlaySound(SND_ASYNC | SND_LOOP).
    Any previously playing music is stopped instantly before the new track begins.
    """
    global _music_wav_path, _music_paused, _music_track

    if not WINSOUND_AVAILABLE:
        print("[Music] winsound not available – music disabled.")
        return

    # Stop whatever is playing right now, instantly
    _winsound_stop()
    _music_paused = False
    _music_track  = track

    composer = compose_menu_music if track == "menu" else compose_casino_music

    def _build_and_play():
        global _music_wav_path
        try:
            pcm           = composer()
            _music_wav_path = _pcm_to_wav_file(pcm)
            atexit.register(
                lambda: os.unlink(_music_wav_path)
                if _music_wav_path and os.path.exists(_music_wav_path) else None
            )
            # Only start playing if we haven't been told to stop/pause
            # while composing (takes a second or two)
            if not _music_paused and _music_track == track:
                _winsound_play(_music_wav_path)
        except Exception as e:
            print(f"[Music] Could not compose/start music: {e}")

    threading.Thread(target=_build_and_play, daemon=True).start()


def stop_background_music():
    """Stop music immediately."""
    global _music_track
    _music_track = None
    _winsound_stop()


def pause_background_music():
    """Pause (stop) music immediately."""
    global _music_paused
    _music_paused = True
    _winsound_stop()


def resume_background_music():
    """Resume the current track immediately from the beginning of its loop."""
    global _music_paused
    _music_paused = False
    _winsound_play(_music_wav_path)


# ─────────────────────────────────────────────
#  SOUND EFFECTS
# ─────────────────────────────────────────────

def play_sfx(sound_type):
    """Play short sound effects using winsound on Windows."""
    if WINSOUND_AVAILABLE:
        try:
            fx = {
                "deal": [(800,  80)],
                "win":  [(500, 100), (650, 100), (800, 150)],
                "loss": [(400, 120), (300, 200)],
                "buy":  [(1000, 60), (1300, 100)],
            }.get(sound_type, [])
            for freq, dur in fx:
                winsound.Beep(freq, dur)
        except Exception:
            pass


# ─────────────────────────────────────────────
#  GAME LOGIC
# ─────────────────────────────────────────────

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = CARD_VALUES[rank]
        self.symbol = suit.split()[-1]
        self.color = COLOR_RED_CARD if '♥' in suit or '♦' in suit else COLOR_BLACK_CARD

    def __str__(self):
        return f"{self.rank} of {self.suit}"


class BlackjackGame:
    def __init__(self):
        self.deck = []

    def generate_shuffled_deck(self):
        self.deck = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        random.shuffle(self.deck)

    @staticmethod
    def calculate_score(hand):
        score = sum(card.value for card in hand)
        aces = sum(1 for card in hand if card.rank == 'Ace')
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score


# ─────────────────────────────────────────────
#  GUI
# ─────────────────────────────────────────────

class BlackjackGUI:
    def __init__(self, root, music_already_playing=False, menu_music_was_on=True):
        self.root = root
        self.root.title("♠️ CASINO ROYALE BLACKJACK ULTRA ♠️")
        self.root.geometry("1000x720")
        self.root.configure(bg=COLOR_BG)

        self.engine = BlackjackGame()

        # Economie & Inventaris
        self.score = 1000
        self.lives = 0
        self.mults = 0
        self.rigs = 0
        self.peeks = 0
        self.freezes = 0
        self.mulligans = 0

        # Statistieken
        self.win_streak = 0

        # Ronde Status
        self.current_bet = 0
        self.is_manual_mult_active = False
        self.is_dealer_frozen = False
        self.player_hand = []
        self.dealer_hand = []
        self.is_fullscreen = False

        self.setup_ui()
        self.setup_fullscreen_bindings()
        self.update_stats_display()

        # Start in-game music track (unless already playing or was muted in menu)
        if not music_already_playing and menu_music_was_on:
            start_background_music(track="game")
        self.music_on = menu_music_was_on

        # Sync music button label with inherited state
        self.root.after(100, self._sync_music_btn)

    # ── UI SETUP ──────────────────────────────

    def setup_ui(self):
        top_container = tk.Frame(self.root, bg=COLOR_BG)
        top_container.pack(pady=5, fill=tk.X, padx=20)

        header_lbl = tk.Label(top_container, text="★ CASINO ROYALE ULTRA ★",
                               font=("Georgia", 16, "bold italic"), bg=COLOR_BG, fg=COLOR_GOLD)
        header_lbl.pack(side=tk.LEFT)

        self.btn_fullscreen = tk.Button(top_container, text="🖵 Fullscreen (F11)",
                                        command=self.toggle_fullscreen,
                                        font=("Arial", 9, "bold"), bg=COLOR_GOLD,
                                        fg=COLOR_TEXT_DARK, relief=tk.RAISED, cursor="hand2")
        self.btn_fullscreen.pack(side=tk.RIGHT)

        self.btn_music = tk.Button(top_container, text="🎵 Music: ON",
                                   command=self.toggle_music,
                                   font=("Arial", 9, "bold"), bg="#333333",
                                   fg=COLOR_GOLD, relief=tk.RAISED, cursor="hand2")
        self.btn_music.pack(side=tk.RIGHT, padx=8)

        stats_frame = tk.Frame(self.root, bg="#262626", bd=2, relief=tk.RIDGE,
                               highlightbackground=COLOR_GOLD, highlightthickness=1)
        stats_frame.pack(fill=tk.X, padx=20, pady=5)

        self.lbl_score = tk.Label(stats_frame, text="", font=("Courier New", 12, "bold"),
                                   bg="#262626", fg=COLOR_GOLD)
        self.lbl_score.pack(side=tk.LEFT, padx=15, pady=8)

        self.lbl_items = tk.Label(stats_frame, text="", font=("Arial", 10, "bold"),
                                   bg="#262626", fg=COLOR_TEXT_LIGHT)
        self.lbl_items.pack(side=tk.RIGHT, padx=15, pady=8)

        main_split_frame = tk.Frame(self.root, bg=COLOR_BG)
        main_split_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        left_table_frame = tk.Frame(main_split_frame, bg=COLOR_BG)
        left_table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        bet_control_container = tk.Frame(left_table_frame, bg=COLOR_BG)
        bet_control_container.pack(pady=5)

        self.bet_frame = tk.Frame(bet_control_container, bg=COLOR_BG)
        self.bet_frame.pack()

        tk.Label(self.bet_frame, text="PLACE BET ($):", font=("Arial", 11, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT_LIGHT).grid(row=0, column=0, padx=5)
        self.entry_bet = tk.Entry(self.bet_frame, width=10, font=("Courier New", 12, "bold"),
                                  bg="#FFFFFF", fg=COLOR_TEXT_DARK, justify="center")
        self.entry_bet.grid(row=0, column=1, padx=5)
        self.entry_bet.insert(0, "100")

        self.btn_deal = tk.Button(self.bet_frame, text="DEAL", command=self.start_round,
                                  bg="#B81D24", fg=COLOR_TEXT_LIGHT, font=("Arial", 10, "bold"),
                                  width=10, cursor="hand2")
        self.btn_deal.grid(row=0, column=2, padx=5)

        quick_bet_frame = tk.Frame(bet_control_container, bg=COLOR_BG)
        quick_bet_frame.pack(pady=5)

        for amt in [10, 50, 100]:
            tk.Button(quick_bet_frame, text=f"+${amt}",
                      command=lambda a=amt: self.modify_bet(a),
                      bg="#333333", fg=COLOR_GOLD, font=("Arial", 8, "bold"), width=6
                      ).pack(side=tk.LEFT, padx=3)
        tk.Button(quick_bet_frame, text="MAX", command=self.set_max_bet,
                  bg="#333333", fg=COLOR_GOLD, font=("Arial", 8, "bold"), width=6
                  ).pack(side=tk.LEFT, padx=3)

        self.btn_use_mult = tk.Button(bet_control_container,
                                      text="🔥 Activate 2x Multiplier Chip 🔥",
                                      command=self.activate_manual_mult, bg="#4A154B",
                                      fg=COLOR_TEXT_LIGHT, font=("Arial", 9, "bold"), cursor="hand2")
        self.btn_use_mult.pack(pady=5)

        self.board_frame = tk.Frame(left_table_frame, bg=COLOR_FELT, bd=6, relief=tk.SUNKEN,
                                    highlightbackground=COLOR_GOLD, highlightthickness=2)
        self.board_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.dealer_container = tk.Frame(self.board_frame, bg=COLOR_FELT)
        self.dealer_container.pack(pady=5, fill=tk.X, expand=True)

        self.player_container = tk.Frame(self.board_frame, bg=COLOR_FELT)
        self.player_container.pack(pady=5, fill=tk.X, expand=True)

        self.action_frame = tk.Frame(left_table_frame, bg=COLOR_BG)
        self.action_frame.pack(pady=10)

        self.btn_hit = tk.Button(self.action_frame, text="HIT", command=self.player_hit,
                                 state=tk.DISABLED, width=10, bg="#2E7D32",
                                 fg=COLOR_TEXT_LIGHT, font=("Arial", 10, "bold"), cursor="hand2")
        self.btn_hit.grid(row=0, column=0, padx=4)

        self.btn_double = tk.Button(self.action_frame, text="DOUBLE DOWN",
                                    command=self.player_double_down, state=tk.DISABLED, width=12,
                                    bg="#455A64", fg=COLOR_TEXT_LIGHT, font=("Arial", 10, "bold"),
                                    cursor="hand2")
        self.btn_double.grid(row=0, column=1, padx=4)

        self.btn_stand = tk.Button(self.action_frame, text="STAND", command=self.player_stand,
                                   state=tk.DISABLED, width=10, bg="#C62828",
                                   fg=COLOR_TEXT_LIGHT, font=("Arial", 10, "bold"), cursor="hand2")
        self.btn_stand.grid(row=0, column=2, padx=4)

        self.btn_rig = tk.Button(self.action_frame, text="RIG DECK", command=self.player_rig,
                                 state=tk.DISABLED, width=10, bg="#E65100",
                                 fg=COLOR_TEXT_LIGHT, font=("Arial", 10, "bold"), cursor="hand2")
        self.btn_rig.grid(row=0, column=3, padx=4)

        cheat_buttons_frame = tk.Frame(left_table_frame, bg=COLOR_BG)
        cheat_buttons_frame.pack(pady=2)

        self.btn_peek = tk.Button(cheat_buttons_frame, text="👁️ Peek Dealer",
                                  command=self.use_peek, state=tk.DISABLED,
                                  bg="#333333", fg=COLOR_GOLD, font=("Arial", 8, "bold"))
        self.btn_peek.pack(side=tk.LEFT, padx=5)

        self.btn_freeze = tk.Button(cheat_buttons_frame, text="❄️ Freeze Dealer",
                                    command=self.use_freeze, state=tk.DISABLED,
                                    bg="#333333", fg=COLOR_GOLD, font=("Arial", 8, "bold"))
        self.btn_freeze.pack(side=tk.LEFT, padx=5)

        # ── RIGHT PANEL ──────────────────────────────
        right_panel_frame = tk.Frame(main_split_frame, bg="#262626", bd=2, relief=tk.RIDGE,
                                     highlightbackground=COLOR_GOLD, highlightthickness=1, width=240)
        right_panel_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0), pady=5)
        right_panel_frame.pack_propagate(False)

        tk.Label(right_panel_frame, text="💎 VIP CASHIER 💎",
                 font=("Georgia", 11, "bold"), bg="#262626", fg=COLOR_GOLD).pack(pady=10)

        items_config = [
            ('life',     "Extra Leven / Safe",     500),
            ('mult',     "2x Multiplier Chip",      200),
            ('rig',      "Deck Mechanic Rigger",   1500),
            ('peek',     "Card Peek Power",          300),
            ('freeze',   "Dealer Freeze Tech",       600),
            ('mulligan', "Mulligan Reset",           400),
        ]
        for itype, iname, iprice in items_config:
            tk.Button(right_panel_frame, text=f"{iname}\n${iprice}",
                      command=lambda t=itype, p=iprice: self.purchase_item(t, p),
                      bg="#333333", fg=COLOR_GOLD, font=("Arial", 8, "bold"),
                      cursor="hand2", height=2, width=24).pack(pady=4)

        tk.Label(right_panel_frame, text="🏆 LEADERBOARD 🏆",
                 font=("Georgia", 10, "bold"), bg="#262626", fg=COLOR_GOLD).pack(pady=(15, 2))
        self.lbl_leaderboard = tk.Label(right_panel_frame, text="",
                                        font=("Courier New", 8), bg="#262626",
                                        fg=COLOR_TEXT_LIGHT, justify=tk.LEFT)
        self.lbl_leaderboard.pack(pady=5)
        self.load_highscores()

    # ── MUSIC TOGGLE ──────────────────────────

    def _sync_music_btn(self):
        label = "🎵 Music: ON" if self.music_on else "🎵 Music: OFF"
        self.btn_music.config(text=label)

    def toggle_music(self):
        if not PLAYSOUND_AVAILABLE:
            messagebox.showinfo("Music", "Installeer playsound3 voor achtergrondmuziek:\n\npip install playsound3")
            return
        if self.music_on:
            pause_background_music()
            self.music_on = False
            self.btn_music.config(text="🎵 Music: OFF")
        else:
            resume_background_music()
            self.music_on = True
            self.btn_music.config(text="🎵 Music: ON")

    # ── BET HELPERS ───────────────────────────

    def modify_bet(self, amount):
        try:
            current = int(self.entry_bet.get().strip()) if self.entry_bet.get() else 0
            self.entry_bet.delete(0, tk.END)
            self.entry_bet.insert(0, str(min(current + amount, self.score)))
        except ValueError:
            pass

    def set_max_bet(self):
        self.entry_bet.delete(0, tk.END)
        self.entry_bet.insert(0, str(self.score))

    # ── SHOP ──────────────────────────────────

    def purchase_item(self, item_type, price):
        if self.score >= price:
            self.score -= price
            play_sfx("buy")
            attr_map = {'life': 'lives', 'mult': 'mults', 'rig': 'rigs',
                        'peek': 'peeks', 'freeze': 'freezes', 'mulligan': 'mulligans'}
            setattr(self, attr_map[item_type], getattr(self, attr_map[item_type]) + 1)
            self.update_stats_display()
        else:
            messagebox.showerror("VIP Denied", "Onvoldoende fiches om dit item aan te schaffen.")

    # ── FULLSCREEN ────────────────────────────

    def setup_fullscreen_bindings(self):
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        self.btn_fullscreen.config(
            text="🖵 Exit Fullscreen (Esc)" if self.is_fullscreen else "🖵 Fullscreen (F11)")

    def exit_fullscreen(self):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.root.attributes("-fullscreen", False)
            self.btn_fullscreen.config(text="🖵 Fullscreen (F11)")

    # ── STATS ─────────────────────────────────

    def update_stats_display(self):
        self.lbl_score.config(text=f"CHIPS: ${self.score} | STREAK: {self.win_streak}🔥")
        self.lbl_items.config(
            text=(f"❤️:{self.lives} | 🪙:{self.mults} | 🔧:{self.rigs} | "
                  f"👁️:{self.peeks} | ❄️:{self.freezes} | ↩️:{self.mulligans}"))

    # ── MULTIPLIER ────────────────────────────

    def activate_manual_mult(self):
        if self.mults > 0 and not self.is_manual_mult_active:
            self.is_manual_mult_active = True
            self.mults -= 1
            self.update_stats_display()
            messagebox.showinfo("High Roller",
                                "🔥 High Roller Chip Geactiveerd! Dubbele uitbetaling bij winst! 🔥")
        elif self.is_manual_mult_active:
            messagebox.showwarning("Warning", "Er is al een actieve chip ingezet voor deze ronde.")
        else:
            messagebox.showwarning("Error", "Geen Multiplier Chips in je bezit.")

    # ── GAME FLOW ─────────────────────────────

    def start_round(self):
        if self.score <= 0:
            self.check_game_over()
            return

        try:
            bet_val = int(self.entry_bet.get().strip())
            if bet_val <= 0 or bet_val > self.score:
                raise ValueError
            self.current_bet = bet_val
        except ValueError:
            messagebox.showerror("Table Limit",
                                 f"Ongeldige inzet! Voer een bedrag in tussen $1 en ${self.score}.")
            return

        self.engine.generate_shuffled_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.is_dealer_frozen = False

        self.btn_deal.config(state=tk.DISABLED)
        self.btn_use_mult.config(state=tk.DISABLED)

        self.deal_card_animated(self.player_hand, 0)
        self.deal_card_animated(self.dealer_hand, 200)
        self.deal_card_animated(self.player_hand, 400)
        self.deal_card_animated(self.dealer_hand, 600)

        self.root.after(800, self.activate_gameplay_buttons)

    def deal_card_animated(self, hand, delay):
        self.root.after(delay, lambda: [
            play_sfx("deal"),
            hand.append(self.engine.deck.pop()),
            self.update_board_display(hide_dealer=True)
        ])

    def activate_gameplay_buttons(self):
        self.btn_hit.config(state=tk.NORMAL)
        self.btn_stand.config(state=tk.NORMAL)
        self.btn_rig.config(state=tk.NORMAL)
        self.btn_peek.config(state=tk.NORMAL)
        self.btn_freeze.config(state=tk.NORMAL)
        if self.score >= self.current_bet * 2:
            self.btn_double.config(state=tk.NORMAL)
        if self.engine.calculate_score(self.player_hand) == 21:
            self.player_stand()

    def render_hand_widgets(self, container, title, hand, hide_first=False):
        for widget in container.winfo_children():
            widget.destroy()

        score_suffix = "" if hide_first else f" ({self.engine.calculate_score(hand)})"
        tk.Label(container, text=f"{title}{score_suffix}",
                 font=("Georgia", 11, "bold"), bg=COLOR_FELT, fg=COLOR_GOLD).pack()

        cards_frame = tk.Frame(container, bg=COLOR_FELT)
        cards_frame.pack(expand=True)

        for idx, card in enumerate(hand):
            card_lbl = tk.Label(cards_frame, width=14, height=7, bd=2, relief=tk.RAISED)
            if hide_first and idx == 0:
                card_lbl.config(text="◆ ◆ ◆ ◆\n◆ CASINO ◆\n◆ ◆ ◆ ◆",
                                bg="#8B0000", fg="#FFFFFF",
                                font=("Courier New", 9, "bold"), justify=tk.CENTER)
            else:
                card_text = f"{card.rank} of\n{card.suit.split()[-1]}\n\n{card.symbol}"
                card_lbl.config(text=card_text, bg=card.color, fg=COLOR_TEXT_DARK,
                                font=("Courier New", 10, "bold"), justify=tk.CENTER)
            card_lbl.pack(side=tk.LEFT, padx=6, pady=2)

    def update_board_display(self, hide_dealer=True):
        self.render_hand_widgets(self.dealer_container, "DEALER HAND",
                                 self.dealer_hand, hide_first=hide_dealer)
        self.render_hand_widgets(self.player_container, "YOUR HAND",
                                 self.player_hand, hide_first=False)

    def player_hit(self):
        self.btn_double.config(state=tk.DISABLED)
        self.player_hand.append(self.engine.deck.pop())
        self.update_board_display(hide_dealer=True)
        p_score = self.engine.calculate_score(self.player_hand)
        if p_score > 21:
            if self.mulligans > 0:
                ans = messagebox.askyesno(
                    "Mulligan?",
                    "Je gaat BUST! Wil je een Mulligan inzetten om je laatste kaart weg te gooien?")
                if ans:
                    self.mulligans -= 1
                    self.player_hand.pop()
                    self.update_stats_display()
                    self.update_board_display(hide_dealer=True)
                    return
            self.player_stand()
        elif p_score == 21:
            self.player_stand()

    def player_double_down(self):
        self.current_bet *= 2
        self.player_hand.append(self.engine.deck.pop())
        self.update_board_display(hide_dealer=True)
        self.player_stand()

    def use_peek(self):
        if self.peeks > 0:
            self.peeks -= 1
            self.update_stats_display()
            messagebox.showinfo("Card Peek",
                                f"De verborgen kaart van de dealer is:\n{self.dealer_hand[-1]}")
        else:
            messagebox.showwarning("Error", "Je hebt geen Card Peeks in je bezit.")

    def use_freeze(self):
        if self.freezes > 0:
            self.freezes -= 1
            self.is_dealer_frozen = True
            self.update_stats_display()
            messagebox.showinfo("Dealer Frozen",
                                "❄️ De dealer is bevroren! Hij zal stoppen op elke waarde vanaf 15! ❄️")
        else:
            messagebox.showwarning("Error", "Je hebt geen Dealer Freezes in je bezit.")

    def player_rig(self):
        if self.rigs <= 0:
            messagebox.showwarning("No Riggers", "Je hebt geen Deck Riggers over.")
            return

        raw_input = simpledialog.askstring(
            "Card Mechanic",
            f"Kies een waarde om naar boven te halen:\n{', '.join(RANKS)}")
        if raw_input is None:
            return

        target = raw_input.strip().capitalize()
        if target in RANKS:
            found = next((i for i, c in enumerate(self.engine.deck) if c.rank == target), None)
            if found is not None:
                self.engine.deck.append(self.engine.deck.pop(found))
                self.rigs -= 1
                self.update_stats_display()
                self.player_hand.append(self.engine.deck.pop())
                self.update_board_display(hide_dealer=True)
                messagebox.showinfo("Card Rigged",
                                    f"Sleight of hand geslaagd! Je trekt een: {self.player_hand[-1]}")
                if self.engine.calculate_score(self.player_hand) >= 21:
                    self.player_stand()
            else:
                messagebox.showerror("Error",
                                     f"Er zitten geen {target} kaarten meer in het deck.")

    def player_stand(self):
        for btn in (self.btn_hit, self.btn_double, self.btn_stand,
                    self.btn_rig, self.btn_peek, self.btn_freeze):
            btn.config(state=tk.DISABLED)

        p_final = self.engine.calculate_score(self.player_hand)

        if p_final > 21:
            self.score -= self.current_bet
            self.win_streak = 0
            play_sfx("loss")
            messagebox.showinfo("Bust", f"Bust! Je verliest ${self.current_bet} aan fiches.")
            self.clean_up_round()
            return

        stop_limit = 15 if self.is_dealer_frozen else 17
        while self.engine.calculate_score(self.dealer_hand) < stop_limit:
            self.dealer_hand.append(self.engine.deck.pop())

        self.update_board_display(hide_dealer=False)
        d_final = self.engine.calculate_score(self.dealer_hand)

        if d_final > 21 or p_final > d_final:
            win_mult = 1
            chance = random.random()
            bonus_msg = ""
            if chance < 0.05:
                bonus_msg = "✨ TRIPLE WIN BONUS! ✨\n"
                win_mult = 3
            elif chance < 0.15:
                bonus_msg = "✨ DOUBLE WIN BONUS! ✨\n"
                win_mult = 2
            final_factor = (win_mult * 2) if self.is_manual_mult_active else win_mult
            winnings = self.current_bet * final_factor
            self.score += winnings
            self.win_streak += 1
            play_sfx("win")
            messagebox.showinfo("Payout!",
                                f"{bonus_msg}Gefeliciteerd, je wint de hand! +${winnings} aan fiches.")
        elif p_final < d_final:
            self.score -= self.current_bet
            self.win_streak = 0
            play_sfx("loss")
            messagebox.showinfo("House Wins", f"De bank wint! Je verliest ${self.current_bet}.")
        else:
            messagebox.showinfo("Push", "Gelijkspel! Je inzet wordt teruggegeven.")

        self.clean_up_round()

    def clean_up_round(self):
        self.is_manual_mult_active = False
        self.update_stats_display()
        self.btn_deal.config(state=tk.NORMAL)
        self.btn_use_mult.config(state=tk.NORMAL)
        self.check_game_over()

    def check_game_over(self):
        if self.score <= 0:
            if self.lives > 0:
                self.lives -= 1
                self.score = 100
                self.update_stats_display()
                messagebox.showinfo("Insurance Saved",
                                    "💀 Bankroet voorkomen! Je herstart met $100.")
            else:
                self.save_highscore()
                ans = messagebox.askyesno(
                    "BANKROET",
                    "Geen fiches en levens meer! Wil je opnieuw inkopen bij de tafel?")
                if ans:
                    for attr in ('score', 'lives', 'mults', 'rigs',
                                 'peeks', 'freezes', 'mulligans', 'win_streak'):
                        setattr(self, attr, 1000 if attr == 'score' else 0)
                    self.update_stats_display()
                else:
                    stop_background_music()
                    self.root.destroy()
                    sys.exit()

    def save_highscore(self):
        name = simpledialog.askstring("High Score!",
                                      "Je bent bankroet! Voer je naam in voor het Leaderboard:")
        if not name:
            name = "VIP Player"

        scores = []
        if os.path.exists(HIGHSCORE_FILE):
            with open(HIGHSCORE_FILE, "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) == 2:
                        try:
                            scores.append((parts[0], int(parts[1])))
                        except ValueError:
                            pass

        scores.append((name, self.win_streak))
        scores = sorted(scores, key=lambda x: x[1], reverse=True)[:5]

        with open(HIGHSCORE_FILE, "w") as f:
            for sname, sstreak in scores:
                f.write(f"{sname}:{sstreak}\n")
        self.load_highscores()

    def load_highscores(self):
        if not os.path.exists(HIGHSCORE_FILE):
            self.lbl_leaderboard.config(text="No scores yet.")
            return

        text = ""
        with open(HIGHSCORE_FILE, "r") as f:
            for idx, line in enumerate(f):
                parts = line.strip().split(":")
                if len(parts) == 2:
                    text += f"{idx + 1}. {parts[0][:10]:<10} - {parts[1]} wins\n"
        self.lbl_leaderboard.config(text=text)


# ─────────────────────────────────────────────
#  MAIN MENU
# ─────────────────────────────────────────────

class MainMenuGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("♠️ CASINO ROYALE BLACKJACK ULTRA ♠️")
        self.root.geometry("700x600")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        # Start grand lounge music on menu screen
        start_background_music(track="menu")

        self._build_ui()
        self._animate_title(0)

    def _build_ui(self):
        # ── Outer glow border frame ──
        border = tk.Frame(self.root, bg=COLOR_GOLD, bd=3)
        border.place(relx=0.05, rely=0.04, relwidth=0.90, relheight=0.92)

        inner = tk.Frame(border, bg=COLOR_BG)
        inner.place(relx=0.003, rely=0.005, relwidth=0.994, relheight=0.990)

        # ── Felt strip behind title ──
        felt_strip = tk.Frame(inner, bg=COLOR_FELT, height=110)
        felt_strip.pack(fill=tk.X)

        # ── Animated title ──
        self.lbl_title = tk.Label(
            felt_strip,
            text="♠  CASINO ROYALE  ♠",
            font=("Georgia", 30, "bold italic"),
            bg=COLOR_FELT, fg=COLOR_GOLD
        )
        self.lbl_title.pack(pady=(18, 2))

        self.lbl_subtitle = tk.Label(
            felt_strip,
            text="B L A C K J A C K   U L T R A",
            font=("Courier New", 11, "bold"),
            bg=COLOR_FELT, fg=COLOR_TEXT_LIGHT,
        )
        self.lbl_subtitle.pack()

        # ── Card suit decorations ──
        suits_frame = tk.Frame(inner, bg=COLOR_BG)
        suits_frame.pack(pady=12)
        for suit, color in [("♠", COLOR_TEXT_LIGHT), ("♥", COLOR_RED_CARD),
                             ("♦", COLOR_RED_CARD), ("♣", COLOR_TEXT_LIGHT)]:
            tk.Label(suits_frame, text=suit, font=("Arial", 28), bg=COLOR_BG,
                     fg=color).pack(side=tk.LEFT, padx=18)

        # ── Menu buttons ──
        btn_cfg = dict(font=("Georgia", 13, "bold"), width=22, cursor="hand2",
                       relief=tk.FLAT, bd=0, pady=10)

        tk.Button(inner, text="▶   PLAY NOW", bg=COLOR_GOLD, fg=COLOR_TEXT_DARK,
                  command=self._start_game, **btn_cfg).pack(pady=8)

        tk.Button(inner, text="🏆   LEADERBOARD", bg="#2A2A2A", fg=COLOR_GOLD,
                  command=self._show_leaderboard, **btn_cfg).pack(pady=4)

        tk.Button(inner, text="📖   HOW TO PLAY", bg="#2A2A2A", fg=COLOR_GOLD,
                  command=self._show_help, **btn_cfg).pack(pady=4)

        tk.Button(inner, text="🎵   MUSIC: ON", bg="#2A2A2A", fg=COLOR_GOLD,
                  command=self._toggle_music, **btn_cfg).pack(pady=4)
        self._music_btn = inner.winfo_children()[-1]

        tk.Button(inner, text="✖   QUIT", bg="#5A0000", fg=COLOR_TEXT_LIGHT,
                  command=self._quit, **btn_cfg).pack(pady=8)

        # ── Footer ──
        tk.Label(inner, text="© Casino Royale Ultra  •  Good luck at the tables  •  Made By Utku Yeniay",
                 font=("Arial", 10), bg=COLOR_BG, fg="#555555").pack(side=tk.BOTTOM, pady=10)

        self._music_on = True

    def _animate_title(self, step):
        """Pulse the title color between gold and white."""
        colors = [COLOR_GOLD, "#FFE066", "#FFFFFF", "#FFE066", COLOR_GOLD]
        self.lbl_title.config(fg=colors[step % len(colors)])
        self.root.after(500, self._animate_title, step + 1)

    def _toggle_music(self):
        if self._music_on:
            pause_background_music()
            self._music_on = False
            self._music_btn.config(text="🎵   MUSIC: OFF")
        else:
            resume_background_music()
            self._music_on = True
            self._music_btn.config(text="🎵   MUSIC: ON")

    def _start_game(self):
        # Stop menu music instantly, then launch the game
        stop_background_music()
        self.root.destroy()
        game_window = tk.Tk()
        app = BlackjackGUI(game_window, music_already_playing=False, menu_music_was_on=self._music_on)
        game_window.mainloop()

    def _show_leaderboard(self):
        win = tk.Toplevel(self.root)
        win.title("Leaderboard")
        win.geometry("340x280")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)
        tk.Label(win, text="TOP PLAYERS", font=("Georgia", 14, "bold"),
                 bg=COLOR_BG, fg=COLOR_GOLD).pack(pady=12)
        if not os.path.exists(HIGHSCORE_FILE):
            tk.Label(win, text="No scores yet. Play a game first!",
                     font=("Courier New", 11), bg=COLOR_BG, fg=COLOR_TEXT_LIGHT).pack(pady=20)
        else:
            text = ""
            with open(HIGHSCORE_FILE, "r") as f:
                for idx, line in enumerate(f):
                    parts = line.strip().split(":")
                    if len(parts) == 2:
                        medals = ["1.", "2.", "3.", "4.", "5."]
                        medal = medals[idx] if idx < len(medals) else str(idx+1)+"."
                        text += "  {}  {:<12}  {} wins\n".format(medal, parts[0][:12], parts[1])
            tk.Label(win, text=text or "No scores yet.", font=("Courier New", 11),
                     bg=COLOR_BG, fg=COLOR_TEXT_LIGHT, justify=tk.LEFT).pack(pady=10, padx=20)
        tk.Button(win, text="Close", command=win.destroy, bg=COLOR_GOLD,
                  fg=COLOR_TEXT_DARK, font=("Arial", 10, "bold"), width=10).pack(pady=10)

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("How to Play")
        win.geometry("440x460")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)
        tk.Label(win, text="HOW TO PLAY", font=("Georgia", 14, "bold"),
                 bg=COLOR_BG, fg=COLOR_GOLD).pack(pady=12)
        lines = [
            "GOAL",
            "  Beat the dealer by getting closer to 21",
            "  without going over (bust).",
            "",
            "ACTIONS",
            "  HIT         - Draw another card",
            "  STAND       - Keep your hand",
            "  DOUBLE DOWN - Double your bet, draw once",
            "",
            "POWER-UPS  (buy in the VIP Cashier)",
            "  Extra Life  - Saves you from bankruptcy",
            "  Multiplier  - 2x payout on next win",
            "  Rig Deck    - Pick your next card",
            "  Peek        - See dealers hidden card",
            "  Freeze      - Dealer stops at 15",
            "  Mulligan    - Undo a bust card",
            "",
            "Win hands to build your streak.",
            "High streaks earn leaderboard fame!",
        ]
        rules = "\n".join(lines)
        tk.Label(win, text=rules, font=("Courier New", 10), bg=COLOR_BG,
                 fg=COLOR_TEXT_LIGHT, justify=tk.LEFT).pack(padx=20, pady=5)
        tk.Button(win, text="Lets Play!", command=win.destroy, bg=COLOR_GOLD,
                  fg=COLOR_TEXT_DARK, font=("Arial", 10, "bold"), width=12).pack(pady=12)

    def _quit(self):
        stop_background_music()
        self.root.destroy()
        sys.exit()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    main_window = tk.Tk()
    MainMenuGUI(main_window)
    main_window.mainloop()