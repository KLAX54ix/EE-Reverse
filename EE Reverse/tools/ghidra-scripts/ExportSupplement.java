// ExportSupplement.java - L1 supplement exporter for one program.
// Produces, in the output dir (default D:\EE Reverse\ledger\raw):
//   <mod>_xrefs.csv     per function: xrefs_in / xrefs_in_code / xrefs_in_data / calls_out
//   <mod>_callees.csv   call-graph edges (deduped pairs): caller_rva, callee_rva, callee_name, ref_type
//   <mod>_strings.csv   defined string data: addr_rva, length, value_preview, refs_count, ref_rvas
//   <mod>_vtables.csv   vftable symbols: rva, name, namespace, entry_count, func_rvas
//
// Usage:
//   analyzeHeadless <projDir> <proj> -process <program> -noanalysis \
//     -scriptPath <dir> -postScript ExportSupplement.java [<outDir>]

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeSet;

public class ExportSupplement extends GhidraScript {

    private static final String DEFAULT_DIR = "D:\\EE Reverse\\ledger\\raw";
    private long imageBase;
    private String module;
    private AddressSpace mainSpace;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File outDir = (args.length >= 1 && args[0] != null && !args[0].isEmpty())
                ? new File(args[0]) : new File(DEFAULT_DIR);
        outDir.mkdirs();
        String base = baseName(currentProgram.getName());
        module = currentProgram.getName();
        imageBase = currentProgram.getImageBase().getOffset();
        mainSpace = currentProgram.getAddressFactory().getDefaultAddressSpace();

