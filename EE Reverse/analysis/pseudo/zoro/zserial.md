# zoro 序列化栈 — 反编译规格（阶段 2 · 第三批 0.4/0.5/0.6）

- 模块：zoro.dll；函数：105 个（zMemory 30 · zStream 34 · zFile 18 · zFileSerializer 13 · zArchive 10）
- 伪代码（原样）：`analysis/pseudo/zoro/zserial.decomp.txt`（105/105 dumped）
- 类型头：`analysis/types/zserial.h`
- 台账：105/105 → `decompiled`
- **这是 .wsd 存盘/读取的底层通道（S4）**。Editor 侧拿一个 `zStream` 接口（实际是 `zArchive`
  或 `zFileSerializer`），把对象树串下去。

## 0. 两条平行基接口（本批最重要的结构结论）

| 基类 | vtable 槽（字节偏移） | 角色 |
|---|---|---|
| `zStream` | `+0x00` dtor · `+0x08` **WriteRaw(void*, ulong)** · `+0x0C` **ReadRaw(void*, ulong)** · `+0x04`/`+0x10` 未观测 | 前端接口（对象调用它写字段） |
| `zBaseBuffer` | `+0x00` dtor · `+0x04` GetBufferSize · `+0x08` GetPosition · `+0x0C` Seek · `+0x10` Read · `+0x14` Write | 后端存储接口（文件/内存） |

- `zStream` 家族（前端）：`zArchive`、`zFileSerializer` —— 它们实现 `+0x08/+0x0C`。
- `zBaseBuffer` 家族（后端）：`zFile`、`zMemory` —— 它们实现 `GetBufferSize/GetPosition/Seek/Read/Write`。
- 桥接：`zArchive` 抱着一个 `zBaseBuffer*`（+0x08），把自己的 `Write/Read` 转发到它的 `+0x14/+0x10`；
  `zFileSerializer` 内嵌 `zFile`，同理。
- 证据：`zStream::WriteByte 0xc170`（`(**(*this+8))(p,n)`）；`zArchive::Write 0xcb90`（`(**(*(this+8)+0x14))(p,n)`）；
  `zFileSerializer::Flush 0xcf20`（`(**(*(this+8)+0x14))`）。

## 1. zMemory（引用计数内存缓冲 + 游标，zBaseBuffer 后端）

**布局**（`zBaseMemory` 基类含 vptr）：

| 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| +0x04 | uint | 增长步长（ctor 参数；拷贝/默认=0x100） | `ctor 0x1e7e0`；增长公式 `cap=need+step` |
| +0x08 | uchar* | 数据（`realloc`/`zrt_new`/`free` 管理） | 全族 |
| +0x0C | uint | 逻辑长度 size | `Read 0x1ede0` 越界判据 |
| +0x10 | uint | 已分配容量 cap（≥size；增长=need+step） | `Write 0x1f070` |
| +0x14 | uint | 游标 position | `GetPosition 0xabe0` |
| +0x18 | int | 引用计数（`AddRef 0x1eaf0`/`Release 0x1eb10`→vtbl[0](1) 自毁） | |

