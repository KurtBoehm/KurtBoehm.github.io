# This file is part of https://github.com/KurtBoehm/KurtBoehm.github.io.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from math import cos, radians, sin, sqrt
from pathlib import Path
from typing import Final, Literal, Protocol, TypedDict, final, overload

import svg
from bs4 import BeautifulSoup, Tag
from colorama import Fore
from svg_path_editor import SvgPath, optimize_path

from .open_color import (
    black,
    cyan3,
    cyan5,
    cyan7,
    grape3,
    grape5,
    grape7,
    green3,
    green5,
    green7,
    indigo3,
    indigo5,
    indigo7,
    orange4,
    orange6,
    orange8,
    pink3,
    pink5,
    pink7,
    red4,
    red6,
    red8,
    white,
    yellow3,
    yellow5,
    yellow7,
    yellow9,
)

Number = Decimal | float | int


def circy(x: float, r: float):
    return sqrt(r * r - x * x)


class PathData(Protocol):
    def __init__(self, x: float, y: float) -> None: ...

    @property
    def x(self) -> Number: ...
    @property
    def y(self) -> Number: ...


def stof(s: str) -> int | float:
    f = float(s)
    i = int(f)
    return i if f == i else f


def ntof(n: Number):
    f = float(n)
    i = int(f)
    return i if f == i else f


def length_value(x: Number | svg.Length) -> float:
    return ntof(x.value) if isinstance(x, svg.Length) else ntof(x)


def as_length(x: float, length: Number | svg.Length | None) -> float | svg.Length:
    x = int(x) if int(x) == x else x
    return svg.Length(x, length.unit) if isinstance(length, svg.Length) else x


@final
class Mat:
    def __init__(
        self,
        a00: float,
        a01: float,
        a02: float,
        a10: float,
        a11: float,
        a12: float,
    ) -> None:
        self.a00 = a00
        self.a01 = a01
        self.a02 = a02
        self.a10 = a10
        self.a11 = a11
        self.a12 = a12

    def __matmul__(self, a: tuple[float, float, float]) -> tuple[float, float]:
        return (
            self.a00 * a[0] + self.a01 * a[1] + self.a02 * a[2],
            self.a10 * a[0] + self.a11 * a[1] + self.a12 * a[2],
        )


def trans_rotate(mat: Mat, rot: str) -> str:
    rotx, roty = mat @ (1, 1, 0)
    rotm = rotx * roty
    angle, x, y = rot.strip().split()
    angle = stof(angle)
    angle = -angle if rotm < 0 else angle
    x, y = mat @ (stof(x), stof(y), 1)
    return f"{angle} {x} {y}"


