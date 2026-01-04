# 🔄 Phase 2: Queue-Based System (1K - 10K Posts/Day)

## 🎯 Overview

Phase 2 transforms your current synchronous cron job into an asynchronous queue-based system capable of handling 10,000 posts/day reliably with background processing, retry logic, and enterprise-grade error handling.

## 🏗️ Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Cron Job  │───▶│   Redis     │───▶│ Background │
│  (Producer) │    │   Queue     │    │  Workers   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│Rate Limiting│    │  Dead      │    │  Platform  │
│  (Redis)    │    │  Letter    │    │   APIs     │
└─────────────┘    │  Queue     │    └─────────────┘
                   └─────────────┘
```

## 📦 Components

### 1. Redis Queue System

```python
# queue_system.py
import redis.asyncio as redis
import json
from typing import List, Dict, Any, Optional
import asyncio

class RedisQueueSystem:
    """Redis-based queue system for reliable message processing"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.queues = {
            'high_priority': 'social_posts_high',
            'normal_priority': 'social_posts_normal',
            'low_priority': 'social_posts_low',
            'retry_queue': 'social_posts_retry',
            'dead_letter': 'social_posts_failed'
        }

    async def enqueue_posts(self, posts: List[Dict], priority: str = 'normal') -> int:
        """Add posts to queue with priority"""
        queue_name = self.queues.get(priority, self.queues['normal_priority'])

        enqueued_count = 0
        for post in posts:
            # Add metadata
            post_data = {
                'post': post,
                'enqueued_at': datetime.utcnow().isoformat(),
                'priority': priority,
                'attempts': 0,
                'max_attempts': 3,
                'next_retry_at': None
            }

            # Add to queue
            await self.redis.lpush(queue_name, json.dumps(post_data))
            enqueued_count += 1

        return enqueued_count

    async def dequeue_post(self, priority: str = 'normal') -> Optional[Dict]:
        """Get next post from queue"""
        queue_name = self.queues.get(priority, self.queues['normal_priority'])

        # Try high priority first, then normal, then low
        for queue in [self.queues['high_priority'], queue_name, self.queues['low_priority']]:
            post_data = await self.redis.rpop(queue)
            if post_data:
                return json.loads(post_data)

        return None

    async def requeue_with_delay(self, post_data: Dict, delay_seconds: int = 60):
        """Requeue post with delay for retry"""
        post_data['attempts'] += 1
        post_data['next_retry_at'] = (
            datetime.utcnow() + timedelta(seconds=delay_seconds)
        ).isoformat()

        # Use retry queue
        await self.redis.lpush(self.queues['retry_queue'], json.dumps(post_data))

    async def move_to_dead_letter(self, post_data: Dict, reason: str):
        """Move failed post to dead letter queue"""
        post_data['failed_at'] = datetime.utcnow().isoformat()
        post_data['failure_reason'] = reason

        await self.redis.lpush(self.queues['dead_letter'], json.dumps(post_data))

    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue lengths for monitoring"""
        stats = {}
        for name, queue in self.queues.items():
            length = await self.redis.llen(queue)
            stats[name] = length
        return stats
```

### 2. Rate Limiting System

```python
# rate_limiter.py
import redis.asyncio as redis
from datetime import datetime, timedelta

