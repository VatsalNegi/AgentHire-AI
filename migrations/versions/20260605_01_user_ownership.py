"""Add authenticated user profiles and nullable resource ownership.

Existing interview sessions and documents intentionally remain unowned.
"""

from alembic import op


revision = "20260605_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.user_profiles (
            id uuid PRIMARY KEY
                REFERENCES auth.users (id) ON DELETE CASCADE,
            role varchar(20) NOT NULL DEFAULT 'user',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_user_profiles_role
                CHECK (role IN ('user', 'admin'))
        )
        """
    )
    op.execute(
        """
        INSERT INTO public.user_profiles (id, role)
        SELECT id, 'user'
        FROM auth.users
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.create_user_profile()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public, auth
        AS $function$
        BEGIN
            INSERT INTO public.user_profiles (id, role)
            VALUES (NEW.id, 'user')
            ON CONFLICT (id) DO NOTHING;
            RETURN NEW;
        END;
        $function$
        """
    )
    op.execute(
        """
        CREATE TRIGGER on_auth_user_created_profile
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.create_user_profile()
        """
    )
    op.execute(
        """
        REVOKE ALL ON TABLE public.user_profiles FROM PUBLIC, anon, authenticated
        """
    )
    op.execute(
        "ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION public.create_user_profile()
        FROM PUBLIC, anon, authenticated
        """
    )

    op.execute(
        """
        ALTER TABLE public.interview_sessions
        ADD COLUMN owner_id uuid NULL
            REFERENCES public.user_profiles (id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.documents
        ADD COLUMN owner_id uuid NULL
            REFERENCES public.user_profiles (id) ON DELETE SET NULL
        """
    )
    for table_name in (
        "interview_sessions",
        "questions",
        "candidate_answers",
        "evaluations",
        "documents",
        "document_chunks",
    ):
        op.execute(
            f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY"
        )
    op.create_index(
        "ix_interview_sessions_owner_id",
        "interview_sessions",
        ["owner_id"],
        schema="public",
    )
    op.create_index(
        "ix_documents_owner_id",
        "documents",
        ["owner_id"],
        schema="public",
    )


def downgrade() -> None:
    for table_name in (
        "document_chunks",
        "documents",
        "evaluations",
        "candidate_answers",
        "questions",
        "interview_sessions",
    ):
        op.execute(
            f"ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY"
        )
    op.drop_index(
        "ix_documents_owner_id", table_name="documents", schema="public"
    )
    op.drop_index(
        "ix_interview_sessions_owner_id",
        table_name="interview_sessions",
        schema="public",
    )
    op.drop_column("documents", "owner_id", schema="public")
    op.drop_column("interview_sessions", "owner_id", schema="public")
    op.execute("DROP TRIGGER on_auth_user_created_profile ON auth.users")
    op.execute("DROP FUNCTION public.create_user_profile()")
    op.drop_table("user_profiles", schema="public")
