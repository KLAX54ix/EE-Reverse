# zoro 遗留字符串族 — 反编译规格（阶段 2 · 第二批 0.2/0.3）

- 模块：zoro.dll；函数：88 个（`zstr 15 · zwstr 18 · zWSharedString 6 · zWstrArray 12 · zWstrList 22 · zStringItem 4 · zStringList 5 · zItem/zList<zStringItem> 6`）
- 伪代码（原样）：`analysis/pseudo/zoro/zstr-legacy.decomp.txt`（88/88 dumped）
- 类型头：`analysis/types/zstr-legacy.h`
- 台账：88/88 → `decompiled`（status-overrides.csv）
- 关系图：`zstr`/`zwstr` = `zStringTemplate` 的薄子类；`zWstrArray` = `zTypedPtrArray<wchar_t>` 派生；`zWstrList` = `zSection` 派生 + 侵入式双向链表；`zStringItem` = `zItem<zStringItem>` 派生（装载进 `zStringList`=`zList<zDataItem>`）

## 1. zstr / zwstr（ANSI / 宽字符薄子类）

**布局**：与 `zStringTemplate` 相同（12 B：+0x00 data / +0x04 len / +0x08 cap，字符数；见 zStringTemplate.h）。
除下列自有方法外全部转发基类。

| 函数 | 入口 | 规格 |
|---|---|---|
| `zstr::zstr()` / `(char*)` / `(char*,int)` / `(char)` / `(zstr const&)` | `0x2310/0x23a0/0x23c0/0x23e0/0x2400` | 纯转发基类（`(char*,int)` 即 SetString 语义） |
| `zstr::zstr(int)` | `0x2330` | 默认构造 + `Format("%d", n)`（格式串 = RVA `0x2c520` = `"%d"`，已从二进制取字节确认） |
| `zstr::zstr(wchar_t*)` | `0x2420` | **截断式转换**：`len=wcslen(p)`；逐字符 `(char)p[i]`；自管字段（绕过 SetString）；**cap 写成 len 而非 len+1（Q1）** |
| `zstr::operator=(wchar_t*)` | `0x2540` | 同 Q1 行为，返回 data 指针 |
| `zstr::operator<<` ×4 | `0x1caa0/0x1cad0/0x1cb00/0x1cb50` | Append(char*)/Append(zstr)/Format("%d",int)/Append(char) |
| `zstr::Format` | `0x1cba0` | `vsprintf` 家族 |
| `zwstr::zstr 全套 ctor` | `0x1fa0-0x2080` | 转发基类（`wchar_t*`、`wchar_t*,int`、`wchar_t`、拷贝、基类引用、不含 `std::wstring`） |
| `zwstr::zwstr(char*)` | `0x20a0` | `zEncoder::AnsiToUnicode` 转换；**Q2：仅当 `wcslen(转换结果)>1` 才 SetString —— 单字符 ANSI 输入停留在空串** |
| `zwstr::zwstr(std::wstring const&)` | `0x2050` | `FUN_1000a130`(=std::string::length) + `c_str()` |
| `zwstr::Enum(std::function<void(wchar_t)>)` | `0x2180` | 逐字符回调 |
| `zwstr::CompareFromFirst(wchar_t*)` | `0x2210` | 前缀比较（返回剩余差？见伪代码） |
| `zwstr::operator=` | `0x22f0` | 转发基类 op= |
| `zwstr::operator<<` ×4 + `MakeFrom(__int64/double)` + `Format(wchar_t*,...)` | `0x1c530-0x1c9f0` | Append/数字格式化（int64 283B、double 662B）/`vswprintf` |

## 2. zWSharedString（引用计数宽串，6 B/8 B 对象）