class PlatformRateLimiter:
    """Advanced rate limiting with Redis backend"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

        # Platform-specific rate limits (requests per hour)
        self.platform_limits = {
            'facebook': 200,
            'instagram': 100,
            'linkedin': 20,   # per day for company pages
            'youtube': 100
        }

        # Window sizes (seconds)
        self.windows = {
            'facebook': 3600,   # 1 hour
            'instagram': 3600,  # 1 hour
            'linkedin': 86400,  # 24 hours
            'youtube': 3600     # 1 hour
        }

    async def can_publish(self, platform: str, user_id: Optional[str] = None) -> bool:
        """Check if we can publish to this platform"""
        if platform not in self.platform_limits:
            return True  # No limit set

        # Create keys for global and user-specific limits
        keys = [f"rate:{platform}:global"]
        if user_id:
            keys.append(f"rate:{platform}:user:{user_id}")

        # Check each key
        for key in keys:
            current_count = await self.redis.get(key)
            current_count = int(current_count) if current_count else 0

            limit = self.platform_limits[platform]
            if current_count >= limit:
                return False

        return True

    async def record_publish(self, platform: str, user_id: Optional[str] = None):
        """Record a successful publish"""
        keys = [f"rate:{platform}:global"]
        if user_id:
            keys.append(f"rate:{platform}:user:{user_id}")

        window = self.windows.get(platform, 3600)

        # Increment counters
        for key in keys:
            await self.redis.incr(key)
            await self.redis.expire(key, window)

    async def get_remaining_capacity(self, platform: str) -> int:
        """Get remaining capacity for platform"""
        key = f"rate:{platform}:global"
        current = await self.redis.get(key)
        current = int(current) if current else 0

        limit = self.platform_limits[platform]
        return max(0, limit - current)
```

### 3. Background Worker System

```python
# background_worker.py
import asyncio
import signal
import sys
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BackgroundWorker:
    """Background worker for processing queued posts"""

    def __init__(self, worker_id: str, platform: str, queue_system, rate_limiter):
        self.worker_id = worker_id
        self.platform = platform
        self.queue = queue_system
        self.rate_limiter = rate_limiter
        self.running = False
        self.processed_count = 0
        self.error_count = 0

    async def start(self):
        """Start the worker loop"""
        self.running = True
        logger.info(f"Worker {self.worker_id} started for platform {self.platform}")

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Worker {self.worker_id} received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        try:
            while self.running:
                try:
                    # Get next post for this platform
                    post_data = await self.queue.dequeue_post(self.platform)

                    if post_data:
                        await self.process_post(post_data)
                    else:
                        # No posts available, wait before checking again
                        await asyncio.sleep(5)

                except Exception as e:
                    logger.error(f"Worker {self.worker_id} error: {e}")
                    self.error_count += 1
                    await asyncio.sleep(10)  # Back off on errors

        except Exception as e:
            logger.error(f"Worker {self.worker_id} fatal error: {e}")
        finally:
            logger.info(f"Worker {self.worker_id} stopped. Processed: {self.processed_count}, Errors: {self.error_count}")

    async def process_post(self, post_data: Dict[str, Any]):
        """Process a single post"""
        post = post_data['post']
        attempts = post_data.get('attempts', 0)

        try:
            # Check rate limits
            if not await self.rate_limiter.can_publish(self.platform, post.get('user_id')):
                logger.warning(f"Rate limit exceeded for {self.platform}, requeuing...")
                await self.queue.requeue_with_delay(post_data, delay_seconds=60)
                return

            # Publish the post
            success = await self.publish_post(post)

            if success:
                # Record successful publish
                await self.rate_limiter.record_publish(self.platform, post.get('user_id'))

                # Update database status
                await self.update_post_status(post['id'], 'published', {
                    'processed_by': self.worker_id,
                    'attempts': attempts + 1,
                    'published_at': datetime.utcnow().isoformat()
                })

                self.processed_count += 1
                logger.info(f"✅ Worker {self.worker_id} published post {post['id']}")
            else:
                # Handle failure
                await self.handle_publish_failure(post_data)

        except Exception as e:
            logger.error(f"❌ Worker {self.worker_id} failed to process post {post.get('id')}: {e}")
            await self.handle_publish_failure(post_data)

    async def publish_post(self, post: Dict) -> bool:
        """Publish post to platform (simplified version)"""
        try:
            # Import your existing publisher
            from content_publisher import ContentPublisherService

            # Initialize publisher (add proper credentials)
            publisher = ContentPublisherService(None, None)  # Add real credentials
            return await publisher.publish_created_content(post)

        except Exception as e:
            logger.error(f"Publish error for post {post.get('id')}: {e}")
            return False

    async def handle_publish_failure(self, post_data: Dict):
        """Handle publishing failure with retry logic"""
        attempts = post_data.get('attempts', 0) + 1
        max_attempts = post_data.get('max_attempts', 3)

        if attempts < max_attempts:
            # Requeue for retry with exponential backoff
            delay = 60 * (2 ** attempts)  # 1min, 2min, 4min delays
            await self.queue.requeue_with_delay(post_data, delay)
            logger.info(f"🔄 Requeued post {post_data['post']['id']} for retry {attempts}/{max_attempts}")
        else:
            # Move to dead letter queue
            await self.queue.move_to_dead_letter(
                post_data,
                f"Max retries exceeded ({max_attempts} attempts)"
            )
            logger.error(f"💀 Moved post {post_data['post']['id']} to dead letter queue")

    async def update_post_status(self, post_id: str, status: str, metadata: Dict = None):
        """Update post status in database"""
        try:
            # Add your Supabase update logic here
            # This is a placeholder - implement with your actual database code
            logger.info(f"Updated post {post_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update post {post_id} status: {e}")
```

### 4. Worker Manager

```python
# worker_manager.py
import asyncio
from typing import Dict, List
from background_worker import BackgroundWorker
from queue_system import RedisQueueSystem
from rate_limiter import PlatformRateLimiter

class WorkerManager:
    """Manages a pool of background workers"""

    def __init__(self):
        self.queue_system = RedisQueueSystem()
        self.rate_limiter = PlatformRateLimiter(self.queue_system.redis)

        # Worker configuration
        self.worker_config = {
            'facebook': 3,    # 3 workers for Facebook
            'instagram': 2,   # 2 workers for Instagram
            'linkedin': 1,    # 1 worker for LinkedIn
            'youtube': 2      # 2 workers for YouTube
        }

        self.workers: Dict[str, List[BackgroundWorker]] = {}
        self.running = False

    async def start_all_workers(self):
        """Start all platform-specific workers"""
        self.running = True
        logger.info("🚀 Starting worker pool...")

        tasks = []
        for platform, worker_count in self.worker_config.items():
            task = self.start_platform_workers(platform, worker_count)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def start_platform_workers(self, platform: str, count: int):
        """Start workers for a specific platform"""
        logger.info(f"👷 Starting {count} workers for {platform}")

        workers = []
        for i in range(count):
            worker_id = f"{platform}_worker_{i+1}"
            worker = BackgroundWorker(
                worker_id=worker_id,
                platform=platform,
                queue_system=self.queue_system,
                rate_limiter=self.rate_limiter
            )

            # Start worker in background
            worker_task = asyncio.create_task(worker.start())
            workers.append((worker, worker_task))

        self.workers[platform] = workers

        # Wait for all workers to complete (they run indefinitely)
        await asyncio.gather(*[task for _, task in workers], return_exceptions=True)

    async def stop_all_workers(self):
        """Stop all workers gracefully"""
        logger.info("🛑 Stopping all workers...")

        for platform, workers in self.workers.items():
            for worker, task in workers:
                worker.running = False
                try:
                    await asyncio.wait_for(task, timeout=10)
                except asyncio.TimeoutError:
                    logger.warning(f"Worker {worker.worker_id} didn't stop gracefully")

        self.running = False

    async def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics"""
        stats = {
            'total_workers': 0,
            'active_workers': 0,
            'processed_posts': 0,
            'error_count': 0,
            'queue_stats': await self.queue_system.get_queue_stats()
        }

        for platform, workers in self.workers.items():
            for worker, _ in workers:
                stats['total_workers'] += 1
                if worker.running:
                    stats['active_workers'] += 1
                stats['processed_posts'] += worker.processed_count
                stats['error_count'] += worker.error_count

        return stats