@final
class Transformer:
    def __init__(self, mat: Mat) -> None:
        self.mat = mat

    @overload
    def __call__[T: svg.Element | svg.PathData](
        self,
        el: T,
        *,
        in_place: Literal[False],
    ) -> T: ...
    @overload
    def __call__(
        self,
        el: svg.Element | svg.PathData,
        *,
        in_place: Literal[True],
    ) -> None: ...

    def __call__[T: svg.Element | svg.PathData](
        self, el: T, *, in_place: bool
    ) -> T | None:
        if not in_place:
            el = deepcopy(el)
            self(el, in_place=True)
            return el
        match el:
            case svg.Circle():
                cx, cy = length_value(el.cx or 0), length_value(el.cy or 0)
                cx, cy = self.mat @ (cx, cy, 1)
                el.cx, el.cy = as_length(cx, el.cx), as_length(cy, el.cy)
                r = length_value(el.r or 0)
                rx, ry = self.mat @ (r, r, 0)
                r = 0.5 * (abs(rx) + abs(ry))
                ri = int(r)
                el.r = as_length(ri if r == ri else r, el.r)
                for eli in el.elements or []:
                    self(eli, in_place=True)
            case svg.Path():
                d: list[svg.PathData]
                if el.d:
                    el0 = el.d[0]
                    if isinstance(el0, svg.MoveToRel):
                        mt = svg.MoveTo(el0.dx, el0.dy)
                        self(mt, in_place=True)
                        el0.dx, el0.dy = mt.x, mt.y
                        d = el.d[1:]
                    else:
                        d = el.d
                else:
                    d = []
                for r in d:
                    self(r, in_place=True)
                for eli in el.elements or []:
                    self(eli, in_place=True)
            case svg.AnimateTransform(type="rotate"):
                if el.from_:
                    el.from_ = trans_rotate(self.mat, el.from_)
                if el.to:
                    el.to = trans_rotate(self.mat, el.to)
                if isinstance(el.values, str):
                    el.values = ";".join(
                        trans_rotate(self.mat, vseg) for vseg in el.values.split(";")
                    )
            case svg.VerticalLineTo():
                _, el.y = self.mat @ (0, ntof(el.y), 1)
            case svg.MoveTo() | svg.LineTo():
                el.x, el.y = self.mat @ (ntof(el.x), ntof(el.y), 1)
            case svg.MoveToRel() | svg.LineToRel():
                el.dx, el.dy = self.mat @ (ntof(el.dx), ntof(el.dy), 0)
            case svg.CubicBezier():
                el.x, el.y = self.mat @ (ntof(el.x), ntof(el.y), 1)
                el.x1, el.y1 = self.mat @ (ntof(el.x1), ntof(el.y1), 1)
                el.x2, el.y2 = self.mat @ (ntof(el.x2), ntof(el.y2), 1)
            case svg.CubicBezierRel():
                el.dx, el.dy = self.mat @ (ntof(el.dx), ntof(el.dy), 0)
                el.dx1, el.dy1 = self.mat @ (ntof(el.dx1), ntof(el.dy1), 0)
                el.dx2, el.dy2 = self.mat @ (ntof(el.dx2), ntof(el.dy2), 0)
            case svg.SmoothCubicBezier():
                el.x, el.y = self.mat @ (ntof(el.x), ntof(el.y), 1)
                el.x2, el.y2 = self.mat @ (ntof(el.x2), ntof(el.y2), 1)
            case svg.SmoothCubicBezierRel():
                el.dx, el.dy = self.mat @ (ntof(el.dx), ntof(el.dy), 0)
                el.dx2, el.dy2 = self.mat @ (ntof(el.dx2), ntof(el.dy2), 0)
            case svg.Arc():
                el.rx, el.ry = self.mat @ (ntof(el.rx), ntof(el.ry), 0)
                el.x, el.y = self.mat @ (ntof(el.x), ntof(el.y), 1)
            case svg.ArcRel():
                el.rx, el.ry = self.mat @ (ntof(el.rx), ntof(el.ry), 0)
                el.dx, el.dy = self.mat @ (ntof(el.dx), ntof(el.dy), 0)
            case svg.ClosePath():
                pass
            case _:
                assert False, f"{type(el)} is not supported!"


def rotate[T: svg.PathData](p: T, theta: float) -> T:
    s, c = sin(radians(theta)), cos(radians(theta))
    return Transformer(Mat(c, -s, 0, s, c, 0))(p, in_place=False)


def make_spike(r0: float, r1: float, w: float):
    return [
        svg.M(-w, circy(w, r0)),
        svg.L(0, r1),
        svg.L(w, circy(w, r0)),
        svg.Z(),
    ]


def make_eye(cx: float) -> list[svg.PathData]:
    return [
        svg.M(cx - 3, -1),
        svg.a(3, 3, 0, False, True, 3, -3),
        svg.a(3, 3, 0, False, True, 3, 3),
        svg.Z(),
    ]


border = black  # #282818


