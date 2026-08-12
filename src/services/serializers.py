from src.models import Company, CompanyUser, Contract, Message, Proposal, Rfq
from src.schemas.company import (
    CompanyCategorySchema,
    CompanyCertificateSchema,
    CompanyProfileSchema,
    CompanyStatsSchema,
    CompanyUserSchema,
    CompanyWithRelations,
    ReviewSchema,
)


def _user_display_name(user) -> str:
    if not user:
        return "Участник"
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email or "Участник"


def _message_to_dict(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "sender_name": _user_display_name(getattr(msg, "sender", None)),
        "text": msg.text,
        "attachment": None,
        "created_at": msg.created_at,
    }


def _submission_assets(submission) -> list[dict]:
    raw = getattr(submission, "assets", None) or []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") or "file"
        name = item.get("name") or ""
        url = item.get("url") or ""
        if not name or not url:
            continue
        result.append(
            {
                "kind": kind,
                "name": name,
                "url": url,
                "file_type": item.get("file_type"),
            }
        )
    if result:
        return result
    return [
        {"kind": "file", "name": name, "url": "#", "file_type": None}
        for name in (submission.file_names or [])
        if name
    ]


def company_to_schema(company: Company) -> CompanyWithRelations:
    team_members = [m.user_id for m in company.members]
    company_users = [
        CompanyUserSchema(
            id=m.id,
            company_id=m.company_id,
            user_id=m.user_id,
            role=m.role.value,
            email=m.user.email if m.user else None,
        )
        for m in company.members
    ]
    return CompanyWithRelations(
        id=company.id,
        title=company.title,
        actor_type=company.actor_type.value,
        owner_id=company.owner_id,
        team_members=team_members,
        legal_name=company.legal_name,
        tax_number=company.tax_number,
        website=company.website,
        description=company.description,
        logo=company.logo,
        country=company.country,
        city=company.city,
        address=company.address,
        verification_status=company.verification_status.value,
        rating=company.rating,
        created_at=company.created_at,
        updated_at=company.updated_at,
        profile=CompanyProfileSchema.model_validate(company.profile) if company.profile else None,
        categories=[CompanyCategorySchema.model_validate(c) for c in company.categories],
        stats=CompanyStatsSchema.model_validate(company.stats) if company.stats else None,
        certificates=[CompanyCertificateSchema.model_validate(c) for c in company.certificates],
        reviews=[ReviewSchema.model_validate(r) for r in company.reviews_received],
        company_users=company_users,
    )


def rfq_to_response(rfq: Rfq) -> dict:
    base = {
        "id": rfq.id,
        "actor_id": str(rfq.actor_id),
        "created_by": rfq.created_by,
        "title": rfq.title,
        "description": rfq.description,
        "category_id": rfq.category_id,
        "budget_type": rfq.budget_type.value,
        "budget_from": rfq.budget_from,
        "budget_to": rfq.budget_to,
        "currency": rfq.currency,
        "deadline": rfq.deadline,
        "visibility": rfq.visibility.value,
        "status": rfq.status.value,
        "created_at": rfq.created_at,
        "updated_at": rfq.updated_at,
        "attachments": [
            {
                "id": a.id,
                "rfq_id": a.rfq_id,
                "file_name": a.file_name,
                "file_url": a.file_url,
                "file_type": a.file_type,
            }
            for a in rfq.attachments
        ],
        "invited_supplier_ids": [i.supplier_id for i in rfq.invited_suppliers],
    }
    if rfq.type.value == "product":
        return {
            **base,
            "type": "product",
            "quantity": rfq.quantity,
            "delivery_country": rfq.delivery_country,
            "delivery_city": rfq.delivery_city,
            "delivery_address": rfq.delivery_address,
            "delivery_date": rfq.delivery_date,
        }
    return {
        **base,
        "type": "service",
        "project_duration": rfq.project_duration,
        "start_date": rfq.start_date,
        "team_size_required": rfq.team_size_required,
        "experience_required": rfq.experience_required,
    }


def proposal_to_schema(proposal: Proposal) -> dict:
    data = {
        "id": proposal.id,
        "rfq_id": proposal.rfq_id,
        "supplier_actor_id": proposal.supplier_actor_id,
        "price": proposal.price,
        "currency": proposal.currency.value,
        "delivery_time": proposal.delivery_time,
        "message": proposal.message,
        "status": proposal.status.value,
        "created_at": proposal.created_at,
        "attachment": None,
    }
    if proposal.attachment:
        data["attachment"] = {
            "id": proposal.attachment.id,
            "proposal_id": proposal.attachment.proposal_id,
            "file_name": proposal.attachment.file_name,
            "file_url": proposal.attachment.file_url,
            "file_type": proposal.attachment.file_type,
        }
    return data


def contract_to_schema(contract: Contract) -> dict:
    payment_plan = None
    if contract.payment_plan:
        payment_plan = {
            "id": contract.payment_plan.id,
            "contract_id": contract.payment_plan.contract_id,
            "payment_type": contract.payment_plan.payment_type.value,
            "milestones": [
                {
                    "id": m.id,
                    "contract_id": m.contract_id,
                    "title": m.title,
                    "percentage": m.percentage,
                    "amount": m.amount,
                    "trigger": m.trigger,
                    "status": m.status.value,
                }
                for m in contract.payment_plan.milestones
            ],
        }
    conversation = None
    if contract.conversation:
        conversation = {
            "id": contract.conversation.id,
            "contract_id": contract.conversation.contract_id,
            "messages": [
                _message_to_dict(msg) for msg in contract.conversation.messages
            ],
        }
    return {
        "id": contract.id,
        "rfq_id": contract.rfq_id,
        "proposal_id": contract.proposal_id,
        "buyer_actor_id": contract.buyer_actor_id,
        "supplier_actor_id": contract.supplier_actor_id,
        "title": contract.title,
        "description": contract.description,
        "agreed_amount": contract.agreed_amount,
        "currency": contract.currency.value,
        "start_date": contract.start_date,
        "due_date": contract.due_date,
        "payment_type": contract.payment_type.value,
        "status": contract.status.value,
        "created_at": contract.created_at,
        "payment_plan": payment_plan,
        "conversation": conversation,
        "files": [
            {
                "id": f.id,
                "contract_id": f.contract_id,
                "file_name": f.file_name,
                "file_url": f.file_url,
                "file_type": f.file_type,
                "uploaded_by": f.uploaded_by,
                "created_at": f.created_at,
            }
            for f in contract.files
        ],
        "submissions": [
            {
                "id": s.id,
                "contract_id": s.contract_id,
                "type": s.type.value,
                "note": s.note,
                "status": s.status.value,
                "submitted_at": s.submitted_at,
                "file_names": s.file_names or [a["name"] for a in _submission_assets(s)],
                "assets": _submission_assets(s),
            }
            for s in contract.submissions
        ],
    }
