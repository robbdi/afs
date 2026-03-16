import * as vscode from "vscode";

export function getConfig<T>(key: string, defaultValue: T): T {
  return vscode.workspace.getConfiguration("afs").get<T>(key, defaultValue);
}
