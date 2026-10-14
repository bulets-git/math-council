'use client';

import React, { Component, ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

interface ErrorBoundaryProps {
  fallbackText: string;
  className?: string;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class MathErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.warn('MathRenderer render error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className={`whitespace-pre-wrap font-sans text-slate-800 ${this.props.className || ''}`}>
          {this.props.fallbackText}
        </div>
      );
    }
    return this.props.children;
  }
}

interface MathRendererProps {
  content: string;
  className?: string;
}

export function MathRenderer({ content, className = '' }: MathRendererProps) {
  if (!content) return null;

  return (
    <MathErrorBoundary fallbackText={content} className={className}>
      <div className={`math-renderer leading-relaxed text-slate-800 break-words ${className}`}>
        <ReactMarkdown
          remarkPlugins={[remarkMath]}
          rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        >
          {content}
        </ReactMarkdown>
      </div>
    </MathErrorBoundary>
  );
}

export default MathRenderer;
