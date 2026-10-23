// List defined symbols whose name contains any of the given substrings, with
// their addresses.  Used to locate Editer.exe's OWN copies of the eslib classes
// (it links its own implementation, so its ctors live at different addresses
// than eslib.dll's exports).
// Args: <outFile> <substring> [substring...]

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.SymbolTable;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;

public class SymAddr extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("need <outFile> <substring> [substring...]");
            return;
        }
        String[] subs = new String[args.length - 1];
        System.arraycopy(args, 1, subs, 0, subs.length);

        SymbolTable st = currentProgram.getSymbolTable();
        try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(new File(args[0]))))) {
            w.println("// program=" + currentProgram.getName()
                    + " imageBase=" + currentProgram.getImageBase());
            for (String sub : subs) {
                w.println();
                w.println("// ==== substring: " + sub);
                SymbolIterator it = st.getSymbolIterator(sub, true);
                int n = 0;
                while (it.hasNext()) {
                    Symbol s = it.next();
                    if (!s.getName(true).contains(sub)) continue;
                    w.println(s.getAddress() + "  " + s.getName(true)
                            + "  [" + s.getSymbolType() + "]");
                    n++;
                    if (n > 200) { w.println("// ... truncated"); break; }
                }
                w.println("// matched=" + n);
            }

            // also dump function entry points for exact names
            w.println();
            w.println("// ==== functions (entry points)");
            FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
            int m = 0;
            while (fit.hasNext()) {
                Function f = fit.next();
                String nm = f.getName(true);
                for (String sub : subs) {
                    if (nm.contains(sub)) {
                        w.println(f.getEntryPoint() + "  " + nm
                                + "  sig=" + f.getPrototypeString(false, false));
                        m++;
                        break;
                    }
                }
                if (m > 300) { w.println("// ... truncated"); break; }
            }
            w.println("// functions=" + m);
        }
        println("SymAddr: done -> " + args[0]);
    }
}
