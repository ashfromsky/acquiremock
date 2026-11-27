import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Button } from './ui/Button';
import styles from './ErrorBoundary.module.css';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    message: '',
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || 'An unexpected rendering error occurred.',
    };
  }

  componentDidCatch(_error: Error, _errorInfo: ErrorInfo): void {
  }

  private handleReset = () => {
    this.setState({ hasError: false, message: '' });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className={styles.wrap} role="alert">
          <div className={styles.card}>
            <h1 className={styles.title}>Something went wrong</h1>
            <p className={styles.message}>{this.state.message}</p>
            <div className={styles.actions}>
              <Button variant="primary" onClick={this.handleReset}>
                Try again
              </Button>
              <Button variant="secondary" onClick={() => window.location.assign('/')}>
                Return home
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
