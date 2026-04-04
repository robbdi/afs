import * as esbuild from "esbuild";
import { globSync } from "glob";
import * as path from "path";

const testFiles = globSync("test/suite/**/*.test.ts");

await esbuild.build({
  entryPoints: testFiles,
  bundle: true,
  outdir: "dist-test/suite",
  alias: {
    vscode: path.resolve("test/support/vscode.ts"),
  },
  external: ["mocha"],
  format: "cjs",
  platform: "node",
  target: "node20",
  sourcemap: true,
});

console.log(`Test build complete: ${testFiles.length} file(s).`);
