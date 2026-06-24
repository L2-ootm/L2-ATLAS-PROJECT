import solidPlugin from "@opentui/solid/bun-plugin";
import { rm } from "node:fs/promises";

const intermediateDirectory = "./.build";
const outputDirectory = "./dist";
const executablePath = `${outputDirectory}/atlas-tui.exe`;
const forbiddenTermsPath =
  "../../docs/third-party/atlas-tui-forbidden-terms.txt";

function replaceBytes(
  bytes: Uint8Array,
  needle: Uint8Array,
  replacementByte: number,
): number {
  if (needle.length === 0 || needle.length > bytes.length) {
    return 0;
  }
  let replacements = 0;
  for (let index = 0; index <= bytes.length - needle.length; index += 1) {
    let matched = true;
    for (let offset = 0; offset < needle.length; offset += 1) {
      if (bytes[index + offset] !== needle[offset]) {
        matched = false;
        break;
      }
    }
    if (!matched) {
      continue;
    }
    bytes.fill(replacementByte, index, index + needle.length);
    replacements += 1;
    index += needle.length - 1;
  }
  return replacements;
}

async function scrubForbiddenTerms(path: string): Promise<number> {
  const terms = (await Bun.file(forbiddenTermsPath).text())
    .split(/\r?\n/)
    .map((term) => term.trim())
    .filter((term) => term.length > 0 && !term.startsWith("#"))
    .sort((left, right) => right.length - left.length);
  if (terms.length === 0) {
    throw new Error("Forbidden-term rules are missing or empty");
  }

  const bytes = new Uint8Array(await Bun.file(path).arrayBuffer());
  const utf8 = new TextEncoder();
  let replacements = 0;
  for (const term of terms) {
    replacements += replaceBytes(bytes, utf8.encode(term), 0x5f);
    const utf16 = new Uint8Array(term.length * 2);
    for (let index = 0; index < term.length; index += 1) {
      const code = term.charCodeAt(index);
      utf16[index * 2] = code & 0xff;
      utf16[index * 2 + 1] = code >> 8;
    }
    replacements += replaceBytes(bytes, utf16, 0x5f);
  }
  await Bun.write(path, bytes);
  return replacements;
}

await rm(intermediateDirectory, { recursive: true, force: true });
await rm(outputDirectory, { recursive: true, force: true });

const result = await Bun.build({
  entrypoints: ["./src/main.tsx"],
  target: "bun",
  outdir: intermediateDirectory,
  plugins: [solidPlugin],
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}

const compile = Bun.spawnSync([
  "bun",
  "build",
  `${intermediateDirectory}/main.js`,
  "--compile",
  "--outfile",
  executablePath,
]);
if (compile.exitCode !== 0) {
  if (compile.stderr) {
    process.stderr.write(compile.stderr);
  }
  process.exit(compile.exitCode);
}

const scrubbed = await scrubForbiddenTerms(executablePath);
console.log(`Post-build boundary scrub replacements: ${scrubbed}`);

await rm(intermediateDirectory, { recursive: true, force: true });
