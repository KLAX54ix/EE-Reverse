// analysis/types/zserial.h
// 序列化栈（zStream / zBaseBuffer / zMemory / zArchive / zFile / zFileSerializer）
// — 阶段 2 第三批（zoro.dll）
//
// 证据：
//   [ev:pseudo] analysis/pseudo/zoro/zserial.decomp.txt   (105/105 函数原样伪代码)
//   [ev:spec]   analysis/pseudo/zoro/zserial.md           (行为规格 Q1–Q6 + S4 格式)
//   [ev:ledger] ledger/ledger.csv  zoro:1e7e0..  status=decompiled
#pragma once

namespace zoro {

// ============================================================
// zStream — 前端抽象流（写/读原语全部动态派发到 vtbl+8/+0xC）
// [ev:pseudo WriteByte 0xc170; ctor 0xbf70; IsStoring 0xbfc0]
class zStream {
    /* +0x00 */ void* m_vftable;  // [8]=WriteRaw(void*,ulong) [0xC]=ReadRaw(void*,ulong)
    /* +0x04 */ int   m_mode;     // 0=storing(写)  !=0=loading(读)
public:
    zStream(int mode);                                   // 0xbf70
    virtual ~zStream();
    int  IsStoring() const;                              // 0xbfc0 (mode==0)
    // 原语（全部单次虚调用）：
    int  WriteByte(unsigned char);                       // 0xc170  (=WriteChar(char) 同址)
    int  WriteChar(wchar_t);                             // 0xc190  (=Int16/Short/Word 同址, 2B)
    int  WriteDWord(unsigned long);                      // 0xc1d0  (=Int32/Float 同址, 4B)
    int  WriteDouble(double);                            // 0xc210  (=Int64 同址, 8B)
    int  WriteText(char const*, int n);                  // 0xc1f0  n<0→strlen, 字节
    int  WriteText(wchar_t const*, int n);               // 0xc250  n<0→wcslen, n*2 字节
    int  EndLine(int wide);                              // 0xc290  wide→L"\r\n"(4B) 否则 "\r\n"(2B)
    int  WriteStringLength(unsigned n, int wide);        // 0xc880  变长编码（见 spec §2）
    int  ReadStringLength(unsigned& n, int& wide);       // 0xc930
    // 原始读写（实现类提供）：
    virtual long WriteRaw(void const*, unsigned long) = 0;   // vtbl+0x08
    virtual long ReadRaw(void* , unsigned long) = 0;         // vtbl+0x0C
    // operator<<(zMemory&) 0xc9e0 / operator>>(zMemory&) 0xca30（自由函数族）
};

// ============================================================
// zBaseBuffer — 后端存储抽象（vtable 布局与 zStream 不同！）
// [ev:pseudo zArchive::Write 0xcb90 经 +8→vtbl+0x14; zFile 0x17050]
class zBaseBuffer {
    /* +0x00 */ void*  m_vftable;   // [+4]GetBufferSize [+8]GetPosition [+0xC]Seek [+0x10]Read [+0x14]Write
public:
    virtual ~zBaseBuffer();
    virtual unsigned GetBufferSize() const;                   // vtbl+0x04
    virtual long     GetPosition() const;                     // vtbl+0x08
    virtual int      Seek(long off, int whence);              // vtbl+0x0C (z_seek 0/1/2)
    virtual int      Read(void*, unsigned);                   // vtbl+0x10
    virtual int      Write(void const*, unsigned);            // vtbl+0x14
};

// ============================================================
// zMemory — 引用计数字节缓冲 + 游标（zBaseBuffer 实现；与 zSharedMemory 共实现）
// [ev:pseudo ctor 0x1e7e0; Write 0x1f070; Serialize 0x1f260]
class zMemory : public zBaseMemory /* : zBaseBuffer */ {
    /* +0x04 */ unsigned m_step;      // 增长步长（ctor 参数；default_ctor_closure=0x100）
    /* +0x08 */ unsigned char* m_data; // realloc/zrt_new 系；free 释放
    /* +0x0C */ unsigned m_size;      // 逻辑长度
    /* +0x10 */ unsigned m_cap;       // 已分配容量（≥size；增长=need+m_step）
    /* +0x14 */ unsigned m_pos;       // 游标
    /* +0x18 */ int      m_refs;      // AddRef 0x1eaf0 / Release 0x1eb10 → vtal[0](1) 自毁
public:
    zMemory(unsigned step);                              // 0x1e7e0
    zMemory(unsigned char*, unsigned size, unsigned step); // 0x1e860 接管指针(不拷贝)
    zMemory(tagBYTEDATA&, unsigned step);                // 0x1e8d0
    zMemory(zMemory const&);                             // 0x1e950 copy: step=0x100+CopyFrom
    zMemory(zMemory&&);                                  // 0x1ea00 move
    virtual ~zMemory();                                  // 0x1eab0
    void AddRef(); void Release();                       // 0x1eaf0 / 0x1eb10
    void Zero(); void Clear();                           // 0x1eb70 / 0x1eba0
    int  IsEqual(zMemory const&) const;                  // 0x1ebf0
    long Realloc(unsigned n);                            // 0x1ec60  n>cap→realloc；size=n
    int  Insert(unsigned pos, void*, unsigned n);        // 0x1ecc0  拒绝自身缓冲内源(Q6)
    virtual int Read(void*, unsigned);                   // 0x1ede0  越界→0
    int  Attach(unsigned char*, unsigned);               // 0x1ee40  free 旧数据后接管
    void CopyFrom(zMemory const&);                       // 0x1eea0
    void CopyFrom(void*, unsigned);                      // 0x1eed0  cap 不足用 zrt_new
    void TransferFrom(zMemory*);                         // 0x1ef70  Clear+窃取
    unsigned char* AllocWrite(unsigned n);               // 0x1efc0
    virtual int Write(void const*, unsigned);            // 0x1f070
    virtual int Seek(long, z_seek);                      // 0x1f130  seek-end=size-off(Q4)
    unsigned char* GetBuffer(unsigned n);                // 0x1f1b0  顺带 size=n(Q3)
    unsigned char* Detach();                             // 0x1f210
    void Serialize(zArchive&);                           // 0x1f260  格式见 spec §6
    void SetSize(unsigned n);                            // 0x1f390  扩→补零；缩→clamp 游标
    // 低簇封闭实现（ILT 折叠群）：
    operator unsigned char*() const;                     // 0x5b40 (=Lock/GetData 同址) → m_data
    unsigned char& operator[](int i);                    // 0xabb0  m_data[i] 无检查
    long Unlock();                                       // 0xabd0  → 1
    long GetPosition() const;                            // 0xabe0  → m_pos
};

// ============================================================
// zArchive — zStream 前端 + 任意 zBaseBuffer 后端适配器
// [ev:pseudo ctor 0xca80; Write 0xcb90; Close 0xcb70]
class zArchive : public zStream {
    /* +0x08 */ zBaseBuffer* m_buffer;
    /* +0x0C */ int         m_pad0c;   // ctor 置 0（用途待查）
public:
    zArchive(zBaseBuffer*, int mode, int rewind);        // 0xca80  rewind→buffer->Seek(0,0)
    virtual ~zArchive();                                 // 0xcb20
    void Close();                                        // 0xcb70  仅解绑，不关后端(Q5)
    virtual long Write(void const*, unsigned long);      // 0xcb90  委托 +0x14；成功=n
    virtual long Read(void*, unsigned long);             // 0xcbe0  委托 +0x10；成功=n
    int  Seek(long, z_seek);                             // 0xcc30  委托 +0xC（非虚 QAE）
    long GetPosition() const;                            // 0xcc70  委托 +0x8
    unsigned GetBufferSize() const;                      // 0xc580  委托 +0x4
    zBaseBuffer* GetBufferObj() const;                   // 同址别名 → +0x08
};

// ============================================================
// zFile — Win32 文件（zBaseBuffer 实现）
// [ev:pseudo ctor 0x17050/0x17090; Open 0x17110 (CreateFileW)]
class zFile : public zBaseBuffer {
    /* +0x04 */ void* m_hFile;   // 初始/关闭后 = 0xFFFFFFFF(-1)
    /* +0x08 */ int   m_dirty;   // 写成功置 1
public:
    zFile();                                             // 0x17050
    zFile(wchar_t const*, int openFlags);                // 0x17090 → Open
    virtual ~zFile();                                    // 0xafb0
    zFile& operator=(zFile const&);                      // 0xb040  拷贝 +4/+8
    int  Open(wchar_t const*, int openFlags);            // 0x17110  flags: 0=读/1=写(创建)/2=读写
    int  Close();                                        // 0x17360  CloseHandle→-1
    virtual int Read(void*, unsigned);                   // 0x171e0  p==NULL||h==0→-1(Q2)
    virtual int Write(void const*, unsigned);            // 0x17240  h==0→0；成功置 dirty
    int  WriteStr(char const*);                          // 0x172a0  strlen+虚 Write
    int  WriteWStr(wchar_t const*);                      // 0x17300  wcslen→UTF-8(栈 4KB)→虚 Write
    int  WriteAsUTF8(wchar_t const*, unsigned n);        // 0x17410  n==0→slen；堆转换
    virtual unsigned GetBufferSize() const;              // 0x174f0  GetFileSize
    virtual long GetPosition() const;                    // 0x17520  SetFilePointer(0,0,1)
    virtual int Seek(long, z_seek);                      // 0x17560  0/1/2→0/1/2
    void SetFileSize(long);                              // 0x175e0  Seek(size,0)+SetEndOfFile
    int  FlushFileBuffers_();                            // 0x17660  直通 Win32
};

// ============================================================
// zFileSerializer — zStream 前端 + 内嵌 zFile 后端 + 写缓冲
// [ev:pseudo ctor 0xcd40; Write 0xcfc0; Flush 0xcf20; Open 0xce90]
class zFileSerializer : public zStream {
    /* +0x08 */ zFile  m_file;        // 12B 内嵌（vptr,hFile,flags）
    /* +0x14 */ unsigned m_pending;   // 未刷字节数
    /* +0x18 */ unsigned m_totalLo;   // 累计已写 64 位（+0x1C=hi）
    /* +0x1C */ unsigned m_totalHi;
    /* +0x20 */ unsigned m_bufSize;
    /* +0x24 */ unsigned char* m_buf; // zrt_new ≥0x400；free 释放
public:
    zFileSerializer(int mode);                           // 0xcca0
    zFileSerializer(wchar_t const*, int mode, unsigned bufSize); // 0xcd40
    virtual ~zFileSerializer();                          // 0xcdf0
    int  Open(wchar_t const*, unsigned bufSize);         // 0xce90  buf<0x400→0x400；mode==0→写
    void Close();                                        // 0xcf60  写模式先 Flush
    void Flush();                                        // 0xcf20  内嵌 zFile::Write(buf,pending)
    virtual long Write(void const*, unsigned long);      // 0xcfc0  仅写模式；返回值恒 0(Q1)
    virtual long Read(void*, unsigned long);             // 0xd0b0  仅读模式；成功=n
    int  Seek(long, z_seek);                             // 0xd100  先 Flush
    long GetPosition() const;                            // 0xd130  zFile 位 + pending
};

} // namespace zoro
