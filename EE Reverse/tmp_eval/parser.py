"""
WSTUDIO5 (.wsd) 文件解析器
解析 EduEditer 的二进制格式，提取字体表和带字体信息的文本。
"""

from dataclasses import dataclass, field
from typing import List, Optional
import struct

SEP = b'\xff\xfe\xff'  # 记录分隔符


@dataclass
class Font:
    """字体定义"""
    index: int
    cn_name: str          # 中文名 (宋体, 微软雅黑)
    en_name: str          # 英文名 (SimSun, Microsoft YaHei)
    property_val: int = 0 # 属性值


@dataclass
class TextRun:
    """格式化运行: 一段使用相同字体/颜色/字号的连续文本"""
    text: str
    font: Optional[Font] = None
    color: Optional[str] = None   # '#RRGGBB' 前景/文字色
    bgcolor: Optional[str] = None # '#RRGGBB' 背景色
    font_size_pt: Optional[float] = None  # 字号(pt)
    paragraph: int = 0  # 所在段落(行)序号, 0 起
    offset: int = 0  # run 表起始偏移 (用于识别表格单元格)
    in_table: bool = False  # 是否属于某个表格的单元格
    strikethrough: bool = False  # 删除线
    bold: bool = False  # 粗体
    italic: bool = False  # 斜体
    underline: bool = False  # 下划线
    underline_color: Optional[str] = None  # 下划线颜色 '#RRGGBB'
    list_type: Optional[str] = None  # 列表类型: None=普通, 'ul'=无序, 'ol'=有序
    align: Optional[str] = None  # 段落对齐: None=默认, 'center'/'left'/'right'/'justify'


@dataclass
class Image:
    """嵌入的图片对象 (JPEG 原始字节流)"""
    index: int
    width: int      # 显示宽度 (编辑器放置框, 可能 ≠ 实际像素)
    height: int     # 显示高度
    data: bytes     # JPEG 原始数据 (FF D8 ... FF D9)
    data_format: str = "JPEG"
    actual_width: int = 0   # 实际像素宽 (从 JPEG SOF 解析)
    actual_height: int = 0  # 实际像素高
    paragraph: int = 0  # 所在段落(行)序号, 0 起


@dataclass
class Table:
    """表格对象 (单元格文本按行优先存储)"""
    col: int  # 列数
    row: int  # 行数
    cells: List[List[str]] = field(default_factory=list)  # row x col 单元格文本
    cell_offsets: List[int] = field(default_factory=list)  # 各单元格 run 表偏移
    cell_runs: List[List[TextRun]] = field(default_factory=list)  # row x col 单元格 TextRun(含样式)


