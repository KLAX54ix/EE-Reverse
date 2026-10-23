// RenameList.java - batch-rename functions from a CSV (rva,newname[,namespace]).
//
// Usage:
//   analyzeHeadless <proj> <name> -process <program> -noanalysis \
//     -scriptPath <dir> -postScript RenameList.java <csv> [--dry]
//
// rva is the PE RVA (e.g. 0x15b0); Ghidra address = imageBase + rva.
// Names are written with SourceType.USER_DEFINED so they survive re-analysis.

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;

public class RenameList extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("RenameList: need <csv> [--dry]");
            return;
        }
        boolean dry = false;
        for (String a : args) {
            if (a.equals("--dry")) dry = true;
        }
        File csv = new File(args[0]);
        if (!csv.exists()) {
            println("RenameList: missing " + csv);
            return;
        }
        int ok = 0, fail = 0, skip = 0;
        try (BufferedReader r = new BufferedReader(new FileReader(csv))) {
            String line;
            while ((line = r.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                String[] p = line.split(",");
                if (p.length < 2) continue;
                String s0 = p[0].trim();
                if (s0.toLowerCase().equals("rva")) continue; // header
                long rva;
                try {
                    rva = Long.parseLong(s0.startsWith("0x") ? s0.substring(2) : s0, 16);
                } catch (NumberFormatException e) {
                    println("RenameList: bad rva: " + line);
                    fail++;
                    continue;
                }
                String name = p[1].trim();
                Address a = currentProgram.getImageBase().add(rva);
                Function f = getFunctionAt(a);
                if (f == null) {
                    println("RenameList: no function @ " + a + " for " + name);
                    fail++;
                    continue;
                }
                if (f.getName().equals(name)) {
                    skip++;
                    continue;
                }
                if (dry) {
                    println("RenameList[dry]: " + a + " " + f.getName() + " -> " + name);
                    ok++;
                    continue;
                }
                try {
                    f.setName(name, SourceType.USER_DEFINED);
                    ok++;
                } catch (Exception e) {
                    println("RenameList: FAIL " + a + " -> " + name + ": " + e.getMessage());
                    fail++;
                }
            }
        }
        println("RenameList: renamed=" + ok + " skip=" + skip + " fail=" + fail
                + (dry ? " (dry)" : ""));
    }
}
