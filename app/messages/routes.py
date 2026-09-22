"""
In-app messaging between employers and candidates.

- Employers start a conversation from a candidate's profile.
- Both sides can view their inbox and reply within a thread.
- Each employer/candidate pair only ever has one conversation - replying
  just adds to the same thread instead of creating a new one.
- The thread page polls /messages/thread/<id>/poll every few seconds so
  new messages show up without either person needing to refresh.
"""
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user

from app.messages import messages_bp
from app.extensions import db
from app.models import Conversation, Message, CandidateProfile


def _serialize_message(message):
    return {
        "id": message.id,
        "body": message.body,
        "sent_at": message.sent_at.strftime("%d %b, %H:%M"),
        "is_own": message.sender_id == current_user.id,
    }


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
        message = None
        if body:
            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                body=body[:4000],
            )
            db.session.add(message)
            conversation.last_message_at = message.sent_at
            db.session.commit()

        # If the request was made via fetch() (AJAX), return JSON instead
        # of redirecting, so the page can append the new message instantly
        # without a full reload.
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            if message is None:
                return jsonify({"error": "Message body is required."}), 400
            return jsonify({"message": _serialize_message(message)})

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


@messages_bp.route("/thread/<int:conversation_id>/poll")
@login_required
def poll(conversation_id):
    """Return any messages newer than the given message id, and mark them
    as read if they were sent by the other person. The thread page calls
    this every few seconds so new messages show up live.
    """
    conversation = Conversation.query.get_or_404(conversation_id)
    if current_user.id not in (conversation.employer_id, conversation.candidate_id):
        abort(403)

    after_id = request.args.get("after", 0, type=int)
    new_messages = [m for m in conversation.messages if m.id > after_id]

    unread = [m for m in new_messages if m.sender_id != current_user.id and not m.read]
    for m in unread:
        m.read = True
    if unread:
        db.session.commit()

    return jsonify({"messages": [_serialize_message(m) for m in new_messages]})


@messages_bp.route("/unread-count")
@login_required
def unread_count():
    """Total unread messages across every conversation for the current
    user - polled by the nav bar so the badge updates live.
    """
    if current_user.is_employer():
        conversations = Conversation.query.filter_by(employer_id=current_user.id).all()
    else:
        conversations = Conversation.query.filter_by(candidate_id=current_user.id).all()

    count = sum(c.unread_count_for(current_user.id) for c in conversations)
    return jsonify({"count": count})


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
