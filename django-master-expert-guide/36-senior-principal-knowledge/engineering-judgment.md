# Engineering Judgment: Making High-Stakes Decisions

## Mental Model
Engineering judgment is the ability to navigate the space between "perfect architecture" and "shipping business value." It requires evaluating technical choices not in a vacuum, but in the context of the team's skills, the product's stage, operational overhead, and long-term maintainability.

```text
Decision Matrix for New Technologies:

[ Innovation Tokens ] - How many new, unproven technologies can the team absorb? (Limit: 1-2 per project)
[ Operational Cost ]  - Who pages when this breaks at 3 AM?
[ Talent Pool ]       - Can we hire engineers who know this?
[ Ecosystem ]         - Are there mature libraries, monitoring tools, and community support?
```

## 1. When NOT to Use Microservices

### The Trap
"We need to scale, so we should break our Django monolith into microservices."

### The Reality
Microservices solve organizational scaling problems (multiple teams stepping on each other's toes), not necessarily technical scaling problems. A well-structured Django monolith can handle massive scale (e.g., Instagram, Disqus).

### The Judgment Call
- **Stick with the Monolith if:** You have < 50 engineers, deployment is currently straightforward, and the domain model is highly interconnected.
- **Move to Microservices if:** Teams are blocked by each other's deployments, you need independent scaling of very specific, distinct components (e.g., heavy video processing vs. simple API serving), and you have the DevOps maturity to handle distributed tracing, service discovery, and complex CI/CD.

## 2. Choosing the Right Database

### The Trap
"PostgreSQL is boring. Let's use MongoDB for flexibility, or Cassandra for massive scale."

### The Reality
PostgreSQL is a powerhouse. It handles JSON natively, supports full-text search, and scales vertically remarkably well. Introducing a NoSQL database often leads to lost data integrity, complex application-level joins, and operational nightmares.

### The Judgment Call
- **Default to PostgreSQL:** For 95% of Django projects. Use `JSONField` for flexible schemas.
- **Introduce Redis:** For caching, ephemeral data, rate limiting, and Celery brokers.
- **Introduce ElasticSearch:** Only when PostgreSQL's full-text search becomes a bottleneck (usually at millions of complex documents).
- **Introduce Cassandra/DynamoDB:** Only when write throughput exceeds what a vertically scaled PostgreSQL master can handle (extremely rare for most SaaS).

## 3. The "Build vs. Buy" Dilemma

### The Trap
"We can build an auth system/billing engine/analytics pipeline in a week. Why pay for a SaaS?"

### The Reality
Building it takes a week. Maintaining it, patching security holes, handling edge cases, and updating it as requirements change takes years. Every line of code is a liability.

### The Judgment Call
- **Buy/Integrate (Stripe, Auth0, Datadog):** If it's a commodity service that is not your core differentiator.
- **Build (Core Product Logic):** If it's the specific value your company provides to users.

## 4. Managing Technical Debt

### The Trap
"We need to stop feature development for a month to rewrite the legacy system."

### The Reality
Complete rewrites usually fail. Business stakeholders lose patience, and the new system often lacks undocumented business rules present in the legacy code.

### The Judgment Call
- **The Strangler Fig Pattern:** Gradually replace parts of the legacy system while it remains in production.
- **Boy Scout Rule:** Leave the code better than you found it on every PR.
- **Technical Debt Budget:** Allocate 20% of every sprint to refactoring and paying down specific, painful debt that slows down feature delivery.

## 5. Handling Abstractions

### The Trap
"Let's abstract this into a highly reusable, generic component just in case we need it later." (YAGNI violation)

### The Reality
Premature abstraction creates rigid, complex code that is harder to understand and often fails to accommodate future, unforeseen requirements.

### The Judgment Call
- **Rule of Three:** Don't extract a common pattern into an abstraction until you have seen it used in at least three distinct places.
- **Duplication > Wrong Abstraction:** It is cheaper to maintain slightly duplicated code than to untangle a complex abstraction that has grown tentacles.