```

## 🚀 Usage Example

```python
# main_queue_system.py
import asyncio
from queue_system import RedisQueueSystem
from worker_manager import WorkerManager
from timezone_scheduler import TimezoneAwareScheduler

async def run_queue_based_system():
    """Run the complete queue-based publishing system"""

    # Initialize components
    queue_system = RedisQueueSystem()
    worker_manager = WorkerManager()
    scheduler = TimezoneAwareScheduler()

    # Start background workers
    worker_task = asyncio.create_task(worker_manager.start_all_workers())

    try:
        while True:
            # Run normal cron job to find due posts
            due_posts = await scheduler.find_scheduled_content_timezone_aware()

            if due_posts:
                # Filter expired posts
                valid_posts = await scheduler.filter_expired_posts(due_posts)

                if valid_posts:
                    # Enqueue posts instead of publishing immediately
                    enqueued = await queue_system.enqueue_posts(valid_posts, priority='normal')
                    print(f"📋 Enqueued {enqueued} posts for background processing")

                    # Workers will process them automatically
                    print("👷 Background workers will process posts automatically")

            # Wait before next check
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        print("🛑 Shutting down queue system...")
        await worker_manager.stop_all_workers()
        worker_task.cancel()

if __name__ == "__main__":
    asyncio.run(run_queue_based_system())
