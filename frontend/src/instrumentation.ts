// Replacement for Promise.withResolvers, missing in Node 20 and needed by pdfjs on load.
export async function register() {
  if (typeof (Promise as any).withResolvers === "undefined") {
    (Promise as any).withResolvers = function <T>() {
      let resolve!: (value: T | PromiseLike<T>) => void;
      let reject!: (reason?: unknown) => void;
      const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    };
  }
}
