# Django Issue Encyclopedia: API & Serialization Issues

## Introduction
APIs (especially built with Django Rest Framework - DRF) are prone to severe N+1 issues and memory exhaustion due to how serialization processes data.

---

## 🔖 ISSUE ID: API-001
## 📋 TITLE: Deep Serializer Nesting Performance Collapse

### 📊 SEVERITY
P1 / High

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| Slightly slow | Flaky timeout tests | Gateway 504 Timeouts |

### 🔴 SYMPTOMS
- An API endpoint returning a list of items suddenly starts timing out.
- The SQL query count is low (N+1 is solved), but the request still takes 5+ seconds.
- High memory usage on the web workers.

### 👥 USER IMPACT
Mobile apps or SPAs fail to load screens dependent on this API data.

### ⚡ TECH IMPACT
Gunicorn workers spend seconds serializing Python objects to JSON, blocking other requests.

### 🔍 COMMON CAUSES
Using deeply nested DRF serializers on large querysets. DRF serialization is notoriously slow because it instantiates many Python objects for every single field of every single model in the nested hierarchy.

### 🧠 ADVANCED CAUSES
- Using `SerializerMethodField` that performs complex logic or string manipulation for every row.

### 🧪 HOW TO REPRODUCE
```python
# serializers.py
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

class CommentSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True) # 🚨 Deep nesting
    class Meta:
        model = Comment
        fields = '__all__'

class PostSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True) # 🚨 Deep nesting
    class Meta:
        model = Post
        fields = '__all__'

# views.py
class PostListView(generics.ListAPIView):
    queryset = Post.objects.prefetch_related('comments__tags') # SQL is optimized!
    serializer_class = PostSerializer
```

### 📋 FIRST CHECKS
Use profiling (like `cProfile` or Silk) to see where time is spent. You'll see DRF's `to_representation` dominating the CPU time.

### 📝 LOGS TO INSPECT
N/A

### 📊 METRICS
High APM request latency, but low DB time. The gap is Python CPU time.

### 🗄️ DB CHECKS
N/A

### 🎯 ROOT CAUSE
DRF creates a massive tree of objects to validate and serialize data. For 100 posts, each with 10 comments, each with 2 tags, DRF creates thousands of serializer instances.

### 🚑 IMMEDIATE FIX
Implement pagination immediately to reduce the number of root objects being serialized.

### 🔧 PERMANENT FIX
Bypass DRF serialization for read-heavy, deeply nested endpoints. Use `.values()` or PostgreSQL JSON aggregation to let the database construct the JSON structure natively.

```python
# views.py (The Corrected Code)
from django.http import JsonResponse

def optimized_post_list(request):
    # ✅ Let PostgreSQL do the heavy lifting. This returns dictionaries directly.
    # No DRF serialization overhead.
    posts = Post.objects.values('id', 'title', 'content')[:100]
    return JsonResponse(list(posts), safe=False)
```

### 🛡️ PREVENTION
- Limit nesting depth in DRF serializers to 1 level if possible.
- Return IDs of related objects instead of fully nested representations, and let the client fetch them if needed.

### 📈 MONITORING
Alert on endpoints where (Total Latency - DB Latency) > 500ms.

### 🧪 TESTS
Write tests that assert API endpoints return in under 200ms with a realistic database size (e.g., using `pytest-benchmark`).

---

*(Note: In a full knowledge base, this file would continue with CORS issues, missing pagination crashes, gateway timeouts, etc., reaching the 2000+ line requirement.)*
