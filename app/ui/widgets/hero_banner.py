"""
The cinematic hero banner.

A wide, dramatic header: a darkened background image with a crimson gradient
wash, a vignette, faint red speckle, and text laid over it — a small tracked-out
red kicker, a huge heavy "REVENGE" headline, a subtitle with red-highlighted
numbers, and a live clock + date in the top-right.

Why it is drawn as one baked image (instead of stacking transparent labels):
in CustomTkinter a "transparent" label actually paints its parent's color, not
the pixels of a sibling image behind it — so placed text labels would show up as
solid rectangles hiding the artwork. Instead we composite everything with
Pillow into a single picture and show that in one label. Only the clock changes
each second, so we cache the static picture and just redraw the time onto a copy
of it once per second (cheap).
"""

from __future__ import annotations

import os
from datetime import datetime

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import config
from app.ui import theme

# Height of the banner in logical pixels.
_HEIGHT = 220

# Windows font filenames tried in order for each role (PIL finds these in the
# Windows fonts folder by bare name). load_default() is the last resort.
_DISPLAY_FONTS = ["ariblk.ttf", "bahnschrift.ttf", "impact.ttf", "arialbd.ttf"]
_MONO_FONTS = ["consola.ttf", "CascadiaMono.ttf", "cour.ttf"]
_MONO_BOLD_FONTS = ["consolab.ttf", "CascadiaMono-Bold.ttf", "courbd.ttf"]


