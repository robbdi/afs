import type { ITransportClient } from "../transport/types";

export interface FileEntry {
  path: string;
  is_dir: boolean;
}

export class FileService {
  constructor(private readonly transport: ITransportClient) {}

  async read(filePath: string): Promise<string> {
    const result = await this.transport.callTool("context.read", { path: filePath });
    return result.content as string;
  }

  async write(
    filePath: string,
    content: string,
    options?: { append?: boolean; mkdirs?: boolean },
  ): Promise<{ path: string; bytes: number }> {
    const result = await this.transport.callTool("context.write", {
      path: filePath,
      content,
      append: options?.append ?? false,
      mkdirs: options?.mkdirs ?? false,
    });
    return { path: result.path as string, bytes: result.bytes as number };
  }

  async list(dirPath: string, maxDepth?: number): Promise<FileEntry[]> {
    const result = await this.transport.callTool("context.list", {
      path: dirPath,
      max_depth: maxDepth ?? 1,
    });
    return (result.entries ?? []) as FileEntry[];
  }
}
