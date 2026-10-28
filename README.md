# exam-photo

跨平台报名照片处理工具。复刻人社部人事考试中心 `PhotoProcess.exe` 的输出规格，让你在 **macOS / Linux / Windows** 上都能处理国考、事业单位、烟草、四六级等报名照片，不用装 Windows 虚拟机，也不用找国产软件。

```bash
$ exam-photo 原图.jpg -o 报名照片.jpg
处理 原图.jpg
  输入   1280x1707 -> 295x413
  输出   报名照片.jpg
  体积   9.9 KB (quality=79) OK
  校验   通过
```

---

## 为什么会有这个项目

报名国考、省考、事业单位、烟草、铁路这类考试，官网通常给一个 `照片处理工具.exe`，只发 Windows 版。Mac 用户的路只有三条：开虚拟机、装 CrossOver、或者找人借电脑。

我本人是 Mac + Windows 双机，2026 年 10 月报中国烟草时卡在这里，于是把这个 exe 拆开看了一遍：

| 项目 | 逆向结果 |
|---|---|
| 文件类型 | PE32, i386, GUI |
| 是否加壳 | 无壳 |
| 编译特征 | MFC42 + OpenCV 1.0 |
| 内部版本号 | `PhotoProcess v1.0.0.25` |
| 发布者字段 | `人社部人事考试中心` |
| 输出文件名 | `报名照片.JPG` |

处理流程是从 `photo.ini` 读参数，再用 OpenCV 走一遍：

```
cvLoadImage → 宽度 < 295 则拒绝
            → Haar 级联检测，要求恰好 1 张人脸
            → 判断白底 / 蓝底
            → cvResize 到 295×413
            → cvSaveImage 输出 baseline JPEG，约 10KB
```

关键发现是**输出文件没有任何签名或水印**，服务器端只校验格式、宽高、体积、底色。也就是说，只要产出满足这四个条件的 JPEG，和官方工具的输出在服务端看来是一样的。

这个项目就是把那段流程用 Pillow + numpy 重写了一遍。依赖只有两个，全平台可用。

> 逆向过程记录在 [docs/photoprocess-reverse-notes.md](docs/photoprocess-reverse-notes.md)。

---

## 安装

需要 Python 3.8+。

```bash
git clone https://github.com/ZhaowTao/exam-photo.git
cd exam-photo
pip install .
```

或者不想装，直接跑源码：

```bash
pip install Pillow numpy
PYTHONPATH=src python3 -m exam_photo 原图.jpg
```

`uv` 用户：

```bash
uv run --with Pillow --with numpy exam-photo 原图.jpg
```

---

## 用法

### 最常用：按国标处理

```bash
exam-photo 原图.jpg
# 默认输出 报名照片.jpg，295x413，10KB 以内
```

### 指定输出路径

```bash
exam-photo 原图.jpg -o ~/Desktop/报名照片.jpg
```

### 选规格

```bash
exam-photo 原图.jpg --preset cet        # 四六级 144x192
exam-photo 原图.jpg --preset 2inch      # 2寸 413x579
exam-photo 原图.jpg --size 480x640      # 自定义
exam-photo 原图.jpg --max-kb 20         # 体积上限改成 20KB
```

### 换底色

官方工具**不换底**，只做校验和缩放。但很多人手上只有红底照片，而报名要求白底或蓝底，所以这个功能是我加的附加项：

```bash
exam-photo 原图.jpg --bg blue           # 白底/红底 -> 蓝底
exam-photo 原图.jpg --bg white
exam-photo 原图.jpg --bg red
```

原理是从四条边做 flood fill，找出与角落颜色连通、且色差在容差内的区域，只替换这一块。所以头发、皮肤、白衬衫不会被误伤——白衬衫和背景同色，但它被西装隔开、不与画面边缘连通，因此保留。

前提是**原图背景是纯色**。渐变灰、花背景、影棚光斑都不适用，这种图建议直接重拍。

容差默认 28，遇到边缘吃掉头发或残留一圈旧底色时调：

```bash
exam-photo 原图.jpg --bg blue --bg-tolerance 40   # 更激进，吞得更多
exam-photo 原图.jpg --bg blue --bg-tolerance 18   # 更保守，只吃最像的
```

