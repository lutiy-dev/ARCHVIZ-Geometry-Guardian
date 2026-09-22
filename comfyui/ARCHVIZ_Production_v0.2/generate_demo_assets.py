"""Generate deterministic demo input + masks using Python standard library only."""
from pathlib import Path
import struct
import zlib


W, H = 768, 512


def _png(path, width, height, channels, rows):
    color_type = 2 if channels == 3 else 0
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    raw = b"".join(b"\x00" + row for row in rows)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _mask_rect(x0, y0, x1, y1, feather=0):
    rows = []
    for y in range(H):
        row = bytearray(W)
        for x in range(W):
            if feather:
                dx = min(x - x0, x1 - 1 - x)
                dy = min(y - y0, y1 - 1 - y)
                d = min(dx, dy)
                if x0 <= x < x1 and y0 <= y < y1:
                    row[x] = 255 if d >= feather else max(0, min(255, int(255 * (d + 1) / feather)))
            elif x0 <= x < x1 and y0 <= y < y1:
                row[x] = 255
        rows.append(bytes(row))
    return rows


def _union(*masks):
    rows = []
    for y in range(H):
        rows.append(bytes(max(m[y][x] for m in masks) for x in range(W)))
    return rows


def _subtract(a, b):
    rows = []
    for y in range(H):
        rows.append(bytes(a[y][x] if b[y][x] == 0 else 0 for x in range(W)))
    return rows


def ensure_demo_assets(root):
    root = Path(root)
    demo = root / "input" / "archviz_demo_v02"
    original_path = root / "input" / "archviz_demo_v02_original.png"
    required = [
        demo / "building_protect.png",
        demo / "empty.png",
        demo / "facade_composite.png",
        demo / "facade_edit.png",
        demo / "facade_protect.png",
        demo / "greenery_composite.png",
        demo / "greenery_edit.png",
        demo / "original.png",
        demo / "people_composite.png",
        demo / "people_edit.png",
        demo / "people_influence.png",
        demo / "road_composite.png",
        demo / "road_edit.png",
        original_path,
    ]
    if all(p.is_file() for p in required):
        return required

    # Synthetic architectural scene: sky, facade, windows, road, greenery.
    rgb_rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            if y < 130:
                c = (165, 195, 220)
            elif y < 390:
                c = (176, 170, 158)
                # window grid
                if 100 < x < 665 and ((x - 110) % 110) < 55 and ((y - 155) % 85) < 42:
                    c = (55, 70, 78)
            else:
                c = (75, 78, 80)
            if y > 330 and x < 145:
                c = (70, 118, 66)
            row.extend(c)
        rgb_rows.append(bytes(row))

    _png(original_path, W, H, 3, rgb_rows)
    _png(demo / "original.png", W, H, 3, rgb_rows)

    empty = [bytes(W) for _ in range(H)]
    facade = _mask_rect(70, 125, 700, 390)
    road = _mask_rect(0, 385, W, H)
    greenery = _mask_rect(0, 300, 180, 460)
    people = _mask_rect(500, 250, 565, 430)
    people_influence = _mask_rect(470, 230, 600, 455)
    building_protect = _mask_rect(70, 125, 700, 390)
    facade_protect = _union(
        _mask_rect(70, 125, 90, 390),
        _mask_rect(680, 125, 700, 390),
        _mask_rect(70, 125, 700, 145),
    )

    assets = {
        "empty.png": empty,
        "facade_edit.png": facade,
        "facade_protect.png": facade_protect,
        "facade_composite.png": facade,
        "road_edit.png": road,
        "road_composite.png": road,
        "greenery_edit.png": greenery,
        "greenery_composite.png": greenery,
        "building_protect.png": building_protect,
        "people_edit.png": people,
        "people_influence.png": people_influence,
        "people_composite.png": people_influence,
    }
    for name, rows in assets.items():
        _png(demo / name, W, H, 1, rows)

    return required


if __name__ == "__main__":
    ensure_demo_assets(Path(__file__).resolve().parent)
    print("ARCHVIZ v0.2 demo assets ready.")
