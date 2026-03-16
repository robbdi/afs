import * as vscode from "vscode";
import { OUTPUT_CHANNEL_NAME } from "../constants";

export function createLogger(): vscode.OutputChannel {
  return vscode.window.createOutputChannel(OUTPUT_CHANNEL_NAME, { log: true });
}
