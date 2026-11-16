/** Hands over a streamed body line by line, onChunk fires whenever data arrived. */
export async function readLines(
  body: ReadableStream<Uint8Array>,
  onLine: (line: string) => void,
  onChunk?: () => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk?.();
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) onLine(line);
  }
  if (buffer.trim()) onLine(buffer);
}
