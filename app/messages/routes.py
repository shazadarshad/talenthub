"""
In-app messaging between employers and candidates.

- Employers start a conversation from a candidate's profile.
- Both sides can view their inbox and reply within a thread.
- Each employer/candidate pair only ever has one conversation - replying
  just adds to the same thread instead of creating a new one.
"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.messages import messages_bp
from app.extensions import db
from app.models import Conversation, Message, CandidateProfile


@messages_bp.route("/inbox")
@login_required
def inbox():
    if current_user.is_employer():
        conversations = (
            Conversation.query.filter_by(employer_id=current_user.id)
            .order_by(Conversation.last_message_at.desc())
            .all()
        )
    else:
        conversations = (
            Conversation.query.filter_by(candidate_id=current_user.id)
            .order_by(Conversation.last_message_at.desc())
            .all()
        )

    return render_template("messages/inbox.html", conversations=conversations)


@messages_bp.route("/thread/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def thread(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)

    # Only the two people in this conversation can see it.
    if current_user.id not in (conversation.employer_id, conversation.candidate_id):
        abort(403)

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                body=body[:4000],
            )
            db.session.add(message)
            conversation.last_message_at = message.sent_at
            db.session.commit()
        return redirect(url_for("messages.thread", conversation_id=conversation.id))

    # Mark the other person's messages as read now that this user has
    # opened the thread.
    unread = [
        m for m in conversation.messages
        if m.sender_id != current_user.id and not m.read
    ]
    for m in unread:
        m.read = True
    if unread:
        db.session.commit()

    other_party = conversation.other_party(current_user.id)
    return render_template(
        "messages/thread.html",
        conversation=conversation,
        other_party=other_party,
        candidate_profile=conversation.candidate_profile,
    )


@messages_bp.route("/start/<int:profile_id>", methods=["GET", "POST"])
@login_required
def start(profile_id):
    """An employer starts (or resumes) a conversation with a candidate,
    from that candidate's profile page.
    """
    if not current_user.is_employer():
        abort(403)

    profile = CandidateProfile.query.get_or_404(profile_id)

    # Re-use the existing conversation if one already exists, rather than
    # ever creating a duplicate thread for the same pair of people.
    conversation = Conversation.query.filter_by(
        employer_id=current_user.id, candidate_id=profile.user_id
    ).first()

    if conversation is None:
        if request.method != "POST":
            return render_template("messages/start.html", candidate=profile)

        body = request.form.get("body", "").strip()
        if not body:
            flash("Please write a message before sending.", "error")
            return render_template("messages/start.html", candidate=profile)

        conversation = Conversation(
            employer_id=current_user.id,
            candidate_id=profile.user_id,
            candidate_profile_id=profile.id,
        )
        db.session.add(conversation)
        db.session.flush()

        message = Message(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            body=body[:4000],
        )
        db.session.add(message)
        conversation.last_message_at = message.sent_at
        db.session.commit()

        flash(f"Message sent to {profile.full_name}.", "success")

    return redirect(url_for("messages.thread", conversation_id=conversation.id))
