import type { BinaryInfo } from "../transport/clientFactory";

const SHELL_SAFE_ARG = /^[A-Za-z0-9_./:=+-]+$/;

function shellQuote(value: string): string {
  if (!value) {
    return "''";
  }
  if (SHELL_SAFE_ARG.test(value)) {
    return value;
  }
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

export function buildTerminalCommand(
  binaryInfo: Pick<BinaryInfo, "command" | "args">,
  extraArgs: string[],
): string {
  return [binaryInfo.command, ...binaryInfo.args, ...extraArgs]
    .map((item) => shellQuote(item))
    .join(" ");
}
