type Listener<T> = (event: T) => unknown;

export interface Disposable {
  dispose(): void;
}

export type Event<T> = (listener: Listener<T>) => Disposable;

export class EventEmitter<T> {
  private listeners = new Set<Listener<T>>();

  readonly event: Event<T> = (listener: Listener<T>) => {
    this.listeners.add(listener);
    return {
      dispose: () => {
        this.listeners.delete(listener);
      },
    };
  };

  fire(event: T): void {
    for (const listener of this.listeners) {
      listener(event);
    }
  }

  dispose(): void {
    this.listeners.clear();
  }
}

export interface OutputChannel {
  appendLine(value: string): void;
  dispose(): void;
}

export const workspace = {
  workspaceFolders: [] as Array<{ uri: { fsPath: string } }>,
  getConfiguration: () => ({
    get<T>(_section: string, defaultValue: T): T {
      return defaultValue;
    },
  }),
};

export const window = {
  createOutputChannel(): OutputChannel {
    return {
      appendLine(): void {},
      dispose(): void {},
    };
  },
};