def sun(tr: Transformer | None = None):
    cradius = 36

    spikes0: list[svg.PathData] = [
        rotate(s, i * 30) for i in range(12) for s in make_spike(cradius, 60, 6)
    ]
    spikes1: list[svg.PathData] = [
        rotate(s, i * 30 + 15) for i in range(12) for s in make_spike(cradius, 52, 4)
    ]
    face0: list[svg.PathData] = [
        svg.m(-25, -7),
        svg.s(4, -5, 10, -5),
        svg.Arc(10, 10, 0, False, True, -5, -2),
        svg.V(7),
        svg.a(5, 5, 0, False, False, 5, 5),
        svg.a(5, 5, 0, False, False, 5, -5),
        svg.V(-2),
        svg.a(10, 10, 0, False, True, 10, -10),
        svg.c(6, 0, 10, 5, 10, 5),
    ]

    def anim():
        return svg.AnimateTransform(
            attributeName="transform",
            type="rotate",
            dur=timedelta(seconds=30),
            from_="0 0 0",
            to="360 0 0",
            repeatCount="indefinite",
        )

    elements = [
        svg.Path(
            d=spikes0,
            fill=yellow7,
            stroke=border,
            stroke_width=2,
            stroke_linejoin="round",
            elements=[anim()],
        ),
        svg.Path(
            d=spikes1,
            fill=yellow9,
            stroke=border,
            stroke_width=2,
            stroke_linejoin="round",
            elements=[anim()],
        ),
        svg.Circle(
            cx=0,
            cy=0,
            r=cradius,
            fill=yellow5,
            stroke=border,
            stroke_width=2,
        ),
        svg.Path(
            d=face0,
            fill="none",
            stroke=border,
            stroke_width=2,
            stroke_linecap="round",
        ),
        svg.Path(
            d=[svg.m(-15, 14), svg.s(5, 7.5, 15, 7.5), svg.S(15, 14, 15, 14)],
            fill="none",
            stroke=border,
            stroke_width=2,
            stroke_linecap="round",
        ),
        svg.Path(
            d=make_eye(-16),
            fill=border,
            stroke=border,
            stroke_width=2,
            stroke_linejoin="round",
        ),
        svg.Path(
            d=make_eye(16),
            fill=border,
            stroke=border,
            stroke_width=2,
            stroke_linejoin="round",
        ),
    ]

    if tr:
        for el in elements:
            tr(el, in_place=True)

    return svg.SVG(viewBox=svg.ViewBoxSpec(-64, -64, 128, 128), elements=list(elements))


class BaseStyle(TypedDict):
    stroke: str
    stroke_width: int
    stroke_linecap: Literal["round"]
    stroke_linejoin: Literal["round"]


style_base = BaseStyle(
    stroke=border,
    stroke_width=2,
    stroke_linecap="round",
    stroke_linejoin="round",
)
bb_dark = "#302322"
bb_light = "#534343"
bb_iris = "#281810"


def blackbird_leg(x: float, y: float, length: float, name: str, anim: bool):
    return svg.Path(
        id=name,
        d=[
            svg.m(x, y),
            svg.l(-length, length),
            svg.c(-3, 4, -3, 8, 0, 12),
            svg.m(3, -3),
            svg.c(-2, -2, -3, -4, -3, -9),
            svg.c(4, -1, 7, 1, 8, 3),
        ],
        fill="none",
        **style_base,
        elements=[blackbird_anim(x, y, -5)] if anim else [],
    )


def blackbird_anim(x: float, y: float, degrees: float):
    return svg.AnimateTransform(
        attributeName="transform",
        type="rotate",
        values=f"0 {x} {y}; {degrees} {x} {y}; 0 {x} {y}",
        keyTimes=[0, 0.5, 1],
        dur=timedelta(seconds=1.5),
        repeatCount="indefinite",
    )


def blackbird_wing(x: float, y: float) -> list[svg.PathData]:
    return [
        svg.M(x, y),
        svg.s(7, -21.5, 31.5, -46),
        svg.c(16.8, -16.8, 15, -7.5, 3, 5.5),
        svg.c(21, -16.5, 20, -7, 5.5, 3.5),
        svg.c(20, -11, 21, -5, 5, 4),
        svg.c(16, -5.5, 19, -2, 2.5, 5),
        svg.c(16, -3, 13, 3, 1, 5.5),
        svg.c(11, -1, 9.5, 5, -0.5, 5),
        svg.c(7.5, 0.5, 7, 6.5, -1.5, 5),
        svg.c(6, 2.5, 4.5, 7.5, -3, 4.5),
        svg.c(8, 4.5, 1.5, 7, -3, 4),
        svg.c(5.5, 3, 5, 8, -3, 4.5),
        svg.c(7.5, 5, 3, 7.5, -3, 4.5),
        svg.c(8.5, 5.5, 2, 7.5, -3, 5),
        svg.c(8.5, 4.5, 3.5, 7.5, -3.5, 4.5),
    ]


def blackbird_wing_back() -> list[svg.PathData]:
    return [
        svg.M(69, 77),
        svg.l(4, -55.5),
        svg.C(85.6, 6, 83.6, 2, 69.8, 17.6),
        svg.C(58.2, 30.7, 49, 38, 40, 64),
        svg.Z(),
    ]


