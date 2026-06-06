import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";

/**
 * In-memory navigation stack for the component/module detail+edit pages.
 *
 * Behaves like a browser history slice scoped to the asset tree:
 *  - Visiting a new detail/edit URL pushes onto the stack (capped at 15 entries).
 *  - Going back/forward via `<` / `>` moves the cursor and navigates.
 *  - Resetting (when the user clicks the `X` close button to return to a list)
 *    clears the stack so the next exploration starts fresh.
 *
 * The stack lives in memory (resets on full page reload), which matches the
 * intent: it is a shortcut for the current exploration session.
 */

const MAX_ENTRIES = 15;

interface NavEntry {
  pathname: string;
}

interface NavState {
  stack: NavEntry[];
  cursor: number;
}

interface DetailNavStackValue {
  push: (pathname: string) => void;
  goBack: () => void;
  goForward: () => void;
  reset: () => void;
  canGoBack: boolean;
  canGoForward: boolean;
}

const DetailNavStackContext = createContext<DetailNavStackValue | null>(null);

const INITIAL_STATE: NavState = { stack: [], cursor: -1 };

export function DetailNavStackProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [state, setState] = useState<NavState>(INITIAL_STATE);
  // Tracks whether the next push originates from an internal back/forward
  // jump. We set this flag right before navigating, then the destination
  // page's auto-push lands here and we clear it — leaving the stack/cursor
  // untouched.
  const skipNextPushRef = useRef(false);

  const push = useCallback((pathname: string) => {
    if (skipNextPushRef.current) {
      skipNextPushRef.current = false;
      return;
    }
    setState(({ stack, cursor }) => {
      const current = stack[cursor];
      if (current && current.pathname === pathname) {
        return { stack, cursor };
      }
      const truncated = stack.slice(0, cursor + 1);
      const appended = [...truncated, { pathname }];
      if (appended.length > MAX_ENTRIES) {
        const overflow = appended.length - MAX_ENTRIES;
        const trimmed = appended.slice(overflow);
        return { stack: trimmed, cursor: trimmed.length - 1 };
      }
      return { stack: appended, cursor: appended.length - 1 };
    });
  }, []);

  const goBack = useCallback(() => {
    if (state.cursor <= 0) return;
    const target = state.stack[state.cursor - 1];
    if (!target) return;
    skipNextPushRef.current = true;
    setState({ stack: state.stack, cursor: state.cursor - 1 });
    navigate(target.pathname);
  }, [state, navigate]);

  const goForward = useCallback(() => {
    if (state.cursor < 0 || state.cursor >= state.stack.length - 1) return;
    const target = state.stack[state.cursor + 1];
    if (!target) return;
    skipNextPushRef.current = true;
    setState({ stack: state.stack, cursor: state.cursor + 1 });
    navigate(target.pathname);
  }, [state, navigate]);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
    skipNextPushRef.current = false;
  }, []);

  const value = useMemo<DetailNavStackValue>(
    () => ({
      push,
      goBack,
      goForward,
      reset,
      canGoBack: state.cursor > 0,
      canGoForward: state.cursor >= 0 && state.cursor < state.stack.length - 1,
    }),
    [push, goBack, goForward, reset, state.cursor, state.stack.length],
  );

  return <DetailNavStackContext.Provider value={value}>{children}</DetailNavStackContext.Provider>;
}

export function useDetailNavStack(): DetailNavStackValue {
  const ctx = useContext(DetailNavStackContext);
  if (!ctx) {
    throw new Error("useDetailNavStack must be used inside <DetailNavStackProvider>");
  }
  return ctx;
}
