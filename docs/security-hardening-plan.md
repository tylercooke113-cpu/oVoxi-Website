# oVoxi Security Hardening: Claude Code Brief (items 1 to 12)

Prepared 2026-09-22 from a read of `backend/server.py`, `infra/modal/stem_worker.py`, the frontend pages and `vercel.json`.

---

## 0. How to use this brief

- The work is split into **5 batches (A to E)**. A batch is one deploy checkpoint. Paste one batch at a time into Claude Code, along with the Standing Rules in section 2.
- Items stay in the ranked order (1 to 12). There is one exception: **Step B0 pulls the token-verification rewrite (part of #8) forward**, because #2 and #3 are built on it. Building them on the current verifier would mean doing that work twice.
- Every numbered change ends with **"Show me the diff before saving."** Claude Code must stop at each one and wait for your approval.
- Anything marked **[TYLER]** is a dashboard step only you can do (Clerk, Railway, Modal, Cloudflare).
- **Before you paste Batch C:** do the first real production upload under `STEM_ENGINE=modal` (the pending /04 verification). Batch C edits the stem worker. If something breaks afterwards, you want to know whether the cause was /04 or these changes.

---

## 1. Decisions you need to make before Batch B

My recommendation is listed first in each row. Reply with your choices, or just say "all recommended".

| # | Decision | Recommended | Alternatives |
|---|---|---|---|
| D1 | Your standing rule says never touch `/apply`, `/vault` or `/admin`. This plan needs **four scoped exceptions**: `AdminPage.jsx` (#2), the `/apply/tracks` route (#6), a hidden honeypot field in `ApplyPage.jsx` (#10), and the backend response of `GET /api/vault/tracks` (#11; `VaultPage.jsx` itself is not edited). | Grant a one-time exception limited to exactly these edits | Skip those parts. #2 cannot be fixed without editing AdminPage. |
| D2 | How does an account become an "approved artist" (#3)? | `role` in Clerk public metadata, set by hand in the Clerk dashboard for now. An "Approve" button in admin comes later. | An email allowlist in an env var (fast, but does not scale). Or keep signup open and rely on quotas only (weakest option). |
| D3 | The legacy `/apply/tracks` upload (#6) | Retire it: the endpoint returns 410, and `/apply/tracks` redirects to `/signup` | Keep it, but require Clerk login and move storage to R2 (more work for a flow the Clerk upload already replaces) |
| D4 | Upload limits (#4) | 150 MB max file, 15 min max duration | Other values. Both are env vars, so you can change them without a deploy. |
| D5 | Job runner (#9) | A Mongo-backed queue inside the existing backend. No new infrastructure, and it can later be split into a second Railway service with one env var. | Move scan and mastering into a Modal CPU function (more moving parts while /04 is still unverified). Or Redis plus an `arq` worker (a new paid service). |
| D6 | Form spam protection (#10) | A honeypot field plus per-IP rate limits now; add Cloudflare Turnstile only if spam shows up | Turnstile now (adds signup friction and a Cloudflare setup step) |
| D7 | Existing data in the Mongo `leads` collection (#1) | Your call: export it from Atlas, then keep or drop it. Claude Code will not touch the database. | |

---

## 2. Standing rules (paste at the top of every Claude Code session)

```
STANDING RULES FOR THIS SESSION
1. Run `git pull` on main before editing anything. Report `git status` and the last 3 commits.
2. Before debugging anything, confirm the Railway and Vercel deploy timestamps match HEAD of main.
3. Never modify frontend/src/index.js.
4. Only touch /apply, /vault, /admin files where this brief explicitly says to (approved exception D1).
5. For every numbered change: show me the full diff and WAIT for my "approved" before saving.
6. No destructive steps (deleting files, DB writes, R2 deletes, env var removal) without my explicit go-ahead.
7. No em dashes in any code comment, copy, or commit message.
8. One commit per item, message format: `sec(#N): <summary>`. Do not push until I say "push".
9. Frontend deploys: `npx vercel --prod` only. Modal deploys: `modal deploy infra/modal/stem_worker.py`.
10. If you are not certain how a platform behaves (Railway, Clerk, R2, Modal), say "I do not know" and propose a test. Do not guess.
```

---

## 3. Batch A: Hotfix today (#1)

Ship this on its own, today. It is a live data leak.

### A1. Remove the public leads endpoint (#1)

```
TASK A1 (#1): Close the unauthenticated GET /api/leads.

1. grep the whole repo (frontend/src, tests, scripts, backend) for "leads".
   Report every hit before changing anything.
2. In backend/server.py delete the `get_leads` route (GET /api/leads) entirely.
3. If step 1 shows POST /api/leads is not called by any frontend code, also delete
   `create_lead`, `LeadCreate`, and `Lead`. Update or remove backend/tests/test_leads_api.py
   to match. If POST /leads IS used, keep it and tell me where.
4. Show me the diff before saving.
5. Verification after I deploy (give me these commands, do not run against prod yourself):
   curl -i https://ovoxi-website-production.up.railway.app/api/leads
   Expected: 404 or 405, never 200.
6. Commit: `sec(#1): remove unauthenticated GET /api/leads`
```

**[TYLER] same day:**
1. Rotate `ADMIN_PASSWORD` in Railway to a long random value (run `openssl rand -base64 32` in Terminal). It stays in use until Batch B replaces it.
2. Check Railway's HTTP logs for past `GET /api/leads` requests. I do not know whether it was ever accessed, and the logs are the only evidence.
3. Decide D7.
4. Push, confirm the Railway deploy timestamp, then run the curl check.

---

## 4. Batch B: Auth foundation (B0, then #2 and #3)

### [TYLER] Clerk dashboard setup, before any code ships

1. **Sessions > Customize session token**: add `{"metadata": "{{user.public_metadata}}"}`. This puts each user's role inside their login token.
2. **Users > (your account) > Metadata > Public**: set `{"role": "admin"}`.
3. **API Keys**: copy the **JWKS URL** and the **Frontend API URL** (the issuer). I expect them to be `https://clerk.ovoxi.net/.well-known/jwks.json` and `https://clerk.ovoxi.net`, but confirm them in the dashboard.
4. Add these Railway env vars (do not remove anything yet):
   - `CLERK_JWKS_URL` = the public JWKS URL from step 3
   - `CLERK_ISSUER` = the Frontend API URL
   - `CLERK_AUTHORIZED_PARTIES` = `https://ovoxi.net,https://www.ovoxi.net`

### B0. Rewrite token verification (pulled forward from #8)

```
TASK B0: Replace python-jose token verification with PyJWT + cached JWKS, add role helpers.

Why: the current verifier re-downloads Clerk's keys on EVERY request, does not check issuer
or authorized party, leaks error details, and python-jose has published CVEs
(CVE-2024-33663, CVE-2024-33664). PyJWT is already in requirements.txt.

1. In backend/server.py replace `from jose import jwt, JWTError` and `verify_clerk_token` with:

   import jwt
   from jwt import PyJWKClient

   CLERK_JWKS_URL = os.environ["CLERK_JWKS_URL"]
   CLERK_ISSUER = os.environ["CLERK_ISSUER"]
   CLERK_AUTHORIZED_PARTIES = {
       o.strip() for o in os.environ.get(
           "CLERK_AUTHORIZED_PARTIES", "https://ovoxi.net,https://www.ovoxi.net"
       ).split(",") if o.strip()
   }
   # Keys are cached in-process for an hour; Clerk is only called on cache miss or key rotation.
   _jwks_client = PyJWKClient(CLERK_JWKS_URL, cache_keys=True, lifespan=3600)

   async def verify_clerk_token(authorization: str = Header(default=None)) -> dict:
       if not authorization or not authorization.startswith("Bearer "):
           raise HTTPException(status_code=401, detail="Not authenticated")
       token = authorization.split(" ", 1)[1]
       try:
           signing_key = await asyncio.to_thread(_jwks_client.get_signing_key_from_jwt, token)
           payload = jwt.decode(
               token,
               signing_key.key,
               algorithms=["RS256"],
               issuer=CLERK_ISSUER,
               options={"require": ["exp", "iat", "iss", "sub"]},
               leeway=5,
           )
       except jwt.PyJWTError as exc:
           logger.info("Rejected Clerk token: %s", exc)
           raise HTTPException(status_code=401, detail="Not authenticated")
       azp = payload.get("azp")
       if azp and azp not in CLERK_AUTHORIZED_PARTIES:
           logger.info("Rejected Clerk token: azp=%s", azp)
           raise HTTPException(status_code=401, detail="Not authenticated")
       return payload

   def _role(payload: dict) -> Optional[str]:
       return (payload.get("metadata") or {}).get("role")

   def require_role(*roles: str):
       async def _dep(payload: dict = Depends(verify_clerk_token)) -> dict:
           if _role(payload) not in roles:
               raise HTTPException(status_code=403, detail="Forbidden")
           return payload
       return _dep

   require_artist = require_role("artist", "admin")
   require_admin = require_role("admin")

2. CLERK_SECRET_KEY is no longer needed for verification. Keep the variable loaded (the
   backfill script in B2 uses it), but it must never be sent to the JWKS URL again.
3. Confirm in your own words that `jwt.PyJWKClientError` subclasses `jwt.PyJWTError` in the
   installed PyJWT version (check the source in the venv, do not assume).
4. Add backend/tests/test_auth.py. Generate a local RSA keypair in the test and monkeypatch
   `_jwks_client` so no network is used. Test: valid token passes; expired token is 401;
   wrong issuer is 401; azp not in allowlist is 401; alg "none" is 401; a missing
   Authorization header is 401; require_admin with role "artist" is 403.
5. Show me the diff before saving. Then run the tests and show output.
6. Commit: `sec(#8a): cached JWKS verification with issuer and azp checks`
```

### B1. Replace the shared admin password with a Clerk admin role (#2)

```
TASK B1 (#2): Admin endpoints require a Clerk user with role "admin".

Backend (backend/server.py):
1. For GET /api/contact, /api/artists, /api/submissions, /api/appeals:
   - remove the `x_admin_password` Header parameter and the ADMIN_PASSWORD comparison
   - add `admin: dict = Depends(require_admin)`
   - add `request: Request` if missing and decorate with `@limiter.limit("30/minute")`
   - first line of each handler: logger.info("admin_access user=%s path=%s", admin.get("sub"), request.url.path)
2. grep for any other use of ADMIN_PASSWORD or x-admin-password and report it.

Frontend (frontend/src/pages/AdminPage.jsx, approved exception D1):
3. Remove the password state, password form, and 'x-admin-password' header.
4. Use Clerk:
   import { useAuth } from '@clerk/clerk-react';
   import { Navigate } from 'react-router-dom';
   const { isLoaded, isSignedIn, getToken } = useAuth();
   const [forbidden, setForbidden] = useState(false);

   fetchAll: const token = await getToken();
             const headers = { Authorization: `Bearer ${token}` };
             on any 403 response -> setForbidden(true)
   useEffect(() => { if (isLoaded && isSignedIn) fetchAll(); }, [isLoaded, isSignedIn]);

   if (!isLoaded) return null;
   if (!isSignedIn) return <Navigate to="/login" replace />;
   if (forbidden) render a short "This account does not have admin access." message.
5. Keep every other part of AdminPage unchanged (tables, status handling, STEM_LABELS).
6. Show me both diffs before saving.
7. Commit: `sec(#2): admin endpoints gated by Clerk admin role`
```

**[TYLER] after B1 is verified in production:**
- Turn on MFA for your Clerk account. I do not know whether your Clerk plan includes MFA, so check under Configure > Multi-factor.
- Delete `ADMIN_PASSWORD` from Railway and from your local `backend/.env`.

### B2. Stop free accounts from spending your money (#3)

```
TASK B2 (#3): Only approved artists can upload, uploads are owned, quotas and a kill switch exist,
and Modal GPU concurrency is capped.

Backend (backend/server.py):
1. presign_upload: change `Depends(verify_clerk_token)` to `Depends(require_artist)`.
2. complete_upload: add `clerk_payload: dict = Depends(require_artist)` and an ownership check:
       if sub.get("clerk_user_id") != clerk_payload.get("sub"):
           raise HTTPException(status_code=403, detail="Not your submission")
   (The frontend already sends the token on this call; the backend has been ignoring it.)
3. Kill switch at the top of presign_upload and complete_upload:
       if os.environ.get("UPLOADS_ENABLED", "true") != "true":
           raise HTTPException(status_code=503, detail="Uploads are temporarily paused")
4. Quotas in presign_upload (admins exempt), before creating the submission:
       from datetime import timedelta
       MAX_UPLOADS_PER_DAY = int(os.environ.get("MAX_UPLOADS_PER_DAY", "20"))
       MAX_OPEN_SUBMISSIONS = int(os.environ.get("MAX_OPEN_SUBMISSIONS", "5"))
       OPEN_STATUSES = ["pending", "uploaded", "scanning", "mastering", "processing"]
       uid = clerk_payload["sub"]
       since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
       if await db.track_submissions.count_documents({"clerk_user_id": uid, "upload_date": {"$gte": since}}) >= MAX_UPLOADS_PER_DAY:
           raise HTTPException(status_code=429, detail="Daily upload limit reached")
       if await db.track_submissions.count_documents({"clerk_user_id": uid, "status": {"$in": OPEN_STATUSES}}) >= MAX_OPEN_SUBMISSIONS:
           raise HTTPException(status_code=429, detail="Too many uploads in progress")
   Confirm upload_date is always stored as an ISO string with the same UTC format, so the
   string comparison is valid. Show me evidence from the code.
5. Add a startup hook that creates indexes (idempotent):
       track_submissions: [("clerk_user_id", 1), ("upload_date", -1)], [("status", 1), ("upload_date", 1)], [("id", 1)]
       appeals: [("id", 1)]
   Do NOT make any index unique in this step.

Modal (infra/modal/stem_worker.py):
6. Add `max_containers=2` to the @app.function decorator. Confirm this is the correct
   parameter name for modal==1.5.4 by checking the installed package, not from memory.

Frontend (frontend/src/pages/UploadPage.jsx):
7. Handle 403 with "Your account is pending approval. We will email you once you are cleared to upload."
   Handle 429 and 503 by showing the server's detail message.

Script (scripts/backfill_artist_roles.py, new):
8. Reads distinct clerk_user_id values from track_submissions and, for each one, calls
   PATCH https://api.clerk.com/v1/users/{user_id}/metadata with
   {"public_metadata": {"role": "artist"}} using CLERK_SECRET_KEY.
   - DRY RUN by default; only writes with --apply
   - skips users who already have a role; reports 404s (dev-instance users that no longer exist)
   - prints a summary table
9. Show me every diff before saving. Commit: `sec(#3): artist role gate, ownership, quotas, kill switch, GPU cap`
```

**[TYLER] Batch B deploy order:**
1. Finish the Clerk dashboard setup above. Run the backfill script in dry run, review the output, then run it with `--apply`.
2. Add these Railway env vars: `UPLOADS_ENABLED=true`, `MAX_UPLOADS_PER_DAY=20`, `MAX_OPEN_SUBMISSIONS=5`.
3. Push, which deploys the backend. Then `npx vercel --prod`, then `modal deploy`.
4. Set billing alerts or spend caps in Modal, ACRCloud and Cloudflare R2, wherever each plan offers them.
5. Run this verification matrix. To get a token, open the browser console on ovoxi.net while signed in and run `await window.Clerk.session.getToken()`.

| Test | Expected |
|---|---|
| Admin endpoints with no token | 401 |
| Admin endpoints with an artist token | 403 |
| Admin page while signed in as you | loads |
| Presign with a fresh account that has no role | 403 |
| `upload/complete` with another user's submission_id | 403 |
| Normal upload as an approved artist | works end to end |

---

## 5. Batch C: Upload safety and storage (#4, #5)

### C1. Oversized or fake files can't take the server down (#4)

```
TASK C1 (#4): Enforce file size, stream to disk instead of RAM, validate audio, limit heavy jobs.

Backend:
1. PresignRequest: add `file_size: int = Field(..., gt=0)`.
   MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(150 * 1024 * 1024)))
   Reject > MAX_UPLOAD_BYTES with 413.
   Add "ContentLength": payload.file_size to the presign Params so the size is part of the
   signature. Reduce ExpiresIn to 900. Store `expected_size` on the submission document.
2. complete_upload, before queueing: head_object on original_r2_path.
   - object missing -> 400 "Upload not found"
   - ContentLength > MAX_UPLOAD_BYTES or != expected_size -> delete the object, set
     status "failed" with error "file_rejected_size", return 400.
   (Using the existing "failed" status on purpose so AdminPage and VaultPage need no changes.)
3. Replace in-memory downloads in _process_stems and _master_track with streaming to disk:
       async def _r2_download_to(key: str, path: str) -> None:
           await asyncio.to_thread(r2_client.download_file, R2_BUCKET, key, path)
   and upload the mastered file with r2_client.upload_file from the path (ExtraArgs ContentType)
   instead of reading it into memory.
4. After download and BEFORE the ACRCloud scan (saves ACR cost), validate with ffprobe
   (ffmpeg is in the Dockerfile):
       ffprobe -v error -show_entries format=format_name,duration -of json <path>
   Fail the submission with error "file_rejected_format" if there is no audio stream,
   ffprobe errors, or duration > MAX_TRACK_SECONDS (env, default 900).
5. Interim guard until #9: a module-level
       HEAVY_JOBS = asyncio.Semaphore(int(os.environ.get("HEAVY_JOB_CONCURRENCY", "1")))
   wrapping the scan + mastering section so only one runs at a time.

Frontend (UploadPage.jsx):
6. Send file_size: file.size in the presign body. Pre-check size client-side with a clear message.

Verification (write me a script, scripts/verify_upload_limits.sh, do not run against prod):
7. (a) presign with a small declared size, then PUT a larger file to the URL -> expect R2 to
   reject it. I do not know for certain that R2 enforces a signed Content-Length; this test
   is how we find out. If R2 accepts it, the check in step 2 is the backstop.
   (b) a 200 MB file is rejected at presign with 413.
   (c) a renamed .txt file ends as failed / file_rejected_format.
8. Show me diffs before saving. Commit: `sec(#4): size limits, streaming IO, audio validation`
```

### C2. Artists can't overwrite each other's stems (#5, closes OQ-2 and OQ-6)

```
TASK C2 (#5): Stem keys become unique per submission and no pipeline step overwrites an object.

1. infra/modal/stem_worker.py line ~157:
       stem_prefix = f"{key_prefix}/{artist_slug}/{track_slug}/{submission_id}/stems"
2. Before each r2.put_object in the worker, add a write guard:
       def _exists(key: str) -> bool:
           try:
               r2.head_object(Bucket=bucket, Key=key)
               return True
           except ClientError as e:
               if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                   return False
               raise
       if _exists(out_key):
           raise RuntimeError(f"Refusing to overwrite existing object {out_key}")
   (The raise must go through the existing failure path so the failed callback still fires.)
3. Same guard in backend _master_track before writing mastered_r2_key.
4. Do NOT migrate existing R2 keys. Existing documents keep their stored stem_paths.
5. New read-only script scripts/audit_stem_collisions.py: finds track_submissions whose
   stem_paths values are shared by more than one submission and prints id, artist, track,
   status, and upload_date. No writes.
6. Update docs/open-questions.md: OQ-2 and OQ-6 marked fixed for new uploads, with the audit
   script as the path for historical collisions.
7. Show me diffs before saving. Commit: `sec(#5): per-submission stem keys and write guards`
```

**[TYLER]:** push, `modal deploy`, run one real upload, check that the new key contains the submission ID, then run the audit script and review what it reports.

---

## 6. Batch D: Close old doors (#6, #7, #8 cleanup)

### D-1. Retire the legacy upload route (#6)

```
TASK D-1 (#6): Remove the unauthenticated /api/artists/{email}/tracks upload and the public /uploads mount.

1. First, tell me whether you can see the contents of the Railway container's backend/uploads
   directory with the tools you have. If you cannot, say so and stop; I will check in Railway.
   If files exist, write scripts/backup_legacy_uploads.py that copies them to R2 under
   legacy/uploads/ (private). Do not delete anything.
2. After I confirm the backup: in server.py
   - replace upload_artist_tracks with a handler that returns 410 "This upload flow has moved. Please sign up at /signup."
   - remove app.mount("/uploads", ...) and the UPLOADS_DIR mkdir
   - in get_artists, stop building track["url"] (keep the filename field)
3. Frontend (approved exception D1):
   - App.js: '/apply/tracks' -> <Navigate to='/signup' replace />
   - ApplyPage.jsx line 49: navigate to '/signup' after a successful application instead of /apply/tracks
   - leave ApplyTracksPage.jsx in the repo but unrouted (additive first, delete later)
4. Show me diffs before saving. Commit: `sec(#6): retire legacy unauthenticated upload flow`
```

### D-2. Make the rate limiter trust the right IP (#7)

```
TASK D-2 (#7): Evidence first, then fix.

Step 1: diagnose (temporary)
1. Add an endpoint that only works while DEBUG_IP_ENDPOINT=true:
       @api_router.get("/internal/debug-ip")
       async def debug_ip(request: Request):
           if os.environ.get("DEBUG_IP_ENDPOINT") != "true":
               raise HTTPException(status_code=404)
           return {
               "x_forwarded_for": request.headers.get("x-forwarded-for"),
               "x_real_ip": request.headers.get("x-real-ip"),
               "client_host": request.client.host if request.client else None,
           }
2. Give me the test commands:
       curl -s https://ifconfig.me
       curl -s https://ovoxi-website-production.up.railway.app/api/internal/debug-ip
       curl -s -H "X-Forwarded-For: 6.6.6.6" https://ovoxi-website-production.up.railway.app/api/internal/debug-ip
   Then STOP and wait for me to paste the results.

Step 2: fix based on the evidence
3. If Railway APPENDS the real IP to the end of X-Forwarded-For:
       TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "1"))
       def get_real_client_ip(request: Request) -> str:
           hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
           if len(hops) >= TRUSTED_PROXY_HOPS:
               return hops[-TRUSTED_PROXY_HOPS]
           return request.client.host if request.client else "unknown"
   If Railway sets a header the client cannot forge (for example it overwrites X-Real-IP), use that instead.
   Explain which case the evidence shows before writing code.
4. Remove the debug endpoint in the same commit.
5. Tell me how many replicas the Railway service runs. slowapi's default storage is in-memory
   per replica; if it is more than 1, flag it (Redis storage would then be a follow-up decision).
6. Show me diffs before saving. Commit: `sec(#7): client IP from trusted proxy hop only`
```

### D-3. Finish #8: dependency cleanup

```
TASK D-3 (#8b): Remove python-jose and dead dependencies, pin versions.

1. grep backend/ for every import and list which requirements.txt entries are unused
   (candidates: python-jose, passlib, bcrypt, requests-oauthlib, jq, typer, pandas).
   Check whether matchering, pyacrcloud or modal need any of them transitively before removing.
2. Remove python-jose and the confirmed-unused packages.
3. Move pytest, black, isort, flake8, mypy into backend/requirements-dev.txt.
4. Pin every remaining direct dependency to an exact version: build a clean venv from the
   new file, run the tests, and use `pip freeze` for the versions of the direct deps.
5. Add a test proving a token signed by a different Clerk instance (different issuer) is
   rejected. This confirms the backend only trusts the production instance (related to OQ-8).
6. Show me diffs before saving. Commit: `sec(#8b): drop python-jose, pin deps, split dev requirements`
```

**[TYLER]:** push, then watch the Railway build log to confirm the dependencies install cleanly. Delete `DEBUG_IP_ENDPOINT` from Railway and set `TRUSTED_PROXY_HOPS` if D-2 needs it.

---

## 7. Batch E: Reliability and hygiene (#9, #10, #11, #12)

### E1. Jobs survive restarts (#9, closes OQ-5)

```
TASK E1 (#9): Replace FastAPI BackgroundTasks with a Mongo-backed job queue plus a stale-job sweeper.

1. Helper used for EVERY status change in the pipeline:
       def _now() -> str: return datetime.now(timezone.utc).isoformat()
       async def _set_status(sid: str, status: str, **extra) -> None:
           await db.track_submissions.update_one(
               {"id": sid}, {"$set": {"status": status, "status_updated_at": _now(), **extra}})
2. complete_upload: set status "uploaded" (+status_updated_at). Remove background_tasks.add_task.
3. Worker loop, started on startup when RUN_WORKER=true (default true):
       INSTANCE_ID = uuid.uuid4().hex
       async def _claim_next():
           return await db.track_submissions.find_one_and_update(
               {"status": "uploaded"},
               {"$set": {"status": "scanning", "claimed_by": INSTANCE_ID,
                         "claimed_at": _now(), "status_updated_at": _now()},
                "$inc": {"attempts": 1}},
               sort=[("upload_date", 1)],
               return_document=ReturnDocument.AFTER,
           )
       async def _worker_loop():
           while True:
               try:
                   job = await _claim_next()
                   if not job:
                       await asyncio.sleep(5)
                       continue
                   await _process_stems(job["id"], job["original_r2_path"],
                                        job["artist_name"], job["track_name"])
               except Exception:
                   logger.exception("worker loop error")
                   await asyncio.sleep(5)
   Start WORKER_CONCURRENCY (env, default 1) loops. Remove the C1 semaphore, since the loop
   count now limits concurrency.
4. When dispatching to Modal, also set "modal_dispatched_at": _now().
5. Sweeper, every 5 minutes (same startup hook):
   a) status in [scanning, mastering, processing], no modal_dispatched_at, claimed_at older than
      STALE_LOCAL_MIN (default 20):
        attempts < 2 -> reset to "uploaded" (it will be re-claimed)
        else -> failed, error "pipeline_timeout"
   b) status "processing" with modal_dispatched_at older than STALE_MODAL_MIN (default 45;
      the Modal timeout is 30) -> failed, error "stem_callback_timeout"
   Use atomic update filters so two replicas can't double-handle a job. Treat a missing
   `attempts` field as 0.
6. Explain how a job that was mid-mastering during a redeploy gets recovered, step by step.
7. Show me diffs before saving. Commit: `sec(#9): durable Mongo job queue and stale-job sweeper`
```

**Later, optional:** add a second Railway service from the same repo with `RUN_WORKER=true`, and set `RUN_WORKER=false` on the web service. Mastering CPU then stops competing with website traffic. No code change is needed.

### E2. Spam, enumeration and leftover endpoints (#10)

```
TASK E2 (#10):
1. Delete GET and POST /api/status and the StatusCheck models.
2. Add `request: Request` and @limiter.limit("5/minute;30/day") to POST /api/contact and POST /api/artists.
3. Honeypot: add `website: Optional[str] = Field(default=None, max_length=200)` to
   ContactSubmissionCreate and ArtistCreate. If filled, log it and return success WITHOUT storing.
   Frontend: add a visually hidden, aria-hidden, tabIndex={-1}, autoComplete="off" input named
   "website" to ContactPage.jsx and ApplyPage.jsx (approved exception D1).
4. POST /api/artists enumeration fix: return {"ok": true} with 201 whether or not the email
   already exists; never return the existing record. Check ApplyPage.jsx's use of the response
   and error branch (line ~52) and update it to match.
5. Show me diffs before saving. Commit: `sec(#10): rate limits, honeypot, no email enumeration, remove /status`
```

### E3. Stop leaking internals (#11)

```
TASK E3 (#11):
1. app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
   (/docs and /openapi.json are currently public and list every endpoint, including the callback.)
2. GET /api/vault/tracks: return an explicit allowlist per submission. VaultPage and AppealPage
   read only these fields:
       id, artist_name, track_name, genre, upload_date, status, stem_urls, mastered_url
   Drop everything else (matched_*, acrid, confidence, raw_code, error, *_r2_key, stem_paths,
   claimed_by, attempts). This also closes a leak where ACRCloud match details were in the
   artist API response even though the UI hides them. Grep VaultPage.jsx and AppealPage.jsx
   to confirm no other field is read before you strip anything.
3. Keep full `error` detail for admin (AdminPage renders it). Truncate stored error strings to 500 chars.
4. Global handler:
       @app.exception_handler(Exception)
       async def _unhandled(request: Request, exc: Exception):
           logger.exception("Unhandled error on %s", request.url.path)
           return JSONResponse(status_code=500, content={"error": "Internal error"})
5. Show me diffs before saving. Commit: `sec(#11): disable API docs, allowlist vault fields, generic errors`
```

### E4. Callback replay protection (#12)

```
TASK E4 (#12): Timestamped HMAC plus stricter state rules on /api/internal/stems/callback.

Worker (_post_callback in stem_worker.py):
1.  ts = str(int(time.time()))
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(webhook_secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    headers: "X-Ovoxi-Timestamp": ts, "X-Ovoxi-Signature": f"sha256={sig}"

Backend (stems_callback):
2. Reject with 401 if the timestamp is missing, not digits, or more than 300 seconds from now.
   Verify HMAC over ts + b"." + body with hmac.compare_digest.
3. Both the "completed" and "failed" updates filter on {"id": sid, "status": "processing"}.
   (Today the failed branch has no guard and can flip a completed track to failed.)
4. Validate stem_paths: must be a dict whose keys are the known stem names and whose values
   are strings containing f"/{sid}/stems/" under the same top-level prefix as the submission's
   original_r2_path. Otherwise 400.
5. Update infra/modal/preflight_callback.py to sign with the new scheme.
6. Deploy order note for me: backend first, then modal deploy, at a moment when no submission
   is in "processing". Give me a Mongo query to check that.
7. Show me diffs before saving. Commit: `sec(#12): timestamped callback signatures and terminal-state guards`
```

**[TYLER]:** push, then `npx vercel --prod`, then `modal deploy`. Then run one full upload end to end.

---

## 8. Wrap-up (final Claude Code task)

```
TASK WRAP:
1. Update CLAUDE.md section 4 (Security / config facts): Clerk role model, no ADMIN_PASSWORD,
   the job queue, callback signing scheme, upload limits, env var list.
2. Update docs/open-questions.md: OQ-2, OQ-5 and OQ-6 status.
3. Produce a table of every env var added or removed across Railway, Vercel, and the Modal
   secret, with the value source (never the secret values themselves).
4. Show me the diffs, then commit `docs: security hardening state` and push when I say "push".
```

### Env var reference (Railway unless noted)

| Variable | Batch | Value |
|---|---|---|
| `ADMIN_PASSWORD` | A, then removed in B | rotate now, delete after B1 is verified |
| `CLERK_JWKS_URL` | B | public JWKS URL from the Clerk dashboard |
| `CLERK_ISSUER` | B | Clerk Frontend API URL |
| `CLERK_AUTHORIZED_PARTIES` | B | `https://ovoxi.net,https://www.ovoxi.net` |
| `UPLOADS_ENABLED` | B | `true` (set `false` to pause uploads instantly) |
| `MAX_UPLOADS_PER_DAY` / `MAX_OPEN_SUBMISSIONS` | B | `20` / `5` |
| `MAX_UPLOAD_BYTES` / `MAX_TRACK_SECONDS` | C | `157286400` / `900` |
| `DEBUG_IP_ENDPOINT` | D (temporary) | `true` during the test, then delete |
| `TRUSTED_PROXY_HOPS` | D | set from the D-2 evidence |
| `RUN_WORKER` / `WORKER_CONCURRENCY` | E | `true` / `1` |
| `STALE_LOCAL_MIN` / `STALE_MODAL_MIN` | E | `20` / `45` |

### Not in scope (low tier, available later)
#13 appeal file malware scanning, #14 CSP tightening and dropping localhost from CORS, #15 non-root container, #16 secret rotation schedule and shorter download links.
