# This file is part of https://github.com/KurtBoehm/KurtBoehm.github.io.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import re
from functools import partial
from pathlib import Path
from shutil import copy
from typing import Callable, Final

from markdown_it import MarkdownIt
from pydantic import BaseModel

from generate import generate_svg
from mdit_plugins.maths import dollarmath_plugin


class PageInfo(BaseModel):
    wrapper: Path
    template: Path = Path("src/template.html")
    title: str


class MakeInfo(BaseModel):
    assets: list[Path]
    pages: list[PageInfo]


repl_path_re: Final = re.compile(r"([ ]*)\{\{([^{}]+)\}\}")
content_re: Final = re.compile(r"([ ]*)\{\{content\}\}")
title_re: Final = re.compile(r"\{\{title\}\}")
navbar_re: Final = re.compile(r'<a class="navbar-item" href="([^"]+)">([^<]+)</a>')
mdit: Final = MarkdownIt()
mdit.use(partial(dollarmath_plugin, double_inline=True))


def read_html(name: Path, indent: str) -> str:
    with open(name, "r") as f:
        txt = f.read()
    if name.suffix == ".md":
        txt = mdit.render(txt)
        assert isinstance(txt, str)
        txt = txt.rstrip()
    txt = "".join(indent + line for line in txt.splitlines(keepends=True))
    return txt


def regex_replace(
    txt: str,
    regex: re.Pattern[str],
    replacement: Callable[[re.Match[str]], str | None],
    *,
    recursive: bool,
):
    run_again = True
    while run_again:
        base, txt = txt, ""
        prev = 0
        run_again = False
        for match in regex.finditer(base):
            if (repl := replacement(match)) is None:
                continue
            txt += base[prev : match.start()]
            txt += repl
            prev = match.end()
            run_again = recursive
        txt += base[prev:]
    return txt


def highlight_navbar(html: str, path: Path) -> str:
    if path.name == "index.html":
        url = "/"
    else:
        url = path.name

    def repl(match: re.Match[str]) -> str | None:
        print("repl", match.group(1), url)
        if match.group(1) != url:
            return
        g1, g2 = match.group(1), match.group(2)
        return f'<a class="navbar-item" href="{g1}"><strong>{g2}</strong></a>'

    return regex_replace(html, navbar_re, repl, recursive=False)


def flatten(page_path: Path) -> str:
    with open(page_path, "r") as f:
        page = f.read()
    return regex_replace(
        page,
        repl_path_re,
        lambda match: read_html(page_path.parent / match.group(2), match.group(1)),
        recursive=True,
    )


dist: Final = Path("dist")
dist.mkdir(exist_ok=True)


with open("make.json", "r") as f:
    make_info: Final = MakeInfo.model_validate_json(f.read())

for asset in make_info.assets:
    copy(asset, dist / asset.name)

generate_svg(dist)

for page in make_info.pages:
    print(page)
    content = flatten(page.wrapper).rstrip()
    with open(page.template, "r") as f:
        template = f.read()
    template = highlight_navbar(template, page.wrapper)
    merged = regex_replace(
        template,
        content_re,
        lambda match: "".join(
            match.group(1) + line for line in content.splitlines(keepends=True)
        ),
        recursive=True,
    )
    merged = regex_replace(merged, title_re, lambda _m: page.title, recursive=False)
    with open(dist / page.wrapper.name, "w") as f:
        f.write(merged)
