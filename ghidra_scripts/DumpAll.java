// Decompile all functions in the current program and write to a file.
//@category Decompiler

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.io.FileWriter;
import java.io.Writer;

public class DumpAll extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String out = getScriptArgs().length > 0 ? getScriptArgs()[0] : "decomp.txt";
		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
		try (Writer w = new FileWriter(out)) {
			while (it.hasNext() && !monitor.isCancelled()) {
				Function f = it.next();
				DecompileResults r = di.decompileFunction(f, 60, monitor);
				w.write("/* ===== " + f.getName() + " @ " + f.getEntryPoint() + " ===== */\n");
				if (r.decompileCompleted() && r.getDecompiledFunction() != null) {
					w.write(r.getDecompiledFunction().getC());
				} else {
					w.write("/* decompile failed: " + r.getErrorMessage() + " */\n");
				}
				w.write("\n");
			}
		}
		di.dispose();
		println("wrote " + out);
	}
}
