# Django System Design Interview Scenarios

## Mental Model
System design interviews for Django roles test your ability to take a high-level requirement and map it to a scalable, resilient architecture using Django and its ecosystem (PostgreSQL, Redis, Celery, Load Balancers, etc.).

```text
[ Requirements ] -> [ Capacity Estimation ] -> [ High-Level Design ] -> [ API & DB Schema ] -> [ Deep Dives & Bottlenecks ]
```

## Scenario 1: Design a Twitter-like Feed System in Django

### 1. Requirements Clarification
- **Functional:** Users can post tweets, follow other users, and view a timeline of tweets from users they follow.
- **Non-Functional:** High read throughput (timeline), fast write (posting), low latency. Highly available.

### 2. High-Level Design
- **Clients:** Web/Mobile
- **Load Balancer:** Nginx / AWS ALB
- **Web Tier:** Gunicorn running Django application
- **Database:** PostgreSQL (Primary-Replica setup)
- **Cache:** Redis
- **Background Workers:** Celery (for fanout)

### 3. Database Schema (Django Models)
```python
class User(AbstractUser):
    # standard fields
    pass

class Follow(models.Model):
    follower = models.ForeignKey(User, related_name='following')
    followed = models.ForeignKey(User, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('follower', 'followed')

class Tweet(models.Model):
    author = models.ForeignKey(User)
    content = models.CharField(max_length=280)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

### 4. Deep Dive: The Timeline Generation Problem
**Problem:** A user follows 1000 people. Querying all their tweets and sorting by time on every request is too slow (N+1, massive joins).

**Solution A: Pull Model (Read-Heavy)**
- Calculate timeline on the fly.
- `Tweet.objects.filter(author__in=user.following.all()).order_by('-created_at')[:20]`
- **Pros:** Storage efficient.
- **Cons:** High latency for users following many people.

**Solution B: Push Model / Fanout-on-Write (Write-Heavy)**
- When a user posts a tweet, asynchronously push the tweet ID to the Redis timelines of all their followers.
- Django + Celery Implementation:
```python
# In views.py
def post_tweet(request):
    tweet = Tweet.objects.create(author=request.user, content=...)
    fanout_tweet.delay(tweet.id, request.user.id)

# In tasks.py
@shared_task
def fanout_tweet(tweet_id, author_id):
    followers = Follow.objects.filter(followed_id=author_id).values_list('follower_id', flat=True)
    
    # Redis pipeline for efficiency
    pipeline = redis_client.pipeline()
    for follower_id in followers:
        key = f"timeline:{follower_id}"
        pipeline.lpush(key, tweet_id)
        pipeline.ltrim(key, 0, 999) # Keep only latest 1000
    pipeline.execute()
```
- **Pros:** Read latency is O(1) from Redis.
- **Cons:** "Justin Bieber problem" - if a user has 100M followers, fanout takes too long and uses too much memory.

**Solution C: Hybrid Approach (Production Standard)**
- Use Push model for active users and small accounts.
- Use Pull model for celebrities. When fetching a timeline, merge the Redis timeline (normal accounts) with a DB query for celebrity tweets.

## Scenario 2: Design a Flash Sale / High-Concurrency Ticketing System

### 1. Requirements
- Sell 10,000 concert tickets.
- 1,000,000 users trying to buy exactly at 12:00 PM.
- Must not oversell (strict consistency).

### 2. Bottlenecks
- Thundering herd problem on the database.
- Row-level lock contention on the `Event` inventory counter.

### 3. Architecture & Mitigation
- **Rate Limiting:** Drop traffic aggressively at the CDN/Load Balancer layer.
- **Queueing System:** Put users in a virtual waiting room.

### 4. Database Strategy (Django)
**Anti-Pattern:**
```python
ticket_count = Event.objects.get(id=event_id).available_tickets
if ticket_count > 0:
    # Do payment
    event.available_tickets -= 1
    event.save() # RACE CONDITION! Oversell guaranteed.
```

**Production Implementation (Redis + Postgres):**
1. Pre-load inventory into Redis: `SET event:123:tickets 10000`
2. Use Redis atomic decrement (LUA script) to claim a ticket quickly.
3. If successful, enqueue a Celery task to process payment and update Postgres.

```python
# Atomic Redis claim
def claim_ticket(event_id, user_id):
    # LUA script ensures atomic check-and-set
    script = """
    local tickets = tonumber(redis.call('get', KEYS[1]))
    if tickets and tickets > 0 then
        redis.call('decr', KEYS[1])
        return 1
    else
        return 0
    end
    """
    key = f"event:{event_id}:tickets"
    success = redis_client.eval(script, 1, key)
    
    if success:
        process_payment_task.delay(event_id, user_id)
        return "Ticket claimed, pending payment."
    return "Sold out."
```
