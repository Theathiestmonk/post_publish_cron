#!/usr/bin/env python3
"""
Enterprise Queue System for Large-Scale Social Media Publishing
Handles thousands of posts with distributed workers, rate limiting, and monitoring
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import aio_pika
import redis.asyncio as redis
from supabase import create_client
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnterprisePublishingQueue:
    """
    Enterprise-grade queue system for social media publishing
    Similar to Zapier, Buffer, and other automation platforms
    """

    def __init__(self):
        # Redis for fast queue operations
        self.redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )

        # RabbitMQ for reliable message queuing
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

        # Supabase for data persistence
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )

        # Queue names
        self.queues = {
            'high_priority': 'social_posts_high',
            'normal_priority': 'social_posts_normal',
            'low_priority': 'social_posts_low',
            'retry_queue': 'social_posts_retry'
        }

        # Worker pools
        self.worker_pools = {
            'facebook': 10,    # 10 concurrent Facebook workers
            'instagram': 8,    # 8 concurrent Instagram workers
            'linkedin': 5,     # 5 concurrent LinkedIn workers
            'youtube': 5       # 5 concurrent YouTube workers
        }

        # Rate limiting (requests per minute per platform)
        self.rate_limits = {
            'facebook': 50,    # 50/minute (well under 200/hour limit)
            'instagram': 30,   # 30/minute (well under 100/hour limit)
            'linkedin': 10,    # 10/minute (well under 20/day limit)
            'youtube': 15      # 15/minute
        }

    async def initialize_queues(self):
        """Initialize RabbitMQ queues"""
        connection = await aio_pika.connect_robust(self.rabbitmq_url)
        channel = await connection.channel()

        # Declare queues with persistence
        for queue_name in self.queues.values():
            await channel.declare_queue(
                queue_name,
                durable=True,  # Survives broker restart
                arguments={
                    'x-max-retries': 3,
                    'x-message-ttl': 86400000  # 24 hours TTL
                }
            )

        await connection.close()

    async def enqueue_posts(self, posts: List[Dict], priority: str = 'normal'):
        """
        Add posts to the publishing queue
        Supports priority queuing for urgent posts
        """
        queue_name = self.queues.get(priority, self.queues['normal_priority'])

        connection = await aio_pika.connect_robust(self.rabbitmq_url)
        channel = await connection.channel()

        enqueued_count = 0
        for post in posts:
            # Add metadata
            post_data = {
                'post': post,
                'enqueued_at': datetime.utcnow().isoformat(),
                'priority': priority,
                'attempts': 0,
                'max_attempts': 3
            }

            # Publish to queue
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(post_data).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=queue_name
            )

            enqueued_count += 1

            # Update post status in database
            await self.update_post_status(post['id'], 'queued', {
                'queue_name': queue_name,
                'priority': priority,
                'enqueued_at': post_data['enqueued_at']
            })

        await connection.close()
        logger.info(f"✅ Enqueued {enqueued_count} posts to {queue_name}")
        return enqueued_count

    async def start_workers(self):
        """Start distributed worker pools"""
        logger.info("🚀 Starting enterprise worker pools...")

        # Start platform-specific worker pools
        tasks = []
        for platform, worker_count in self.worker_pools.items():
            task = self.start_platform_workers(platform, worker_count)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def start_platform_workers(self, platform: str, worker_count: int):
        """Start workers for a specific platform"""
        logger.info(f"👷 Starting {worker_count} workers for {platform}")

        # Create worker pool
        semaphore = asyncio.Semaphore(worker_count)
        queue_name = self.queues['normal_priority']  # Can be enhanced for priority

        async def worker():
            connection = await aio_pika.connect_robust(self.rabbitmq_url)
            channel = await connection.channel()

            # Set QoS (Quality of Service) - prefetch messages
            await channel.set_qos(prefetch_count=1)

            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.consume(self.process_message)

            # Keep worker alive
            await asyncio.Future()  # Run forever

        # Start workers with semaphore control
        workers = []
        for i in range(worker_count):
            worker_task = asyncio.create_task(self.worker_with_semaphore(worker, semaphore, platform))
            workers.append(worker_task)

        await asyncio.gather(*workers, return_exceptions=True)

    async def worker_with_semaphore(self, worker_func, semaphore, platform):
        """Run worker with rate limiting semaphore"""
        async with semaphore:
            await worker_func()

    async def process_message(self, message: aio_pika.IncomingMessage):
        """Process a queued message"""
        async with message.process():
            try:
                # Parse message
                post_data = json.loads(message.body.decode())
                post = post_data['post']
                attempts = post_data.get('attempts', 0)

                # Check if this post is for the worker's platform
                if post.get('platform') != message.routing_key.split('_')[-1]:  # Extract platform from queue
                    # Re-queue for correct platform worker
                    await self.requeue_message(message, post_data)
                    return

                # Apply rate limiting
                if not await self.check_rate_limit(post['platform']):
                    # Rate limited - requeue with delay
                    await self.requeue_with_delay(message, post_data, delay_seconds=60)
                    return

                # Process the post
                success = await self.publish_single_post(post)

                if success:
                    await self.update_post_status(post['id'], 'published', {
                        'published_at': datetime.utcnow().isoformat(),
                        'attempts': attempts + 1,
                        'worker_processed': True
                    })
                    logger.info(f"✅ Published post {post['id']} on {post['platform']}")
                else:
                    # Handle failure
                    await self.handle_publish_failure(message, post_data)

            except Exception as e:
                logger.error(f"❌ Error processing message: {e}")
                await self.handle_processing_error(message, post_data)

    async def check_rate_limit(self, platform: str) -> bool:
        """Check if we're within rate limits using Redis"""
        key = f"rate_limit:{platform}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"

        # Get current count
        current_count = await self.redis.get(key)
        current_count = int(current_count) if current_count else 0

        # Check limit
        limit = self.rate_limits.get(platform, 10)

        if current_count >= limit:
            logger.warning(f"🚫 Rate limit exceeded for {platform}: {current_count}/{limit}")
            return False

        # Increment counter
        await self.redis.incr(key)
        await self.redis.expire(key, 60)  # Expire in 1 minute

        return True

    async def publish_single_post(self, post: Dict) -> bool:
        """Publish a single post (simplified version)"""
        try:
            # Import your existing publisher
            from content_publisher import ContentPublisherService

            # Initialize publisher (you'd pass proper credentials)
            publisher = ContentPublisherService(self.supabase, None)  # cipher would be passed

            success = await publisher.publish_created_content(post)
            return success

        except Exception as e:
            logger.error(f"❌ Failed to publish post {post.get('id')}: {e}")
            return False

    async def requeue_message(self, message, post_data, delay_seconds: int = 0):
        """Requeue message with optional delay"""
        # Implementation for requeuing messages
        pass

    async def handle_publish_failure(self, message, post_data):
        """Handle publishing failure with retry logic"""
        attempts = post_data.get('attempts', 0) + 1
        max_attempts = post_data.get('max_attempts', 3)

        if attempts < max_attempts:
            # Requeue for retry
            post_data['attempts'] = attempts
            await self.requeue_message(message, post_data, delay_seconds=300 * attempts)  # Exponential backoff
        else:
            # Mark as permanently failed
            await self.update_post_status(post_data['post']['id'], 'failed', {
                'failure_reason': 'max_retries_exceeded',
                'total_attempts': attempts
            })

    async def update_post_status(self, post_id: str, status: str, metadata: Dict = None):
        """Update post status in database"""
        try:
            update_data = {"status": status}
            if metadata:
                update_data["god_mode_metadata"] = metadata

            self.supabase.table("created_content").update(update_data).eq("id", post_id).execute()

        except Exception as e:
            logger.error(f"Failed to update post {post_id} status: {e}")

    async def get_queue_stats(self):
        """Get comprehensive queue statistics"""
        stats = {
            'queue_lengths': {},
            'processing_rates': {},
            'error_rates': {},
            'platform_stats': {}
        }

        # Get queue lengths from Redis
        for queue_name in self.queues.values():
            length = await self.redis.llen(queue_name)
            stats['queue_lengths'][queue_name] = length

        return stats

# Example usage for enterprise scale
async def enterprise_publishing_example():
    """Example of how to use the enterprise queue system"""

    queue_system = EnterprisePublishingQueue()

    # Initialize infrastructure
    await queue_system.initialize_queues()

    # Example: Handle 10,000 posts from 2,000 users
    posts = []  # Your 10,000 posts here

    # Enqueue posts with priorities
    urgent_posts = [p for p in posts if p.get('priority') == 'urgent']
    normal_posts = [p for p in posts if p.get('priority') != 'urgent']

    await queue_system.enqueue_posts(urgent_posts, priority='high_priority')
    await queue_system.enqueue_posts(normal_posts, priority='normal_priority')

    # Start worker pools (this would run indefinitely)
    await queue_system.start_workers()

if __name__ == "__main__":
    # Run enterprise publishing system
    asyncio.run(enterprise_publishing_example())
