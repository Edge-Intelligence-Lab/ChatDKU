# 日志系统使用说明

## 日志文件位置

### Backend 日志
- `backend_YYYYMMDD.log` - 所有日志（DEBUG级别）
- `backend_errors_YYYYMMDD.log` - 仅错误日志（ERROR级别）

### 日志内容
- 请求/响应详情（方法、路径、状态码、耗时）
- 错误堆栈信息
- API 调用详情

## Backend 使用方法

### 1. 在路由中使用日志

```python
from logger_config import logger

@app.route('/api/example')
def example():
    logger.info("处理示例请求")
    try:
        # 业务逻辑
        result = do_something()
        logger.debug(f"结果: {result}")
        return {"data": result}
    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        return {"error": str(e)}, 500
```

### 2. 启用请求日志中间件（可选）

在 `app/__init__.py` 中添加：

```python
from app.logging_middleware import init_logging_middleware
init_logging_middleware(app)
```

## Frontend 使用方法

```typescript
import { logger } from '@/lib/logger';

// API 调用
async function fetchData() {
  logger.logApiRequest('GET', '/api/data');

  try {
    const response = await fetch('/api/data');
    logger.logApiResponse('GET', '/api/data', response.status);
    return await response.json();
  } catch (error) {
    logger.logApiError('GET', '/api/data', error);
    throw error;
  }
}

// 错误记录
try {
  // 代码
} catch (error) {
  logger.error('操作失败', error);
}
```

## 查看日志

```bash
# 实时查看所有日志
tail -f logs/backend_*.log

# 查看错误日志
tail -f logs/backend_errors_*.log

# 搜索特定错误
grep "ERROR" logs/backend_*.log
```
