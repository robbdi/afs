import type { ITransportClient } from "../transport/types";
import type { IndexSummary, MountType, QueryEntry } from "../types";

export interface QueryOptions {
  mountTypes?: MountType[];
  relativePrefix?: string;
  limit?: number;
  includeContent?: boolean;
}

export class IndexService {
  constructor(private readonly transport: ITransportClient) {}

  async rebuild(contextPath: string, mountTypes?: MountType[]): Promise<IndexSummary> {
    const args: Record<string, unknown> = { context_path: contextPath };
    if (mountTypes?.length) args.mount_types = mountTypes;
    return (await this.transport.callTool(
      "context.index.rebuild",
      args,
    )) as unknown as IndexSummary;
  }

  async query(contextPath: string, query: string, options?: QueryOptions): Promise<QueryEntry[]> {
    const args: Record<string, unknown> = { context_path: contextPath, query };
    if (options?.mountTypes?.length) args.mount_types = options.mountTypes;
    if (options?.relativePrefix) args.relative_prefix = options.relativePrefix;
    if (options?.limit) args.limit = options.limit;
    if (options?.includeContent) args.include_content = options.includeContent;
    const result = await this.transport.callTool("context.query", args);
    return (result.entries ?? []) as QueryEntry[];
  }
}