```

## 📊 Monitoring & Operations

### Health Checks

```python
# health_check.py
async def check_system_health():
    """Monitor system health"""
    manager = WorkerManager()

    stats = await manager.get_stats()

    # Alert thresholds
    alerts = []
    if stats['active_workers'] < stats['total_workers'] * 0.8:
        alerts.append("⚠️ Worker availability below 80%")

    if stats['queue_stats']['normal_priority'] > 1000:
        alerts.append("⚠️ Queue depth over 1000 posts")

    if stats['error_count'] > stats['processed_posts'] * 0.05:
        alerts.append("⚠️ Error rate over 5%")

    return {
        'status': 'healthy' if not alerts else 'warning',
        'stats': stats,
        'alerts': alerts
    }
```

### Scaling Decisions

```python
# auto_scaler.py
class AutoScaler:
    """Automatically scale workers based on queue depth"""

    def __init__(self, worker_manager):
        self.manager = worker_manager
        self.scale_thresholds = {
            'scale_up': 500,    # Add workers when queue > 500
            'scale_down': 50,   # Remove workers when queue < 50
            'max_workers': 20,  # Maximum workers per platform
            'min_workers': 1    # Minimum workers per platform
        }

    async def check_and_scale(self):
        """Check queue depths and scale workers accordingly"""
        stats = await self.manager.get_stats()

        for platform in ['facebook', 'instagram', 'linkedin', 'youtube']:
            queue_depth = stats['queue_stats'].get(f'{platform}_queue', 0)

            if queue_depth > self.scale_thresholds['scale_up']:
                await self.scale_up(platform)
            elif queue_depth < self.scale_thresholds['scale_down']:
                await self.scale_down(platform)

    async def scale_up(self, platform):
        """Add more workers for a platform"""
        current_workers = len(self.manager.workers.get(platform, []))
        if current_workers < self.scale_thresholds['max_workers']:
            # Add worker logic here
            print(f"📈 Scaling up {platform} workers to {current_workers + 1}")

    async def scale_down(self, platform):
        """Remove workers for a platform"""
        current_workers = len(self.manager.workers.get(platform, []))
        if current_workers > self.scale_thresholds['min_workers']:
            # Remove worker logic here
            print(f"📉 Scaling down {platform} workers to {current_workers - 1}")
```

## 📈 Performance Targets

| Metric | Target | Monitoring |
|--------|--------|------------|
| **Queue Depth** | < 100 posts | Redis monitoring |
| **Processing Time** | < 5 minutes | Worker metrics |
| **Success Rate** | > 99% | Error tracking |
| **Worker Utilization** | 70-90% | Performance monitoring |

## 🛠️ Deployment

### Docker Setup

```dockerfile
# Dockerfile for workers
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "background_worker.py", "--platform", "facebook"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  facebook-worker:
    build: .
    command: python background_worker.py --platform facebook
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis
    deploy:
      replicas: 3

  instagram-worker:
    build: .
    command: python background_worker.py --platform instagram
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis
    deploy:
      replicas: 2

  # Add other platform workers...
```

## 🎯 Benefits

- **Reliability**: Failed posts automatically retry
- **Scalability**: Handle traffic spikes with queue buffering
- **Monitoring**: Real-time visibility into system health
- **Error Handling**: Dead letter queues for unprocessable posts
- **Rate Limiting**: Respect platform limits automatically

## 📋 Migration Path

1. **Deploy Redis** alongside current system
2. **Add queue enqueueing** to existing cron job
3. **Deploy workers** to process queue
4. **Monitor performance** for 1 week
5. **Gradually migrate** all processing to queue system
6. **Remove old synchronous processing**

This phase provides a solid foundation for scaling to 10K posts/day with enterprise-grade reliability and error handling.
