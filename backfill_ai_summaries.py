"""
One-off backfill: generate AI summaries for any candidate profile that
has a CV on file but no AI summary yet (e.g. profiles created via the
seed script, which bypasses the normal upload route).

Idempotent: only processes profiles where ai_summary is still empty.
"""
from app import create_app
from app.extensions import db
from app.models import CandidateProfile
from app.utils import extract_pdf_text
from app.candidates.routes import _generate_ai_summary


def backfill(app=None):
    owns_app = app is None
    if owns_app:
        app = create_app()

    processed = 0
    skipped = 0

    with app.app_context():
        profiles = CandidateProfile.query.filter(
            CandidateProfile.ai_summary.is_(None),
            CandidateProfile.cv_filename.isnot(None),
        ).all()

        for profile in profiles:
            _generate_ai_summary(profile)
            if profile.ai_summary:
                db.session.commit()
                print(f"OK    {profile.full_name} - AI summary generated")
                processed += 1
            else:
                db.session.rollback()
                print(f"SKIP  {profile.full_name} - AI summary generation failed or unavailable")
                skipped += 1

    print(f"\nDone. Generated {processed}, skipped {skipped}.")


if __name__ == "__main__":
    backfill()
