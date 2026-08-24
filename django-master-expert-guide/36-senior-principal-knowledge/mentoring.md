# Mentoring: Building Engineering Culture

## Mental Model
A senior engineer writes great code. A Staff engineer builds great engineers. Mentoring is not about answering questions; it's about transferring your mental models so juniors can answer their own questions.

```text
[ Give Answer ] -> Dependency
[ Teach Mental Model ] -> Autonomy
```

## 1. The Code Review Culture

### The Anti-Pattern: "Nitpicking"
- Leaving 40 comments on variable names, PEP8 spacing, and syntax.
- **Result:** The junior engineer feels attacked, learns nothing about architecture, and relies on the senior as a human linter.

### The Production Implementation: "Structural Review"
- Use automated tools (Ruff, Black, Mypy) to eliminate all style discussions.
- Focus review on the 30-Point Framework: Security, Performance, Concurrency.

**Example Comment:**
> ❌ "Rename `lst` to `users_list`."
> ✅ "I notice we're pulling this queryset into memory on line 45, but the table has 2M rows. What happens if this endpoint gets hit by 10 concurrent users? Let's pair on using `iterator()` here."

## 2. Leveling Up Engineers (The Framework)

1. **The "I Do, You Watch" Phase**
   Pair programming where the senior drives. The senior explicitly verbalizes their internal monologue ("I'm checking the DB indexes because...").

2. **The "You Do, I Watch" Phase**
   The junior drives. The senior asks questions instead of giving commands ("Why did you choose a List API view here?").

3. **The "You Do, I Review" Phase**
   Standard async PR process.

## 3. Creating Safety

- **Celebrate Failure:** When a junior takes down production, the Staff engineer's response must be: "Fascinating! How did our CI pipeline allow this? Let's fix the pipeline together."
- **Blameless Post-Mortems:** Focus on the system, never the human.
