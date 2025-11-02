from io import BytesIO
from pathlib import Path
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from cairosvg import svg2png
from PIL import Image
from PIL.Image import Resampling

# the correct sizes are 256x256, 48x48, 32x32, 16x16
ico_sizes: Final = (48, 32, 16)


@dataclass
class ImageData:
    width: int
    height: int
    data: bytes  # RGBA, row-major, top-down

    @staticmethod
    def from_pillow(img: Image.Image) -> "ImageData":
        img = img.convert("RGBA")
        width, height = img.size
        data = img.tobytes("raw", "RGBA")
        return ImageData(width=width, height=height, data=data)

    @staticmethod
    def from_png(path: Path) -> "ImageData":
        return ImageData.from_pillow(Image.open(path))

    @staticmethod
    def from_svg(path: Path, size: int) -> "ImageData":
        data = BytesIO()
        with open(path, "rb") as f:
            svg2png(f.read(), write_to=data, output_width=size, output_height=size)
        return ImageData.from_pillow(Image.open(data))

    @property
    def pillow(self) -> Image.Image:
        return Image.frombytes("RGBA", (self.width, self.height), self.data)

    def resize(
        self,
        w: int,
        h: int,
        *,
        resample: Resampling | None = None,
    ) -> "ImageData":
        return ImageData.from_pillow(
            self.pillow.resize((w, h), resample=resample or Resampling.BOX)
        )

    def write_to_file(self, path: Path) -> None:
        self.pillow.save(path)


def convert_png_to_ico(
    filepath: Path | Sequence[Path],
    *,
    resample: Resampling | None = None,
    sizes: Sequence[int] = ico_sizes,
) -> bytes:
    if not isinstance(filepath, Path):
        images = [ImageData.from_png(p) for p in filepath]
        return images_to_ico(images)

    png = ImageData.from_png(filepath)
    if png.width != png.height:
        raise ValueError(f"Requires a square PNG, got {png.width}×{png.height}")

    image = png if png.width in (256, 512) else png.resize(256, 256, resample=resample)
    images = [image.resize(s, s, resample=resample) for s in sizes]
    return images_to_ico(images)


def images_to_ico(images: list[ImageData]) -> bytes:
    header = get_header(len(images))
    header_and_icon_dir = [header]
    image_data_arr = []

    offset = len(header) + 16 * len(images)

    for img in images:
        dir_entry = get_dir(img, offset)
        bmp_info_header = get_bmp_info_header(img)
        dib = get_dib(img)

        new_size = len(bmp_info_header) + len(dib)
        offset += new_size

        # write the real size into bytes 8..11 of the directory entry
        struct.pack_into("<I", dir_entry, 8, new_size)

        header_and_icon_dir.append(bytes(dir_entry))
        image_data_arr.append(bmp_info_header)
        image_data_arr.append(dib)

    return b"".join(header_and_icon_dir + image_data_arr)


# https://en.wikipedia.org/wiki/ICO_(file_format)
def get_header(num_of_images: int) -> bytes:
    # Reserved=0 (2 bytes), Type=1 (2 bytes), Count=num_of_images (2 bytes)
    return struct.pack("<HHH", 0, 1, num_of_images)


def get_dir(img: ImageData, offset: int) -> bytearray:
    # Directory entry is 16 bytes
    buf = bytearray(16)
    width = 0 if img.width >= 256 else img.width
    height = width
    bpp = 32

    # 0: width (1 byte), 1: height (1 byte)
    buf[0] = width & 0xFF
    buf[1] = height & 0xFF
    buf[2] = 0  # palette count
    buf[3] = 0  # reserved
    struct.pack_into("<H", buf, 4, 1)  # color planes
    struct.pack_into("<H", buf, 6, bpp)  # bits per pixel
    struct.pack_into("<I", buf, 8, 0)  # size of image data (filled later)
    struct.pack_into("<I", buf, 12, offset)  # offset to image data

    return buf


# https://en.wikipedia.org/wiki/BMP_file_format
def get_bmp_info_header(img: ImageData) -> bytes:
    width = img.width
    # Height is doubled in ICO BMP to account for XOR + AND masks
    height = width * 2
    bpp = 32

    # BITMAPINFOHEADER (40 bytes)
    # size, width, height, planes, bitcount, compression, sizeImage,
    # xPelsPerMeter, yPelsPerMeter, clrUsed, clrImportant
    return struct.pack(
        "<IiiHHIIiiII",
        40,  # biSize
        width,  # biWidth
        height,  # biHeight (doubled)
        1,  # biPlanes
        bpp,  # biBitCount
        0,  # biCompression (BI_RGB)
        0,  # biSizeImage (can be 0 for BI_RGB)
        0,  # biXPelsPerMeter
        0,  # biYPelsPerMeter
        0,  # biClrUsed
        0,  # biClrImportant
    )


# https://en.wikipedia.org/wiki/BMP_file_format
# Note that bitmap data in BMP is bottom-up, and color order is BGRA.
def get_dib(img: ImageData) -> bytes:
    width = img.width
    height = width  # square icon enforced by caller
    size = len(img.data)

    and_map_row = get_row_stride(width)
    and_map_size = and_map_row * height

    buf = bytearray(size + and_map_size)

    # XOR map: BGRA, bottom-up
    for y in range(height):
        for x in range(width):
            px_color = get_pixel_color(img, x, y)
            r = (px_color >> 24) & 0xFF
            g = (px_color >> 16) & 0xFF
            b = (px_color >> 8) & 0xFF
            a = px_color & 0xFF
            new_color = b | (g << 8) | (r << 16) | (a << 24)
            pos = ((height - y - 1) * width + x) * 4
            struct.pack_into("<I", buf, pos, new_color)

    # AND map (1 bit per pixel, padded to 32 bits per row)
    for y in range(height):
        for x in range(width):
            px_color = get_pixel_color(img, x, y)
            alpha = 0 if (px_color & 0xFF) > 0 else 1  # 1 => transparent
            bit_num = (height - y - 1) * width + x

            # width in multiples of 32 bits
            if width % 32 == 0:
                width32 = width // 32
            else:
                width32 = (width // 32) + 1

            line = bit_num // width
            offset = bit_num % width
            bit_val = alpha & 0x01

            pos = size + line * width32 * 4 + (offset // 8)
            current = buf[pos]
            buf[pos] = current | (bit_val << (7 - (offset % 8)))

    return bytes(buf)


def get_row_stride(width: int) -> int:
    if width % 32 == 0:
        return width // 8
    else:
        return 4 * ((width // 32) + 1)


def get_pixel_color(img: ImageData, x: int, y: int) -> int:
    xi = 0 if x < 0 else x
    yi = 0 if y < 0 else y

    if xi >= img.width:
        xi = img.width - 1
    if yi >= img.height:
        yi = img.height - 1

    if xi < 0 or xi >= img.width or yi < 0 or yi >= img.height:
        return 0

    i = ((img.width * yi) + xi) * 4
    r = img.data[i]
    g = img.data[i + 1]
    b = img.data[i + 2]
    a = img.data[i + 3]

    # Match JS readUInt32BE on RGBA bytes => (r<<24)|(g<<16)|(b<<8)|a
    return (r << 24) | (g << 16) | (b << 8) | a


def save_ico(
    input_path: Path | Sequence[Path],
    output_path: Path,
    *,
    resample: Resampling | None = None,
    sizes: Sequence[int] = ico_sizes,
):
    ico_bytes = convert_png_to_ico(input_path, resample=resample, sizes=sizes)
    with open(output_path, "wb") as f:
        f.write(ico_bytes)
