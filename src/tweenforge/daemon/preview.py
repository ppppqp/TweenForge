"""Tkinter preview window for the companion daemon.

Shows generated inbetween frames as a strip with playback controls
and accept/reject buttons. Lightweight — no browser needed.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import Image, ImageTk

THUMB_SIZE = 96
PLAYBACK_MS = 120  # ~8fps


class PreviewWindow:
    """A small popup showing generated frames with accept/reject."""

    def __init__(
        self,
        frame_a_path: Path,
        frame_b_path: Path,
        generated_paths: list[Path],
        on_accept: Callable[[], None],
        on_reject: Callable[[], None],
    ):
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._all_paths = [frame_a_path] + generated_paths + [frame_b_path]
        self._playing = False
        self._play_index = 0
        self._play_job = None

        self.root = tk.Tk()
        self.root.title("TweenForge — Preview")
        self.root.configure(bg="#2b2b2b")
        self.root.resizable(False, False)

        # Load all images as thumbnails
        self._photos: list[ImageTk.PhotoImage] = []
        self._labels: list[str] = []
        for i, p in enumerate(self._all_paths):
            img = Image.open(p)
            img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._photos.append(photo)
            if i == 0:
                self._labels.append("Key A")
            elif i == len(self._all_paths) - 1:
                self._labels.append("Key B")
            else:
                self._labels.append(f"tw {i}")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._reject)

    def _build_ui(self):
        bg = "#2b2b2b"
        fg = "#e0e0e0"
        muted = "#888888"

        # Title
        tk.Label(
            self.root, text="TweenForge Preview", font=("Helvetica", 14, "bold"),
            bg=bg, fg=fg,
        ).pack(pady=(12, 4))

        tk.Label(
            self.root, text=f"{len(self._all_paths) - 2} inbetween(s) generated",
            font=("Helvetica", 10), bg=bg, fg=muted,
        ).pack(pady=(0, 8))

        # Frame strip
        strip_frame = tk.Frame(self.root, bg=bg)
        strip_frame.pack(padx=12, pady=4)

        self._thumb_labels: list[tk.Label] = []
        for i, (photo, label_text) in enumerate(zip(self._photos, self._labels)):
            col_frame = tk.Frame(strip_frame, bg=bg)
            col_frame.pack(side=tk.LEFT, padx=3)

            img_label = tk.Label(col_frame, image=photo, bg="#1a1a1a", bd=2, relief="solid")
            img_label.pack()
            self._thumb_labels.append(img_label)

            tk.Label(col_frame, text=label_text, font=("Helvetica", 9), bg=bg, fg=muted).pack()

        # Large preview (shows current playback frame)
        self._large_photos: list[ImageTk.PhotoImage] = []
        for p in self._all_paths:
            img = Image.open(p)
            img.thumbnail((320, 320), Image.Resampling.LANCZOS)
            self._large_photos.append(ImageTk.PhotoImage(img))

        self._large_label = tk.Label(self.root, image=self._large_photos[0], bg="#1a1a1a")
        self._large_label.pack(padx=12, pady=8)

        # Playback controls
        ctrl_frame = tk.Frame(self.root, bg=bg)
        ctrl_frame.pack(pady=4)

        btn_style = {"font": ("Helvetica", 12), "bg": "#404040", "fg": fg,
                      "activebackground": "#555", "activeforeground": fg,
                      "bd": 0, "padx": 10, "pady": 4}

        tk.Button(ctrl_frame, text="\u25C0", command=self._prev_frame, **btn_style).pack(side=tk.LEFT, padx=4)
        self._play_btn = tk.Button(ctrl_frame, text="\u25B6", command=self._toggle_play, **btn_style)
        self._play_btn.pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl_frame, text="\u25B6", command=self._next_frame, **btn_style).pack(side=tk.LEFT, padx=4)

        # Accept / Reject
        action_frame = tk.Frame(self.root, bg=bg)
        action_frame.pack(pady=(8, 12))

        tk.Button(
            action_frame, text="Accept & Import", command=self._accept,
            font=("Helvetica", 12, "bold"), bg="#5bd565", fg="#1a1a1a",
            activebackground="#4cc44f", bd=0, padx=16, pady=6,
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            action_frame, text="Discard", command=self._reject,
            font=("Helvetica", 12), bg="#404040", fg=fg,
            activebackground="#555", bd=0, padx=16, pady=6,
        ).pack(side=tk.LEFT, padx=6)

    def _show_frame(self, index: int):
        self._play_index = index % len(self._all_paths)
        self._large_label.configure(image=self._large_photos[self._play_index])
        # Highlight active thumbnail
        for i, lbl in enumerate(self._thumb_labels):
            lbl.configure(bd=2 if i == self._play_index else 1)

    def _next_frame(self):
        self._show_frame(self._play_index + 1)

    def _prev_frame(self):
        self._show_frame(self._play_index - 1)

    def _toggle_play(self):
        if self._playing:
            self._playing = False
            self._play_btn.configure(text="\u25B6")
            if self._play_job:
                self.root.after_cancel(self._play_job)
        else:
            self._playing = True
            self._play_btn.configure(text="\u23F8")
            self._play_step()

    def _play_step(self):
        if not self._playing:
            return
        self._show_frame(self._play_index + 1)
        self._play_job = self.root.after(PLAYBACK_MS, self._play_step)

    def _accept(self):
        self._playing = False
        self.root.destroy()
        self._on_accept()

    def _reject(self):
        self._playing = False
        self.root.destroy()
        self._on_reject()

    def show(self):
        """Display the preview window. Blocks until closed."""
        self.root.mainloop()
