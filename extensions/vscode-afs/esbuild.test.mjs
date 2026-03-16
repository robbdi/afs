import * as esbuild from "esbuild";
import { globSync } from "glob";

const testFiles = globSync("test/suite/**/*.test.ts");

await esbuild.build({
  entryPoints: testFiles,
  bundle: true,
  outdir: "dist-test/suite",
  external: ["vscode", "mocha"],
  format: "cjs",
  platform: "node",
  target: "node20",
  sourcemap: true,
});

console.log(`Test build complete: ${testFiles.length} file(s).`);
