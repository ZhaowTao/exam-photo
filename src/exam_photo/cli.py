# -*- coding: utf-8 -*-
"""Command line interface."""

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image

from . import __version__
from .encode import save
from .presets import DEFAULT_PRESET, PRESETS, get_preset, parse_size
from .transform import crop_to_ratio, replace_background
from .validate import validate_file

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _open_rgb(path: Path) -> Image.Image:
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P", "PA"):
        # Transparent PNGs would otherwise composited onto black when saved as
        # JPEG — a bug we hit for real while building this tool.
        background = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        background.paste(im, mask=im.split()[-1])
        im = background
    return im.convert("RGB")


def process_one(src: Path, dst: Path, args, width: int, height: int,
                max_bytes: int) -> dict:
    im = _open_rgb(src)
    original_size = im.size

    result = {
        "input": str(src),
        "output": str(dst),
        "input_size": list(original_size),
        "target_size": [width, height],
    }

    if args.bg != "keep":
        im = replace_background(im, args.bg, tol=args.bg_tolerance)
        result["background_replaced"] = args.bg

    im = crop_to_ratio(im, width, height, head_bias=args.head_bias)
    info = save(im, str(dst), max_bytes)
    result.update(info)

    check = validate_file(
        str(dst), expect_w=width, expect_h=height,
        max_kb=max_bytes / 1024, allowed_bg=("white", "blue", "red"),
    )
    result["validation"] = check.as_dict()
    return result


def _print_report(res: dict, verbose: bool = True) -> None:
    print(f"  输入   {res['input_size'][0]}x{res['input_size'][1]} -> "
          f"{res['target_size'][0]}x{res['target_size'][1]}")
    if res.get("background_replaced"):
        print(f"  换底   -> {res['background_replaced']}")
    print(f"  输出   {res['output']}")
    print(f"  体积   {res['kb']} KB (quality={res['quality']})"
          f" {'OK' if res['within_budget'] else 'OVER BUDGET'}")
    v = res["validation"]
    for issue in v["issues"]:
        print(f"  [X] {issue}")
    if verbose:
        for warn in v["warnings"]:
            print(f"  [!] {warn}")
    status = "通过" if v["ok"] else "未通过"
    print(f"  校验   {status}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="exam-photo",
        description="报名照片处理：复刻人社部 PhotoProcess 规格，跨平台可用（macOS / Linux / Windows）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  exam-photo photo.jpg                        # 295x413, 10KB, 白/蓝底
  exam-photo photo.jpg --preset cet           # 四六级 144x192
  exam-photo photo.jpg --bg blue -o 报名.jpg   # 换成蓝底
  exam-photo --batch ./raw --outdir ./out      # 批量处理整个目录
  exam-photo photo.jpg --check-only            # 只体检，不改图
""",
    )
    p.add_argument("src", nargs="?", help="原图路径，或配合 --batch 作为目录")
    p.add_argument("-o", "--out", help="输出文件路径（单张时）")
    p.add_argument("-p", "--preset", default=DEFAULT_PRESET,
                   help="规格预设，默认 %s。可选：%s" % (DEFAULT_PRESET, ", ".join(PRESETS)))
    p.add_argument("-s", "--size", help="自定义尺寸，如 295x413（覆盖 --preset）")
    p.add_argument("--max-kb", type=float, help="体积上限 KB（覆盖预设）")
    p.add_argument("--bg", default="keep", choices=["keep", "white", "blue", "red"],
                   help="是否替换底色，默认 keep 不改")
    p.add_argument("--bg-tolerance", type=int, default=28,
                   help="换底容差，纯色背景 20-40 较稳，默认 28")
    p.add_argument("--head-bias", type=float, default=0.28,
                   help="裁剪时从顶部多切掉的比例，默认 0.28（保留头部空间）")
    p.add_argument("--batch", metavar="DIR", help="批量处理目录")
    p.add_argument("--outdir", default="out", help="批量输出目录，默认 ./out")
    p.add_argument("--check-only", action="store_true", help="只校验不处理")
    p.add_argument("--strict", action="store_true", help="有任何警告即视为失败（退出码 1）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    p.add_argument("-q", "--quiet", action="store_true", help="只输出错误")
    p.add_argument("-V", "--version", action="version", version=f"exam-photo {__version__}")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # Resolve target geometry
    if args.size:
        width, height = parse_size(args.size)
        max_kb = args.max_kb if args.max_kb else 100.0
    else:
        try:
            preset = get_preset(args.preset)
        except KeyError as exc:
            print(f"[X] {exc}", file=sys.stderr)
            return 2
        width, height = preset.size
        max_kb = args.max_kb if args.max_kb else preset.max_kb
    max_bytes = int(max_kb * 1024)

    # --check-only
    if args.check_only:
        if not args.src:
            print("[X] --check-only 需要给出文件路径", file=sys.stderr)
            return 2
        res = validate_file(args.src, expect_w=width, expect_h=height,
                            max_kb=max_kb, allowed_bg=("white", "blue", "red"))
        if args.json:
            print(json.dumps(res.as_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"检查 {args.src}")
            for issue in res.issues:
                print(f"  [X] {issue}")
            for warn in res.warnings:
                print(f"  [!] {warn}")
            print("  结论 " + ("通过" if res.ok else "未通过"))
        if not res.ok:
            return 1
        return 1 if (args.strict and res.warnings) else 0

    # Batch mode
    if args.batch:
        src_dir = Path(args.batch)
        if not src_dir.is_dir():
            print(f"[X] 不是目录：{src_dir}", file=sys.stderr)
            return 2
        out_dir = Path(args.outdir)
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(p for p in src_dir.iterdir()
                       if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file())
        if not files:
            print(f"[X] {src_dir} 下没有图片", file=sys.stderr)
            return 2
        results, failed = [], 0
        for src in files:
            dst = out_dir / (src.stem + ".jpg")
            try:
                res = process_one(src, dst, args, width, height, max_bytes)
                results.append(res)
                if not args.quiet:
                    print(f"处理 {src.name}")
                    _print_report(res, verbose=not args.quiet)
                if not res["validation"]["ok"]:
                    failed += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"[X] {src.name}: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"\n完成 {len(results)} 张，失败 {failed} 张。输出目录：{out_dir.resolve()}")
        return 1 if failed else 0

    # Single file
    if not args.src:
        build_parser().print_help()
        return 2
    src = Path(args.src)
    if not src.exists():
        print(f"[X] 文件不存在：{src}", file=sys.stderr)
        return 2
    dst = Path(args.out) if args.out else src.with_name("报名照片.jpg")
    try:
        res = process_one(src, dst, args, width, height, max_bytes)
    except ValueError as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[X] 处理失败：{exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"处理 {src.name}")
        _print_report(res)
        print("\n把上面输出的那张图传上去即可。")

    if not res["validation"]["ok"]:
        return 1
    if args.strict and res["validation"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