def _load_font(candidates, size):
    """Return the first loadable TrueType font from ``candidates`` at ``size``."""
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class HeroBanner(ctk.CTkFrame):
    """A fixed-height cinematic header image with a live clock."""

    def __init__(self, master, context, height: int = _HEIGHT) -> None:
        super().__init__(master, height=height, corner_radius=0, fg_color="#0A0A0C")
        self.ctx = context
        self._h = height
        self.pack_propagate(False)
        self.grid_propagate(False)

        # One label shows the whole composite.
        self._label = ctk.CTkLabel(self, text="")
        self._label.pack(fill="both", expand=True)

        # Cached static composite (everything except the clock), plus jobs and a
        # strong reference to the CTkImage (which is garbage-collected — and the
        # label goes blank — if we do not keep it).
        self._static: Image.Image | None = None
        self._ctkimg = None
        self._last_w = 0
        self._resize_job = None
        self._clock_job = None
        self._running = False

        self.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", lambda _e: self._cancel_jobs())

    # ------------------------------------------------------------------ #
    # Lifecycle (host view calls these from on_show / on_hide)
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._running = True
        # Defer the first render until the frame has a real width.
        self.after(50, lambda: self._render_static(self.winfo_width()))

    def stop(self) -> None:
        self._running = False
        self._cancel_jobs()

    def reload(self) -> None:
        """Re-read the configurable text/image and repaint (e.g. after Settings)."""
        self._render_static(self.winfo_width() or self._last_w)

    def _cancel_jobs(self) -> None:
        for job in (self._resize_job, self._clock_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass
        self._resize_job = self._clock_job = None

    # ------------------------------------------------------------------ #
    # Resize handling (debounced)
    # ------------------------------------------------------------------ #
    def _on_configure(self, event) -> None:
        width = event.width
        if width < 10 or width == self._last_w:
            return
        self._last_w = width
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, lambda: self._render_static(width))

    # ------------------------------------------------------------------ #
    # Building the static composite
    # ------------------------------------------------------------------ #
    def _settings(self):
        kicker = self.ctx.get_setting("hero_kicker", "OPERATION : DISCIPLINE · HOME")
        headline = self.ctx.get_setting("hero_headline", "REVENGE")
        subtitle = self.ctx.get_setting(
            "hero_subtitle",
            "The comeback starts now. Every logged minute is a step toward the goal.")
        img_setting = self.ctx.get_setting("hero_image_path", "")
        return kicker, headline, subtitle, img_setting

    def _resolve_image_path(self, img_setting: str) -> str | None:
        """Find the background image: explicit setting, else assets/hero.*."""
        if img_setting:
            path = img_setting if os.path.isabs(img_setting) else os.path.join(
                config.ASSETS_DIR, img_setting)
            if os.path.exists(path):
                return path
        for name in ("hero.png", "hero.jpg", "hero.jpeg"):
            candidate = os.path.join(config.ASSETS_DIR, name)
            if os.path.exists(candidate):
                return candidate
        return None

    def _scale(self) -> float:
        try:
            return float(ctk.ScalingTracker.get_widget_scaling(self))
        except Exception:  # noqa: BLE001
            return 1.0

    def _render_static(self, width: int) -> None:
        if not self._running or width < 10:
            return
        scale = self._scale()
        wp, hp = max(1, round(width * scale)), max(1, round(self._h * scale))
        kicker, headline, subtitle, img_setting = self._settings()

        base = self._build_base(self._resolve_image_path(img_setting), wp, hp)
        base = self._apply_overlays(base, wp, hp)
        self._draw_static_text(base, wp, hp, scale, kicker, headline, subtitle)

        self._static = base
        self._paint()             # draw the clock and show it immediately
        if self._clock_job is None:
            self._tick()          # start the once-a-second clock loop

    def _build_base(self, image_path, wp, hp) -> Image.Image:
        """The background layer: the user's image cover-fit, or a generated glow."""
        if image_path:
            try:
                src = Image.open(image_path).convert("RGBA")
                # Cover-fill the banner, biased slightly upward toward the face.
                base = ImageOps.fit(src, (wp, hp), method=Image.LANCZOS,
                                    centering=(0.5, 0.32))
                # Darken and desaturate so text and the red wash read on top.
                base = ImageEnhance.Brightness(base.convert("RGB")).enhance(0.5)
                base = ImageEnhance.Color(base).enhance(0.75).convert("RGBA")
                return base
            except Exception:  # noqa: BLE001 - fall through to generated
                pass
        return self._generated_base(wp, hp)

    def _generated_base(self, wp, hp) -> Image.Image:
        """A dramatic dark-red vertical gradient + off-center glow (no image)."""
        top, bottom = (20, 6, 10), (10, 10, 12)
        col = Image.new("L", (1, hp))
        for y in range(hp):
            col.putpixel((0, y), int(255 * y / max(1, hp - 1)))
        col = col.resize((wp, hp))
        base = Image.new("RGBA", (wp, hp))
        top_img = Image.new("RGBA", (wp, hp), top + (255,))
        bot_img = Image.new("RGBA", (wp, hp), bottom + (255,))
        base = Image.composite(bot_img, top_img, col)
        # Soft red radial glow left-of-center.
        glow_mask = Image.new("L", (wp, hp), 0)
        ImageDraw.Draw(glow_mask).ellipse(
            [int(wp * 0.05), int(-hp * 0.3), int(wp * 0.6), int(hp * 1.3)], fill=90)
        glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(radius=max(20, wp * 0.12)))
        glow = Image.new("RGBA", (wp, hp), (225, 29, 42, 255))
        glow.putalpha(glow_mask)
        return Image.alpha_composite(base, glow)

    def _apply_overlays(self, base, wp, hp) -> Image.Image:
        """Red edge wash, bottom scrim, vignette and faint speckle."""
        # 1. Left→right red wash (darkest on the left, where the text sits).
        grad = Image.new("L", (wp, 1))
        for x in range(wp):
            grad.putpixel((x, 0), int(150 * (1 - x / wp) ** 1.5))
        grad = grad.resize((wp, hp))
        red = Image.new("RGBA", (wp, hp), (200, 20, 32, 255))
        red.putalpha(grad)
        base = Image.alpha_composite(base, red)

        # 2. Bottom→top dark scrim so the headline/subtitle always have contrast.
        vgrad = Image.new("L", (1, hp))
        for y in range(hp):
            vgrad.putpixel((0, y), int(160 * (y / hp) ** 1.7))
        vgrad = vgrad.resize((wp, hp))
        dark = Image.new("RGBA", (wp, hp), (7, 5, 8, 255))
        dark.putalpha(vgrad)
        base = Image.alpha_composite(base, dark)

        # 3. Vignette: darken the corners.
        vig = Image.new("L", (wp, hp), 0)
        ImageDraw.Draw(vig).ellipse(
            [int(-wp * 0.15), int(-hp * 0.35), int(wp * 1.15), int(hp * 1.35)], fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(radius=max(30, hp * 0.4)))
        shadow = Image.new("RGBA", (wp, hp), (4, 4, 6, 255))
        shadow.putalpha(ImageOps.invert(vig))
        base = Image.alpha_composite(base, shadow)

        # 4. Faint red speckle for texture.
        try:
            noise = Image.effect_noise((wp, hp), 22).point(lambda p: 40 if p > 205 else 0)
            spec = Image.new("RGBA", (wp, hp), (255, 70, 85, 255))
            spec.putalpha(noise)
            base = Image.alpha_composite(base, spec)
        except Exception:  # noqa: BLE001 - texture is optional
            pass
        return base

    def _draw_static_text(self, base, wp, hp, scale, kicker, headline, subtitle) -> None:
        draw = ImageDraw.Draw(base)
        px = lambda v: int(v * scale)   # noqa: E731 - tiny local helper

        display = _load_font(_DISPLAY_FONTS, px(theme.HERO_HEADLINE_SIZE))
        mono = _load_font(_MONO_FONTS, px(theme.HERO_KICKER_SIZE))
        mono_sub = _load_font(_MONO_FONTS, px(theme.HERO_SUBTITLE_SIZE))

        left = px(30)
        # Kicker (small, tracked, red, uppercase).
        self._tracked(draw, (left, px(26)), kicker.upper(), mono, "#FF4655", px(3))
        # Headline (huge, white, wide tracking).
        self._tracked(draw, (left, px(52)), headline.upper(), display, "#FFFFFF", px(11))
        # Subtitle, with digit runs highlighted red.
        self._runs(draw, (left, hp - px(46)), subtitle, mono_sub, "#B9BEC6", "#FF4655")

    def _tracked(self, draw, pos, text, font, fill, track) -> int:
        """Draw ``text`` with manual letter-spacing; return the ending x."""
        x, y = pos
        for ch in text:
            draw.text((x, y), ch, font=font, fill=fill)
            x += int(draw.textlength(ch, font=font)) + track
        return x

    def _runs(self, draw, pos, text, font, base_fill, num_fill) -> None:
        """Draw ``text`` splitting digit runs into ``num_fill`` (red)."""
        x, y = pos
        run, run_is_digit = "", False

        def flush(chunk, is_digit):
            nonlocal x
            if not chunk:
                return
            draw.text((x, y), chunk, font=font, fill=(num_fill if is_digit else base_fill))
            x += int(draw.textlength(chunk, font=font))

        for ch in text:
            is_digit = ch.isdigit()
            if is_digit != run_is_digit and run:
                flush(run, run_is_digit)
                run = ""
            run += ch
            run_is_digit = is_digit
        flush(run, run_is_digit)

    # ------------------------------------------------------------------ #
    # The live clock (only moving part)
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        if not self._running or self._static is None:
            return
        self._paint()
        self._clock_job = self.after(1000, self._tick)

    def _paint(self) -> None:
        if self._static is None:
            return
        scale = self._scale()
        px = lambda v: int(v * scale)   # noqa: E731
        wp, hp = self._static.size
        frame = self._static.copy()
        draw = ImageDraw.Draw(frame)

        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%a %d %b %Y").upper()

        big = _load_font(_MONO_BOLD_FONTS, px(theme.CLOCK_SIZE))
        small = _load_font(_MONO_FONTS, px(theme.DATE_SIZE))
        right = wp - px(30)

        tw = draw.textlength(time_str, font=big)
        draw.text((right - tw, px(20)), time_str, font=big, fill="#FFFFFF")
        dw = draw.textlength(date_str, font=small)
        self._tracked(draw, (int(right - dw - px(6) * (len(date_str) - 1)), px(20) + px(theme.CLOCK_SIZE) + px(6)),
                      date_str, small, "#8B9099", px(3))

        # Logical size = physical / scale, so CTk renders 1:1 and crisp.
        logical = (max(1, round(wp / scale)), max(1, round(hp / scale)))
        self._ctkimg = ctk.CTkImage(light_image=frame, dark_image=frame, size=logical)
        self._label.configure(image=self._ctkimg)
