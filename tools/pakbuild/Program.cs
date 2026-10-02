using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;

class P {
    static string LibDir;
    static Assembly Lslib;

    static void Main(string[] args) {
        LibDir = args[0];
        string mode = args.Length > 1 ? args[1] : "probe";
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) => {
            var name = new AssemblyName(e.Name).Name + ".dll";
            var path = Path.Combine(LibDir, name);
            return File.Exists(path) ? Assembly.LoadFrom(path) : null;
        };
        Directory.SetCurrentDirectory(LibDir);
        Lslib = Assembly.LoadFrom(Path.Combine(LibDir, "LSLib.dll"));
        Console.WriteLine("LSLib " + Lslib.GetName().Version);

        if (mode == "pack") Pack(args[2], args[3]);
        else if (mode == "convert") Convert(args[2], args[3]);
        else if (mode == "extract") Extract(args[2], args[3], args[4]);
    }

    // Extract only files whose packaged path contains `match` (case-insensitive).
    static void Extract(string pak, string outDir, string match) {
        var packagerType = Lslib.GetType("LSLib.LS.Packager");
        var pfi = Lslib.GetType("LSLib.LS.PackagedFileInfo");
        var mi = packagerType.GetMethods().First(m => m.Name == "UncompressPackage"
            && m.GetParameters().Length == 3 && m.GetParameters()[0].ParameterType == typeof(string));
        // Build Func<PackagedFileInfo,bool> f = x => x.Name.Contains(match, OrdinalIgnoreCase)
        var p = System.Linq.Expressions.Expression.Parameter(pfi, "x");
        var nameMember = (MemberInfo)pfi.GetProperty("Name") ?? pfi.GetField("Name");
        var name = System.Linq.Expressions.Expression.MakeMemberAccess(p, nameMember);
        var contains = typeof(string).GetMethod("Contains", new[] { typeof(string), typeof(StringComparison) });
        var body = System.Linq.Expressions.Expression.Call(name, contains,
            System.Linq.Expressions.Expression.Constant(match), System.Linq.Expressions.Expression.Constant(StringComparison.OrdinalIgnoreCase));
        var funcType = typeof(Func<,>).MakeGenericType(pfi, typeof(bool));
        var filter = System.Linq.Expressions.Expression.Lambda(funcType, body, p).Compile();
        Directory.CreateDirectory(outDir);
        mi.Invoke(Activator.CreateInstance(packagerType), new object[] { pak, outDir, filter });
        Console.WriteLine("EXTRACTED '" + match + "' from " + pak + " -> " + outDir);
    }

    static void Pack(string srcDir, string outPak) {
        var buildType = Lslib.GetType("LSLib.LS.PackageBuildData");
        var verEnum   = Lslib.GetType("LSLib.LS.Enums.PackageVersion");
        var compEnum  = Lslib.GetType("LSLib.LS.CompressionMethod");
        var build = Activator.CreateInstance(buildType);
        buildType.GetProperty("Version").SetValue(build, Enum.Parse(verEnum, "V18"));
        buildType.GetProperty("Compression").SetValue(build, Enum.Parse(compEnum, "LZ4"));
        buildType.GetProperty("ExcludeHidden").SetValue(build, true);
        var packagerType = Lslib.GetType("LSLib.LS.Packager");
        var packager = Activator.CreateInstance(packagerType);
        var mi = packagerType.GetMethod("CreatePackage");
        var task = (Task) mi.Invoke(packager, new object[] { outPak, srcDir, build });
        task.GetAwaiter().GetResult();
        Console.WriteLine("PACKED -> " + outPak + "  (" + new FileInfo(outPak).Length + " bytes)");
    }

    static void Convert(string inPath, string outPath) {
        var ru = Lslib.GetType("LSLib.LS.ResourceUtils");
        var rfmt = Lslib.GetType("LSLib.LS.Enums.ResourceFormat") ?? Lslib.GetType("LSLib.LS.ResourceFormat");
        // Formats from file extensions, so this converts either way (lsx->lsf or lsf->lsx).
        var lsx = Enum.Parse(rfmt, Path.GetExtension(inPath).TrimStart('.').ToUpperInvariant());
        var lsf = Enum.Parse(rfmt, Path.GetExtension(outPath).TrimStart('.').ToUpperInvariant());

        // LoadResource(string path, ResourceFormat format, ResourceLoadParameters loadParams)
        var load = ru.GetMethods().First(m => m.Name == "LoadResource" && m.GetParameters().Length == 3
            && m.GetParameters()[0].ParameterType == typeof(string) && m.GetParameters()[1].ParameterType == rfmt);
        var loadParams = MakeParam(load.GetParameters()[2].ParameterType);
        Console.WriteLine("Load: " + load + "  loadParams=" + loadParams);
        object res = load.Invoke(null, new object[] { inPath, lsx, loadParams });
        Console.WriteLine("Loaded: " + res);

        // SaveResource(Resource, string path, ResourceFormat format, ResourceConversionParameters conv)
        var save = ru.GetMethods().First(m => m.Name == "SaveResource" && m.GetParameters().Length == 4
            && m.GetParameters()[1].ParameterType == typeof(string) && m.GetParameters()[2].ParameterType == rfmt);
        var convParams = MakeParam(save.GetParameters()[3].ParameterType);
        Console.WriteLine("Save: " + save + "  convParams=" + convParams);
        save.Invoke(null, new object[] { res, outPath, lsf, convParams });
        Console.WriteLine("CONVERTED -> " + outPath + "  (" + new FileInfo(outPath).Length + " bytes)");
    }

    // Build a ResourceLoadParameters / ResourceConversionParameters via FromGameVersion(BG3) or default ctor.
    static object MakeParam(Type t) {
        var game = Lslib.GetType("LSLib.LS.Enums.Game") ?? Lslib.GetType("LSLib.LS.Game");
        var fromGV = t.GetMethods(BindingFlags.Public | BindingFlags.Static).FirstOrDefault(m => m.Name == "FromGameVersion");
        if (fromGV != null && game != null) {
            var bg3 = Enum.GetNames(game).FirstOrDefault(n => n.Contains("BaldursGate3") || n.Contains("BG3"));
            if (bg3 != null) { try { return fromGV.Invoke(null, new object[] { Enum.Parse(game, bg3) }); } catch (Exception ex) { Console.WriteLine("FromGameVersion failed: " + ex.Message); } }
        }
        try { return Activator.CreateInstance(t); } catch { return null; }
    }
}
