import * as vscode from "vscode";
import type { ITransportClient } from "../transport/types";

function parseToolJson(result: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  const content = result?.content;
  if (!Array.isArray(content) || content.length === 0) {
    return null;
  }
  const first = content[0];
  if (!first || typeof first !== "object") {
    return null;
  }
  const text = Reflect.get(first, "text");
  if (typeof text !== "string" || !text.trim()) {
    return null;
  }
  const parsed = JSON.parse(text);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? (parsed as Record<string, unknown>)
    : null;
}

export class AfsTrainingProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "afs.training";

  private view?: vscode.WebviewView;

  constructor(
    private readonly transport: ITransportClient,
    private readonly logger: vscode.OutputChannel,
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage(async (msg) => {
      switch (msg.command) {
        case "refresh":
          await this.updateContent();
          break;
        case "exportAntigravity":
          await vscode.commands.executeCommand("afs.training.exportAntigravity");
          await this.updateContent();
          break;
        case "extractSessions":
          await vscode.commands.executeCommand("afs.training.extractSessions");
          await this.updateContent();
          break;
        case "generateRouter":
          await vscode.commands.executeCommand("afs.training.generateRouter");
          await this.updateContent();
          break;
        case "freshnessGate":
          await vscode.commands.executeCommand("afs.training.freshnessGate");
          await this.updateContent();
          break;
      }
    });
    this.updateContent();
  }

  async refresh(): Promise<void> {
    await this.updateContent();
  }

  private async updateContent(): Promise<void> {
    if (!this.view) return;

    const connected = this.transport.isReady();
    let agentCaps: Record<string, unknown> | null = null;
    let memoryStatus: Record<string, unknown> | null = null;

    if (connected) {
      try {
        const capsResult = await this.transport.callTool("agent.capabilities", {});
        const parsed = parseToolJson(capsResult);
        if (parsed) {
          agentCaps = parsed;
        }
      } catch {
        // tool may not exist
      }

      try {
        const memResult = await this.transport.callTool("memory.status", {});
        const parsed = parseToolJson(memResult);
        if (parsed) {
          memoryStatus = parsed;
        }
      } catch {
        // tool may not exist
      }
    }

    this.view.webview.html = this.buildHtml(connected, agentCaps, memoryStatus);
  }

  private buildHtml(
    connected: boolean,
    agentCaps: Record<string, unknown> | null,
    memoryStatus: Record<string, unknown> | null,
  ): string {
    let agentsHtml = "";
    if (agentCaps) {
      const agents = (agentCaps as any).agents ?? [];
      if (Array.isArray(agents) && agents.length > 0) {
        const rows = agents
          .map((a: any) => {
            const name = a.name ?? "unknown";
            const hasCaps = a.capabilities ? "yes" : "no";
            return `<div class="row"><span class="label">${this.esc(name)}</span><span class="value">${hasCaps}</span></div>`;
          })
          .join("");
        agentsHtml = `
          <div class="section">
            <h3>Agent Capabilities</h3>
            ${rows}
          </div>`;
      }
    }

    let memoryHtml = "";
    if (memoryStatus) {
      const entries = (memoryStatus as any).entry_count ?? 0;
      const stale = (memoryStatus as any).stale ?? false;
      const cls = stale ? "stale" : "fresh";
      memoryHtml = `
        <div class="section">
          <h3>Memory</h3>
          <div class="row"><span class="label">Entries</span><span class="value">${entries}</span></div>
          <div class="row"><span class="label">Status</span><span class="value ${cls}">${stale ? "Stale" : "Fresh"}</span></div>
        </div>`;
    }

    const notConnected = !connected
      ? `<div class="notice">Connect to AFS server for training tools.</div>`
      : "";

    return `<!DOCTYPE html>
<html>
<head>
<style>
  body {
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--vscode-foreground);
    padding: 8px;
    margin: 0;
  }
  .section { margin-bottom: 12px; }
  .section h3 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--vscode-descriptionForeground);
    margin: 0 0 6px 0;
  }
  .row {
    display: flex;
    justify-content: space-between;
    padding: 2px 0;
    font-size: 12px;
  }
  .label { color: var(--vscode-descriptionForeground); }
  .value { font-weight: 500; }
  .value.fresh { color: var(--vscode-testing-iconPassed); }
  .value.stale { color: var(--vscode-editorWarning-foreground); }
  .notice {
    color: var(--vscode-descriptionForeground);
    font-size: 12px;
    font-style: italic;
    padding: 8px 0;
  }
  .actions {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
  }
  .action-group {
    margin-bottom: 12px;
  }
  .action-group h3 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--vscode-descriptionForeground);
    margin: 0 0 6px 0;
  }
  button {
    background: var(--vscode-button-secondaryBackground);
    color: var(--vscode-button-secondaryForeground);
    border: none;
    padding: 4px 8px;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--vscode-font-family);
    text-align: left;
    width: 100%;
  }
  button:hover {
    background: var(--vscode-button-secondaryHoverBackground);
  }
  button.primary {
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
  }
  button.primary:hover {
    background: var(--vscode-button-hoverBackground);
  }
</style>
</head>
<body>
  ${notConnected}

  ${agentsHtml}
  ${memoryHtml}

  <div class="action-group">
    <h3>Data Sources</h3>
    <div class="actions">
      <button class="primary" onclick="post('exportAntigravity')">Export Antigravity Trajectories</button>
      <button onclick="post('extractSessions')">Extract Session Replay Data</button>
      <button onclick="post('generateRouter')">Generate Router Dataset</button>
    </div>
  </div>

  <div class="action-group">
    <h3>Validation</h3>
    <div class="actions">
      <button onclick="post('freshnessGate')">Run Freshness Gate</button>
      <button onclick="post('refresh')">Refresh</button>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    function post(cmd) {
      vscode.postMessage({ command: cmd });
    }
  </script>
</body>
</html>`;
  }

  private esc(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}
