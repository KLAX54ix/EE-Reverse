#!/usr/bin/env python3
"""re_ledger.py - idempotent builder of the L1/L2 ledger for the EduEditer RE project.

Inputs (required, relative to workspace root):
  recon/{eslib,eulib,zoro,eglib}_exports.txt        (PE export table: ordinal, 0xRVA, mangled)
  ledger/raw/{Editer,eslib,eulib,zoro,eglib}_functions.csv  (ExportFunctions.java via Ghidra)

Inputs (optional, included in manifest when present):
  ledger/raw/{mod}_xrefs.csv      (ExportSupplement.java: entry_rva,xrefs_in,...,calls_out)
  ledger/raw/{mod}_strings.csv    (ExportSupplement.java: addr_rva,length,value_preview,refs...)
  ledger/raw/{mod}_vtables.csv    (ExportSupplement.java: vftable symbol scan)
  ledger/raw/demangled.csv        (DemangleList.java: name_mangled,ok,demangled)
  ledger/status-overrides.csv     (phase-2 progress: id,status,evidence,notes,updated;
                                   status/evidence replace, notes append; applied after build)

Outputs (all under ledger/):
  exports.csv             one row per PE export entry, with merge status
  functions.csv           consolidated Ghidra function inventory
  ledger.csv              master table (functions + standalone exports + strings + vtables),
                          spec columns: id,kind,name,demangled,owner_class,module,entry_RVA,size,
                          xrefs_in,calls_out,status,evidence,notes + extras
  unresolved-mangling.csv mangled names whose class/method could not be parsed
  manifest.json           input hashes + output hashes + stats (idempotency record)

Idempotency: re-run is a no-op (exit 0) when all input hashes match manifest and
outputs are intact, unless --force is given.

Usage:  python tools/re_ledger.py [--force]
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

MODULES = [
    {"key": "Editer", "program": "Editer.exe", "exports": None},                          # main exe
    {"key": "eslib",  "program": "eslib.dll",  "exports": "recon/eslib_exports.txt"},
    {"key": "eulib",  "program": "eulib.dll",  "exports": "recon/eulib_exports.txt"},
    {"key": "zoro",   "program": "zoro.dll",   "exports": "recon/zoro_exports.txt"},
    {"key": "eglib",  "program": "eglib.dll",  "exports": "recon/eglib_exports.txt"},
]

LEDGER_COLS = [
    "id", "kind", "name", "demangled", "owner_class", "module", "entry_RVA",
    "size", "xrefs_in", "calls_out", "status", "evidence", "notes",
    "name_mangled", "export_ordinal", "is_export", "is_thunk", "is_external",
    "param_count", "symbol_source",
]

RE_FUN_NAME = re.compile(r"^(FUN_|thunk_FUN_|LAB_|Ordinal)")

PROGRAM_TO_KEY = {m["program"]: m["key"] for m in MODULES}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_exports(path: Path):
    """Parse recon export dump: '  ordinal 0xRVA mangled_name'. Returns list of dicts."""
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            m = re.match(r"\s*(\d+)\s+(0x[0-9a-fA-F]+)\s+(\S.*?)\s*$", line)
            if not m:
                continue
            out.append({
                "ordinal": int(m.group(1)),
                "rva": int(m.group(2), 16),
                "mangled": m.group(3),
            })
    return out


def owner_from_local_static(mangled: str) -> str:
    """Extract enclosing class of a function-local static symbol (?name@?1?<enclosing>@4...).

    The Ghidra demangler returns only the local name for these; the enclosing
    function's mangled part still carries the class (member function) which is
    what the ledger needs for ownership. Best-effort structural parse.
    """
    m = re.search(r"\?1\?(.*)@4[A-Za-z0-9_@]+A$", mangled)
    if not m:
        return ""
    enc = m.group(1)
    m = re.search(r"\?\$([A-Za-z_][A-Za-z0-9_]*)", enc)
    if m:
        return m.group(1)
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)@@(?=[QIE][AIBE]E)", enc)
    return m.group(1) if m else ""


def describe_mangled(name: str):
    """Best-effort structural description of an export name (no full demangler).

    Returns dict(kind, owner, method, demangled, reason). reason != "" means the
    parse is incomplete and the entry must be triaged (unresolved-mangling.csv).
    """
    d = {"kind": "export", "owner": "", "method": "", "demangled": "", "reason": ""}
    if not name.startswith("?"):
        d["method"] = name
        d["demangled"] = name
        return d
    if name.startswith("??_7"):
        cls = name[4:].split("@")[0]
        d.update(kind="vtable", owner=cls, method="vftable",
                 demangled=("vftable for %s" % cls) if cls else "")
        if not cls:
            d["reason"] = "vtable-class-not-parsed"
        return d
    if name.startswith("??_8"):
        cls = name[4:].split("@")[0]
        d.update(kind="vbtable", owner=cls, method="vbtable",
                 demangled=("vbtable for %s" % cls) if cls else "")
        if not cls:
            d["reason"] = "vbtable-class-not-parsed"
        return d
    if name.startswith("??_R"):
        m = re.search(r"\?A[VU]?([^@]+)@", name)
        cls = m.group(1) if m else ""
        d.update(kind="rtti", owner=cls, method="rtti",
                 demangled=("RTTI type descriptor for %s" % cls) if cls else "")
        if not cls:
            d["reason"] = "rtti-class-not-parsed"
        return d
    if name.startswith("??_C@"):
        d.update(kind="string", method="string-literal")
        d["reason"] = "string-literal-not-decoded"
        return d
    if name.startswith("?$TSS"):
        m = re.search(r"\?B([^@]+)@@", name)
        cls = m.group(1) if m else ""
        if not cls:
            m2 = re.search(r"@\?\$([A-Za-z_][A-Za-z0-9_]*)", name)
            if m2:
                cls = m2.group(1)
        d.update(kind="data", owner=cls, method="tss-guard")
        if not cls:
            d["reason"] = "tss-owner-not-parsed"
        return d
    for pre, meth in (("??0", "ctor"), ("??1", "dtor")):
        if name.startswith(pre):
            if "?$" in name:
                d["reason"] = "template-not-demangled"
                return d
            cls = name[3:].split("@")[0]
            d.update(owner=cls, method=meth)
            if not cls:
                d["reason"] = "ctor-class-not-parsed"
            return d
    m = re.match(r"\?\?(_?[A-Z0-9])", name)
    if m:
        d["method"] = "special-??" + m.group(1).strip("_")
        d["reason"] = "special-code-not-demangled"
        return d
    if "@?1?" in name:
        local = name[1:].split("@")[0]
        own = owner_from_local_static(name)
        d.update(kind="data", method=local, owner=own)
        if own:
            d["demangled"] = "%s::%s [local-static]" % (own, local)
        else:
            d["reason"] = "local-static-owner-not-parsed"
        return d
    if "@@" in name:
        head, tail = name[1:].split("@@", 1)
    else:
        head, tail = name[1:], ""
    if "?" not in head:
        head_toks = [t for t in head.split("@") if t]
        if not head_toks:
            d["reason"] = "empty-tokens"
            return d
        d["method"] = head_toks[0]
        if len(head_toks) > 1 and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", head_toks[-1]):
            d["owner"] = head_toks[-1]
        if tail[:1].isdigit():
            d["kind"] = "data"
        if not d["owner"] and d["kind"] != "data" and len(head_toks) > 1:
            d["reason"] = "owner-not-identifier"
        return d
    d["reason"] = "template-not-demangled"
    return d


def parse_functions_csv(path: Path):
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        if not header or header[0] != "module":
            raise RuntimeError("unexpected header in %s: %r" % (path, header))
        for line in r:
            if len(line) < 10:
                continue
            rows.append({
                "module_program": line[0],
                "rva": int(line[1], 16),
                "name_display": line[2],
                "name_orig": line[3],
                "namespace": line[4],
                "size": int(line[5]) if line[5] else 0,
                "is_thunk": line[6] == "true",
                "is_external": line[7] == "true",
                "param_count": int(line[8]) if line[8] else 0,
                "symbol_source": line[9],
            })
    return rows


def parse_xrefs_csv(path: Path):
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for line in r:
            if len(line) < 6:
                continue
            out[int(line[1], 16)] = {
                "xrefs_in": int(line[2] or 0),
                "in_code": int(line[3] or 0),
                "in_data": int(line[4] or 0),
                "calls_out": int(line[5] or 0),
            }
    return out


def parse_strings_csv(path: Path):
    out = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for line in r:
            if len(line) < 6:
                continue
            out.append({
                "rva": int(line[1], 16),
                "length": int(line[2] or 0),
                "preview": line[3],
                "refs": int(line[4] or 0),
                "ref_rvas": line[5],
            })
    return out


def parse_vtables_csv(path: Path):
    out = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for line in r:
            if len(line) < 6:
                continue
            out.append({
                "rva": int(line[1], 16),
                "name": line[2],
                "ns": line[3],
                "entries": int(line[4] or 0),
                "funcs": line[5],
            })
    return out


def parse_overrides_csv(path: Path):
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for line in r:
            if len(line) < 2 or not line[0]:
                continue
            out[line[0]] = {
                "status": line[1].strip() if len(line) > 1 else "",
                "evidence": line[2].strip() if len(line) > 2 else "",
                "notes": line[3].strip() if len(line) > 3 else "",
            }
    return out


def parse_demangled_csv(path: Path):
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for line in r:
            if len(line) < 3:
                continue
            out[line[0]] = (line[1] == "true", line[2])
    return out


def write_csv_atomic(path: Path, cols, rows):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)
    os.replace(tmp, path)


def write_json_atomic(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=True)
        f.write("\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="rebuild even if inputs unchanged")
    ap.add_argument("--workspace", default=None)
    args = ap.parse_args()

    ws = Path(args.workspace).resolve() if args.workspace else Path(__file__).resolve().parent.parent
    ledger_dir = ws / "ledger"
    raw_dir = ledger_dir / "raw"
    ledger_dir.mkdir(exist_ok=True)

    # --- collect inputs ---
    input_paths = []
    for m in MODULES:
        if m["exports"]:
            input_paths.append(ws / m["exports"])
    for m in MODULES:
        input_paths.append(raw_dir / ("%s_functions.csv" % m["key"]))
    missing = [str(p) for p in input_paths if not p.exists()]
    if missing:
        print("re_ledger: MISSING inputs:")
        for p in missing:
            print("   " + p)
        return 2
    inputs = {str(p.relative_to(ws)).replace("\\", "/"): sha256_file(p) for p in input_paths}
    optional_paths = []
    for m in MODULES:
        for pat in ("%s_xrefs.csv", "%s_strings.csv", "%s_vtables.csv"):
            optional_paths.append(raw_dir / (pat % m["key"]))
    optional_paths.append(raw_dir / "demangled.csv")
    optional_paths.append(ledger_dir / "status-overrides.csv")
    for p in optional_paths:
        if p.exists():
            inputs[str(p.relative_to(ws)).replace("\\", "/")] = sha256_file(p)

    # --- idempotency check ---
    manifest_path = ledger_dir / "manifest.json"
    out_names = ["exports.csv", "functions.csv", "ledger.csv", "unresolved-mangling.csv"]
    if manifest_path.exists() and not args.force:
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            old = None
        if old and old.get("inputs") == inputs:
            intact = all((ledger_dir / n).exists() for n in out_names)
            if intact and all(
                sha256_file(ledger_dir / n) == old.get("output_hashes", {}).get(n)
                for n in out_names
            ):
                print("re_ledger: inputs unchanged and outputs intact - up-to-date (idempotent skip).")
                print("re_ledger: use --force to rebuild.")
                return 0

    # --- load exports ---
    exports_by_mod = {}
    for m in MODULES:
        exports_by_mod[m["key"]] = parse_exports(ws / m["exports"]) if m["exports"] else []

    # --- load functions ---
    funcs_by_mod = {}
    for m in MODULES:
        rows = parse_functions_csv(raw_dir / ("%s_functions.csv" % m["key"]))
        funcs_by_mod[m["key"]] = rows

    # --- load optional supplements ---
    xrefs_by_mod, strings_by_mod, vtables_by_mod = {}, {}, {}
    for m in MODULES:
        key = m["key"]
        p = raw_dir / ("%s_xrefs.csv" % key)
        xrefs_by_mod[key] = parse_xrefs_csv(p) if p.exists() else {}
        p = raw_dir / ("%s_strings.csv" % key)
        strings_by_mod[key] = parse_strings_csv(p) if p.exists() else []
        p = raw_dir / ("%s_vtables.csv" % key)
        vtables_by_mod[key] = parse_vtables_csv(p) if p.exists() else []
    demangled_path = raw_dir / "demangled.csv"
    demangled_map = parse_demangled_csv(demangled_path) if demangled_path.exists() else {}

    # --- build merged ledger ---
    ledger_rows = []
    export_rows = []
    unresolved_rows = []

    totals = Counter()
    per_mod_stats = OrderedDict()

    for m in MODULES:
        key = m["key"]
        st = Counter()
        funcs = funcs_by_mod[key]
        exports = exports_by_mod[key]

        exp_by_rva = {}
        for e in exports:
            exp_by_rva.setdefault(e["rva"], []).append(e)

        merged_rvas = set()

        # functions
        for f in funcs:
            st["functions"] += 1
            rva = f["rva"]
            exps = exp_by_rva.get(rva, [])
            if exps:
                merged_rvas.add(rva)
            ex = exps[0] if exps else None
            disp = f["name_display"]
            ns = f["namespace"]
            owner = ns if ns not in ("", "Global", "::") else ""
            if not owner and "::" in disp:
                owner = "::".join(disp.split("::")[:-1])
            method = ""
            if f["name_orig"] and not RE_FUN_NAME.match(f["name_orig"]):
                method = f["name_orig"]
            elif "::" in disp:
                method = disp.split("::")[-1]
            name_mangled = ex["mangled"] if ex else ""
            if not owner and ex and not name_mangled.startswith("??_") :
                desc = describe_mangled(name_mangled)
                if "?$" not in name_mangled and desc["owner"] and not desc["reason"]:
                    owner = desc["owner"]
            is_export = 1 if ex else 0
            ordinal = ex["ordinal"] if ex else ""
            status = "todo"
            notes = []
            if f["is_thunk"]:
                status = "stub"
                st["stub"] += 1
                notes.append("ghidra-thunk")
            if f["is_external"]:
                status = "external"
            if ex:
                notes.append("exported")
                if len(exps) > 1:
                    notes.append("alias:%s" % ",".join(str(x["ordinal"]) for x in exps[1:]))
            if RE_FUN_NAME.match(disp):
                st["unnamed"] += 1
            else:
                st["named"] += 1
            if owner:
                st["owner_known"] += 1
            xrefs_in_s, calls_out_s = "", ""
            evidence = ("ghidra:ExportFunctions.java;recon:%s" % m["exports"]) if ex else "ghidra:ExportFunctions.java"
            xr = xrefs_by_mod[key].get(rva)
            if xr is not None:
                xrefs_in_s = xr["xrefs_in"]
                calls_out_s = xr["calls_out"]
                evidence += ";ghidra:ExportSupplement.java"
                st["xrefs_linked"] += 1
                if xr["in_code"] or xr["in_data"]:
                    notes.append("refs:code=%d,data=%d" % (xr["in_code"], xr["in_data"]))
            ledger_rows.append([
                "%s:%x" % (key, rva), "function", disp, disp, owner, key,
                "0x%x" % rva, f["size"], xrefs_in_s, calls_out_s, status,
                evidence,
                ";".join(notes), name_mangled, ordinal, is_export,
                str(f["is_thunk"]).lower(), str(f["is_external"]).lower(),
                f["param_count"], f["symbol_source"],
            ])

        # standalone exports (vtables, rtti, data, strings, or unmatched)
        for e in exports:
            if e["rva"] in merged_rvas:
                continue
            st["exports_standalone"] += 1
            desc = describe_mangled(e["mangled"])
            kind = desc["kind"]
            sk = st.setdefault("standalone_kinds", {})
            sk[kind] = sk.get(kind, 0) + 1
            status = "todo"
            notes = ["no-function-match"] if kind == "export" else []
            if desc["reason"]:
                unresolved_rows.append([key, e["ordinal"], "0x%x" % e["rva"], e["mangled"], desc["reason"]])
                st["unresolved"] += 1
            if kind == "export" and e["mangled"].startswith("?"):
                st["standalone_function_like"] += 1
            ledger_rows.append([
                "%s:%x#%d" % (key, e["rva"], e["ordinal"]), kind, e["mangled"], desc["demangled"],
                desc["owner"], key, "0x%x" % e["rva"], 0, "", "", status,
                "recon:%s" % m["exports"], ";".join(notes), e["mangled"],
                e["ordinal"], 1, "false", "false", "", "",
            ])

        # exports.csv rows (all exports, with merge info)
        func_by_rva = {f["rva"]: f for f in funcs}
        for e in exports:
            st["exports"] += 1
            if e["rva"] in merged_rvas:
                st["exports_merged_entries"] += 1
            desc = describe_mangled(e["mangled"])
            f = func_by_rva.get(e["rva"])
            export_rows.append([
                key, e["ordinal"], "0x%x" % e["rva"], e["mangled"],
                desc["kind"], desc["owner"], desc["method"], desc["demangled"],
                f["name_display"] if f else "",
                f["size"] if f else "",
                (f["namespace"] if f else ""),
                desc["reason"],
            ])

        st["exports_merged"] = len(merged_rvas)
        st["export_aliases"] = st.get("exports_merged_entries", 0) - st["exports_merged"]
        per_mod_stats[key] = dict(st)
        for k, v in st.items():
            if isinstance(v, dict):
                continue
            totals[k] += v

    # --- supplements: demangled fill, strings, vtables ---
    stats_extra = Counter()

    if demangled_map:
        for row in ledger_rows:
            if row[1] == "function":
                continue
            nm = row[13]
            if nm.startswith("?"):
                ok, dem = demangled_map.get(nm, (False, ""))
                if ok and dem and not row[3]:
                    row[3] = dem
                    row[11] += ";ghidra:DemangleList.java"

    row_index = {}
    for i, row in enumerate(ledger_rows):
        if row[1] != "function":
            row_index[(row[5], row[6])] = i

    for m in MODULES:
        key = m["key"]
        for s in strings_by_mod[key]:
            rk = (key, "0x%x" % s["rva"])
            i = row_index.get(rk)
            if i is not None:
                row = ledger_rows[i]
                if row[1] in ("string", "data"):
                    row[7] = s["length"]
                    row[8] = s["refs"]
                    if "string-literal" not in row[12]:
                        row[12] = (row[12] + ";string-literal").lstrip(";")
                    row[11] += ";ghidra:ExportSupplement.java"
                    stats_extra["strings_merged"] += 1
                    continue
            notes = "string-literal;refs=%d" % s["refs"]
            if s["ref_rvas"]:
                notes += ";ref_by=" + ";".join(s["ref_rvas"].split(";")[:4])
            ledger_rows.append([
                "%s:%x#str" % (key, s["rva"]), "string", s["preview"], "", "", key,
                "0x%x" % s["rva"], s["length"], s["refs"], "", "todo",
                "ghidra:ExportSupplement.java", notes, "", "", 0, "false", "false", "", "",
            ])
            row_index[rk] = len(ledger_rows) - 1
            stats_extra["strings_added"] += 1

    for m in MODULES:
        key = m["key"]
        for v in vtables_by_mod[key]:
            rk = (key, "0x%x" % v["rva"])
            i = row_index.get(rk)
            if i is not None:
                row = ledger_rows[i]
                row[7] = v["entries"] * 4
                add = "vt-entries=%d" % v["entries"]
                if add not in row[12]:
                    row[12] = (row[12] + ";" + add).lstrip(";")
                row[11] += ";ghidra:ExportSupplement.java"
                stats_extra["vtables_merged"] += 1
                continue
            funcs = v["funcs"].split(";") if v["funcs"] else []
            fshow = ";".join(funcs[:6]) + (";+%d" % (len(funcs) - 6) if len(funcs) > 6 else "")
            notes = "vt-entries=%d" % v["entries"]
            if fshow:
                notes += ";vt-funcs=" + fshow
            ledger_rows.append([
                "%s:%x#vt" % (key, v["rva"]), "vtable", v["name"], "", v["ns"], key,
                "0x%x" % v["rva"], v["entries"] * 4, "", "", "todo",
                "ghidra:ExportSupplement.java", notes, "", "", 0, "false", "false", "", "",
            ])
            row_index[rk] = len(ledger_rows) - 1
            stats_extra["vtables_added"] += 1

    overrides_path = ledger_dir / "status-overrides.csv"
    if overrides_path.exists():
        overrides = parse_overrides_csv(overrides_path)
        idx_by_id = {row[0]: row for row in ledger_rows}
        applied = 0
        for oid, ov in overrides.items():
            row = idx_by_id.get(oid)
            if row is None:
                continue
            applied += 1
            if ov["status"]:
                row[10] = ov["status"]
            if ov["evidence"] and ov["evidence"] not in row[11]:
                row[11] += ";" + ov["evidence"]
            if ov["notes"]:
                row[12] = (row[12] + ";" + ov["notes"]).lstrip(";")
        stats_extra["overrides_defined"] = len(overrides)
        stats_extra["overrides_applied"] = applied

    if demangled_map and unresolved_rows:
        kept = []
        for row in unresolved_rows:
            ok, dem = demangled_map.get(row[3], (False, ""))
            if ok and "::" in dem:
                stats_extra["unresolved_resolved_by_demangler"] += 1
                continue
            kept.append(row)
        unresolved_rows = kept

    # sort ledger by module order then rva
    mod_order = {m["key"]: i for i, m in enumerate(MODULES)}
    def sort_key(r):
        kind = r[1]
        return (mod_order[r[5]], int(r[6], 16), 0 if kind == "function" else 1)
    ledger_rows.sort(key=sort_key)

    # checks
    ids = [r[0] for r in ledger_rows]
    kind_counts = Counter(r[1] for r in ledger_rows)
    checks = {
        "id_unique": len(ids) == len(set(ids)),
        "exports_all_accounted": (totals["exports_merged_entries"] + totals["exports_standalone"]) == totals["exports"],
        "functions_all_registered": kind_counts["function"] == totals["functions"],
    }
    if any(xrefs_by_mod.values()):
        checks["xrefs_linked"] = totals.get("xrefs_linked", 0) == totals["functions"]
    if "overrides_defined" in stats_extra:
        checks["overrides_valid"] = stats_extra["overrides_applied"] == stats_extra["overrides_defined"]

    # --- write outputs ---
    write_csv_atomic(ledger_dir / "exports.csv",
                     ["module", "ordinal", "rva", "name_mangled", "kind_hint", "owner_hint",
                      "method_hint", "demangled_hint", "merged_function", "merged_size",
                      "merged_namespace", "parse_reason"],
                     export_rows)
    write_csv_atomic(ledger_dir / "functions.csv",
                     ["module", "entry_rva", "name_display", "name_orig", "namespace", "size",
                      "is_thunk", "is_external", "param_count", "symbol_source"],
                     [[m["key"], "0x%x" % f["rva"], f["name_display"], f["name_orig"],
                       f["namespace"], f["size"], str(f["is_thunk"]).lower(),
                       str(f["is_external"]).lower(), f["param_count"], f["symbol_source"]]
                      for m in MODULES for f in funcs_by_mod[m["key"]]])
    write_csv_atomic(ledger_dir / "ledger.csv", LEDGER_COLS, ledger_rows)
    write_csv_atomic(ledger_dir / "unresolved-mangling.csv",
                     ["module", "ordinal", "rva", "name_mangled", "reason"],
                     unresolved_rows)

    output_hashes = {n: sha256_file(ledger_dir / n) for n in out_names}
    manifest = {
        "schema": "re-ledger/1",
        "tool": "tools/re_ledger.py",
        "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "workspace": str(ws),
        "inputs": inputs,
        "output_hashes": output_hashes,
        "counts": {n: sum(1 for _ in open(ledger_dir / n, encoding="utf-8")) - 1 for n in out_names},
        "stats": {
            "totals": dict(totals),
            "per_module": per_mod_stats,
            "extra": dict(stats_extra),
            "demangled": {
                "names": len(demangled_map),
                "ok": sum(1 for ok, _ in demangled_map.values() if ok),
            },
            "checks": checks,
        },
    }
    write_json_atomic(manifest_path, manifest)

    # --- summary ---
    print("=== re_ledger summary ===")
    print("%-8s %10s %9s %9s %10s %11s %11s %8s %9s" % (
        "module", "functions", "exports", "merged_fn", "merged_ent", "standalone", "unresolved", "thunks", "named"))
    for m in MODULES:
        s = per_mod_stats[m["key"]]
        print("%-8s %10d %9d %9d %10d %11d %11d %8d %9d" % (
            m["key"], s.get("functions", 0), s.get("exports", 0), s.get("exports_merged", 0),
            s.get("exports_merged_entries", 0), s.get("exports_standalone", 0),
            s.get("unresolved", 0), s.get("stub", 0), s.get("named", 0)))
    t = totals
    print("%-8s %10d %9d %9d %10d %11d %11d %8d %9d" % (
        "TOTAL", t["functions"], t["exports"], t["exports_merged"], t["exports_merged_entries"],
        t["exports_standalone"], t["unresolved"], t["stub"], t["named"]))
    kind_total = Counter()
    for m in MODULES:
        for kk, vv in per_mod_stats[m["key"]].get("standalone_kinds", {}).items():
            kind_total[kk] += vv
    print("standalone kinds: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(kind_total.items())))
    print("export aliases (extra entries on shared RVAs): %d" % t["export_aliases"])
    print("checks: " + ", ".join("%s=%s" % (k, "PASS" if v else "FAIL") for k, v in checks.items()))
    print("standalone function-like exports (triaged as no-function-match): %d" % t["standalone_function_like"])
    print("xrefs linked: %d/%d | strings: +%d merged %d | vtables: +%d merged %d" % (
        t.get("xrefs_linked", 0), t["functions"],
        stats_extra["strings_added"], stats_extra["strings_merged"],
        stats_extra["vtables_added"], stats_extra["vtables_merged"]))
    print("unresolved after demangle pass: %d (resolved by demangler: %d)" % (
        len(unresolved_rows), stats_extra["unresolved_resolved_by_demangler"]))
    if "overrides_defined" in stats_extra:
        print("status overrides applied: %d/%d" % (
            stats_extra["overrides_applied"], stats_extra["overrides_defined"]))
    print("written: %s" % ledger_dir)
    if not all(checks.values()):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