**行为表**：

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(uint step)` | `0x1e7e0` | step==0→0；全清零。默认闭包=`zMemory(0x100)`（`0xac00`） |
| `ctor(uchar*, size, step)` | `0x1e860` | **接管外部指针**（不拷贝；dtor 会 `free` 它 —— 所有权假设） |
| `ctor(tagBYTEDATA&, step)` | `0x1e8d0` | 同上（取 {ptr,size}） |
| `ctor(copy/move)` | `0x1e950/0x1ea00` | 拷贝=step 0x100+CopyFrom；移动=窃取+源置零 |
| `~` | `0x1eab0` | `free(data)` |
| `Zero/Clear` | `0x1eb70/0x1eba0` | memset(size) / free+清零 |
| `IsEqual` | `0x1ebf0` | 尺寸相等 + `memcmp` |
| `Realloc(n)` | `0x1ec60` | n>cap→`realloc` 并更新 cap；设 size=n（不收缩数据） |
| `Insert(pos, p, n)` | `0x1ecc0` | 拒绝 pos>size；**拒绝 p 落在自身缓冲内**（重叠防呆）；size+=n；cap 不足→`realloc` 至 size+step；memmove 腾位+memcpy |
| `Read(p, n)` | `0x1ede0` | 越界（pos+n>size）→0；否则 memcpy、pos+=n、返回 1 |
| `Attach(p, n)` | `0x1ee40` | **free 旧数据**后接管 p（size=cap=n） |
| `CopyFrom(m)` / `(p,n)` | `0x1eea0/0x1eed0` | 深拷贝；cap 不足时用 **`zrt_new`**（注意与 realloc 混用） |
| `TransferFrom(m)` | `0x1ef70` | Clear + 取 m 的 Detach 指针 Attach |
| `AllocWrite(n)` | `0x1efc0` | 保留游标处 n 字节（cap=need+step），返回指针、pos+=n、size 随增 |
| `Write(p, n)` | `0x1f070` | 同 AllocWrite 但 memcpy；返回 1 |
| `Seek(off, z_seek)` | `0x1f130` | 0/1/2；**seek-end 用 `size - off`（非常规，Q4）**；越界拒绝 |
| `GetBuffer(n)` | `0x1f1b0` | cap<n→realloc；**size=n（隐含 SetSize！Q3）**；返回原始指针 |
| `Detach()` | `0x1f210` | 返回指针并全置零（移交所有权） |
| `SetSize(n)` | `0x1f390` | 扩→补零 memset；缩→clamp 游标；n==0→size=pos=0 |
| `operator uchar*/Lock/GetData` | `0x5b40`（多别名同址） | 返回 +0x08 |
| `operator[]` | `0xabb0` | data+i（无检查） |
| `Unlock` | `0xabd0` | 返回 1（虚槽，恒成功） |
| **`Serialize(zArchive&)`** | `0x1f260` | **格式见 §6**（2 字节长度 or FFFF+dword + 原始载荷） |

## 2. zStream（前端调度器，抽象）

- 字段：`+0x00` vptr · `+0x04` **mode（0=storing 写，≠0=loading 读）**（`IsStoring 0xbfc0`、`ctor 0xbf70`）。
- 全部 WriteX/ReadX 都是**一行动态派发**：`(**(code**)(*this+8))(ptr,size)` / `(**(code**)(*this+0xC))`。
- 类型→尺寸：Byte/Char→1 · `WriteChar(wchar_t)`/Int16/Short/Word→2 · DWord/Int32/Float→4 · Double/Int64→8（`0xc170-0xc1d0` 同一模板）。
- `WriteText(char*,n)` n<0→strlen，写 n 字节；`WriteText(wchar_t*,n)` n<0→wcslen，写 **n×2 字节**（`0xc1f0/0xc250`）。
- `EndLine(int wide)`：宽=0 → 写 `_endline`（2 字节 CR LF）；否则 `_wendline`（4 字节 L"\r\n"）（`0xc290`）。
- **`WriteStringLength(n, wideFlag)` / `ReadStringLength`（0xc880/0xc930）——字符串变长格式（S4 关键）**：

```
宽字符串前缀（wideFlag!=0 时先写）: FF FE FF          (3B: byte FF + LE16 0xFFFE)
长度编码（LE）:
  n < 0xFF        : [n]                                (1B)
  0xFF ≤ n < 0xFFFE : FF [n16]                         (3B)
  0xFFFE ≤ n < 0xFFFFFFF : FF FF FF [n32]              (7B: FF + LE16 0xFFFF + dword)
  n ≥ 0xFFFFFFF   : FF FF FF FF                        (4B 哨兵，无后续 —— 异常路径)
读侧（0xc930）：byte<FF→len；=FF→读16位：==FFFE→wide=1，再读 byte≠FF 则 len=byte 直接结束；
               否则（16 位 <FFFF）→len=16 位值；==FFFF→读 dword（>0x7FFFFFFE 钳为 0xFFFFFFFF）
```
- `operator<<(zMemory&)`（`0xc9e0`）：`WriteDWord(size)` + 原始字节（size 来自后端 vtbl+4）；
  `operator>>(zMemory&)`（`0xca30`）：读 DWord，<1→对方 `Clear`，否则 `GetBuffer(n)`+读 n 字节。

## 3. zArchive（zStream 前端 + zBaseBuffer 后端适配器）

- 布局：`zStream`(vptr,mode) · `+0x08` `zBaseBuffer* m_buffer` · `+0x0C` int（ctor 置 0，用途待查）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(zBaseBuffer*, mode, rewind)` | `0xca80` | rewind≠0 且 buffer 非空 → buffer->Seek(0,0) |
| `~` | `0xcb20` | Close（仅解绑）+ ~zStream |
| `Close` | `0xcb70` | **仅把 +0x08 置 0（不关后端，Q5）** |
| `Write/Read(p, n)` | `0xcb90/0xcbe0` | 委托后端 `+0x14/+0x10`；后端空或写失败→返回 0，否则返回 n |
| `Seek/GetPosition` | `0xcc30/0xcc70` | 委托后端 `+0xC/+0x8`；空→0 |
| `GetBufferSize` | `0xc580` | 委托后端 `+0x4`；空→0 |
| `GetBufferObj` | （别名同址 `0x5b40` 群） | 返回 +0x08 |

## 4. zFileSerializer（zStream 前端 + 内嵌 zFile 后端 + 缓冲写入）

