from .memory import MemoryStorage
from .hf_bucket import HFBucketStorage
from .hf_dataset import HFDatasetStorage


def get_storage():
    from config import config
    if config.BUCKET_TYPE == "dataset" and config.HF_TOKEN:
        return HFDatasetStorage()
    if config.BUCKET_TYPE == "hf" and config.HF_TOKEN:
        return HFBucketStorage()
    return MemoryStorage()


__all__ = ["MemoryStorage", "HFBucketStorage", "HFDatasetStorage", "get_storage"]