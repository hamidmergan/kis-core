// Polyfill for Promise.withResolvers — available since Node 22, missing in Node 20.
// Required by pdfjs-dist which calls it at module evaluation time (SSR).
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
