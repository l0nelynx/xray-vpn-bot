from enum import Enum
from typing import Optional


class SubscriptionType(str, Enum):
    FREE = "free"
    PAID = "paid"


class SubscriptionScenario(str, Enum):
    NEW_USER = "new_user"
    EXTEND = "extend"
    UPDATE = "update"
    ALREADY_ACTIVE = "already_active"
    LIMITED = "limited"


def resolve_scenario(
    user_info: Optional[dict],
    subscription_type: SubscriptionType,
) -> SubscriptionScenario:
    """Pure resolver: which subscription scenario applies given the current
    Remnawave state and the requested subscription type.

    user_info is the normalized dict from RemnawaveClient (or None / 404 if the
    user does not yet exist in Remnawave).
    """
    if not user_info or user_info == 404:
        return SubscriptionScenario.NEW_USER

    status = user_info.get("status")
    limit = user_info.get("data_limit")
    is_paid_subscription = status == "active" and limit is None

    if subscription_type == SubscriptionType.FREE:
        if status == "limited":
            return SubscriptionScenario.LIMITED
        if user_info.get("expire") == 0 or status != "active":
            return SubscriptionScenario.UPDATE
        return SubscriptionScenario.ALREADY_ACTIVE

    if is_paid_subscription:
        return SubscriptionScenario.EXTEND
    return SubscriptionScenario.UPDATE
