# Exercise 06: Transactional Outbox Pattern

## The Problem
In distributed systems, microservices often need to update their own local database and then publish an event to a message broker (like Kafka or RabbitMQ) to notify other services. If this is done naively, failures can lead to inconsistencies. If the database commit succeeds but publishing the event fails, other services are unaware of the change. If publishing succeeds but the database commit fails, other services react to a change that never happened.

## Your Task
Implement the **Transactional Outbox Pattern** to guarantee reliable message delivery without requiring a two-phase commit (2PC).

### Requirements
1. **Model**: Create an `OutboxEvent` model with fields for `aggregate_type`, `aggregate_id`, `event_type`, `payload` (JSON), and `processed` (boolean).
2. **Helper**: Create a `publish_event()` function that creates an `OutboxEvent` within the current database transaction.
3. **Processor**: Create an `OutboxRelay` class that queries unprocessed events, attempts to publish them (simulate publishing with a callback), and marks them as processed.
4. Ensure the relay locks the rows using `select_for_update(skip_locked=True)` so multiple relay workers don't process the same event.
