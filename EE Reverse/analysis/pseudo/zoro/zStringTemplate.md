# zStringTemplate&lt;T, string_manager&gt; — 反编译规格（阶段 2 · 第一批）

- 模块：zoro.dll（`0x10000000` 基址；本文内 RVA 即 `entry=1000xxxx` 去掉 `100`）
- 函数：117 个入口（`<char,ansi_string_manager>` 61 + `<wchar_t,unicode_string_manager>` 56，含 2 个
  `default_constructor_closure` 与共享 ILT thunk）
- 伪代码（原样）：`analysis/pseudo/zoro/zStringTemplate.decomp.txt`（3,786 行，117/117 dumped）
- 类型头：`analysis/types/zStringTemplate.h`
- 台账状态：117/117 → `decompiled`（`ledger/status-overrides.csv`，evidence 列有伪代码路径）
- 相关：L2 曾未解的 5 条 local-static 中 2 条（zoro ord 1410/1411 `?nul_char@?1??GetString...`）
  就是本类的 `GetString` 空指针回退静态量（RVA `0x44d54`/`0x44d56`）

## 1. 字段布局（两个实例化布局相同，均 12 字节）

| 偏移 | 类型 | 含义 | 证据（entry） |
|---|---|---|---|
| +0x00 | `T* m_data` | 堆缓冲指针（可为 NULL：Transfer/move 后） | `GetString 0x7a40/0x9180`、`SetString 0x7c90/0x93e0` |
| +0x04 | `uint m_len` | 长度，**字符数**（wchar 时字节数=2×） | `wchar Append 0x91a0`：`memcpy(data + len*2, p, n<<1)`，`len += n` |
| +0x08 | `uint m_cap` | 容量，**字符数（含结尾 NUL）** | `check_memory 0x8640`：`cap<=n+1 → cap=n+1+extra`；wchar 版 `0x9d60` 分配 `cap<<1` 字节 |

- 分配 = `zrt_new`（= `operator new` 包装，`0x28f64`）；释放 = CRT `free`（对 new 内存调 free —— 原样记录）；
  增长用 CRT `realloc`（`check_memory`）。
- `zBuffer` 与本类布局相同：dtor/Transfer/GetBufferSize/IsEmpty 的 ILT 同时标注两者
  （`0x8380` dtor / `0x8310` Transfer / `0x7400` / `0x74e0` —— 链接器折叠了同字节代码）。

## 2. 不变量（所有写路径成立）

1. `m_data != NULL` 时，恒有 `m_data[m_len] == 0`（每个写路径结尾都补 NUL）。
2. 空串：`m_len==0, m_cap>=1`，且**已分配**缓冲（char 1 字节 / wchar 2 字节），`data[0]=0`。
3. `GetString()` 在 `m_data==NULL` 时返回 local-static `nul_char`（char 版 `0x44d56`、wchar 版 `0x44d54`），
   不抛错 —— 这是 move 后的安全回退。
4. `m_cap` 是"含 NUL 的字符容量"：`GetBufferSize() = cap<2 ? 0 : cap-1`（`0x7400`）。

## 3. 行为规格（按函数组；入口为 char 版 RVA，wchar 版为括号内）

