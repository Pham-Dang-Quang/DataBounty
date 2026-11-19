from app.models import ContributionStatus

REVIEWABLE_STATUSES = {
    ContributionStatus.EVALUATING,
    ContributionStatus.READY,
    ContributionStatus.ERROR,
}
UNDECIDED_STATUSES = REVIEWABLE_STATUSES | {ContributionStatus.AWAITING_PAYOUT}
ACCEPTED_STATUSES = {ContributionStatus.PAID}
