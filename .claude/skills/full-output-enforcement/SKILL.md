---
name: full-output-enforcement
description: "Enforces complete code output. Use when Claude truncates files, writes '// ... rest of component', '// existing code here', '// continue as before', or any other placeholder that leaves the user with incomplete, non-runnable code. Activates strict rules: every file written must be fully complete, every function must be fully implemented, no ellipsis shortcuts, no deferred sections."
---

# Full Output Enforcement

You are in **full output mode**. This skill has one job: ensure every piece of code you produce is complete, runnable, and ready to paste directly into a file.

---

## The Problem This Solves

LLMs (including you) truncate output for three bad reasons:
1. **Context anxiety** — assuming the user can't handle long output
2. **Efficiency theater** — "I'll just show the changed part" (the user then has to merge manually, introducing bugs)
3. **Laziness shortcuts** — `// ... rest of existing code` is not code, it's a broken promise

None of these reasons matter. The user needs complete files.

---

## Absolute Rules (No Exceptions)

### 1. Never truncate a file
If you are writing or editing a file, output the **entire file** from line 1 to the last line. No partial outputs. No "here's the relevant section."

Banned patterns — if you type any of these, you have failed:
```
// ... rest of the component
// existing code unchanged
// ... (previous imports)
// continue as before
// ... other methods remain the same
/* rest of file */
// TODO: add remaining code
[rest of existing code]
... (unchanged)
```

### 2. Never defer implementation
If a function is mentioned, it must be implemented. If a component is listed, it must be written.

Banned patterns:
```
function doSomething() {
  // Implementation here
}

const MyComponent = () => {
  // TODO: implement
}
```

### 3. No skeleton code in final output
Skeleton code is acceptable for *planning* (showing structure before filling in). It is **never acceptable** as final deliverable.

If you wrote a skeleton for planning, fill every part before your final response.

### 4. Split files, never truncate
If a file would be very long, split it into logical modules. Each module is still complete. Never truncate a single file to manage length.

Good: "This is getting long — I'll split it into `utils.py` and `service.py`. Here is `utils.py` complete: [full file]. Here is `service.py` complete: [full file]."

Bad: "The file is long so I'll only show the changed parts."

### 5. Imports must be real
Every import in your code must refer to something that exists or is defined in the same response. No phantom imports.

```python
# Bad
from utils import magic_function  # never defined

# Good — either define magic_function or don't import it
```

---

## When Editing Existing Files

Use the **exact string replacement** pattern:
- Quote the exact lines being replaced (enough context to be unique)
- Provide the exact replacement lines
- Never say "replace the rest of the file with..."

If the edit is so large that it touches >50% of the file, output the entire new file — not a diff.

---

## Response Structure

When producing code, structure your response:

```
[Brief explanation of what you're doing — 1-3 sentences max]

**filename.ext**
```language
[complete file content — every line]
```

[Any follow-up notes — installation, next steps, caveats]
```

Do not interleave explanation paragraphs between code chunks. Complete file first, notes after.

---

## Length Is Not a Problem

If the user asked for a complete implementation, a long response is the correct response. Do not:
- Apologize for length
- Ask if they want you to continue
- Stop mid-file and offer to "show the rest"

Write it all. The user can scroll.

---

## Self-Check Before Responding

Before sending any code response, scan your output for these strings. If any appear, do not send — fix first:

- `// ...`
- `/* ... */`
- `# ...` (as placeholder, not as comment)
- `rest of`
- `existing code`
- `unchanged`
- `as before`
- `TODO`
- `[continue`
- `omitted for brevity`
- `for brevity`
- `abbreviated`

Zero occurrences = proceed. Any occurrence = fix before sending.

---

## Example: Before and After

### ❌ Truncated (unacceptable)
```python
class UserService:
    def __init__(self, db):
        self.db = db

    def get_user(self, user_id):
        # ... existing implementation

    def create_user(self, data):
        # TODO: implement
        pass

    # ... rest of methods
```

### ✅ Complete (required)
```python
class UserService:
    def __init__(self, db):
        self.db = db

    def get_user(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, data: dict) -> User:
        user = User(
            name=data['name'],
            email=data['email'],
            created_at=datetime.utcnow(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True
```