def blackbird(anim: bool, tr: Transformer | None = None):
    elements = [
        blackbird_leg(60, 95, 11, "leg-left", anim=anim),
        blackbird_leg(70, 98, 12, "leg-right", anim=anim),
        svg.Path(
            id="wing-back",
            d=blackbird_wing(40, 64) if anim else blackbird_wing_back(),
            fill=bb_dark,
            **style_base,
            elements=[blackbird_anim(40, 64, -5)] if anim else [],
        ),
        svg.Path(
            id="body",
            d=[
                svg.M(29.5, 58.5),
                svg.c(-4, 0, -8, 1, -8, 7),
                svg.c(0, 3, 7, 16.3, 25, 26),
                svg.c(13.8, 7.4, 30.5, 7, 30.5, 7),
                svg.c(7, 5.5, 13.5, 14, 19, 20.5),
                svg.c(4, 4.5, 7, 3, 6, 0.5),
                svg.c(2, 2.5, 6, 2.5, 5, -1),
                svg.c(2.5, 1.5, 6, 1.5, 4.5, -3),
                svg.c(3.5, 1.5, 5.5, -1.5, 2, -4),
                svg.c(-9, -7, -18, -11, -28.5, -20.5),
                svg.c(-7, -6, -14, -15, -28.5, -21),
                svg.c(-17, -7.5, -21.5, -11.5, -27, -11.5),
                svg.Z(),
            ],
            fill=bb_light,
            **style_base,
            elements=[blackbird_anim(43.5, 65.5, 2)] if anim else [],
        ),
        svg.Path(
            id="wing-front",
            d=blackbird_wing(43.5, 65.5),
            fill=bb_light,
            **style_base,
            elements=[blackbird_anim(43.5, 65.5, 10)] if anim else [],
        ),
        svg.Path(
            id="beak",
            d=[
                svg.M(22, 62.5),
                svg.c(-6, -1, -8, -0.5, -9.5, 1.5),
                svg.C(14, 65, 19, 66.5, 22, 67),
                svg.c(1, -1, 1, -3, 0, -4.5),
                svg.Z(),
            ],
            fill=yellow7,
            **style_base,
            elements=[blackbird_anim(43.5, 65.5, 2)] if anim else [],
        ),
        svg.Circle(
            id="iris",
            cx=28.5,
            cy=65.5,
            r=3,
            fill=bb_iris,
            stroke=yellow7,
            stroke_width=0.5,
            elements=[blackbird_anim(43.5, 65.5, 2)] if anim else [],
        ),
        svg.Circle(
            id="pupil",
            cx=28.5,
            cy=65.5,
            r=1.3,
            fill=black,
            elements=[blackbird_anim(43.5, 65.5, 2)] if anim else [],
        ),
    ]
    if tr:
        for el in elements:
            tr(el, in_place=True)
    return svg.SVG(viewBox=svg.ViewBoxSpec(0, 0, 128, 128), elements=list(elements))


def merged():
    off = 8
    bbl = blackbird(anim=True, tr=Transformer(Mat(-1, 0, off, 0, 1, 0)))
    sol = sun(Transformer(Mat(1, 0, 64, 0, 1, 64)))
    bbr = blackbird(anim=True, tr=Transformer(Mat(1, 0, 128 - off, 0, 1, 0)))
    return svg.SVG(
        viewBox=svg.ViewBoxSpec(-128, 0, 384, 128),
        elements=(bbl.elements or []) + (sol.elements or []) + (bbr.elements or []),
    )


def merged_tri():
    offx, offy = 64, 64
    bbl = blackbird(anim=True, tr=Transformer(Mat(-1, 0, offx, 0, 1, offy)))
    sol = sun(Transformer(Mat(1, 0, 64, 0, 1, 64)))
    bbr = blackbird(anim=True, tr=Transformer(Mat(1, 0, 128 - offx, 0, 1, offy)))
    return svg.SVG(
        viewBox=svg.ViewBoxSpec(-56, 0, 240, 192),
        elements=(bbl.elements or []) + (sol.elements or []) + (bbr.elements or []),
    )


