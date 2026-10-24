"use client";

import { Component, type ReactNode } from "react";

// Keeps one failing panel from blanking the whole app; shows one line and "Try again".
export default class ErrorBoundary extends Component<{ children: ReactNode; label?: string }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="m-4 flex items-center gap-3 rounded-[12px] border border-line bg-surface p-3 text-[14px]">
          <span>{this.props.label ?? "Something went wrong here."}</span>
          <button className="ml-auto rounded-[8px] border border-line px-3 py-1.5" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
