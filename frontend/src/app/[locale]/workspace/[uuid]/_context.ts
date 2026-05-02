import { createContext } from "react";

export const MinimizeContext = createContext<(() => void) | null>(null);
