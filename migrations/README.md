# Database migration review

`versions/20260605_01_user_ownership.py` is an additive migration for an
existing Supabase schema. It assumes `auth.users`, `public.interview_sessions`,
and `public.documents` already exist. It creates profiles for existing Auth
users with the non-privileged `user` role, installs a trigger for new users,
and leaves every existing session and document unowned (`owner_id IS NULL`).

Test this only against a **disposable local Supabase project** that has the
application's existing database tables. Do not use production or a database
containing data that must be retained. The environment variable overrides the
value loaded from `.env`; never put a production URL in the command:

```powershell
$env:DATABASE_URL = "<disposable local Supabase PostgreSQL URL>"
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
```

After upgrading, verify that `public.user_profiles` contains existing Auth
users with role `user`, that new Auth signups receive a profile with role
`user`, and that no existing session or document acquired an owner:

```sql
SELECT count(*) FROM public.interview_sessions WHERE owner_id IS NOT NULL;
SELECT count(*) FROM public.documents WHERE owner_id IS NOT NULL;
SELECT role, count(*) FROM public.user_profiles GROUP BY role;
```

The migration enables row-level security without client policies on
`interview_sessions`, `questions`, `candidate_answers`, `evaluations`,
`documents`, and `document_chunks`; this blocks direct PostgREST access while
the backend continues through its table-owning database connection. Verify in
the disposable project that `anon` and `authenticated` cannot read those
tables or `user_profiles` through PostgREST, and that the backend can still
serve its protected API routes. Do not use a browser-exposed database
credential for the backend connection.
