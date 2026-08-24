# The Staff+ Engineering Track

## Mental Model
The transition from Senior to Staff is not just writing faster or better code. It is a fundamental role change. You move from solving well-defined problems to defining the problems themselves.

```text
Junior -> Mid -> Senior : Execution Focus (How do we build this?)
Senior -> Staff -> Principal : Strategy Focus (What should we build, and why?)
```

## 1. Influence Without Authority

Staff engineers do not manage people (usually), yet they are expected to change the behavior of dozens of engineers.

### The Anti-Pattern
"I am the Staff Engineer. We are moving to GraphQL because I said so." (Dictatorship fails when people just quietly ignore you).

### The Production Implementation
1. **Gather Data:** Document the pain points of the current REST API (e.g., over-fetching, N+1s).
2. **Write an RFC:** Propose the solution and solicit feedback.
3. **Build a Champion Network:** Get buy-in from Senior engineers on individual teams.
4. **Create Paved Roads:** Build the tooling so that doing the "new right thing" is easier than doing the "old wrong thing."

## 2. Technical Strategy

Your job is to look 1-3 years ahead.
- If we continue growing at this rate, when does our PostgreSQL primary run out of write capacity?
- Our frontend team is moving to Next.js. How does our Django auth strategy need to evolve to support Server-Side Rendering?
- We have 3 different ways of sending emails. I need to consolidate this into a single internal service.

## 3. The Staff Archetypes (Will Larson Model)
- **The Tech Lead:** Guides the approach and execution of a specific team.
- **The Architect:** Responsible for the direction, quality, and approach across a critical area (e.g., Data Infrastructure).
- **The Solver:** Plunges into complex, cross-team fires and solves them (e.g., finding the memory leak taking down the monolith).
- **The Right Hand:** Borrows executive authority to solve deep organizational problems (e.g., redesigning the deployment pipeline for the VP of Engineering).