- 布局：`zStream`(vptr,mode) · `+0x08` 内嵌 `zFile`（12B：vptr,handle,flags）· `+0x14` 未刷字节数 ·
  `+0x18/+0x1C` 累计已写 64 位计数 · `+0x20` 缓冲大小 · `+0x24` 缓冲指针（`zrt_new`，`free` 释放）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(int mode)` | `0xcca0` | 零初始化（不开文件） |
| `ctor(path, mode, bufSize)` | `0xcd40` | 同上 + `Open(path, bufSize)` |
| `Open(path, buf)` | `0xce90` | buf<0x400 提升到 0x400；分配缓冲；清计数；`zFile::Open(path, mode==0?写:读)` |
| `Write(p, n)` | `0xcfc0` | **仅 mode==0**；累计 64 位计数；环形塞缓冲，满则 `Flush`；**返回值恒 0（Q1）** |
| `Read(p, n)` | `0xd0b0` | 仅 mode!=0；直读内嵌 zFile；失败→0 否则 n |
| `Flush` | `0xcf20` | 未刷字节→`zFile::Write(buf, pending)`，pending=0 |
| `Seek` | `0xd100` | **先 Flush** 再委托 zFile Seek |
| `GetPosition` | `0xd130` | zFile 位置 + 未刷字节数 |
| `Close` | `0xcf60` | 开着则：写模式 Flush；`free` 缓冲；`zFile::Close` |
| `~` | `0xcdf0` | Close + free(+0x24) + ~zFile + ~zStream |

## 5. zFile（Win32 文件，zBaseBuffer 后端）

- 布局：`zBaseBuffer`(vptr) · `+0x04` HANDLE（初值/关闭后 = `0xFFFFFFFF`）· `+0x08` 写脏标志（成功写置 1）。
- `Open`（`0x17110`，CreateFileW）：
  - flags 0（读）：`GENERIC_READ`，OPEN_EXISTING(3)
  - flags 1（写）：`GENERIC_WRITE`，CREATE_ALWAYS(2)
  - flags 2（读写）：`0xC0000000`，OPEN_EXISTING(3)
- `Read 0x171e0`：p==NULL 或 handle==0 → -1；ReadFile 全量才 1（Q2：与 IsOpen 的 `!=-1` 判据不一致）。
- `Write 0x17240`：handle==0→0；成功置 +8=1。
- `WriteStr/WriteWStr/WriteAsUTF8`：strlen/wcslen → UTF-8（栈 4KB，上限 0xFFF）/堆式转换 → 虚 Write；
  `WriteAsUTF8` n==0→`slen`（wcslen 类）；空指针返回 1 不写。
- `GetLength` GetFileSize · `GetPosition` SetFilePointer(0,0,1) · `Seek` z_seek 0/1/2 → 0/1/2 ·
  `SetFileSize` Seek(size,0)+SetEndOfFile · `FlushFileBuffers` 直通 · `Close` CloseHandle→handle=-1。

## 6. zMemory::Serialize 磁盘格式（S4）

```
写（storing，0x1f260 上半）:
  size < 0x8000 : [size16]            (2B LE)
  else          : [FFFF] [size32]     (2B 哨兵 + 4B LE)
  size != 0     : [原始 size 字节]
读（loading）: 读 16 位；==0xFFFF → 再读 dword 为 size；分配（zrt_new(size)）；读 size 字节；cap=size
```
- 注意与 §2 的 `WriteStringLength` **不是同一格式**（那是字符串字段；这是 blob）。

## 7. 怪癖 / 待复核（Q1–Q5 → RE-UNKNOWNS 候选）

- **Q1** `zFileSerializer::Write` 返回值恒 0（调用方若按"返回 0=失败"判会错；`zArchive::Write` 返回 n/0，语义相反）。
- **Q2** `zFile::Read` 的 handle 判据是 `==0`，而 `IsOpen`/`GetLength` 判据是 `!=-1`——未打开时 Read 可能对无效 handle 调用 ReadFile（依赖 CreateFileW 失败返回值恰为 -1 才不会命中 0 分支）。
- **Q3** `zMemory::GetBuffer(n)` 顺带把 size 置 n（语义近似 SetSize+取指针），调用方需知。
- **Q4** `zMemory::Seek` 的 seek-end 为 `size - off`（常规实现应为 `size + off`）。
- **Q5** `zArchive::Close` 不关闭后端文件/内存，只解绑。
- **Q6** `zMemory::Insert` 的 memmove 目标写为 `data + pos + 1`（疑似反编译伪影，待复核）。
- 分配混用（第三例）：`zMemory` 增长用 `realloc`、`CopyFrom`/`Serialize` 用 `zrt_new`、释放用 `free`。

## 8. 未收录但已见到的别名/折叠（ILT 同址多符号，以后解析导入面时会遇到）

`0x5b40` 折叠群：`zMemory::operator uchar*/Lock/GetData`、`zSharedMemory::GetData/GetPosition/Seek/Unlock`
（zSharedMemory 与 zMemory 共享大部分实现）、`zArchive::GetBufferObj/GetBufferSize`、`zList/zItem::Back/GetHead`、
`zArrayBase::GetCount`、`zSharedBuffer::GetBufferSize` 等（见伪代码第 16-35 行注释块）。
