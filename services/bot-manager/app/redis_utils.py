import redis.asyncio as redis
import logging
from config import REDIS_URL
from typing import Optional

logger = logging.getLogger(__name__)
redis_client = None

async def init_redis():
    """Initializes the Redis client connection."""
    global redis_client
    if redis_client is None:
        try:
            logger.info(f"Connecting to Redis at {REDIS_URL}")
            redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("Successfully connected to Redis and pinged.")
        except Exception as e:
            logger.critical(f"Could not connect to Redis: {e}", exc_info=True)
            redis_client = None
            raise

async def close_redis():
    """Closes the Redis client connection."""
    global redis_client
    if redis_client:
        logger.info("Closing Redis connection.")
        await redis_client.close()
        redis_client = None

def get_redis_client():
    """Returns the initialized Redis client."""
    if redis_client is None:
        logger.error("Redis client requested before initialization.")
    return redis_client 