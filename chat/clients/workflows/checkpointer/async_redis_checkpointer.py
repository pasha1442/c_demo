from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
)
from typing import (
    Any,
    AsyncIterator,
    AsyncGenerator,
    List,
    Optional,
    Tuple,
)
from contextlib import asynccontextmanager, contextmanager
from langchain_core.runnables import RunnableConfig
from backend.services.cache_service import CacheService
from chat.clients.workflows.checkpointer.base_redis_checkpointer import BaseRedisCheckpointer



class AsyncRedisCheckpointer(BaseCheckpointSaver, BaseRedisCheckpointer):
    """Async redis-based checkpoint saver implementation."""

    def __init__(self, cache_db=None):
        super().__init__()

        self.cache_service = CacheService(CacheService.CACHE_DB_WORKFLOW_STATUS_CACHE)
        self.key_expiry = CacheService.DEFAULT_KEY_EXPIRY_SECONDS

    @classmethod
    @asynccontextmanager
    async def from_conn_info(
        cls, *, host: str, port: int, db: int
    ) -> AsyncIterator["AsyncRedisCheckpointer"]:
        try:
            # For backward compatibility, we'll use the workflow status cache
            yield AsyncRedisCheckpointer(CacheService.CACHE_DB_WORKFLOW_STATUS_CACHE)
        finally:
            pass

    @classmethod
    def from_cache_service(cls, cache_db=None):
        """
        Alternative constructor to create an instance using CacheService.
        
        Args:
            cache_db (str, optional): The cache database alias from Django settings.
        
        Returns:
            AsyncRedisCheckpointer: An instance of AsyncRedisCheckpointer.
        """
        return cls(cache_db)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database asynchronously.

        This method saves a checkpoint to Redis. The checkpoint is associated
        with the provided config and its parent config (if any).

        Args:
            config (RunnableConfig): The config to associate with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to save.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        key = self._make_redis_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)

        type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        serialized_metadata = self.serde.dumps(metadata)
        data = {
            "checkpoint": serialized_checkpoint,
            "type": type_,
            "checkpoint_id": checkpoint_id,
            "metadata": serialized_metadata,
            "parent_checkpoint_id": parent_checkpoint_id
            if parent_checkpoint_id
            else "",
        }

        # Use individual hset calls since cache_service doesn't support mapping
        for field, value in data.items():
            self.cache_service.hset(key, field, value, expiry=self.key_expiry)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Store intermediate writes linked to a checkpoint asynchronously.

        This method saves intermediate writes associated with a checkpoint to the database.

        Args:
            config (RunnableConfig): Configuration of the related checkpoint.
            writes (Sequence[Tuple[str, Any]]): List of writes to store, each as (channel, value) pair.
            task_id (str): Identifier for the task creating the writes.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = config["configurable"]["checkpoint_id"]

        for idx, (channel, value) in enumerate(writes):
            key = self._make_redis_checkpoint_writes_key(
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                task_id,
                WRITES_IDX_MAP.get(channel, idx),
            )
            type_, serialized_value = self.serde.dumps_typed(value)
            data = {"channel": channel, "type": type_, "value": serialized_value}
            if all(w[0] in WRITES_IDX_MAP for w in writes):
                # Use HSET which will overwrite existing values
                for field, value in data.items():
                    self.cache_service.hset(key, field, value, expiry=self.key_expiry)
            else:
                # Use HSETNX which will not overwrite existing values
                for field, value in data.items():
                    self.cache_service.hsetnx(key, field, value, expiry=self.key_expiry)

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from Redis asynchronously.

        This method retrieves a checkpoint tuple from Redis based on the
        provided config. If the config contains a "checkpoint_id" key, the checkpoint with
        the matching thread ID and checkpoint ID is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config (RunnableConfig): The config to use for retrieving the checkpoint.

        Returns:
            Optional[CheckpointTuple]: The retrieved checkpoint tuple, or None if no matching checkpoint was found.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        checkpoint_key = await self._aget_checkpoint_key(
            self.cache_service, thread_id, checkpoint_ns, checkpoint_id
        )
        if not checkpoint_key:
            return None

        checkpoint_data = self.cache_service.hgetall(checkpoint_key)

        # load pending writes
        checkpoint_id = (
            checkpoint_id
            or self._parse_redis_checkpoint_key(checkpoint_key)["checkpoint_id"]
        )
        pending_writes = await self._aload_pending_writes(
            thread_id, checkpoint_ns, checkpoint_id
        )
        return self._parse_redis_checkpoint_data(
            self.serde, checkpoint_key, checkpoint_data, pending_writes=pending_writes
        )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        # TODO: implement filtering
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncGenerator[CheckpointTuple, None]:
        """List checkpoints from Redis asynchronously.

        This method retrieves a list of checkpoint tuples from Redis based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

        Args:
            config (Optional[RunnableConfig]): Base configuration for filtering checkpoints.
            filter (Optional[Dict[str, Any]]): Additional filtering criteria for metadata.
            before (Optional[RunnableConfig]): If provided, only checkpoints before the specified checkpoint ID are returned. Defaults to None.
            limit (Optional[int]): Maximum number of checkpoints to return.

        Yields:
            AsyncIterator[CheckpointTuple]: An asynchronous iterator of matching checkpoint tuples.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        pattern = self._make_redis_checkpoint_key(thread_id, checkpoint_ns, "*")
        keys = self._filter_keys(self.cache_service.keys(pattern), before, limit)
        for key in keys:
            data = self.cache_service.hgetall(key)
            if data and b"checkpoint" in data and b"metadata" in data:
                checkpoint_id = self._parse_redis_checkpoint_key(key.decode())[
                    "checkpoint_id"
                ]
                pending_writes = await self._aload_pending_writes(
                    thread_id, checkpoint_ns, checkpoint_id
                )
                yield self._parse_redis_checkpoint_data(
                    self.serde, key.decode(), data, pending_writes=pending_writes
                )

    async def _aload_pending_writes(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> List[PendingWrite]:
        writes_key = self._make_redis_checkpoint_writes_key(
            thread_id, checkpoint_ns, checkpoint_id, "*", None
        )
        matching_keys = self.cache_service.keys(pattern=writes_key)
        parsed_keys = [
            self._parse_redis_checkpoint_writes_key(key.decode()) for key in matching_keys
        ]
        pending_writes = self._load_writes(
            self.serde,
            {
                (parsed_key["task_id"], parsed_key["idx"]): self.cache_service.hgetall(key)
                for key, parsed_key in sorted(
                    zip(matching_keys, parsed_keys), key=lambda x: x[1]["idx"]
                )
            },
        )
        return pending_writes

    async def _aget_checkpoint_key(
        self, cache_service, thread_id: str, checkpoint_ns: str, checkpoint_id: Optional[str]
    ) -> Optional[str]:
        """Asynchronously determine the Redis key for a checkpoint."""
        if checkpoint_id:
            return self._make_redis_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)

        all_keys = cache_service.keys(
            self._make_redis_checkpoint_key(thread_id, checkpoint_ns, "*")
        )
        if not all_keys:
            return None

        latest_key = max(
            all_keys,
            key=lambda k: self._parse_redis_checkpoint_key(k.decode())["checkpoint_id"],
        )
        return latest_key.decode()