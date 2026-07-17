"""
SHERLOCK — Stage C6: CollaborationService.

The one place that writes Comment/Notification/BoardObject/ReviewRequest/
SessionPresence rows, mirroring database/service.py's own rule ("agents
never do SQL directly") for this sprint's new tables. Every write here
also appends a `SessionActivity` row via `_log_activity` — the same
audit-trail table Stage C1 already built, extended with new event_type
values (`comment_added`, `mention_sent`, `board_object_added`,
`board_object_updated`, `review_requested`, `review_decided`) rather than
a second, competing audit mechanism.

Mentions ("@Officer", "@Supervisor") — same honest, pattern-based
philosophy as Stage C2/C4, not real NLU:
  - A handful of role keywords (case-insensitive): "supervisor"/"lead"
    notify the session's `role="lead"` assignee(s); "reviewer" notifies
    `role="reviewer"` assignee(s); "investigator"/"officer" notifies
    every `role="investigator"` assignee. These map directly onto
    Stage C1's real `SessionAssignment.role` vocabulary rather than
    inventing a rank hierarchy the data model doesn't have.
  - Anything else is looked up by name against `Officer.name`
    (case-insensitive substring, same as `find_officer_by_name` already
    used by Stage C3's voice router) — assigned officers on this session
    are checked first, then any officer in the database, so mentioning
    someone not yet assigned still notifies them (a lightweight "hey,
    take a look" rather than requiring a formal assignment first).
  - Ambiguous partial names (two officers matching "Ravi") resolve to
    the first match, same documented limitation as `find_officer_by_name`
    itself — not solved differently here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.database.models import (
    InvestigationSession, SessionActivity, SessionAssignment, Officer,
    BoardObject, Comment, Notification, ReviewRequest, SessionPresence,
    NotificationType, ReviewStatus, CommentTargetType, BoardObjectType, PresenceStatus,
    ConversationTurn, DiscussionRecord,
)

PRESENCE_TTL_SECONDS = 90   # a heartbeat older than this is treated as "no longer present"

_MENTION = re.compile(r"@([A-Za-z]+(?:\s+[A-Za-z]+){0,2})")
_ROLE_KEYWORDS = {
    "supervisor": "lead", "lead": "lead",
    "reviewer": "reviewer",
    "investigator": "investigator", "officer": "investigator",
}


class CollaborationService:

    def __init__(self, session):
        self.session = session

    # -- shared internal helper, mirrors DatabaseService._log_activity ------

    def _log_activity(self, session_id: int, event_type: str,
                       actor_officer_id: int | None = None, detail: str | None = None) -> None:
        self.session.add(SessionActivity(
            session_id=session_id, event_type=event_type,
            actor_officer_id=actor_officer_id, detail=detail,
        ))

    def _notify(self, recipient_officer_id: int, notification_type: NotificationType,
                message: str, session_id: int | None = None,
                related_comment_id: int | None = None, related_review_id: int | None = None) -> Notification:
        n = Notification(
            recipient_officer_id=recipient_officer_id, notification_type=notification_type,
            message=message, session_id=session_id,
            related_comment_id=related_comment_id, related_review_id=related_review_id,
        )
        self.session.add(n)
        return n

    def _assigned_officer_ids(self, session_id: int, role: str | None = None) -> list[int]:
        q = self.session.query(SessionAssignment).filter_by(session_id=session_id, unassigned_at=None)
        if role is not None:
            q = q.filter_by(role=role)
        return [a.officer_id for a in q.all()]

    # -- comments + mentions --------------------------------------------------

    def add_comment(self, session_id: int, target_type: CommentTargetType, target_ref: str,
                     body: str, author_officer_id: int | None = None) -> Comment | None:
        session_row = self.session.get(InvestigationSession, session_id)
        if session_row is None:
            return None

        comment = Comment(session_id=session_id, target_type=target_type, target_ref=target_ref,
                           body=body, author_officer_id=author_officer_id)
        self.session.add(comment)
        self.session.flush()  # need comment.id for notifications/activity detail

        self._log_activity(session_id, "comment_added", author_officer_id,
                            detail=f"Comment on {target_type.value}:{target_ref}")

        mentioned = self._resolve_mentions(session_id, body)
        for officer_id in mentioned:
            if officer_id == author_officer_id:
                continue  # don't notify yourself for @-ing your own name
            self._notify(officer_id, NotificationType.MENTION,
                         message=f'Mentioned in a comment on {target_type.value}:{target_ref}: "{body[:200]}"',
                         session_id=session_id, related_comment_id=comment.id)
        if mentioned:
            self._log_activity(session_id, "mention_sent", author_officer_id,
                                detail=f"Notified officer(s) {sorted(mentioned)}")

        self.session.commit()
        self.session.refresh(comment)
        return comment

    def _resolve_mentions(self, session_id: int, body: str) -> set[int]:
        resolved: set[int] = set()
        for match in _MENTION.finditer(body):
            candidate_words = match.group(1).split()
            resolved_one = self._resolve_one_mention(session_id, candidate_words)
            if resolved_one:
                resolved.update(resolved_one)
        return resolved

    def _resolve_one_mention(self, session_id: int, words: list[str]) -> set[int]:
        # Longest-match-first over 1..3 words, role keywords checked before name lookup.
        for n in range(len(words), 0, -1):
            candidate = " ".join(words[:n])
            role = _ROLE_KEYWORDS.get(candidate.lower())
            if role:
                ids = self._assigned_officer_ids(session_id, role=role)
                if ids:
                    return set(ids)
            officer = self._find_officer_scoped(session_id, candidate)
            if officer:
                return {officer.id}
        return set()

    def _find_officer_scoped(self, session_id: int, name_fragment: str) -> Officer | None:
        assigned_ids = self._assigned_officer_ids(session_id)
        if assigned_ids:
            match = (
                self.session.query(Officer)
                .filter(Officer.id.in_(assigned_ids), Officer.name.ilike(f"%{name_fragment}%"))
                .first()
            )
            if match:
                return match
        return self.session.query(Officer).filter(Officer.name.ilike(f"%{name_fragment}%")).first()

    def get_comments(self, session_id: int, target_type: CommentTargetType | None = None,
                      target_ref: str | None = None) -> list[Comment]:
        q = self.session.query(Comment).filter_by(session_id=session_id)
        if target_type is not None:
            q = q.filter_by(target_type=target_type)
        if target_ref is not None:
            q = q.filter_by(target_ref=target_ref)
        return q.order_by(Comment.created_at).all()

    # -- board objects (shared notes / links / hypotheses) --------------------

    def add_board_object(self, session_id: int, object_type: BoardObjectType, content: str,
                          payload: dict | None = None, created_by_officer_id: int | None = None) -> BoardObject | None:
        session_row = self.session.get(InvestigationSession, session_id)
        if session_row is None:
            return None
        obj = BoardObject(session_id=session_id, object_type=object_type, content=content,
                           payload=json.dumps(payload) if payload else None,
                           created_by_officer_id=created_by_officer_id)
        self.session.add(obj)
        self.session.flush()
        self._log_activity(session_id, "board_object_added", created_by_officer_id,
                            detail=f"{object_type.value}: {content[:100]}")
        self._notify_board_update(session_id, created_by_officer_id,
                                   f'New {object_type.value} added to the board: "{content[:100]}"')
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def update_board_object(self, board_object_id: int, actor_officer_id: int | None = None,
                             content: str | None = None, payload: dict | None = None) -> BoardObject | None:
        obj = self.session.get(BoardObject, board_object_id)
        if obj is None:
            return None
        if content is not None:
            obj.content = content
        if payload is not None:
            obj.payload = json.dumps(payload)
        obj.updated_at = datetime.utcnow()
        self._log_activity(obj.session_id, "board_object_updated", actor_officer_id,
                            detail=f"{obj.object_type.value} #{obj.id} updated")
        self._notify_board_update(obj.session_id, actor_officer_id,
                                   f'{obj.object_type.value.capitalize()} updated on the board: "{obj.content[:100]}"')
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def _notify_board_update(self, session_id: int, actor_officer_id: int | None, message: str) -> None:
        for officer_id in self._assigned_officer_ids(session_id):
            if officer_id == actor_officer_id:
                continue
            self._notify(officer_id, NotificationType.BOARD_UPDATE, message, session_id=session_id)

    def get_board_objects(self, session_id: int) -> list[BoardObject]:
        return (
            self.session.query(BoardObject)
            .filter_by(session_id=session_id)
            .order_by(BoardObject.created_at)
            .all()
        )

    # -- review workflow --------------------------------------------------------

    def request_review(self, session_id: int, requested_by_officer_id: int | None = None,
                        reviewer_officer_id: int | None = None, notes: str | None = None) -> ReviewRequest | None:
        session_row = self.session.get(InvestigationSession, session_id)
        if session_row is None:
            return None
        review = ReviewRequest(session_id=session_id, status=ReviewStatus.IN_REVIEW,
                                requested_by_officer_id=requested_by_officer_id,
                                reviewer_officer_id=reviewer_officer_id, notes=notes)
        self.session.add(review)
        self.session.flush()
        self._log_activity(session_id, "review_requested", requested_by_officer_id,
                            detail=notes or "Review requested")

        recipients = [reviewer_officer_id] if reviewer_officer_id else self._assigned_officer_ids(session_id, role="reviewer")
        if not recipients:
            recipients = self._assigned_officer_ids(session_id, role="lead")
        for officer_id in recipients:
            if officer_id == requested_by_officer_id:
                continue
            self._notify(officer_id, NotificationType.REVIEW_REQUEST,
                         message=f"Review requested for session {session_row.session_code}"
                                 + (f': "{notes[:150]}"' if notes else ""),
                         session_id=session_id, related_review_id=review.id)

        self.session.commit()
        self.session.refresh(review)
        return review

    def decide_review(self, review_id: int, approve: bool, actor_officer_id: int | None = None,
                       decision_notes: str | None = None) -> ReviewRequest | None:
        review = self.session.get(ReviewRequest, review_id)
        if review is None:
            return None
        review.status = ReviewStatus.APPROVED if approve else ReviewStatus.REJECTED
        review.decided_at = datetime.utcnow()
        review.decision_notes = decision_notes
        self._log_activity(review.session_id, "review_decided", actor_officer_id,
                            detail=f"{review.status.value}" + (f": {decision_notes[:150]}" if decision_notes else ""))
        if review.requested_by_officer_id:
            self._notify(review.requested_by_officer_id, NotificationType.REVIEW_DECISION,
                         message=f"Review {review.status.value}"
                                 + (f': "{decision_notes[:150]}"' if decision_notes else ""),
                         session_id=review.session_id, related_review_id=review.id)
        self.session.commit()
        self.session.refresh(review)
        return review

    def get_reviews(self, session_id: int) -> list[ReviewRequest]:
        return (
            self.session.query(ReviewRequest)
            .filter_by(session_id=session_id)
            .order_by(ReviewRequest.created_at)
            .all()
        )

    # -- notifications --------------------------------------------------------

    def list_notifications(self, officer_id: int, unread_only: bool = False) -> list[Notification]:
        q = self.session.query(Notification).filter_by(recipient_officer_id=officer_id)
        if unread_only:
            q = q.filter_by(read_at=None)
        return q.order_by(Notification.created_at.desc()).all()

    def mark_notification_read(self, notification_id: int) -> Notification | None:
        n = self.session.get(Notification, notification_id)
        if n is None:
            return None
        n.read_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(n)
        return n

    # -- presence ---------------------------------------------------------------

    def heartbeat_presence(self, session_id: int, officer_id: int, status: PresenceStatus) -> SessionPresence | None:
        session_row = self.session.get(InvestigationSession, session_id)
        if session_row is None:
            return None
        row = (
            self.session.query(SessionPresence)
            .filter_by(session_id=session_id, officer_id=officer_id)
            .first()
        )
        if row is None:
            row = SessionPresence(session_id=session_id, officer_id=officer_id, status=status)
            self.session.add(row)
        else:
            row.status = status
            row.last_seen_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_presence(self, session_id: int, ttl_seconds: int = PRESENCE_TTL_SECONDS) -> list[SessionPresence]:
        """Officers "currently present" — heartbeat within `ttl_seconds`.
        Stale rows aren't deleted (a late heartbeat should resume the same
        row, and the audit value of "who was here" outlives the TTL) —
        this just filters what counts as *currently* present."""
        cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds)
        return (
            self.session.query(SessionPresence)
            .filter(SessionPresence.session_id == session_id, SessionPresence.last_seen_at >= cutoff)
            .all()
        )

    # -- merged activity feed (human + AI + session + discussion actions) -----

    def get_activity_feed(self, session_id: int) -> list[dict]:
        """Stage C6's "Activity feed: Human actions, AI actions, Session
        actions, Discussion actions" — merges three tables that already
        exist for their own reasons (SessionActivity: Stage C1 session
        lifecycle + this sprint's collaboration events; ConversationTurn:
        Stage C2 conversation history; DiscussionRecord: Stage C4
        discussions) into one chronological view, rather than a fourth
        table duplicating all three."""
        feed = []

        for a in (self.session.query(SessionActivity).filter_by(session_id=session_id).all()):
            feed.append({
                "kind": "session", "event_type": a.event_type,
                "actor_officer_id": a.actor_officer_id, "detail": a.detail,
                "created_at": a.created_at,
            })

        for t in (self.session.query(ConversationTurn).filter_by(session_id=session_id).all()):
            feed.append({
                "kind": "ai_conversation", "event_type": "turn",
                "detail": f'Asked: "{t.raw_query}"' + (f" -> {t.response_summary[:150]}" if t.response_summary else ""),
                "created_at": t.created_at,
            })

        for d in (self.session.query(DiscussionRecord).filter_by(session_id=session_id).all()):
            feed.append({
                "kind": "discussion", "event_type": "discussion_run",
                "detail": f'Discussion on: "{d.query}"',
                "created_at": d.created_at,
            })

        feed.sort(key=lambda e: e["created_at"])
        for e in feed:
            e["created_at"] = e["created_at"].isoformat()
        return feed
