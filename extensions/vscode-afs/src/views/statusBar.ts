import * as vscode from "vscode";
import type { ConnectionState } from "../types";

export class AfsStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
    this.item.command = "afs.mcp.status";
    this.update("disconnected");
  }

  update(state: ConnectionState, contextName?: string): void {
    switch (state) {
      case "connected":
        this.item.text = `$(check) AFS${contextName ? `: ${contextName}` : ""}`;
        this.item.tooltip = "AFS connected — click for MCP status";
        break;
      case "disconnected":
        this.item.text = "$(circle-slash) AFS";
        this.item.tooltip = "AFS disconnected";
        break;
      case "error":
        this.item.text = "$(error) AFS";
        this.item.tooltip = "AFS error — click for details";
        break;
    }
    this.item.show();
  }

  dispose(): void {
    this.item.dispose();
  }
}
