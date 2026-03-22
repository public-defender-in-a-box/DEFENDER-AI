from .suppress import SUPPRESS_TEMPLATE
from .bail_reduction import BAIL_REDUCTION_TEMPLATE
from .dismiss import DISMISS_TEMPLATE
from .discovery_brady import DISCOVERY_BRADY_TEMPLATE
from .limine import LIMINE_TEMPLATE

TEMPLATES: dict[str, dict] = {
    "motion_to_suppress": SUPPRESS_TEMPLATE,
    "motion_for_bail_reduction": BAIL_REDUCTION_TEMPLATE,
    "motion_to_dismiss": DISMISS_TEMPLATE,
    "discovery_brady_demand": DISCOVERY_BRADY_TEMPLATE,
    "motion_in_limine": LIMINE_TEMPLATE,
}
