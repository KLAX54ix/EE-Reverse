// ExportFunctions.java - export a function inventory (one CSV row per function)
// of the current program for the L1 ledger.
//
// Usage:
//   analyzeHeadless <projDir> <projName> -process <program> -noanalysis \
//     -scriptPath <dir> -postScript ExportFunctions.java [<outDirOrCsv>]
//
// Default output dir: D:\EE Reverse\ledger\raw
// Output file name: <programBaseName>_functions.csv (e.g. eslib_functions.csv)
//
// Columns:
//   module, entry_rva, name_display, name_orig, namespace, size,
//   is_thunk, is_external, param_count, symbol_source

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Program;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.Symbol;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

public class ExportFunctions extends GhidraScript {

    private static final String DEFAULT_DIR = "D:\\EE Reverse\\ledger\\raw";

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outPath;
        if (args.length >= 1 && args[0] != null && !args[0].isEmpty()) {
            File f = new File(args[0]);
            if (!f.getName().toLowerCase().endsWith(".csv")) {
                f.mkdirs();
                outPath = new File(f, baseName(currentProgram.getName()) + "_functions.csv").getAbsolutePath();
            } else {
                File parent = f.getParentFile();
                if (parent != null) parent.mkdirs();
                outPath = f.getAbsolutePath();
            }
        } else {
            File dir = new File(DEFAULT_DIR);
            dir.mkdirs();
            outPath = new File(dir, baseName(currentProgram.getName()) + "_functions.csv").getAbsolutePath();
        }

        Program program = currentProgram;
        long imageBase = program.getImageBase().getOffset();
        FunctionIterator it = program.getFunctionManager().getFunctions(true);

        int count = 0;
        int failed = 0;
        try (PrintWriter w = new PrintWriter(new OutputStreamWriter(
                new FileOutputStream(outPath), StandardCharsets.UTF_8))) {
            w.println("module,entry_rva,name_display,name_orig,namespace,size,"
                    + "is_thunk,is_external,param_count,symbol_source");
            while (it.hasNext() && !monitor.isCancelled()) {
                Function f = it.next();
                try {
                    long rva = f.getEntryPoint().getOffset() - imageBase;
                    String nameDisplay = f.getName(true);
                    Symbol sym = f.getSymbol();
                    String nameOrig = (sym == null) ? "" : sym.getName();
                    String source = (sym == null) ? "" : sym.getSource().toString();
                    Namespace ns = f.getParentNamespace();
                    String nsName = (ns == null) ? "" : ns.getName(true);
                    long size = f.getBody().getNumAddresses();
                    w.println(q(program.getName()) + "," + q("0x" + Long.toHexString(rva)) + ","
                            + q(nameDisplay) + "," + q(nameOrig) + "," + q(nsName) + ","
                            + size + "," + f.isThunk() + "," + f.isExternal() + ","
                            + f.getParameterCount() + "," + q(source));
                    count++;
                } catch (Exception e) {
                    failed++;
                }
                if ((count + failed) % 5000 == 0) {
                    w.flush();
                }
            }
        }
        println("ExportFunctions: wrote " + count + " rows (failed=" + failed + ") -> " + outPath);
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
