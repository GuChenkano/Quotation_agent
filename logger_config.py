
import logging
import time
from contextlib import contextmanager

# 1. 配置标准日志格式
# [时间戳] [级别] [模块] [阶段] - 消息
LOG_FORMAT = '%(asctime)s [%(levelname)s] [%(name)s] - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

class PhaseLogger:
    """
    辅助类：用于记录阶段耗时和状态
    """
    def __init__(self, module_name: str, logger: logging.Logger = None):
        self.module_name = module_name
        self.logger = logger or logging.getLogger(module_name)
        self.timings = {}

    @contextmanager
    def phase(self, phase_name: str):
        """
        上下文管理器：记录阶段开始和结束，计算耗时
        """
        start_time = time.time()
        self.logger.info(f"[{phase_name}] 开始")
        try:
            yield
            status = "成功"
        except Exception as e:
            status = "失败"
            self.logger.error(f"[{phase_name}] 失败: {e}")
            raise e
        finally:
            end_time = time.time()
            duration_ms = round((end_time - start_time) * 1000, 2)
            self.timings[phase_name] = self.timings.get(phase_name, 0) + duration_ms
            self.logger.info(f"[{phase_name}] {status} - 耗时: {duration_ms} ms")

    def get_timings(self):
        return self.timings
