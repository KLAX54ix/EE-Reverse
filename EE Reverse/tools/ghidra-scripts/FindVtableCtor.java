// Find what references a vtable and decompile the referencing functions.
// Args: <outFile> <rvaHex> [maxFunctions]
// The vtable is located at imageBase + rva (runtime base observed as 0x660000,
// so rva = runtimeVtable - 0x660000).

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Program;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashMap;
import java.util.Map;

public class FindVtableCtor extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("need <outFile> <rvaHex> [maxFunctions]");
            return;
        }
        long rva = Long.decode(args[1]);
        int maxFns = args.length > 2 ? Integer.decode(args[2]) : 12;

        Program program = currentProgram;
        Address target = program.getImageBase().add(rva);

        DecompInterface di = new DecompInterface();
        di.toggleCCode(true);
        di.setSimplificationStyle("decompile");
        di.openProgram(program);

        try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(new File(args[0]))))) {
            w.println("// program=" + program.getName()
                    + " imageBase=" + program.getImageBase()
                    + " rva=" + Long.toHexString(rva)
                    + " target=" + target);

            Symbol[] syms = program.getSymbolTable().getSymbols(target);
            for (Symbol s : syms) {
                w.println("// symbol at target: " + s.getName() + " [" + s.getSymbolType() + "]");
            }

            ReferenceManager rm = program.getReferenceManager();
            Map<Function, Address> callers = new LinkedHashMap<>();
            int total = 0;
            for (Reference r : rm.getReferencesTo(target)) {
                total++;
                Address from = r.getFromAddress();
                Function f = program.getFunctionManager().getFunctionContaining(from);
                w.println("// ref from " + from + " type=" + r.getReferenceType()
                        + " fn=" + (f == null ? "<none>" : f.getName(true)));
                if (f != null) callers.putIfAbsent(f, from);
            }
            w.println("// total references=" + total + " distinctFunctions=" + callers.size());
            w.println();

            int dumped = 0;
            for (Map.Entry<Function, Address> e : callers.entrySet()) {
                if (dumped >= maxFns) break;
                Function f = e.getKey();
                w.println("// =========================================================");
                w.println("// " + f.getName(true) + "  entry=" + f.getEntryPoint()
                        + "  xref@" + e.getValue());
                w.println("// signature=" + f.getPrototypeString(false, false));
                w.println("// =========================================================");
                try {
                    DecompileResults res = di.decompileFunction(f, 90, monitor);
                    if (res != null && res.decompileCompleted()
                            && res.getDecompiledFunction() != null) {
                        w.println(res.getDecompiledFunction().getC());
                    } else {
                        w.println("// <decompile failed>");
                    }
                } catch (Exception ex) {
                    w.println("// <error " + ex + ">");
                }
                w.println();
                dumped++;
            }
            w.println("// dumped=" + dumped);
        }
        println("FindVtableCtor: target=" + target + " refs walked, see " + args[0]);
    }
}
