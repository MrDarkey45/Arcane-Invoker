using System;
using System.IO;
using System.Linq;
using System.Reflection;

class P {
    static string LibDir;

    static void Main(string[] args) {
        LibDir = args[0];
        string pak = args[1];
        string outDir = args[2];

        AppDomain.CurrentDomain.AssemblyResolve += (s, e) => {
            var name = new AssemblyName(e.Name).Name + ".dll";
            var path = Path.Combine(LibDir, name);
            return File.Exists(path) ? Assembly.LoadFrom(path) : null;
        };
        Directory.SetCurrentDirectory(LibDir); // help native dll resolution
        Directory.CreateDirectory(outDir);

        var lslib = Assembly.LoadFrom(Path.Combine(LibDir, "LSLib.dll"));
        Console.WriteLine("LSLib loaded: " + lslib.GetName().Version);

        var packagerType = lslib.GetType("LSLib.LS.Packager");
        if (packagerType == null) { Console.WriteLine("NO Packager type"); DumpPak(lslib); return; }

        Console.WriteLine("Packager UncompressPackage overloads:");
        var uncompress = packagerType.GetMethods()
            .Where(m => m.Name == "UncompressPackage").ToList();
        foreach (var m in uncompress)
            Console.WriteLine("  " + m);

        var packager = Activator.CreateInstance(packagerType);
        // prefer (string, string, ...) overloads
        var mi = uncompress
            .Where(m => m.GetParameters().Length >= 2 && m.GetParameters()[0].ParameterType == typeof(string))
            .OrderBy(m => m.GetParameters().Length)
            .FirstOrDefault();
        if (mi == null) { Console.WriteLine("No (string,...) UncompressPackage; dumping API."); DumpPak(lslib); return; }

        var ps = mi.GetParameters();
        object[] argv = new object[ps.Length];
        argv[0] = pak; argv[1] = outDir;
        for (int i = 2; i < ps.Length; i++)
            argv[i] = ps[i].HasDefaultValue ? ps[i].DefaultValue : null;

        Console.WriteLine("Invoking: " + mi);
        mi.Invoke(packager, argv);
        Console.WriteLine("DONE. Extracted to " + outDir);
    }

    static void DumpPak(Assembly lslib) {
        var pr = lslib.GetType("LSLib.LS.PackageReader");
        Console.WriteLine("PackageReader: " + pr);
        if (pr != null)
            foreach (var m in pr.GetMethods().Where(x => x.DeclaringType == pr))
                Console.WriteLine("  " + m);
    }
}
