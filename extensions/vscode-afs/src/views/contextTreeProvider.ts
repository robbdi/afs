import * as vscode from "vscode";
import type { ContextService } from "../services/contextService";
import type { FileService } from "../services/fileService";
import type { DiscoveredContext, MountType } from "../types";
import { DEFAULT_POLICIES, PolicyType } from "../types";
import {
  ContextTreeItem,
  ContextFileItem,
  ContextRootItem,
  MountTypeItem,
} from "./contextTreeItems";

const MOUNT_TYPE_ORDER: MountType[] = [
  "memory",
  "knowledge",
  "tools",
  "scratchpad",
  "history",
  "hivemind",
  "global",
  "items",
  "monorepo",
] as MountType[];

export class ContextTreeProvider implements vscode.TreeDataProvider<ContextTreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<ContextTreeItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private contexts: DiscoveredContext[] = [];

  constructor(
    private readonly contextService: ContextService,
    private readonly fileService: FileService,
    private readonly showEmptyMounts: boolean,
  ) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ContextTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: ContextTreeItem): Promise<ContextTreeItem[]> {
    if (!element) {
      return this.getRootItems();
    }
    if (element instanceof ContextRootItem) {
      return this.getMountTypes(element.contextPath);
    }
    if (element instanceof MountTypeItem) {
      return this.getFiles(element.contextPath, element.mountType);
    }
    return [];
  }

  private async getRootItems(): Promise<ContextTreeItem[]> {
    try {
      this.contexts = await this.contextService.discover();
    } catch {
      this.contexts = [];
    }
    return this.contexts.map(
      (ctx) => new ContextRootItem(ctx.project, ctx.path, ctx.valid, ctx.mounts),
    );
  }

  private async getMountTypes(contextPath: string): Promise<MountTypeItem[]> {
    const items: MountTypeItem[] = [];
    for (const mt of MOUNT_TYPE_ORDER) {
      try {
        const entries = await this.fileService.list(`${contextPath}/${mt}`, 1);
        if (entries.length > 0 || this.showEmptyMounts) {
          const policy = DEFAULT_POLICIES[mt] ?? PolicyType.READ_ONLY;
          items.push(new MountTypeItem(mt, contextPath, policy, entries.length));
        }
      } catch {
        if (this.showEmptyMounts) {
          const policy = DEFAULT_POLICIES[mt] ?? PolicyType.READ_ONLY;
          items.push(new MountTypeItem(mt, contextPath, policy, 0));
        }
      }
    }
    return items;
  }

  private async getFiles(
    contextPath: string,
    mountType: string,
  ): Promise<ContextFileItem[]> {
    try {
      const entries = await this.fileService.list(`${contextPath}/${mountType}`, 1);
      return entries.map((e) => new ContextFileItem(e.path, e.is_dir));
    } catch {
      return [];
    }
  }
}