        exportXrefs(new File(outDir, base + "_xrefs.csv"), new File(outDir, base + "_callees.csv"));
        exportStrings(new File(outDir, base + "_strings.csv"));
        exportVtables(new File(outDir, base + "_vtables.csv"));
    }

    private Long rvaOf(Address a) {
        if (a == null || !a.getAddressSpace().equals(mainSpace)) return null;
        return a.getOffset() - imageBase;
    }

    private void exportXrefs(File xout, File cout) throws Exception {
        ReferenceManager rm = currentProgram.getReferenceManager();
        FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
        int nFuncs = 0, nEdges = 0;
        Set<String> edgeSeen = new HashSet<>();
        try (PrintWriter xw = writer(xout); PrintWriter cw = writer(cout)) {
            xw.println("module,entry_rva,xrefs_in,xrefs_in_code,xrefs_in_data,calls_out");
            cw.println("module,caller_rva,callee_rva,callee_name,ref_type");
            while (fit.hasNext() && !monitor.isCancelled()) {
                Function f = fit.next();
                Address ep = f.getEntryPoint();
                Long rva = rvaOf(ep);
                if (rva == null) continue;
                int inTotal = 0, inCode = 0, inData = 0;
                for (Reference r : rm.getReferencesTo(ep)) {
                    inTotal++;
                    if (r.getReferenceType().isData()) inData++;
                    else inCode++;
                }
                TreeSet<String> callees = new TreeSet<>();
                InstructionIterator iit = currentProgram.getListing().getInstructions(f.getBody(), true);
                while (iit.hasNext() && !monitor.isCancelled()) {
                    Instruction ins = iit.next();
                    if (!ins.getFlowType().isCall()) continue;
                    for (Address t : ins.getFlows()) {
                        Function cf = currentProgram.getFunctionManager().getFunctionAt(t);
                        if (cf == null) cf = currentProgram.getFunctionManager().getFunctionContaining(t);
                        Long trva = (cf != null) ? rvaOf(cf.getEntryPoint()) : rvaOf(t);
                        String tkey = (trva != null) ? ("0x" + Long.toHexString(trva)) : t.toString();
                        String cname = (cf != null) ? cf.getName(true) : "";
                        callees.add(tkey);
                        String pair = "0x" + Long.toHexString(rva) + "|" + tkey;
                        if (edgeSeen.add(pair)) {
                            cw.println(q(module) + "," + q("0x" + Long.toHexString(rva)) + ","
                                    + q(tkey) + "," + q(cname) + ","
                                    + q(ins.getFlowType().toString()));
                            nEdges++;
                        }
                    }
                }
                xw.println(q(module) + "," + q("0x" + Long.toHexString(rva)) + ","
                        + inTotal + "," + inCode + "," + inData + "," + callees.size());
                nFuncs++;
                if (nFuncs % 5000 == 0) { xw.flush(); cw.flush(); }
            }
        }
        println("ExportSupplement: xrefs funcs=" + nFuncs + " callEdges=" + nEdges + " -> " + xout.getName());
    }

    private void exportStrings(File out) throws Exception {
        Listing listing = currentProgram.getListing();
        ReferenceManager rm = currentProgram.getReferenceManager();
        DataIterator dit = listing.getDefinedData(true);
        int n = 0;
        try (PrintWriter w = writer(out)) {
            w.println("module,addr_rva,length,value_preview,refs_count,ref_rvas");
            while (dit.hasNext() && !monitor.isCancelled()) {
                Data d = dit.next();
                Object v;
                try { v = d.getValue(); } catch (Exception e) { continue; }
                if (!(v instanceof String)) continue;
                Long rva = rvaOf(d.getAddress());
                if (rva == null) continue;
                String s = (String) v;
                StringBuilder refs = new StringBuilder();
                int cnt = 0;
                for (Reference r : rm.getReferencesTo(d.getAddress())) {
                    cnt++;
                    if (cnt <= 8) {
                        Long fr = rvaOf(r.getFromAddress());
                        if (refs.length() > 0) refs.append(";");
                        refs.append(fr != null ? ("0x" + Long.toHexString(fr)) : r.getFromAddress().toString());
                    }
                }
                w.println(q(module) + "," + q("0x" + Long.toHexString(rva)) + ","
                        + d.getLength() + "," + q(preview(s)) + "," + cnt + "," + q(refs.toString()));
                n++;
                if (n % 5000 == 0) w.flush();
            }
        }
        println("ExportSupplement: strings=" + n + " -> " + out.getName());
    }

    private void exportVtables(File out) throws Exception {
        SymbolTable st = currentProgram.getSymbolTable();
        Memory mem = currentProgram.getMemory();
        Set<Long> seen = new HashSet<>();
        int n = 0;
        try (PrintWriter w = writer(out)) {
            w.println("module,rva,name,namespace,entry_count,func_rvas");
            SymbolIterator sit = st.getAllSymbols(true);
            while (sit.hasNext() && !monitor.isCancelled()) {
                Symbol s = sit.next();
                String nm = s.getName();
                String lower = nm.toLowerCase();
                if (!lower.startsWith("vftable")) continue;
                Address a = s.getAddress();
                Long rva = rvaOf(a);
                if (rva == null || !seen.add(rva)) continue;
                StringBuilder funcs = new StringBuilder();
                int entries = 0;
                Address cur = a;
                for (int i = 0; i < 512; i++) {
                    Address target;
                    try {
                        int v = mem.getInt(cur);
                        target = mainSpace.getAddress(v & 0xFFFFFFFFL);
                    } catch (Exception e) {
                        break;
                    }
                    Function cf = currentProgram.getFunctionManager().getFunctionAt(target);
                    if (cf == null) break;
                    Long tr = rvaOf(target);
                    if (tr == null) break;
                    if (funcs.length() > 0) funcs.append(";");
                    funcs.append("0x").append(Long.toHexString(tr));
                    entries++;
                    cur = cur.add(4);
                }
                String ns = (s.getParentNamespace() == null) ? "" : s.getParentNamespace().getName(true);
                w.println(q(module) + "," + q("0x" + Long.toHexString(rva)) + "," + q(nm) + ","
                        + q(ns) + "," + entries + "," + q(funcs.toString()));
                n++;
            }
        }
        println("ExportSupplement: vtables=" + n + " -> " + out.getName());
    }

    private PrintWriter writer(File f) throws Exception {
        return new PrintWriter(new OutputStreamWriter(new FileOutputStream(f), StandardCharsets.UTF_8));
    }

    private static String preview(String s) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length() && sb.length() < 120; i++) {
            char c = s.charAt(i);
            if (c == '\n') sb.append("\\n");
            else if (c == '\r') sb.append("\\r");
            else if (c == '\t') sb.append("\\t");
            else sb.append(c);
        }
        return sb.toString();
    }

    private static String baseName(String name) {
        int dot = name.lastIndexOf('.');
        return (dot > 0) ? name.substring(0, dot) : name;
    }

    private static String q(String s) {
        if (s == null) return "\"\"";
        StringBuilder sb = new StringBuilder(s.length() + 2);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') sb.append("\"\"");
            else sb.append(c);
        }
        sb.append('"');
        return sb.toString();
    }
}
