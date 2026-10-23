// DemangleList.java - demangle a batch of MSVC mangled names via Ghidra's demangler.
//
// Usage:
//   analyzeHeadless <projDir> <proj> -process <program> -noanalysis \
//     -scriptPath <dir> -postScript DemangleList.java <outCsv> <inputTxt...>
//
// Input txt format: recon export dumps (lines: "ordinal 0xRVA mangled", '#' comments ok).
// Output CSV: name_mangled,ok,demangled   (sorted, unique names only, '?'-prefixed)

import ghidra.app.script.GhidraScript;
import ghidra.app.util.demangler.DemangledObject;
import ghidra.app.util.demangler.DemanglerUtil;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class DemangleList extends GhidraScript {

    private static final Pattern EXPORT_LINE = Pattern.compile("^\\s*\\d+\\s+(0x[0-9a-fA-F]+)\\s+(\\S.*?)\\s*$");

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            println("DemangleList: need <outCsv> <inputTxt...>");
            return;
        }
        File out = new File(args[0]);
        TreeSet<String> names = new TreeSet<>();
        for (int i = 1; i < args.length; i++) {
            File in = new File(args[i]);
            if (!in.exists()) { println("DemangleList: missing " + in); continue; }
            try (BufferedReader r = new BufferedReader(new FileReader(in))) {
                String line;
                while ((line = r.readLine()) != null) {
                    if (line.isEmpty() || line.startsWith("#")) continue;
                    Matcher m = EXPORT_LINE.matcher(line);
                    if (m.matches()) name_add(names, m.group(2));
                }
            }
        }

        int ok = 0, fail = 0;
        try (PrintWriter w = new PrintWriter(new OutputStreamWriter(
                new FileOutputStream(out), StandardCharsets.UTF_8))) {
            w.println("name_mangled,ok,demangled");
            for (String name : names) {
                if (monitor.isCancelled()) break;
                String dem = "";
                boolean good = false;
                try {
                    DemangledObject o = DemanglerUtil.demangle(currentProgram, name);
                    if (o != null) {
                        String d = o.getDemangledName();
                        if (d != null && !d.isEmpty()) {
                            dem = d;
                            good = true;
                        }
                    }
                } catch (Exception e) {
                    dem = "ERR:" + e.getMessage();
                }
                if (good) ok++; else fail++;
                w.println(q(name) + "," + good + "," + q(dem));
            }
        }
        println("DemangleList: names=" + names.size() + " ok=" + ok + " fail=" + fail + " -> " + out.getName());
    }

    private static void name_add(TreeSet<String> set, String name) {
        if (name.startsWith("?")) set.add(name);
    }

    private static String q(String s) {
        if (s == null) return "\"\"";
        StringBuilder sb = new StringBuilder(s.length() + 2);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') sb.append("\"\"");
            else if (c == '\n') sb.append(" ");
            else sb.append(c);
        }
        sb.append('"');
        return sb.toString();
    }
}
