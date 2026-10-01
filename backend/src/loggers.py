import logging
import sys

debug = "debug" in sys.argv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def get_module_logger(module_name: str):
    def _get_logger():
        return logging.getLogger(module_name)

    return _get_logger