def cheshire():
    def anim():
        return svg.AnimateTransform(
            attributeName="transform",
            type="rotate",
            from_="0 64 64",
            to="360 64 64",
            dur=timedelta(seconds=15),
            repeatCount="indefinite",
        )

    def color_anim():
        return svg.Animate(
            attributeName="fill",
            values=[
                pink7,
                red8,
                orange8,
                yellow7,
                green7,
                cyan7,
                indigo7,
                grape7,
                pink7,
            ],
            dur=timedelta(seconds=15),
            repeatCount="indefinite",
        )

    def eye_anim():
        return svg.Animate(
            attributeName="fill",
            values=[
                cyan3,
                indigo3,
                grape3,
                pink3,
                red4,
                orange4,
                yellow3,
                green3,
                cyan3,
            ],
            dur=timedelta(seconds=15),
            repeatCount="indefinite",
        )

    base_elements = [
        svg.Path(
            id="ear-left",
            d=[svg.M(26, 51), svg.c(-8, -17, -2, -32, -2, -32), svg.s(11, 0, 23, 14)],
            **style_base,
            fill=grape7,
            elements=[anim(), color_anim()],
        ),
        svg.Path(
            id="ear-right",
            d=[svg.M(102, 51), svg.c(8, -17, 2, -32, 2, -32), svg.s(-11, 0, -23, 14)],
            **style_base,
            fill=grape7,
            elements=[anim(), color_anim()],
        ),
        svg.Path(
            id="face",
            d=[
                svg.M(16, 72),
                svg.s(9, -42, 48, -42),
                svg.s(48, 42, 48, 42),
                svg.s(-12, 35, -48, 35),
                svg.S(16, 72, 16, 72),
                svg.Z(),
            ],
            **style_base,
            fill=grape5,
            elements=[
                anim(),
                svg.Animate(
                    attributeName="fill",
                    values=[
                        pink5,
                        red6,
                        orange6,
                        yellow5,
                        green5,
                        cyan5,
                        indigo5,
                        grape5,
                        pink5,
                    ],
                    dur=timedelta(seconds=15),
                    repeatCount="indefinite",
                ),
            ],
        ),
        svg.Path(
            id="nose",
            d=[
                svg.M(50.5, 82.5),
                svg.C(56, 84, 72, 84, 77.5, 82.5),
                svg.C(72, 84, 64.2, 83.5, 64.2, 77),
                svg.L(70, 72.5),
                svg.c(0.7901, -0.613, 1.5, -1, 1.5, -2),
                svg.Arc(1.5, 1.5, 0, False, False, 70, 69),
                svg.H(58),
                svg.a(1.5, 1.5, 0, False, False, -1.5, 1.5),
                svg.c(0, 1, 0.8203, 1.4727, 1.5, 2),
                svg.L(63.8, 77),
                svg.c(0, 6.5, -7.8, 7, -13.3, 5.5),
                svg.Z(),
            ],
            **style_base,
            fill=black,
            elements=[anim()],
        ),
        svg.Path(
            id="whiskers-left",
            d=[
                svg.M(28.5, 79),
                svg.L(9, 87.5),
                svg.m(17, -13),
                svg.l(-21, 3),
                svg.m(21, -8),
                svg.l(-21, -3),
                svg.M(28.5, 65),
                svg.L(9, 56.5),
            ],
            **style_base,
            fill="none",
            elements=[anim()],
        ),
        svg.Path(
            id="whiskers-right",
            d=[
                svg.M(119, 56.5),
                svg.L(99.5, 65),
                svg.M(123, 66.5),
                svg.l(-21, 3),
                svg.m(21, 8),
                svg.l(-21, -3),
                svg.m(17, 13),
                svg.L(99.5, 79),
            ],
            **style_base,
            fill="none",
            elements=[anim()],
        ),
        svg.Path(
            id="eye-left",
            d=[
                svg.M(54.5, 64),
                svg.c(0, -9, -11.5, -14, -18.5, -6.5),
                svg.C(39, 67, 49, 68, 54.5, 64),
                svg.Z(),
            ],
            **style_base,
            fill=white,
            elements=[anim(), eye_anim()],
        ),
        svg.Path(
            id="eye-right",
            d=[
                svg.M(73.5, 64),
                svg.c(0, -9, 11.5, -14, 18.5, -6.5),
                svg.C(89, 67, 79, 68, 73.5, 64),
                svg.Z(),
            ],
            **style_base,
            fill=white,
            elements=[anim(), eye_anim()],
        ),
        svg.Path(
            id="pupil-left",
            d=[
                svg.M(45.5, 56),
                svg.c(1.5, 2.5, 1.5, 5.5, 0, 8),
                svg.c(-1.5, -2.5, -1.5, -5.5, 0, -8),
                svg.Z(),
            ],
            **style_base,
            fill=black,
            elements=[anim()],
        ),
        svg.Path(
            id="pupil-right",
            d=[
                svg.M(82.5, 56),
                svg.c(1.5, 2.5, 1.5, 5.5, 0, 8),
                svg.c(-1.5, -2.5, -1.5, -5.5, 0, -8),
                svg.Z(),
            ],
            **style_base,
            fill=black,
            elements=[anim()],
        ),
        svg.Path(
            id="eyebrow-left",
            d=[svg.M(38, 49), svg.c(4, -3, 11, -5, 18, 4)],
            **style_base,
            fill="none",
            elements=[anim()],
        ),
        svg.Path(
            id="eyebrow-right",
            d=[svg.M(72, 53), svg.c(7, -9, 14, -7, 18, -4)],
            **style_base,
            fill="none",
            elements=[anim()],
        ),
    ]
    base_group = svg.G(
        elements=[
            *base_elements,
            svg.Animate(
                attributeName="opacity",
                values=[1, 0, 0, 1, 1],
                keyTimes=[0, 0.4, 0.5, 0.5, 1],
                dur=timedelta(seconds=40),
                repeatCount="indefinite",
            ),
        ]
    )
    mouth_elements = [
        svg.Path(
            id="mouth",
            d=[
                svg.M(29, 70),
                svg.S(32, 97.5, 64, 97.5),
                svg.S(99, 70, 99, 70),
                svg.S(89, 84, 64, 84),
                svg.S(29, 70, 29, 70),
                svg.Z(),
            ],
            **style_base,
            fill=white,
            elements=[anim()],
        ),
        svg.Path(
            id="mouth-lines",
            d=[
                svg.M(37, 77),
                svg.V(87),
                svg.m(8, -6),
                svg.V(93),
                svg.m(9, -10),
                svg.V(96),
                svg.M(64, 84),
                svg.V(97),
                svg.M(74, 83),
                svg.V(96),
                svg.m(9, -15),
                svg.V(93),
                svg.m(8, -16),
                svg.V(87),
            ],
            stroke=border,
            stroke_width=2,
            fill="none",
            elements=[anim()],
        ),
    ]
    grin_group = svg.G(
        elements=[
            *mouth_elements,
            svg.Animate(
                attributeName="opacity",
                values=[1, 1, 0, 1, 1],
                keyTimes=[0, 0.4, 0.5, 0.5, 1],
                dur=timedelta(seconds=40),
                repeatCount="indefinite",
            ),
        ]
    )
    group = svg.G(
        elements=[
            base_group,
            grin_group,
            svg.Animate(
                attributeName="opacity",
                values=[1, 1, 0, 1],
                keyTimes=[0, 0.5, 0.5, 1],
                dur=timedelta(seconds=40),
                repeatCount="indefinite",
            ),
        ],
    )
    return svg.SVG(viewBox=svg.ViewBoxSpec(0, 0, 128, 128), elements=[group])


