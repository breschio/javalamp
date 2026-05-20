"""Matrix rain — per-column streams of falling glyphs with bright heads."""

from __future__ import annotations

from rich.style import Style

from javalamp.scene import Scene, register

_GLYPHS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "0123456789@#$%&*+=-_<>?/\\|"
)


@register
class MatrixScene(Scene):
    name = "matrix"
    title = "Matrix Rain"
    description = "Cascading glyphs in the canonical green wash."

    def setup(self) -> None:
        self.cols = self.width
        # Per-column: head_y (float), speed (cells/sec), trail_len.
        self.head_y = [self.rng.uniform(-self.height, 0) for _ in range(self.cols)]
        self.speed = [self.rng.uniform(8, 22) for _ in range(self.cols)]
        self.trail = [self.rng.randint(6, max(7, self.height // 2)) for _ in range(self.cols)]
        # Pre-pick glyphs per (col, row) so a column's column doesn't shimmer.
        self.glyphs = [
            [self.rng.choice(_GLYPHS) for _ in range(self.height)]
            for _ in range(self.cols)
        ]
        # Periodically swap a glyph so it feels alive.
        self.swap_clock = 0.0

    def update(self, frame: int, dt: float) -> None:
        self.canvas.clear()
        ramp = self.theme.ramp
        # Fade ramp from tail->head: indices low (dim) to high (bright).
        head_color = self.theme.highlight
        bright = ramp[-2]
        mids = (ramp[-3], ramp[-4])
        tail = ramp[-5] if len(ramp) > 5 else self.theme.dim

        for x in range(self.cols):
            self.head_y[x] += self.speed[x] * dt
            head = int(self.head_y[x])
            tlen = self.trail[x]
            for i in range(tlen):
                y = head - i
                if y < 0 or y >= self.height:
                    continue
                ch = self.glyphs[x][y % self.height]
                if i == 0:
                    style = Style(color=head_color, bgcolor=self.theme.bg, bold=True)
                elif i == 1:
                    style = Style(color=bright, bgcolor=self.theme.bg, bold=True)
                elif i < 4:
                    style = Style(color=mids[i % 2], bgcolor=self.theme.bg)
                else:
                    style = Style(color=tail, bgcolor=self.theme.bg, dim=True)
                self.canvas.set(x, y, ch, style)
            # Reset stream after it fully exits.
            if head - tlen > self.height:
                self.head_y[x] = self.rng.uniform(-self.height, -1)
                self.speed[x] = self.rng.uniform(8, 22)
                self.trail[x] = self.rng.randint(6, max(7, self.height // 2))

        # Swap a few glyphs occasionally for shimmer.
        self.swap_clock += dt
        if self.swap_clock > 0.05:
            self.swap_clock = 0.0
            for _ in range(max(1, self.cols // 3)):
                cx = self.rng.randrange(self.cols)
                cy = self.rng.randrange(self.height)
                self.glyphs[cx][cy] = self.rng.choice(_GLYPHS)
