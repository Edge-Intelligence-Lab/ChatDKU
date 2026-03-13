/**
 * 前端日志工具
 * 记录 API 调用、错误和用户操作
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

class Logger {
  private isDev = process.env.NODE_ENV === 'development';

  private formatMessage(level: LogLevel, message: string, data?: any): string {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] [${level.toUpperCase()}] ${message}`;
  }

  debug(message: string, data?: any) {
    if (this.isDev) {
      console.debug(this.formatMessage('debug', message), data || '');
    }
  }

  info(message: string, data?: any) {
    console.info(this.formatMessage('info', message), data || '');
  }

  warn(message: string, data?: any) {
    console.warn(this.formatMessage('warn', message), data || '');
  }

  error(message: string, error?: any) {
    console.error(this.formatMessage('error', message), error || '');
    if (error?.stack) {
      console.error('Stack trace:', error.stack);
    }
  }

  // API 请求日志
  logApiRequest(method: string, url: string, data?: any) {
    this.info(`API Request: ${method} ${url}`, data);
  }

  // API 响应日志
  logApiResponse(method: string, url: string, status: number, data?: any) {
    if (status >= 400) {
      this.error(`API Error: ${method} ${url} - Status ${status}`, data);
    } else {
      this.info(`API Response: ${method} ${url} - Status ${status}`);
    }
  }

  // API 错误日志
  logApiError(method: string, url: string, error: any) {
    this.error(`API Failed: ${method} ${url}`, error);
  }
}

export const logger = new Logger();
