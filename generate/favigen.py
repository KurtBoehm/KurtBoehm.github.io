from pathlib import Path
from shutil import copy
from subprocess import run

from .ico import ico_sizes, images_to_ico, ImageData


def write_rasterized(dst_path: Path, src_path: Path, size: int):
    ImageData.from_svg(src_path, size).write_to_file(dst_path)
    run(["oxipng", "-o", "max", "--strip", "safe", dst_path])


def generate_favicons(dist: Path):
    svg_path = dist / "sun.svg"

    images = [
        ImageData.from_svg(svg_path, 4 * size).resize(size, size) for size in ico_sizes
    ]
    with open(dist / "favicon.ico", "wb") as f:
        f.write(images_to_ico(images))

    copy(svg_path, dist / "favicon.svg")

    write_rasterized(dist / "apple-touch-icon.png", svg_path, 180)
    write_rasterized(dist / "favicon-96x96.png", svg_path, 96)
    write_rasterized(dist / "web-app-manifest-192x192.png", svg_path, 192)
    write_rasterized(dist / "web-app-manifest-512x512.png", svg_path, 512)
