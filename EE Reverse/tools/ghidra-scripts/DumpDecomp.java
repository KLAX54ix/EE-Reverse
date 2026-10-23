// Dump decompiled C for every function whose (demangled) name contains one of
// the supplied substrings.
//
// Usage:
//   analyzeHeadless <proj> <name> -process <program> -noanalysis \
//     -scriptPath <dir> -postScript DumpDecomp.java <outFile> <spec> [spec...]

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Program;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public class DumpDecomp extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("DumpDecomp: need <outFile> <spec> [spec...]");
            return;
        }
        File out = new File(args[0]);
        List<String> specs = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            specs.add(args[i].toLowerCase());
        }

        Program program = currentProgram;
        DecompInterface di = new DecompInterface();
        di.toggleCCode(true);
        di.toggleSyntaxTree(true);
        di.setSimplificationStyle("decompile");
        if (!di.openProgram(program)) {
            println("DumpDecomp: cannot open program");
            return;
        }

        int matched = 0;
        int dumped = 0;
        try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
            w.println("// program=" + program.getName()
                    + " imageBase=" + program.getImageBase());
            w.println("// specs=" + specs);

            FunctionIterator it = program.getFunctionManager().getFunctions(true);
            while (it.hasNext() && !monitor.isCancelled()) {
                Function f = it.next();
                String name = f.getName(true);
                String lower = name.toLowerCase();
                boolean hit = false;
                for (String s : specs) {
                    if (lower.contains(s)) { hit = true; break; }
                }
                if (!hit) continue;
                matched++;

                w.println();
                w.println("// =========================================================");
                w.println("// " + name);
                w.println("// entry=" + f.getEntryPoint());
                w.println("// signature=" + f.getPrototypeString(false, false));
                w.println("// bodyBytes=" + f.getBody().getNumAddresses());
                w.println("// =========================================================");

                try {
                    DecompileResults res = di.decompileFunction(f, 90, monitor);
                    if (res != null && res.decompileCompleted()
                            && res.getDecompiledFunction() != null) {
                        w.println(res.getDecompiledFunction().getC());
                        dumped++;
                    } else {
                        w.println("// <decompilation unavailable: "
                                + (res == null ? "null" : res.getErrorMessage()) + ">");
                    }
                } catch (Exception e) {
                    w.println("// <decompiler error: " + e + ">");
                }
                w.flush();
            }
            w.println();
            w.println("// matched=" + matched + " dumped=" + dumped);
        }
        println("DumpDecomp: matched=" + matched + " dumped=" + dumped + " -> " + out);
    }
}
