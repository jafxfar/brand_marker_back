"""Bootstrap src/modules from services/ and schemas/."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"

MAPPINGS = [
    ("auth", "auth_service.py", "auth.py"),
    ("companies", "company_service.py", "company.py"),
    ("catalog", "category_service.py", "category.py"),
    ("rfqs", "rfq_service.py", "rfq.py"),
    ("proposals", "proposal_service.py", "proposal.py"),
    ("contracts", "contract_service.py", "contract.py"),
    ("payments", "payment_service.py", None),
    ("reviews", "review_service.py", None),
    ("notifications", "notification_service.py", None),
    ("admin", "admin_service.py", None),
]

REPLACEMENTS = [
    ("from src.services.", "from src.modules."),
    ("from src.services import", "from src.shared.serializers import"),
    ("from src.schemas.", "from src.modules."),
    ("src.services.serializers", "src.shared.serializers"),
    ("src.services.rfq_service", "src.modules.rfqs.service"),
    ("src.services.contract_service", "src.modules.contracts.service"),
    ("src.services.notification_service", "src.modules.notifications.service"),
    ("src.services.proposal_service", "src.modules.proposals.service"),
    ("src.services.company_service", "src.modules.companies.service"),
    ("src.services.auth_service", "src.modules.auth.service"),
]

for module, service_file, schema_file in MAPPINGS:
    mod_dir = ROOT / "modules" / module
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "__init__.py").write_text("", encoding="utf-8")

    svc_src = ROOT / "services" / service_file
    svc_dst = mod_dir / "service.py"
    content = svc_src.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    svc_dst.write_text(content, encoding="utf-8")

    if schema_file:
        sch_src = ROOT / "schemas" / schema_file
        sch_dst = mod_dir / "schemas.py"
        content = sch_src.read_text(encoding="utf-8")
        for old, new in REPLACEMENTS:
            content = content.replace(old, new)
        sch_dst.write_text(content, encoding="utf-8")

# shared
shared = ROOT / "shared"
shared.mkdir(exist_ok=True)
enums = '''"""Re-export domain enums from ORM models."""
from src.models import (
    ActorType,
    BudgetType,
    CompanyRole,
    ContractStatus,
    Currency,
    NotificationType,
    PaymentMilestoneStatus,
    PaymentMilestoneTrigger,
    PaymentType,
    ProposalStatus,
    RfqStatus,
    RfqType,
    RfqVisibility,
    UserRole,
    UserStatus,
    VerificationStatus,
    WorkSubmissionStatus,
    WorkSubmissionType,
)

__all__ = [
    "ActorType",
    "BudgetType",
    "CompanyRole",
    "ContractStatus",
    "Currency",
    "NotificationType",
    "PaymentMilestoneStatus",
    "PaymentMilestoneTrigger",
    "PaymentType",
    "ProposalStatus",
    "RfqStatus",
    "RfqType",
    "RfqVisibility",
    "UserRole",
    "UserStatus",
    "VerificationStatus",
    "WorkSubmissionStatus",
    "WorkSubmissionType",
]
'''
(shared / "enums.py").write_text(enums, encoding="utf-8")
(shared / "__init__.py").write_text("", encoding="utf-8")

ser_src = ROOT / "services" / "serializers.py"
ser_content = ser_src.read_text(encoding="utf-8")
ser_content = ser_content.replace("from src.schemas.company", "from src.modules.companies.schemas")
(shared / "serializers.py").write_text(ser_content, encoding="utf-8")

# reviews + notifications schemas from common
common = (ROOT / "schemas" / "common.py").read_text(encoding="utf-8")
common = common.replace("from src.schemas.", "from src.modules.")
(ROOT / "modules" / "reviews" / "schemas.py").write_text(common, encoding="utf-8")
(ROOT / "modules" / "notifications" / "schemas.py").write_text(common, encoding="utf-8")

# payments - no dedicated schema, empty stub
(ROOT / "modules" / "payments" / "schemas.py").write_text(
    '"""Payment DTOs live in contract schemas for now."""\n', encoding="utf-8"
)
(ROOT / "modules" / "admin" / "schemas.py").write_text(
    'from src.modules.auth.schemas import UserPublic\n\n__all__ = ["UserPublic"]\n',
    encoding="utf-8",
)

print("Modules setup complete")