| 偏移 | 类型 | 含义 |
|---|---|---|
| +0x00 | vftable | 虚析构 |
| +0x04 | `zSharedStrBuffer*` | 引用计数缓冲（对象本体 16 B，`operator new` 分配） |

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(wchar_t*, uint)` | `0x1d10` | `new zSharedStrBuffer(p,n)` + `AddRef` |
| `ctor(zSharedStrBuffer*)` / 拷贝 ctor | `0x1db0/0x1df0` | AddRef（非空时） |
| `~` | `0x1e30` | `Release`（非空时） |
| `GetLenght()` | `0x1e90` | 委托缓冲对象（空→0） |
| `operator wchar_t const*` / `GetString` | `0x1ec0`（同址双名） | 委托缓冲对象（空→NULL） |

- 引用计数复用 `zSharedBuffer<unsigned char>::AddRef/Release`（与 `zSharedStrBuffer` 共享 ILT）。
- 全族"delegation"模式：字符串数据与长度都在缓冲对象里，本类只有 vptr+buffer 两个字段。

## 3. zWstrArray（宽字符串数组，虚表 3 槽：dtor/Add/Insert/SetAt）

- 基类 `zTypedPtrArray<wchar_t>`（= `zArrayBase<char*>` 特化）：+0x04 data(char**)、+0x08 count；默认构造参数 `0x40`（初始容量/增长步长，zArrayBase 批次 0.7 复核）。
- 元素 = 独立 `zrt_new(2*(n+1))` 分配的宽串副本（**不是** `zStringTemplate`）。析构基类逐个释放。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor()` | `0x29c0` | 基类(0x40)+vftable |
| `ctor(wchar_t*, wchar_t delim)` | `0x29f0` | 按 delim 切分并 Add 每段（空段规则见伪代码 L825-839） |
| `Clone(wchar_t*)`（私有） | `0x2950` | `zrt_new(2*(wcslen+1))`+memcpy+NUL |
| `Append(p, n)` | `0x2b40` | 定长拷贝 n 字符（不查 NULL） |
| `Add(p)`（虚） | `0x2bb0` | wcslen→clone→`zArrayBase<char*>::Add`；返回索引 |
| `Insert(i,p)`（虚） / `SetAt(i,p)`（虚） | `0x2c30/0x2cb0` | SetAt：`i<count` 才有效，旧值经 **`FUN_10028e01`**（疑 operator delete 包装，Q3）释放，再 Clone |
| `Reset(i,p)` | `0x2d20` | 同 SetAt 但用**裸 `free`**（Q3 混用）且无返回值 |
| `Load(wchar_t*)` | `0x2d80` | 构造临时 `zwstr`，循环 `Find(L'\t')`→`Mid` 取段→**虚槽 1 = Add**；**Q4：末段（无尾随 \t）观察不到 Add，需复核** |
| `operator[]/GetAt(i)` | `0x2e80`（同址双名） | 委托 `zArrayBase<char*>::GetAt` |
| `~` / 移动 ctor | `0x2ef0/0x2f10` | 基类析构 / 基类移动 |

## 4. zWstrList（`zSection` 锁 + 侵入式双向链表）

