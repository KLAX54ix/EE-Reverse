// analysis/types/zstr-legacy.h
// 遗留字符串族布局 — 阶段 2 第二批（zoro.dll）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/zoro/zstr-legacy.decomp.txt   (88/88 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/zoro/zstr-legacy.md           (行为规格 Q1–Q6)
//   [ev:ledger] ledger/ledger.csv  zoro:23xx..  status=decompiled
#pragma once

namespace zoro {

// ============================================================
// zstr / zwstr — zStringTemplate 薄子类（12B 继承布局不变）
// [ev:pseudo zstr ctor 0x23a0-0x2420, zwstr ctor 0x1fa0-0x20a0]
class zstr : public zStringTemplate<char, ansi_string_manager> {
public:
    // 自有：ctor(int)→Format("%d") 0x2330；ctor(wchar_t*)→截断转换+cap=len(Q1) 0x2420；
    // op=(wchar_t*) 0x2540（同 Q1）；operator<< ×4 0x1caa0..；Format 0x1cba0；~ 0x22d0
};
class zwstr : public zStringTemplate<wchar_t, unicode_string_manager> {
public:
    // 自有：ctor(char*)→zEncoder::AnsiToUnicode（len<=1 时保持空串 Q2）0x20a0；
    // Enum 0x2180；CompareFromFirst 0x2210；operator<< ×4 0x1c530..；
    // MakeFrom(__int64/double) 0x1c630/0x1c750；Format 0x1c9f0；op= 0x22f0
};

// ============================================================
// zWSharedString — 引用计数宽串（8B；缓冲对象 16B，operator new 分配）
// [ev:pseudo ctor 0x1d10 / AddRef; dtor 0x1e30 / Release]
class zWSharedString {
    /* +0x00 */ void* m_vftable;
    /* +0x04 */ zSharedStrBuffer* m_buffer;  // AddRef/Release 于 ctor/dtor；可为 NULL
public:
    unsigned GetLenght() const;              // 0x1e90 委托缓冲
    operator wchar_t const*() const;         // 0x1ec0 (= GetString, 同址双名)
};

// ============================================================
// zWstrArray — 宽串数组；基类 zTypedPtrArray<wchar_t>（= zArrayBase<char*> 特化）
// [ev:pseudo 0x29c0 基类 ctor 参数 0x40；GetAt 0x2e80 走 zArrayBase<char*>::GetAt]
class zWstrArray : public zTypedPtrArray<wchar_t> {
    // 基类字段：+0x04 char** m_data; +0x08 uint m_count;
public:
    zWstrArray();                                      // 0x29c0
    zWstrArray(wchar_t const*, wchar_t delim);         // 0x29f0 按 delim 切分
    virtual unsigned Add(wchar_t const*);              // 0x2bb0 vtbl[1]（Load 走虚调用）
    void  Append(wchar_t const*, int n);               // 0x2b40 不查 NULL，无截断
    virtual void Insert(unsigned, wchar_t const*);     // 0x2c30
    virtual int  SetAt(unsigned, wchar_t const*);      // 0x2cb0 旧值经 FUN_10028e01 释放(Q3)
    void  Reset(unsigned, wchar_t const*);             // 0x2d20 旧值经裸 free 释放(Q3)
    void  Load(wchar_t const*);                        // 0x2d80 按 L'\t' 切分（末段行为见 Q4）
    wchar_t const* operator[](int) const;              // 0x2e80 (=GetAt)
private:
    wchar_t* Clone(wchar_t const*);                    // 0x2950 zrt_new(2*(n+1))
};

// ============================================================
// zWstrList — zSection 临界区 + 侵入式双向链表（节点 20B = zwstr(12)+next(4)+prev(4)）
// [ev:pseudo ctor 0x1dae0; AddHead 0x1de70 Enter/Leave; GetNext 0x1e090 +0xC 链]
class zWstrList : public zSection {
    /* +0x08 */ void* m_head;      // 节点（__zPos* = 节点首址 = 其内 zwstr 引用）
    /* +0x0C */ void* m_tail;
    /* +0x10 */ unsigned m_count;
    /* +0x14 */ zwstr m_dummy;     // 12B 哨兵：pos==NULL 时各 Get* 的返回目标
public:
    zWstrList();
    ~zWstrList();
    zwstr& AddHead(wchar_t const*);                    // 0x1de70 返回节点引用(实现为 __zPos*)
    zwstr& AddTail(wchar_t const*);                    // 0x1df40
    int   RemoveHead(); int RemoveTail();              // 0x1dc80/0x1dda0
    zwstr& GetHead(); zwstr& GetTail();                // 0x1dbc0..（各 2 个重载）
    zwstr& GetNext(void*& pos); zwstr& GetPrev(void*&); // 0x1e090/0x1e0d0
    zwstr& GetAt(void* pos);                           // 0x1e110
    void  SetAt(void* pos, wchar_t const*);            // 0x1e140（无锁 Q5）
    void  RemoveAt(void* pos);                         // 0x1e1c0
    zwstr& InsertBefore(void* pos, wchar_t const*);    // 0x1e280
    zwstr& InsertAfter(void* pos, wchar_t const*);     // 0x1e380
    void  RemoveAll();                                 // 0x1e010
    void* Find(wchar_t const*, void* start) const;     // 0x1e480 恒从 head（start 忽略 Q6）
    void* FindIndex(unsigned) const;                   // 0x1e4c0
};

// ============================================================
// zStringItem — 不可变字符串结点（0x18B）；CRT malloc（区别于 zStringTemplate）
// [ev:pseudo ctor 0x17ac0 malloc(n+1); dtor 0x17bf0 free]
class zStringItem : public zItem<zStringItem> {
    /* +0x10 */ char* m_buf;   // malloc(n+1)，恒 NUL 结尾
    /* +0x14 */ int   m_len;   // 无 cap（不可增长）
public:
    zStringItem(char const*, int n);            // 0x17ac0 n<0→strlen
    zStringItem(std::string const&);            // 0x17b70
    virtual ~zStringItem();                     // 0x17bf0 free + zItem 自摘链
};
// zStringList = zList<zDataItem> 实例 + Add 工厂 [ev:pseudo 0x1a210 operator_new(0x18)+Append]
class zStringList : public zList<zDataItem> {
public:
    zStringItem* Add(char const*, int);         // 0x1a210
    zStringItem* Add(std::string const&);       // 0x1a1e0
};

// zItem<zStringItem> 基类字段（自模板实例推得）：
//   +0x00 vftable; +0x04, +0x08 保留(0); +0x0C void* owner_list;（析构时非空→Detach 自摘）

} // namespace zoro