def optimize(svg: str, decimals: int = 2):
    soup: Final = BeautifulSoup(svg, "xml")
    for path in soup.find_all("path"):
        assert isinstance(path, Tag)

        d = path.attrs["d"]
        assert isinstance(d, str)

        svg_path = SvgPath(d)
        d_orig = svg_path.as_string(decimals=decimals, minify=True)
        optimize_path(
            svg_path,
            use_shorthands=True,
            use_horizontal_and_vertical_lines=True,
            use_relative_absolute=True,
            use_reverse=True,
        )
        d_opti = svg_path.as_string(decimals=decimals, minify=True)
        if d_orig != d_opti:
            print(f"{Fore.BLUE}{d_orig}{Fore.RESET}")
            print(f"{Fore.GREEN}{d_opti}{Fore.RESET}")

        path.attrs["d"] = d_orig

    xml = soup.prettify()
    xml = xml[xml.index("\n") + 1 :].rstrip()
    return xml


def output_canvas(canvas: svg.SVG, p: Path):
    with open(p, "w") as f:
        print(canvas, file=f)
    with open(p, "r") as f:
        svg = f.read()
    svg = optimize(svg)
    with open(p, "w") as f:
        print(svg, file=f)


def generate_svg(base: Path):
    output_canvas(sun(), base / "sun.svg")
    output_canvas(blackbird(anim=True), base / "blackbird.svg")
    output_canvas(merged(), base / "merged.svg")
    output_canvas(merged_tri(), base / "merged-tri.svg")
    output_canvas(cheshire(), base / "cheshire.svg")
