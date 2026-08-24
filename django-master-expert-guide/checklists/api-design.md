# Django Mastery: API Design Audit Checklist

## 1. REST Conventions

- [ ] **Resource Nouns**: Use plural nouns (`/users/`, `/orders/`), not verbs (`/get_user/`).
- [ ] **HTTP Methods**: Map CRUD properly (GET = read, POST = create, PUT = full replace, PATCH = partial update, DELETE = remove).
- [ ] **Status Codes**:
  - `200 OK` for GET/PUT/PATCH.
  - `201 Created` for POST.
  - `204 No Content` for DELETE.
  - `400 Bad Request` for validation errors.
  - `401 Unauthorized` for missing/invalid auth.
  - `403 Forbidden` for missing permissions.
  - `404 Not Found` for invalid IDs/slugs.

## 2. API Scalability

- [ ] **Pagination**: Enforce on ALL list endpoints. Prefer `CursorPagination` for massive datasets (prevents OFFSET performance drops).
- [ ] **Filtering**: Use `django-filter`. Expose explicit filtering options, avoid arbitrary query parsing.
- [ ] **Rate Limiting**: Apply throttles (`AnonRateThrottle`, `UserRateThrottle`) globally and to sensitive endpoints (e.g., login, password reset).

## 3. Data Representation

- [ ] **Nesting vs Flat**: Avoid deep nesting (max 1-2 levels). Prefer returning IDs or hyperlinked URLs for related resources.
- [ ] **Consistent Errors**: Format errors consistently. Use a standard exception handler wrapper:
  ```json
  {
      "error": "validation_failed",
      "details": {
          "email": ["This field must be unique."]
      }
  }
  ```
- [ ] **Timestamps**: Return dates in ISO 8601 format (`YYYY-MM-DDThh:mm:ssZ`). Ensure timezone awareness (UTC).

## 4. Security & Safety

- [ ] **Idempotency**: Implement Idempotency-Key headers for critical POST actions (e.g., payments).
- [ ] **Mass Assignment**: Explicitly define `fields` in ModelSerializers. NEVER use `fields = '__all__'`.
- [ ] **CORS**: Audit allowed origins. Do not accept credentials cross-origin unless absolutely necessary.