**布局**：+0x00 `zSection` 基类（vftable；Enter/Leave 临界区）· +0x08 head 节点 · +0x0C tail 节点 · +0x10 count · +0x14 内嵌**哨兵 zwstr**（12 B，GetHead/GetNext/GetAt 在 `pos==NULL` 时返回它）。
**节点** = `operator_new(0x14)`：+0x00..+0x0B = `zwstr` 本体（节点指针==zwstr 引用，`__zPos*` 即节点首址）· +0x0C next · +0x10 prev。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor()` / 拷贝 ctor / `op=` | `0x1dae0/0x30a0/0x3140` | 锁-init、清零、哨兵构造；拷贝逐节点 |
| `~` | `0x1db60` | RemoveAll + 哨兵析构 + zSection 析构 |
| `AddHead/AddTail(wchar_t*)` | `0x1de70/0x1df40` | `Enter`锁 → `new` 节点 + `FUN_1001c230`(zwstr(wchar_t*)) → 头/尾链接 → count++ → `Leave`；返回节点 |
| `RemoveHead/RemoveTail` | `0x1dc80/0x1dda0` | 199 B；解链+释放+count--（返回值见伪代码） |
| `GetHead/GetTail` ×2 | `0x1dbc0-0x1dc50` | 空表→哨兵；返回 `zwstr&` |
| `GetNext/GetPrev(__zPos*&)` | `0x1e090/0x1e0d0` | 返回当前节点 zwstr；`*pos = node->next/prev`；pos==NULL→哨兵（不前进） |
| `GetAt(__zPos*)` | `0x1e110` | `pos==NULL→哨兵`，否则返回 pos |
| `SetAt(__zPos*, wchar_t*)` | `0x1e140` | 临时 `zwstr(p)` → `operator=` 覆写节点字符串（**无锁**，Q5） |
| `RemoveAt(__zPos*)` | `0x1e1c0` | 解链+释放+count-- |
| `InsertBefore/After(__zPos*, wchar_t*)` | `0x1e280/0x1e380` | 锁内插入新节点 |
| `RemoveAll()` | `0x1e010` | 全清（析构用） |
| `Find(wchar_t*, __zPos*)` | `0x1e480` | 从 head 起 `zStringTemplate::Compare`；**Q6：起始位置参数被忽略**（恒从表头扫） |
| `FindIndex(uint)` | `0x1e4c0` | 第 i 个（0 基）；越界→NULL |

## 5. zStringItem / zStringList（装载列表的不可变字符串结点）

**zStringItem（0x18 B）**：+0x00 vftable · +0x04/+0x08/+0x0C `zItem` 基类字段（+0x0C = 所属链表指针，析构时若非空调 `zList<zDataItem>::Detach` 自摘）· +0x10 `char* buf` · +0x14 `int len`（**无 cap，不可增长**）。

| 函数 | 入口 | 规格 |
|---|---|---|
| `ctor(char*, int n)` | `0x17ac0` | `n<0→strlen`；**CRT `malloc(n+1)`**（区别于 zStringTemplate 的 operator new）；memcpy+NUL |
| `ctor(std::string const&)` | `0x17b70` | 同上，长度取 std::string |
| `~` | `0x17bf0` | `free(buf)` + `~zItem`（自摘链） |
| `zStringList::Add(char*,n)` | `0x1a210` | `new(0x18)` + ctor → `zList<zDataItem>::Append`；返回结点 |
| `zStringList::Add(std::string const&)` | `0x1a1e0` | 转发 |
| `zStringList ctors/dtors` | `0x17e50/0x17e70/0x17f20` | = `zList<zDataItem>` 转发 |
| `zItem<zStringItem>` / `zList<zStringItem>` 模板实例 | `0x17c30-0x1a0c0` 内 6 个 | 基类构造/析构/移动（模板语义） |

## 6. 怪癖 / 待复核（Q1–Q6 → RE-UNKNOWNS 候选）

- **Q1** `zstr(wchar_t*)` / `op=(wchar_t*)`：截断式转换（仅适合 ASCII 范围）+ 手写字段 cap=len（不合"cap=len+1"不变量）。
- **Q2** `zwstr(char*)`：转换结果长度 ≤1 时不 SetString（单字符 ANSI 串丢失）。
- **Q3** `zWstrArray` 释放混用：SetAt 用 `FUN_10028e01`（疑 operator delete），Reset 用裸 `free`。
- **Q4** `zWstrArray::Load`：无尾随 \t 的末段观察不到 Add（反编译折叠 or 真实行为）。
- **Q5** `zWstrList::SetAt` 未加锁（对比 AddHead/Insert 都 Enter/Leave）。
- **Q6** `zWstrList::Find` 忽略起始位置参数。

## 7. 待命名（下一批回写 Ghidra 候选）

| 地址 | 暂判身份 | 依据 |
|---|---|---|
| `0x28e01` | `zrt_delete`（operator delete 包装） | `zWstrArray::SetAt` 中与 zrt_new 配对（0x2cb0） |
| `0xa130` | `std::string::length`（跨 char/wchar 实例） | `zwstr(std::wstring)`/`zStringList::Add(std::string)` 中取长度 |
| `0x1c230` | `zWstrList` 节点字符串构造（zwstr(wchar_t*) + 链接初始化前体） | AddHead/AddTail `operator_new(0x14)` 后调用 |
| `0x10028f64` | 已名 `zrt_new`（上批） | — |
| FID 误标 | 伪代码中 `sqDatabase::operator_struct_sqlite3_` 实为 `zStringTemplate<wchar_t>::operator wchar_t const*`；`zMemory::operator_unsigned_char_` 实为 `zSharedBuffer<T>::operator T*`；`FID_conflict_c_str` = `std::string::c_str` | 与 zStringTemplate 规格第 3 节互证 |