@dataclass
class WsdDocument:
    """解析后的 WSD 文档"""
    fonts: List[Font] = field(default_factory=list)
    text_runs: List[TextRun] = field(default_factory=list)
    images: List[Image] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    raw_text: str = ""

    def to_html(self) -> str:
        """生成带字体/颜色/字号样式的 HTML"""
        if not self.text_runs:
            return f"<p>{self.raw_text}</p>"
        parts = []
        for run in self.text_runs:
            font_name = run.font.cn_name if run.font else "宋体"
            style = f"font-family:'{font_name}';"
            if run.font_size_pt:
                style += f"font-size:{run.font_size_pt:.2f}pt;"
            if run.color:
                style += f"color:{run.color};"
            if run.bgcolor:
                style += f"background-color:{run.bgcolor};"
            escaped = (run.text
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
            parts.append(
                f'<span style="{style}">{escaped}</span>'
            )
        return "<p>" + "".join(parts) + "</p>"


# ── 低层工具 ──────────────────────────────────────────────

def _read_utf16_str(data: bytes, offset: int, length: int) -> str:
    """读取指定偏移处 length 个 UTF-16LE 字符"""
    return data[offset:offset + length * 2].decode('utf-16-le')


def _find_all(data: bytes, pattern: bytes) -> List[int]:
    """返回 pattern 在 data 中所有出现位置"""
    positions = []
    start = 0
    while True:
        pos = data.find(pattern, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    return positions


# ── 字体表解析 ────────────────────────────────────────────

def _parse_font_table(data: bytes):
    """解析字体声明表, 返回 (fonts, end_pos)"""
    fonts = []

    # 找到字体表的起点: 搜索记录类型 0x02 后紧跟宋体 UTF-16LE 的位置
    # 宋体 = U+5B8B U+4F53 → LE bytes: 8B 5B 53 4F
    songti_le = bytes([0x8B, 0x5B, 0x53, 0x4F])
    positions = _find_all(data, songti_le)

    for songti_pos in positions:
        # 往前找记录类型 0x02
        if songti_pos >= 1 and data[songti_pos - 1] == 0x02:
            record_type_pos = songti_pos - 1
            # 再往前找分隔符 ff fe ff
            if record_type_pos >= 3 and data[record_type_pos - 3:record_type_pos] == SEP:
                # 再往前找字体数量: record_type_pos - 9 是字体数量
                # 例: testall count=3(宋体/微软雅黑/FS), S1 count=2(宋体/FS类型串)
                count_pos = record_type_pos - 9
                if count_pos >= 0:
                    font_count = data[count_pos]
                    if 1 <= font_count <= 16:
                        return _parse_font_table_at(data, count_pos)
    return fonts, 0x0200


def _parse_font_table_at(data: bytes, pos: int):
    """
    从指定位置解析字体表, 返回 (fonts, end_pos)。

    结构 (所有字符串 UTF-16LE, 由 ff fe ff 分隔):
      [count] [00 padding] SEP [02 table_marker] [raw_cn_name_4B]
        SEP [len en_name] [en_name] [prop_u16]
        SEP [len cn_name] [cn_name]
        SEP [len en_name] [en_name] [prop_u16]
        ...
        SEP [len type_str] [type_str]   ← "FS Math Type" 类型串
        SEP [00 end]
    """
    fonts = []
    font_count = data[pos]
    pos += 1
    if data[pos] == 0x00:
        pos += 1

    # 跳到第一个 SEP
    while pos < len(data) - 3 and data[pos:pos + 3] != SEP:
        pos += 1
    if pos >= len(data):
        return fonts, pos

    # 读表标记 (应该 0x02)
    pos += 3  # skip SEP
    table_marker = data[pos]
    if table_marker != 0x02:
        return fonts, pos
    pos += 1

    # ── 字体 1: 中文名是原始 4 字节 (2 字符) ──
    cn1 = _read_utf16_str(data, pos, 2)
    pos += 4

    # SEP + 英文名
    if data[pos:pos + 3] == SEP:
        pos += 3
    en_len = data[pos]; pos += 1
    en1 = _read_utf16_str(data, pos, en_len)
    pos += en_len * 2
    prop1 = struct.unpack_from('<H', data, pos)[0]
    pos += 2
    fonts.append(Font(index=0, cn_name=cn1, en_name=en1, property_val=prop1))

    # ── 后续字体: SEP + 长度 + 中文名, SEP + 长度 + 英文名 + 属性 ──
    while len(fonts) < font_count and pos + 3 < len(data):
        # SEP
        if data[pos:pos + 3] == SEP:
            pos += 3
        else:
            break

        b = data[pos]
        if b == 0x00:
            break  # 表结束

        # 中文名 (长度前缀)
        cn_len = b; pos += 1
        cn = _read_utf16_str(data, pos, cn_len)
        pos += cn_len * 2

        # SEP + 英文名
        if data[pos:pos + 3] == SEP:
            pos += 3
        en_len = data[pos]; pos += 1
        if en_len == 0:
            # 无英文名 (如 "FS Math Type" 用作第3字体时), 属性=0
            en = ""
            prop = 0
            fonts.append(Font(index=len(fonts), cn_name=cn,
                              en_name=en, property_val=prop))
            # 已是最后一条记录, 结束位置 = 当前位置 (样式区起点)
            return fonts[:font_count], pos
        en = _read_utf16_str(data, pos, en_len)
        pos += en_len * 2

        # 属性值 (uint16 LE)
        prop = struct.unpack_from('<H', data, pos)[0]
        pos += 2

        fonts.append(Font(index=len(fonts), cn_name=cn,
                          en_name=en, property_val=prop))

    # 字体表结束位置: 找到 SEP 00 (end marker) 之后
    end_pos = pos
    i = pos
    while i < len(data) - 4:
        if data[i:i + 3] == SEP and data[i + 3] == 0x00:
            end_pos = i + 4
            break
        i += 1

    return fonts[:font_count], end_pos


# ── 文本记录解析 ──────────────────────────────────────────

def _find_all_text_objects(data: bytes) -> list:
    """
    扫描文件中所有文本对象, 返回 [(text_len, text, run_start), ...]。

    文本对象 = [长度 u32][文本 UTF16][run 表 (字符数u16,样式IDu16)...]。
    run 表字符数合计 = 长度。文件可能含多个文本对象(多行/多段落)。
    """
    objs = []
    i = 0
    while i + 4 < len(data):
        ln = struct.unpack_from('<I', data, i)[0]
        if 1 <= ln <= 1000 and i + 4 + ln * 2 <= len(data):
            try:
                text = data[i + 4:i + 4 + ln * 2].decode('utf-16-le')
                if text and all(c.isprintable() or c in '\r\n\t' for c in text):
                    run_start = i + 4 + ln * 2
                    if _validate_run_table(data, run_start, ln):
                        objs.append((ln, text, run_start))
                        i = run_start  # 跳到 run 表后, 继续
                        continue
            except (UnicodeDecodeError, ValueError):
                pass
        i += 1
    return objs


def _validate_run_table(data: bytes, start: int, text_len: int) -> bool:
    """校验 run 表: (字符数,样式ID) 对, 字符数合计 == text_len"""
    pos = start
    total = 0
    while pos + 4 <= len(data):
        ch = struct.unpack_from('<H', data, pos)[0]
        if ch == 0 or ch > text_len:
            return False
        total += ch
        pos += 4
        if total == text_len:
            return True
        if total > text_len:
            return False
    return False


def _find_image_ref_offsets(data: bytes, image_count: int) -> list:
    """
    在对象流中找每个图片的引用偏移 (用于确定图片显示在哪个段落)。

    图片引用对象以 [图片序号 u32][位置 x u16][位置 y u16] 开头,
    如 `01 00 00 00 08 00 40 00`。图片数据存于文件头部, 但显示
    引用位于对象流中(文本对象之间), 决定图片的段落位置。
    返回 [(序号, 引用偏移), ...]。
    """
    refs = []
    for n in range(1, image_count + 1):
        pat = struct.pack('<I', n) + b'\x08\x00\x40\x00'
        p = data.find(pat)
        if p != -1:
            refs.append((n, p))
    return refs


def _parse_text_object_runs(data: bytes, run_start: int,
                            text_len: int) -> list:
    """从 run 表起始解析 (char_count, style_id) 列表"""
    runs = []
    pos = run_start
    total = 0
    while pos + 4 <= len(data) and total < text_len:
        ch = struct.unpack_from('<H', data, pos)[0]
        sid = struct.unpack_from('<H', data, pos + 2)[0]
        if ch == 0 or ch > text_len:
            break
        runs.append((ch, sid))
        total += ch
        pos += 4
    return runs

def _find_text_record(data: bytes) -> Optional[tuple]:
    """
    找到文本记录 (record type 0x0380), 返回 (offset, text, text_offset, text_len)
    """
    # 搜索记录类型 0x0380 的位置 (LE: 80 03)
    pattern = struct.pack('<H', 0x0380)
    positions = _find_all(data, pattern)

    for pos in positions:
        # 0x0380 后面是 8 个 uint16 header 字段
        header_start = pos + 2
        if header_start + 16 + 4 > len(data):
            continue
        # 文本长度 (uint32 LE) 在 header 之后
        text_len_offset = header_start + 16
        text_len = struct.unpack_from('<I', data, text_len_offset)[0]

        # 合理性检查
        if text_len == 0 or text_len > 10000:
            continue
        text_offset = text_len_offset + 4
        if text_offset + text_len * 2 > len(data):
            continue

        # 尝试解码文本
        try:
            text = _read_utf16_str(data, text_offset, text_len)
            # 检查是否都是可打印字符
            if all(c.isprintable() or c in '\r\n\t' for c in text):
                return (pos, text, text_offset, text_len)
        except (UnicodeDecodeError, ValueError):
            continue

    return None


def _parse_formatting_runs(data: bytes, text_end: int,
                           fonts: List[Font], text_len: int) -> list:
    """
    从文本内容之后解析格式化运行表, 返回 [(char_count, font, style_id), ...]。

    布局 (uint16 LE 序列):
      run1_char_count, style1_id, run2_char_count, style2_id, ...
    每个 run 的 char_count 依次对应字体表中的字体, style_id 对应样式定义。
    """
    runs = []
    pos = text_end
    total = 0
    font_idx = 0

    while pos + 4 <= len(data) and total < text_len:
        char_count = struct.unpack_from('<H', data, pos)[0]
        style_id = struct.unpack_from('<H', data, pos + 2)[0]
        pos += 4

        if char_count == 0 or char_count > text_len:
            break

        font = fonts[font_idx] if font_idx < len(fonts) else None
        runs.append((char_count, font, style_id))
        total += char_count
        font_idx += 1

    return runs


# ── 颜色解析 ──────────────────────────────────────────────

# 颜色记录 flag 值
_FG_FLAGS = (0x05, 0x07)  # 前景/文字色
_BG_FLAG = 0x00           # 背景色
_NONE_FLAG = 0x02         # 无色(默认)

_DEFAULT_SIZE_PT = 10.5   # 默认字号 = 五号


def _highsat(bgr) -> bool:
    """判断 3 字节是否为高饱和颜色(至少一字节 >= 0x80)"""
    return max(bgr) >= 0x80


def _extract_size_pt(data: bytes, pos: int, end: int) -> float:
    """
    从样式记录中提取字号(pt)。

    字号存储在 '34 00' 之后的 uint16 (小端) = pt*100。
    若 '34 00' 后是颜色标志(05/07/02) 或找不到, 则用默认五号(10.5pt)。
    """
    scan_end = min(end, pos + 32)
    si = data.find(b'\x34\x00', pos + 2, scan_end)
    if si == -1 or si + 3 >= len(data):
        return _DEFAULT_SIZE_PT
    nxt = data[si + 2]
    if nxt in _FG_FLAGS or nxt == _BG_FLAG or nxt == _NONE_FLAG:
        return _DEFAULT_SIZE_PT  # 颜色标志, 无字号覆盖
    raw = struct.unpack_from('<H', data, si + 2)[0]
    if 1000 <= raw <= 5000:
        return raw / 100.0
    return _DEFAULT_SIZE_PT


def _extract_style_meta(data: bytes, style_ids, text_record_offset: int,
                        region_start: int = 0x0200) -> dict:
    """
    从样式定义区解析每个样式ID的字体键、前景色、背景色和字号,
    返回 {style_id: {'font_key','fg','bg','size_pt'}}。

    样式记录以 [ID 00] 开头。颜色记录格式为 [flag][BGR 3字节]:
      flag=0x02 无色 | flag=0x00 背景色 | flag=0x05/0x07 前景色。
    字号存储在 '34 00' 之后的 uint16 (小端) = pt*100。
    每条记录范围 = 自身到下一条样式ID 或 区域结束。
    """
    meta = {}
    region_end = text_record_offset

    # 用样式区起点作锚点。优先用"样式0"定位(比 min_sid 更可靠,
    # 避免 min_sid 恰好等于样式表头值被误匹配, 如 ul_color/nolist 的样式11撞表头0b)
    anchor = region_start
    if style_ids:
        a = data.find(bytes([0, 0x00]), region_start)
        if a != -1 and a < region_end:
            anchor = a
        else:
            min_sid = min(style_ids)
            a = data.find(bytes([min_sid, 0x00]), region_start)
            if a != -1 and a < region_end:
                anchor = a

    posmap = {}
    for sid in style_ids:
        pos = data.find(bytes([sid, 0x00]), anchor)
        if pos != -1 and pos < region_end:
            if sid not in posmap or pos < posmap[sid]:
                posmap[sid] = pos

    order = sorted(posmap.items(), key=lambda x: x[1])
    for idx, (sid, pos) in enumerate(order):
        end = order[idx + 1][1] if idx + 1 < len(order) else region_end
        scan_end = min(end, pos + 20)

        font_key = data[pos + 4] if pos + 4 < scan_end else 0

        # 属性第1字节的位标志决定有无前景/背景色:
        #   0x04 = 有前景色, 0x08 = 有背景色 (testall EFG 0x0c = 两者都有)
        attr = data[pos + 2] if pos + 2 < scan_end else 0
        has_fg = bool(attr & 0x04)
        has_bg = bool(attr & 0x08)
        # 文字装饰标志: pos+2 的 bit1(0x02) 表示该样式有文字装饰
        # 此时: pos+6 bit4(0x10)=删除线, pos+7 bit4(0x10)=下划线,
        #       pos+8 bit0(0x01)=粗体, attr bit4(0x10)=有下划线颜色
        # pos+2 非 0x02 时 pos+6/pos+7/pos+8 是字号等其他数据
        has_bold = False
        has_strikethrough = False
        has_underline = False
        has_italic = False
        underline_color = None
        underline_field = None  # 下划线颜色字段位置 (start,end), 颜色扫描时跳过
        if attr & 0x02:
            extra6 = data[pos + 6] if pos + 6 < scan_end else 0
            extra7 = data[pos + 7] if pos + 7 < scan_end else 0
            extra8 = data[pos + 8] if pos + 8 < scan_end else 0
            has_strikethrough = bool(extra6 & 0x10)
            has_underline = bool(extra7 & 0x10)
            has_bold = bool(extra8 & 0x01)
            has_italic = bool(extra8 & 0x02)
            # 有下划线颜色 (attr bit4): 颜色在 pos+10-12 (BGR) + flag(pos+13)
            if attr & 0x10 and pos + 12 < scan_end:
                bgr = data[pos + 10:pos + 13]
                if len(bgr) == 3 and _highsat(bgr):
                    underline_color = "#%02X%02X%02X" % (bgr[2], bgr[1], bgr[0])
                underline_field = (pos + 10, pos + 14)  # 跳过 4 字节, 防 ff 误判为背景色

        # 定位字号字段 ('34 00' 后 uint16∈[1000,5000] 才是字号, 否则是颜色flag)
        size_field = None  # (start, end) 需跳过的字号字段
        si = data.find(b'\x34\x00', pos + 2, scan_end)
        if si != -1 and si + 3 < len(data):
            raw = struct.unpack_from('<H', data, si + 2)[0]
            if 1000 <= raw <= 5000:
                size_field = (si + 2, si + 4)

        fg = bg = None
        i = pos + 2
        while i + 4 <= scan_end:
            # 3 个连续 0x00 = 样式区填充/结束 → 停止 (除非后接高饱和字节=颜色如红 00 00 00 ff)
            if data[i] == 0 and data[i + 1] == 0 and data[i + 2] == 0:
                if data[i + 3] < 0x80:
                    break
            # 跳过字号字段及其可能误判的重叠 (属性尾00 + 字号)
            if size_field and i < size_field[1] and i + 4 > size_field[0]:
                i = size_field[1]
                continue
            # 跳过下划线颜色字段 (防 flag ff 误判为背景色)
            if underline_field and i < underline_field[1] and i + 4 > underline_field[0]:
                i = underline_field[1]
                continue
            f = data[i]
            bgr = data[i + 1:i + 4]
            # 颜色记录 = [flag][BGR 3字节]
            #   flag 05/07 → 前景色; flag ff → 背景色
            #   flag 00 → 由属性位决定 (has_fg 则前景, 仅 has_bg 则背景)
            # bgr[0]∈{05,07,02} 时是属性尾 00 + 前景flag, 跳过避免误判
            if f == _NONE_FLAG:
                i += 1
                continue
            if f in (0x05, 0x07) or (f == 0x00 and has_fg):
                if _highsat(bgr) and bgr[0] not in _FG_FLAGS and bgr[0] != _NONE_FLAG:
                    r, g, b = bgr[2], bgr[1], bgr[0]  # BGR→RGB
                    if fg is None:
                        fg = "#%02X%02X%02X" % (r, g, b)
                    i += 4
                    continue
            elif f == 0xff or (f == 0x00 and has_bg):
                if _highsat(bgr) and bgr[0] not in _FG_FLAGS and bgr[0] != _NONE_FLAG:
                    r, g, b = bgr[2], bgr[1], bgr[0]  # BGR→RGB
                    if bg is None:
                        bg = "#%02X%02X%02X" % (r, g, b)
                    i += 4
                    continue
            i += 1

        size_pt = _extract_size_pt(data, pos, end)

        meta[sid] = {"font_key": font_key, "fg": fg, "bg": bg,
                     "size_pt": size_pt, "bold": has_bold,
                     "strikethrough": has_strikethrough,
                     "underline": has_underline, "italic": has_italic,
                     "underline_color": underline_color}

    return meta


# ── 图片解析 ──────────────────────────────────────────────

def _parse_images(data: bytes) -> List[Image]:
    """
    提取嵌入的 JPEG 图片。

    图片对象头位于 JPEG 数据之前 14 字节:
      [JPEG-14] 对象数 (uint32)
      [JPEG-10] padding (2 字节)
      [JPEG-8]  显示宽 (uint16)
      [JPEG-6]  显示高 (uint16)
      [JPEG-4]  JPEG 数据长度 (uint32)
      [JPEG]    JPEG 原始字节流 (FF D8 ... FF D9)

    通过 JPEG 魔数定位, 并用 JPEG-4 长度校验增强可靠性。
    """
    images = []
    scan = 0
    while True:
        pos = data.find(b'\xff\xd8\xff', scan)
        if pos == -1:
            break
        jp_end = data.find(b'\xff\xd9', pos)
        if jp_end == -1:
            scan = pos + 1
            continue

        # 校验对象头长度字段与实际 JPEG 长度一致
        if pos >= 4:
            declared = struct.unpack_from('<I', data, pos - 4)[0]
            actual = jp_end + 2 - pos
            if declared != actual:
                scan = pos + 1
                continue

        width = struct.unpack_from('<H', data, pos - 8)[0] if pos >= 8 else 0
        height = struct.unpack_from('<H', data, pos - 6)[0] if pos >= 6 else 0

        jp_data = data[pos:jp_end + 2]
        aw, ah = _jpeg_sof_size(jp_data)

        images.append(Image(
            index=len(images),
            width=width, height=height,
            data=jp_data,
            actual_width=aw, actual_height=ah,
        ))
        scan = jp_end + 2

    return images


def _jpeg_sof_size(jp: bytes):
    """从 JPEG 数据解析 SOF 段的实际像素尺寸, 返回 (width, height)"""
    i = 2
    while i < len(jp) - 1:
        if jp[i] == 0xFF:
            marker = jp[i + 1]
            # SOF0-SOF15 (基线/渐进/无损等)
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6,
                          0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if i + 9 <= len(jp):
                    h = struct.unpack_from('>H', jp, i + 5)[0]
                    w = struct.unpack_from('>H', jp, i + 7)[0]
                    return w, h
                break
            if 0xD0 <= marker <= 0xD9:
                i += 2  # 无长度段 (RST/SOI/EOI)
                continue
            if i + 4 <= len(jp):
                seg_len = struct.unpack_from('>H', jp, i + 2)[0]
                if seg_len == 0:
                    break
                i += 2 + seg_len
            else:
                break
        else:
            i += 1
    return 0, 0


# ── 表格解析 ────────────────────────────────────────────

def _find_tables(data: bytes) -> List[Table]:
    """扫描所有表格对象。

    表格结构:
      [01 00 00 00 06 00 50 00]   ← 表头标记 (8 字节)
      [单元格总数 u32]
      [列数 u16][行数 u16]
      [00 00 01 00 00 00 00 00]
      [单元格1: 长度u32 + UTF16文本 + run表] [单元格2: ...] ...

    单元格文本按**行优先**(row-major)顺序存储 (A1 B1 C1 ... / A2 B2 ...)。
    校验: 单元格总数 == 列数 × 行数。
    """
    tables = []
    pat = bytes([0x01, 0x00, 0x00, 0x00, 0x06, 0x00, 0x50, 0x00])
    heads = []
    p = 0
    while True:
        p = data.find(pat, p)
        if p == -1:
            break
        heads.append(p)
        p += 1
    if not heads:
        return tables

    text_objs = _find_all_text_objects(data)
    for ti, head in enumerate(heads):
        if head + 16 > len(data):
            continue
        cell_cnt = struct.unpack_from('<I', data, head + 8)[0]
        col = struct.unpack_from('<H', data, head + 12)[0]
        row = struct.unpack_from('<H', data, head + 14)[0]
        if not (1 <= col <= 60 and 1 <= row <= 60) or cell_cnt != col * row:
            continue
        # 单元格文本: 偏移在表格头之后、下一个表格头之前
        end = heads[ti + 1] if ti + 1 < len(heads) else len(data)
        cell_objs = [(rs, t) for _, t, rs in text_objs if head < rs < end][:cell_cnt]
        cells = [t for _, t in cell_objs]
        offsets = [rs for rs, _ in cell_objs]
        # 行优先: 每行 col 个单元格
        grid = [cells[r * col:(r + 1) * col] for r in range(row)]
        tables.append(Table(col=col, row=row, cells=grid,
                            cell_offsets=offsets))
    return tables


# ── 主解析入口 ────────────────────────────────────────────

def parse_wsd(data: bytes) -> WsdDocument:
    """
    解析 WSTUDIO5 (.wsd) 二进制数据, 返回 WsdDocument。
    """
    doc = WsdDocument()

    # 检查文件头
    if not data.startswith(b'\x00WSTUDIO'):
        return doc

    # 1. 解析字体表
    doc.fonts, font_end = _parse_font_table(data)

    # 1b. 解析嵌入图片
    doc.images = _parse_images(data)

    # 1c. 解析表格
    doc.tables = _find_tables(data)

    # 2. 扫描所有文本对象 (多行/多段落)
    text_objects = _find_all_text_objects(data)
    if not text_objects:
        return doc

    # 收集所有文本和 run
    all_text = "".join(t for (_, t, _) in text_objects)
    doc.raw_text = all_text

    # 收集所有样式ID
    all_style_ids = set()
    for obj_len, _, run_start in text_objects:
        for _, sid in _parse_text_object_runs(data, run_start, obj_len):
            all_style_ids.add(sid)

    # 3. 提取样式元数据 (字体键 + 颜色 + 字号)
    # 样式区锚点用第一个文本对象之前的位置
    first_obj = text_objects[0]
    style_meta = _extract_style_meta(data, all_style_ids, first_obj[2], font_end)

    # 字体键 → 字体索引
    # 规则(按优先级):
    #   1. 互补: property_val + font_key == 55 (宋体3+52, 微软雅黑52+3)
    #   2. 直接: font_key == property_val (S1宋体 prop=52)
    #   3. FS特殊: font_key 0x02 → "FS Math Type" 字体
    #   4. 兜底: font_key & 1 (bit0, 宋体0/微软雅黑1)
    def _map_font_key(fk):
        # font_key 0x00 = 默认字体 (字体表第0个, 宋体)
        if fk == 0:
            return 0
        # 1. 互补: property_val + font_key == 55
        for i, f in enumerate(doc.fonts):
            if f.property_val + fk == 55:
                return i
        # 2. 直接: font_key == property_val (S1宋体 prop=52)
        for i, f in enumerate(doc.fonts):
            if f.property_val == fk and fk != 0:
                return i
        # 3. FS特殊: font_key 0x02 → "FS Math Type" 字体
        if fk == 0x02:
            for i, f in enumerate(doc.fonts):
                if "FS" in f.cn_name:
                    return i
        # 4. 兜底: font_key & 1 (bit0, 宋体0/微软雅黑1)
        return fk & 1
    key_to_font_idx = {style_meta.get(sid, {}).get("font_key", 0): _map_font_key(style_meta.get(sid, {}).get("font_key", 0)) for sid in all_style_ids}

    # 4. 按对象流顺序排序 (文本对象 + 图片引用), 分配段落序号
    #    文本对象偏移用 run_start, 图片用引用偏移
    items = []  # (offset, kind, index)
    for idx, (_, _, run_start) in enumerate(text_objects):
        items.append((run_start, 'text', idx))
    img_refs = _find_image_ref_offsets(data, len(doc.images))
    for img_idx, ref_off in img_refs:
        items.append((ref_off, 'image', img_idx - 1))
    items.sort(key=lambda x: x[0])

    paragraph_of_text = {}   # 文本对象index -> 段落
    paragraph_of_image = {}  # 图片index -> 段落
    for para, (_, kind, idx) in enumerate(items):
        if kind == 'text':
            paragraph_of_text[idx] = para
        else:
            paragraph_of_image[idx] = para

    # 5. 逐文本对象切分, 组合 TextRun (带段落号)
    #    表格单元格偏移集合 (这些 run 不单独显示, 由表格渲染)
    table_cell_offsets = set()
    for tbl in doc.tables:
        table_cell_offsets.update(tbl.cell_offsets)
    #    尾字段类型 tail0 编码段落对齐 (diff_style_align.wsd 隔离实验铁证):
    #      0x01=两端对齐(默认), 0x0c=居中对齐, 0x0d=左对齐, 0x0e=右对齐, 0x10=居中对齐
    #      (diff_style_align 前5行居中=0x0c 后6行左=0x0d, 用户明确确认;
    #       aligns 同此; testall_2 删除线居中=0x10 亦为居中)
    #    列表由对象流中的 Wingdings 项目符号对象决定(has_bullet_obj):
    #      有项目符号对象时, tail0=0x0c→无序列表(居中), 0x0d→有序列表(左)
    #      无项目符号对象时, tail0 仅表示对齐(如 aligns.wsd, diff_style_align.wsd)
    align_map = {0x01: 'justify', 0x0c: 'center', 0x0d: 'left', 0x0e: 'right', 0x10: 'center'}
    # tail0 是段落样式ID, 对齐映射因文件而异 (用户确认 alitest1/2, diff_style_align, aligns 用标准映射)
    # 含删除线/粗体装饰段落的文件(如 testall.wsd, 对象流含 `0f 00 0f 00` 两端段落对象)用另一映射:
    #   testall: 第一行(居中)=0x0d, 删除线/粗体(两端)=0x0c, 与标准映射(0x0d=左/0x0c=居中)相反
    has_obj_two_ends = b'\x0f\x00\x0f\x00' in data   # 删除线两端段落对象
    if has_obj_two_ends:
        align_map[0x0c] = 'justify'   # testall 删除线/粗体两端
        align_map[0x0d] = 'center'    # testall 第一行居中
    bullet_marker = b'\x07\x00\x07\x09\x00\x6c\x00'
    has_bullet_obj = bullet_marker in data
    for obj_idx, (text_len, text, run_start) in enumerate(text_objects):
        runs = _parse_text_object_runs(data, run_start, text_len)
        para = paragraph_of_text[obj_idx]
        # 尾字段: run表结束后, 类型u16
        run_end = run_start + len(runs) * 4
        tail_val = struct.unpack_from('<H', data, run_end)[0] if run_end + 2 <= len(data) else 0
        align = align_map.get(tail_val)
        list_type = None
        if has_bullet_obj:
            # 有项目符号对象 → tail0 表示列表类型 (ul/ol)
            if tail_val == 0x0c:
                list_type = 'ul'
            elif tail_val == 0x0d:
                list_type = 'ol'
        char_pos = 0
        for char_count, style_id in runs:
            if char_pos + char_count > len(text):
                break
            segment = text[char_pos:char_pos + char_count]
            meta = style_meta.get(style_id, {})
            fk = meta.get("font_key", 0)
            fi = key_to_font_idx.get(fk)
            run_font = doc.fonts[fi] if fi is not None and fi < len(doc.fonts) else None
            doc.text_runs.append(TextRun(
                text=segment, font=run_font,
                color=meta.get("fg"), bgcolor=meta.get("bg"),
                font_size_pt=meta.get("size_pt"), paragraph=para,
                offset=run_start, in_table=run_start in table_cell_offsets,
                strikethrough=meta.get("strikethrough", False),
                bold=meta.get("bold", False),
                italic=meta.get("italic", False),
                underline=meta.get("underline", False),
                underline_color=meta.get("underline_color"),
                list_type=list_type,
                align=align,
            ))
            char_pos += char_count
        # 未覆盖的尾部文本
        if char_pos < len(text):
            fallback = doc.fonts[0] if doc.fonts else None
            doc.text_runs.append(TextRun(text=text[char_pos:], font=fallback,
                                         paragraph=para, offset=run_start,
                                         in_table=run_start in table_cell_offsets))

    # 6. 给图片分配段落号
    for img in doc.images:
        img.paragraph = paragraph_of_image.get(img.index, 0)

    # 7. 填充表格单元格的 TextRun (含样式), 供表格渲染
    if doc.tables:
        off_to_run = {}
        for run in doc.text_runs:
            if run.in_table:
                off_to_run.setdefault(run.offset, run)
        for tbl in doc.tables:
            tbl.cell_runs = []
            for r in range(tbl.row):
                row_runs = []
                for c in range(tbl.col):
                    idx = r * tbl.col + c
                    run = None
                    if idx < len(tbl.cell_offsets):
                        run = off_to_run.get(tbl.cell_offsets[idx])
                    row_runs.append(run)
                tbl.cell_runs.append(row_runs)

    return doc


# ── 旧接口兼容 ────────────────────────────────────────────

def parse_ee_bin(bin_: bytes) -> str:
    """兼容旧接口: 返回纯文本字符串"""
    doc = parse_wsd(bin_)
    if doc.raw_text:
        return doc.raw_text
    return "nonfile"


# ── 命令行测试 ────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import tkinter.filedialog

    path = tkinter.filedialog.askopenfilename(
        filetypes=[("WSD files", "*.wsd"), ("All", "*.*")]
    )
    if not path:
        sys.exit(0)

    with open(path, "rb") as f:
        data = f.read()

    doc = parse_wsd(data)

    print(f"字体数量: {len(doc.fonts)}")
    for font in doc.fonts:
        print(f"  [{font.index}] {font.cn_name} / {font.en_name}  "
              f"(property=0x{font.property_val:04x})")

    print(f"\n原始文本: \"{doc.raw_text}\"")
    print(f"格式化运行数: {len(doc.text_runs)}")
    for run in doc.text_runs:
        fname = run.font.cn_name if run.font else "?"
        fg = run.color if run.color else "默认"
        bg = run.bgcolor if run.bgcolor else "无"
        size = f"{run.font_size_pt:g}pt" if run.font_size_pt else "?"
        print(f"  \"{run.text}\" → 字体: {fname}, 字号: {size}, "
              f"前景: {fg}, 背景: {bg}")

    print(f"\n嵌入图片数: {len(doc.images)}")
    for img in doc.images:
        print(f"  [图片{img.index}] 显示尺寸: {img.width}x{img.height}, "
              f"{img.data_format}, 数据长度: {len(img.data)} 字节")

    print(f"\nHTML 输出:")
    print(doc.to_html())
