"""
manim-poc-5s.py — Proof of Concept manim untuk Shorts infografis 5 detik.

Tujuan: validate manim look + render time di sandbox.
Konten sample: infografis statistik penduduk Jawa.
Output: 1080x1920 vertical, 30fps, 5 detik, NO LaTeX (Text class + Pango only).
"""
from manim import (
    Scene, Text, FadeIn, Write, UP, DOWN, ORIGIN,
    config, WHITE, YELLOW, BLUE, GREEN, RED,
)


# Vertical 1080x1920 untuk Shorts
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_rate = 30
config.background_color = "#1C1C2E"  # charcoal, manim signature dark


class InfografisPOC(Scene):
    def construct(self):
        # 0-1s: Title fade in dari bawah
        title = Text("Statistik Penduduk", font="Noto Sans", font_size=48, color=WHITE)
        title.move_to(UP * 3)
        self.play(FadeIn(title, shift=UP * 0.5), run_time=1.0)

        # 1-2s: Subtitle
        subtitle = Text("Bahasa Jawa", font="Noto Sans", font_size=64, color=YELLOW)
        subtitle.next_to(title, DOWN, buff=0.4)
        self.play(Write(subtitle), run_time=1.0)

        # 2-4s: Angka besar count-up style (Write animation, terasa diketik)
        number = Text("84 juta", font="Noto Sans", font_size=120, color=BLUE)
        number.move_to(ORIGIN)
        self.play(Write(number), run_time=2.0)

        # 4s: Caption di bawah angka
        caption = Text("penutur aktif", font="Noto Sans", font_size=36, color=GREEN)
        caption.next_to(number, DOWN, buff=0.5)
        self.play(FadeIn(caption, shift=UP * 0.3), run_time=0.5)

        # 4.5-5s: Source
        source = Text("Sumber: BPS 2020", font="Noto Sans", font_size=24, color=WHITE)
        source.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(source), run_time=0.5)

        # Hold 0.5s
        self.wait(0.5)
