"""Implementation of a langgraph checkpoint saver using Redis."""
from typing import (
    List,
    Optional
)

from langchain_core.runnables import RunnableConfig

from langgraph.checkpoint.base import (
    PendingWrite,
    CheckpointTuple
)
from langgraph.checkpoint.serde.base import SerializerProtocol

class BaseRedisCheckpointer:
    """Base class for Redis checkpoint operations."""
    
    REDIS_KEY_SEPARATOR = "$"

    def __init__(self):
        """Initialize BaseRedisCheckpointer."""
        pass
    
    def _make_redis_checkpoint_key(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> str:
        return self.REDIS_KEY_SEPARATOR.join(
            ["checkpoint", thread_id, checkpoint_ns, checkpoint_id]
        )

    def _make_redis_checkpoint_writes_key(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        idx: Optional[int],
    ) -> str:
        if idx is None:
            return self.REDIS_KEY_SEPARATOR.join(
                ["writes", thread_id, checkpoint_ns, checkpoint_id, task_id]
            )

        return self.REDIS_KEY_SEPARATOR.join(
            ["writes", thread_id, checkpoint_ns, checkpoint_id, task_id, str(idx)]
        )

    def _parse_redis_checkpoint_key(self, redis_key: str) -> dict:
        namespace, thread_id, checkpoint_ns, checkpoint_id = redis_key.split(
            self.REDIS_KEY_SEPARATOR
        )
        if namespace != "checkpoint":
            raise ValueError("Expected checkpoint key to start with 'checkpoint'")

        return {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        }

    def _parse_redis_checkpoint_writes_key(self, redis_key: str) -> dict:
        namespace, thread_id, checkpoint_ns, checkpoint_id, task_id, idx = redis_key.split(
            self.REDIS_KEY_SEPARATOR
        )
        if namespace != "writes":
            raise ValueError("Expected checkpoint key to start with 'checkpoint'")

        return {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "task_id": task_id,
            "idx": idx,
        }

    def _filter_keys(
        self, keys: List[str], before: Optional[RunnableConfig], limit: Optional[int]
    ) -> list:
        """Filter and sort Redis keys based on optional criteria."""
        if before:
            keys = [
                k
                for k in keys
                if self._parse_redis_checkpoint_key(k.decode())["checkpoint_id"]
                < before["configurable"]["checkpoint_id"]
            ]

        keys = sorted(
            keys,
            key=lambda k: self._parse_redis_checkpoint_key(k.decode())["checkpoint_id"],
            reverse=True,
        )
        if limit:
            keys = keys[:limit]
        return keys

    def _load_writes(
        self, serde: SerializerProtocol, task_id_to_data: dict[tuple[str, str], dict]
    ) -> list[PendingWrite]:
        """Deserialize pending writes."""
        writes = [
            (
                task_id,
                data[b"channel"].decode(),
                serde.loads_typed((data[b"type"].decode(), data[b"value"])),
            )
            for (task_id, _), data in task_id_to_data.items()
        ]
        return writes

    def _parse_redis_checkpoint_data(
        self,
        serde: SerializerProtocol,
        key: str,
        data: dict,
        pending_writes: Optional[List[PendingWrite]] = None,
    ) -> Optional[CheckpointTuple]:
        """Parse checkpoint data retrieved from Redis."""
        if not data:
            return None

        parsed_key = self._parse_redis_checkpoint_key(key)
        thread_id = parsed_key["thread_id"]
        checkpoint_ns = parsed_key["checkpoint_ns"]
        checkpoint_id = parsed_key["checkpoint_id"]
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

        checkpoint = serde.loads_typed((data[b"type"].decode(), data[b"checkpoint"]))
        metadata = serde.loads(data[b"metadata"].decode())
        parent_checkpoint_id = data.get(b"parent_checkpoint_id", b"").decode()
        parent_config = (
            {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_checkpoint_id,
                }
            }
            if parent_checkpoint_id
            else None
        )
        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )