// Decompile the function(s) at the given addresses and list their callees.
//
// Usage:
//   analyzeHeadless <proj> <name> -process <program> -noanalysis \
//     -scriptPath <dir> -postScript DecompAt.java <outFile> <addr> [addr...]
//
// Addresses may be given as 0x46dff0 or 46dff0 (image-base-relative addresses
// work because the default address space starts at the image base).

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Program;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.Set;

public class DecompAt extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("DecompAt: need <outFile> <addr> [addr...]");
            return;
        }
        File out = new File(args[0]);
        Program program = currentProgram;
        DecompInterface di = new DecompInterface();
        di.toggleCCode(true);
        di.toggleSyntaxTree(true);
        di.setSimplificationStyle("decompile");
        if (!di.openProgram(program)) {
            println("DecompAt: cannot open program");
            return;
        }
        FunctionManager fm = program.getFunctionManager();
        try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
            w.println("// program=" + program.getName() + " imageBase=" + program.getImageBase());
            for (int i = 1; i < args.length; i++) {
                String s = args[i].startsWith("0x") ? args[i].substring(2) : args[i];
                Address a = program.getAddressFactory().getDefaultAddressSpace().getAddress(s);
                Function f = fm.getFunctionContaining(a);
                if (f == null) f = fm.getFunctionAt(a);
                w.println();
                w.println("// ======================================================");
                if (f == null) {
                    w.println("// addr=" + args[i] + " <no function>");
                    continue;
                }
                w.println("// addr=" + args[i] + " function=" + f.getName(true)
                          + " entry=" + f.getEntryPoint()
                          + " bodyBytes=" + f.getBody().getNumAddresses());
                w.println("// ======================================================");
                try {
                    DecompileResults res = di.decompileFunction(f, 180, monitor);
                    if (res != null && res.decompileCompleted()
                            && res.getDecompiledFunction() != null) {
                        w.println(res.getDecompiledFunction().getC());
                    } else {
                        w.println("// <decompilation unavailable: "
                                  + (res == null ? "null" : res.getErrorMessage()) + ">");
                    }
                } catch (Exception e) {
                    w.println("// <decompiler error: " + e + ">");
                }
                Set<Function> callees = f.getCalledFunctions(monitor);
                for (Function c : callees) {
                    w.println("// CALLEE " + c.getEntryPoint() + " " + c.getName(true)
                              + " body=" + c.getBody().getNumAddresses());
                }
                w.flush();
            }
        }
        println("DecompAt: done -> " + out);
    }
}