### 只体检不改图

拿到一张别人给的照片，先看看合不合格：

```bash
exam-photo 原图.jpg --check-only
```

### 批量

```bash
exam-photo --batch ./raw --outdir ./out --preset rsks
```

### JSON 输出（接脚本用）

```bash
exam-photo 原图.jpg --json
```

### 严格模式

任何警告都当失败，退出码 1。适合放进 CI 或者 Makefile：

```bash
exam-photo 原图.jpg --strict
```

---

## 它检查什么

| 检查项 | 说明 | 不通过时 |
|---|---|---|
| 格式 | 只接受 JPG/JPEG | 直接拒绝 |
| 最低像素 | 宽 ≥ 295、高 ≥ 413 | 拒绝（官方明确禁止放大低像素照片） |
| 目标尺寸 | 输出严格等于目标宽高 | 报错 |
| 宽高比 | 偏离 295:413 超过 2% 时警告 | 警告 |
| 背景 | 判定 white / blue / red / unknown | unknown 时警告 |
| 体积 | 超过上限即失败 | 报错 |
| JPEG 段结构 | 含 EXIF / ICC / 渐进 / 重启标记时警告 | 警告 |

段结构这一项值得说一句：不少省级报名系统跑的是老式 JPEG 解析器，遇到 progressive 或 APP1/APP2 段会直接报「上传失败」。本工具输出固定 baseline、无 EXIF、无 ICC、无 DRI，这是刻意为之，不是随便存的。

---

## 关于人脸检测

官方工具用 OpenCV Haar 级联，要求画面里**恰好一张**人脸，0 张或多张都拒绝。

本项目**没有**引入 OpenCV。理由是 `opencv-python` 装下来一百多兆，为了一个「照片里有没有人」的判断不值得，而且 Haar 级联对侧脸、戴眼镜、刘海遮挡的误判率并不低。

替代做法是一个很轻的启发式：比较画面中部区域和边缘背景的灰度标准差。中部纹理明显高于背景，就认为有人像。它只能发现「画面是纯色块」这种明显错误，**不能替代官方工具的人脸检测**。所以：

- 如果输出被官网驳回、理由是「未检测到人脸」，换一张正面免冠照重来，别跟工具较劲。
- 如果你需要严格的人脸校验，装 `opencv-python` 自己加一段，`validate.py` 里的 `check_face_heuristic` 就是给你替换的位置。

---

## 预设规格

| key | 尺寸 | 体积上限 | 适用 |
|---|---|---|---|
| `rsks` | 295×413 | 10 KB | 人社部人事考试、国考、事业单位、烟草（**经逆向验证**） |
| `1inch` | 295×413 | 20 KB | 1 寸通用 |
| `2inch` | 413×579 | 40 KB | 2 寸通用 |
| `480x640` | 480×640 | 100 KB | 部分省考、教师资格 |
| `cet` | 144×192 | 200 KB | 四六级 |
| `small2` | 413×531 | 50 KB | 部分国企网申 |

⚠️ **只有 `rsks` 是逆向 exe 后确认的**。其余是按常见公告整理的通行尺寸，**每次报名前请以当次公告原文为准**，公告写多少就用 `--size` 填多少。

---

## 兼容性

- macOS 10.15+ / Linux / Windows 10+
- Python 3.8 – 3.13
- 中文路径、中文文件名、含空格路径都测过
- 依赖：`Pillow>=9.0`、`numpy>=1.20`，无编译依赖

透明 PNG 会被自动铺白底再转 JPEG。这个坑我踩过：直接 `RGBA → JPEG` 会把透明区域填成黑色，导致一整块黑边。

---

## 测试

```bash
pip install -e ".[dev]"
pytest
```

12 个用例，全部基于合成图像，仓库里不含任何人脸照片。

---

## 免责

- 本项目是独立重写的工具，与人社部人事考试中心无任何关系，未包含或分发官方程序的任何代码或资源。
- 逆向分析仅针对公开下载的官方工具做规格提取，目的是让非 Windows 用户能产出符合要求的文件。
- 各考试的具体要求以**当次招考公告**为准。工具按你给的参数执行，参数错了它不会替你纠正。

---

## License

MIT