| 函数 | 入口 | 规格 |
|---|---|---|
| `zStringTemplate(char const*)` | `0x84d0` (`0x8990`←wchar 同名对应) | `p==NULL → len=0`；cap=len+1；分配；拷 len；补 NUL |
| `zStringTemplate(char const*, int n)` | `0x8430` | `n<0 → n=strlen(p)`；cap=n+1；分配；**若 p==NULL 则 len 复位 0**（怪癖 Q3）；补 NUL |
| `zStringTemplate(int n)` | `0x85e0` | `len=0; cap=n+1`；分配；`data[0]=0`（预留缓冲构造） |
| `zStringTemplate(char&)` | `0x8570` | 单字符串：len=1, cap=2 |
| 拷贝/移动构造 | `0x83f0` / `0x83b0` | 拷贝=CopyFrom；移动=置零+Transfer |
| `~zStringTemplate` | `0x8380` | `free(m_data)`（不置零字段） |
| `operator=`(串/char/char*/std::string) | `0x70a0/0x70c0/0x70e0/0x7100` | → CopyFrom / SetString / SetString(-1) / SetString(c_str,len) |
| `SetString(p, n)` | `0x7c90` (`0x93e0`) | `n<0→strlen`；free 旧；len=n；`n==0 → cap=1,分配,data[0]=0`；否则 cap=n+1，分配+拷贝+NUL |
| `CopyFrom(s)` | `0x8270` | free 旧；len=s.len；cap=len+1；分配；memcpy；NUL（深拷贝） |
| `Transfer(s)` | `0x8310` | free 旧；窃取三字段；源置零（平移语义） |
| `Append(p, n)` | `0x7a60` (`0x91a0`) | 数据空→SetString；否则 `check_memory(len+n, 0xFF)`；memcpy 于 `data+len`；len+=n；NUL。增长留 0xFF 松弛 |
| `Insert(pos, p)` | `0x7b30` (`0x9270`) | `pos<=len` 才做；n=strlen(p)；`check_memory(len+n,0xFF)`；memmove（含 NUL）后 memcpy；返回新 len |
| `InsertChar(pos, &c)` | `0x7be0` | 同上单字符；`pos<=len` |
| `Remove(pos, n)` | `0x8190` | `[pos,pos+n)` 左移覆盖（前向逐字节），len 调整，补 NUL |
| `Empty()` | `0x7c70` | = `SetString(NULL, 0)` |
| `SetLenght(n)` | `0x7f40` | `check_memory(n,0)`；`data[n]=0`；`len=strlen(data)`（用于截断/延长后重算） |
| `ReleaseBuffer(n)` | `0x7390` | `n<0→len=strlen`；else len=n；`data[len]=0` |
| `GetBuffer(n)` | `0x73e0` | `check_memory(n,0)`；返回 data |
| `GetBufferSize` / `GetString` / `operator char const*` | `0x7400/0x7a40/0x7a20` | 见不变量；`GetString`=NUL 安全回退 |
| `GetAt(i)/GetLast/operator[]` | `0x7480/0x74b0/0x7130` | 越界 GetAt→0；`operator[]` 无检查返回引用 |
| `SetAt(i,c)` | `0x7430` (`0x8ba0`) | `i<len` 才写；**怪癖 Q1** |
| `Compare(p)/CompareNoCase(p)` | `0x7270/0x7230` | 经 `zrt_strcmp 0x1600` / `zrt_stricmp 0x1680`；NULL 参按空串 |
| `operator==`(`char`/`char*`) / `operator!=` | `0x6fd0/0x7020/0x6f60` | 长度先比，`memcmp` 定值；NULL 语义见伪代码 |
| `Find(p,pos)/Find(c,pos)` | `0x7f80/0x7ff0` | `zrt_strstr 0x16b0` / `zrt_strchr 0x16e0`；未找到 -1；`pos>len→-1` |
| `ReverseFind(c,pos)` | `0x8210` | `pos<0→从 len-1` 反向线性扫描 |
| `Replace(a,b)/Replace(c1,c2)` | `0x7d70/0x7ed0` | 串版：循环 Find→按需 `realloc`→memmove/memcpy→续扫；字符版计数替换 |
| `MakeLower/MakeUpper` | `0x72b0/0x7320` | 仅 ASCII `A-Z`↔`a-z` |
| `ProcessEscapeCharacter` | `0x8060` | 就地解析 `\n \r \t \\x`；压缩后 `len=写指针`，若变短补 NUL |
| `Trim()/TrimRight()/TrimLeft()`（返回新串） | `0x7510/0x75b0/0x76c0` | **怪癖 Q2**：只去 1 个空格 |
| `trim()/trim_right()/trim_left()`（就地） | `0x7620/0x7640/0x77f0` | 正确多空格语义：`trim=trim_right→trim_left`；`trim_left` 用 memmove 左移 |
| `RightCount/LeftCount(c)` | `0x7730/0x7790` | 返回 0/1（只判断首/尾字符是否等于 c，**不是计数**） |
| `Mid(pos,n)/Left(n)/Right(n)` | `0x7880/0x7960/0x7900` | 返回新串；越界自动截断；`Mid.pos>=len→空串` |
| `check_memory(n, extra)`(protected) | `0x8640` (`0x9d60`) | `cap<=n+1 → cap=n+1+extra; realloc(cap [×2 wchar])` |

## 4. 怪癖 / 待差分验证（进 RE-UNKNOWNS 候选）

- **Q1 `SetAt(i, 0)`**：写 NUL 后把 `+0x04` 置 **1**（`0x7430`/`0x8ba0`）。与"截断到 i"语义不符，
  属真实代码行为还是反编译误读，留待 L4 差分测试确认。
- **Q2 `Trim*`（返回值版）只去 1 个空格**：`Trim` 依赖 `LeftCount/RightCount`（0/1 型），
  与就地 `trim()` 的多空格语义不一致（`0x7510` vs `0x7620`）。调用方若依赖此行为需注意。
- **Q3 `ctor(p=NULL, n>0)`**：len 先设 n 后复位 0（`0x8430`），即空串但 cap=n+1。
- **Q4 分配/释放混用**：`zrt_new`(operator new) 分配 + `free` 释放 + `realloc` 增长（见 §1）。

## 5. 依赖的 zoro runtime 助手（已回写 Ghidra 名称，`analysis/renames/zoro.csv`）

| RVA | 新名 | 身份（证据 `analysis/pseudo/zoro/zrt-helpers.decomp.txt`） |
|---|---|---|
| 0x15b0 | `zrt_strlenA` | strlen，NULL→0（自写循环） |
| 0x1600 | `zrt_strcmp` | strcmp 包装，NULL→`DAT_10044019`("")，返回 -1/0/1 |
| 0x1680 | `zrt_stricmp` | `_stricmp` 包装，NULL→`DAT_10044018`("") |
| 0x16b0 | `zrt_strstr` | `strstr` 包装（NULL 检查） |
| 0x16e0 | `zrt_strchr` | `strchr` 包装（NULL/c==0→NULL） |
| 0x1710 | `zrt_wcslen` | `lstrlenW` 包装（NULL→0） |
| 0x28f64 | `zrt_new` | `operator new` 薄包装（9 字节） |

## 6. 下一步（本类收尾项）

- [ ] L4 差分：`tools/verify/test_zStringTemplate.py`（活进程不可用此类——zoro 非导出到 Frida 的手段
      需另想；替代：用 Ghidra 仿真或写等价 C++ 单元测试对拍 Q1–Q3）
- [ ] 在 Ghidra 建结构体 `zStringTemplate_layout`（12 字节）并应用到实例 → 改善后续类反编译
- [ ] 调用方普查：eslib/Editer 导入面里谁在用它（阶段 5 汇总时做）
