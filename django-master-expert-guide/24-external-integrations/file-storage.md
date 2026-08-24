# File Storage in Django (Cloud & Presigned URLs)

## 1. Mental Model
```text
[Client] --(Upload request)--> [Django]
                                  | (Generates Presigned POST URL)
                                  v
[Client] --(Direct multipart upload)--> [Cloud Storage (S3 / GCS)]
                                                |
[Client] <--(File URL)--------------------------+
```
Django's default storage saves files to the local disk. In a containerized/cloud environment, local disks are ephemeral (data is lost on restart). You must offload files to Cloud Storage. Furthermore, piping large file uploads through Django blocks worker threads; direct-to-cloud uploads are preferred.

## 2. Why It Exists
If a user uploads a 50MB video directly to Django, a Gunicorn worker is tied up for the entire duration of the upload. By using `django-storages`, Django acts only as an orchestrator—generating secure, temporary URLs that allow the client to upload directly to S3.

## 3. Internal Working
Django abstracts storage via the `DEFAULT_FILE_STORAGE` backend. When you call `model_instance.file.save()`, Django delegates the byte transfer to the configured backend (e.g., `storages.backends.s3boto3.S3Boto3Storage`).

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: Local storage in a Docker container
# settings.py
MEDIA_ROOT = '/app/media/'
MEDIA_URL = '/media/'
# When the container scales down or restarts, all user avatars are permanently deleted!
```

## 5. Production-Ready Implementation
**1. Django Storages Configuration (S3)**
```python
# ✅ PRODUCTION-READY (settings.py)
INSTALLED_APPS += ['storages']

# S3 Configuration
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# Force unique filenames to prevent overwrites
AWS_S3_FILE_OVERWRITE = False

# Use S3 for User Uploads
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

**2. Direct-to-S3 Upload (Presigned URLs)**
```python
import boto3
from django.conf import settings
from django.http import JsonResponse

def generate_presigned_url(request):
    """
    Returns a secure URL the frontend can use to upload directly to S3,
    bypassing Django entirely.
    """
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    filename = f"uploads/{request.user.id}/{request.GET.get('filename')}"
    
    response = s3_client.generate_presigned_post(
        settings.AWS_STORAGE_BUCKET_NAME,
        filename,
        Conditions=[
            ["content-length-range", 1, 10485760] # Max 10MB
        ],
        ExpiresIn=3600 # URL valid for 1 hour
    )
    
    return JsonResponse(response)
```

## 6. Anti-Patterns
🔴 **Serving media via Django:** Using `django.views.static.serve` in production. It is incredibly slow and blocking.
🔴 **Public Buckets:** Making your S3 bucket fully public. Use presigned GET URLs for sensitive files (like invoices), or configure CloudFront with Origin Access Control (OAC).

## 7. Environment-Specific Behavior
| Environment | Storage Backend | Consideration |
|-------------|-----------------|---------------|
| Local | `FileSystemStorage` | Media files kept locally in `/media/`. |
| CI | `locmem` (custom) or `FileSystemStorage` | Keep tests fast, avoid network calls. |
| Production | `S3Boto3Storage` | Combine with CloudFront CDN for global caching. |

## 8. Local Development Issues
🔴 **SYMPTOM:** S3 uploads fail locally with CORS errors.
🔍 **CAUSE:** Your frontend is running on `localhost:3000`, Django on `localhost:8000`, and S3 blocks cross-origin requests by default.
🔧 **FIX:** Configure the CORS policy on your S3 bucket to allow `localhost:3000` during development.

## 9. Production Issues
🔴 **INCIDENT:** Massive AWS bandwidth bill spike.
* **Severity:** Medium (Financial)
* **Investigation:** The site serves thousands of images directly from S3 (`s3.amazonaws.com/...`).
* **Root Cause:** S3 egress bandwidth is expensive. No CDN was configured.
* **Fix:** Placed AWS CloudFront in front of the S3 bucket and configured `AWS_S3_CUSTOM_DOMAIN = 'cdn.my-site.com'` in Django settings.

## 10. Failure Simulation
To test presigned URL expiration, generate a URL, manually wait 61 minutes, and attempt to upload a file via `curl`. You should receive a 403 Forbidden XML response from AWS.

## 11. Decision Matrix
| Pattern | Use Case | Pros | Cons |
|---------|----------|------|------|
| Django Upload | Small files (<1MB), admin panel | Simple code | Ties up Django workers |
| Presigned S3 POST | Large files, high traffic | Highly scalable | Complex frontend implementation |

## 12. Senior-Level Questions
**Q: If a user uploads a file directly to S3 via a presigned URL, how does Django know the upload finished so it can save the file path to the database?**
A: You have two options. 1) The frontend waits for the S3 upload to succeed (HTTP 204), then sends a follow-up POST to Django with the S3 file key to save in the DB. 2) Configure an S3 Event Notification to trigger an AWS Lambda or an SNS topic that hits a Django webhook asynchronously. Option 1 is simpler; Option 2 is robust against frontend crashes.

## 13. Production Checklist
- [ ] `DEFAULT_FILE_STORAGE` set to cloud provider.
- [ ] `AWS_S3_FILE_OVERWRITE = False` to prevent naming collisions.
- [ ] CDN (CloudFront/Cloudflare) placed in front of the bucket.
- [ ] Bucket policies restrict direct public access (using OAC/OAI).
- [ ] Presigned URLs strictly enforce file size limits via `Conditions`.
