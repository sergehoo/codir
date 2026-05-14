from rest_framework.exceptions import APIException
from rest_framework import status


class BusinessRuleError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Règle métier violée."
    default_code = "business_rule_error"


class TransitionNotAllowed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Transition de statut non autorisée."
    default_code = "transition_not_allowed"


class MeetingLocked(APIException):
    status_code = status.HTTP_423_LOCKED
    default_detail = "Réunion verrouillée — terminée ou annulée."
    default_code = "meeting_locked"
