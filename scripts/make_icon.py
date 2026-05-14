"""Generate the FNID launcher / installer .ico file."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    out = Path(__file__).resolve().parent.parent / "installer" / "fnid.ico"
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (256, 256), (31, 56, 100, 255))  # JCF navy
    draw = ImageDraw.Draw(img)
    draw.rectangle((16, 16, 240, 240), outline=(255, 215, 0, 255), width=8)

    text = "FNID"
    try:
        font = ImageFont.truetype("arial.ttf", 72)
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((256 - w) // 2, (256 - h) // 2 - 10),
                  text, fill=(255, 215, 0, 255), font=font)
    except OSError:
        draw.text((80, 100), text, fill=(255, 215, 0, 255))

    img.save(out, sizes=[(16, 16), (32, 32), (48, 48),
                         (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
