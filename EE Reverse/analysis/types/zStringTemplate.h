// analysis/types/zStringTemplate.h
// 类布局与行为规格 — 阶段 2 第一批（zoro.dll）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/zoro/zStringTemplate.decomp.txt   (117/117 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/zoro/zStringTemplate.md           (行为规格表)
//   [ev:helpers] analysis/pseudo/zoro/zrt-helpers.decomp.txt      (zrt_* 助手身份)
//   [ev:ledger] ledger/ledger.csv id=zoro:<rva>  status=decompiled (status-overrides.csv 117 行)
//
// 两个实例化（<char,ansi_string_manager> / <wchar_t,unicode_string_manager>）布局相同：
// 12 字节，三字段。与 zBuffer 同布局（ILT 折叠：dtor 0x8380 / Transfer 0x8310 / 0x7400 / 0x74e0）。
#pragma once

namespace zoro {

template <class T /* char | wchar_t */, class string_manager>
class zStringTemplate {
public:
    T*        m_data;   // +0x00  堆缓冲；NULL 仅出现在 Transfer/move 之后的源对象
                        //        [ev:pseudo GetString 0x7a40, SetString 0x7c90]
    unsigned  m_len;    // +0x04  长度（字符数！wchar 时字节数=2*m_len）
                        //        [ev:pseudo wchar Append 0x91a0: memcpy(data+len*2, p, n<<1)]
    unsigned  m_cap;    // +0x08  容量（字符数，含结尾 NUL）；wchar 实际字节数=2*m_cap
                        //        [ev:pseudo check_memory 0x8640 / 0x9d60]

    // 不变量：
    //   m_data != NULL  <=>  m_data[m_len] == 0          （所有写路径结尾补 NUL）
    //   empty: m_len==0, m_cap>=1，缓冲已分配（T 版 1 元素），data[0]==0
    //   GetString(): m_data==NULL 时返回 local-static nul_char（RVA 0x44d54/0x44d56）
    // 分配/释放（原样记录）：
    //   m_data 由 zrt_new(=operator new, 0x28f64) 或 realloc 取得；由 CRT free 释放
};

static_assert(sizeof(zStringTemplate<char,    void*>) == 12);
static_assert(sizeof(zStringTemplate<wchar_t, void*>) == 12);

} // namespace zoro

// typedef 别名（zoro 导出里直接出现的名字）：
//   zStringTemplate<char, ansi_string_manager>      — ANSI 字符串（如 ZwStringA 语义）
//   zStringTemplate<wchar_t, unicode_string_manager> — UTF-16 字符串
// 已知关联符号：
//   local-static nul_char（zoro ord 1410/1411，RVA 0x44d54/0x44d56）— GetString 的空回退量
