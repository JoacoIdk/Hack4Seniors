"""
Request and response schemas.

Response models double as field filters: routes return raw storage rows and
FastAPI drops anything not declared here (password hashes, puzzle solutions…).
"""

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, model_validator

Day = date  # alias: fields named "date" would otherwise shadow the type

# Shared types -------------------------------------------------------------------

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL.match(value):
        raise ValueError("Invalid email address")
    return value


Email = Annotated[str, AfterValidator(_email)]
Username = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().lower() if isinstance(v, str) else v),
    Field(pattern=r"^[a-z0-9_.]{3,30}$"),
]
Password = Annotated[str, Field(min_length=8, max_length=128)]
Role = Literal["user", "company", "corporate"]
CorporateLevel = Literal["support", "admin", "superadmin"]
MissionKind = Literal["checkin", "send_messages", "chat_people", "solve_puzzles", "redeem_promos", "add_friends"]
PuzzleKind = Literal["chess", "crossword", "sudoku", "wordsearch", "trivia", "riddle", "other"]
PromotionKind = Literal["individual", "group"]
DiscountType = Literal["percent", "amount"]
TicketStatus = Literal["open", "in_progress", "resolved", "closed"]
TicketPriority = Literal["low", "normal", "high", "urgent"]


class Message(BaseModel):
    detail: str


# Auth ---------------------------------------------------------------------------

class RegisterIn(BaseModel):
    email: Email
    password: Password
    username: Username
    display_name: str = Field(min_length=1, max_length=80)
    city: str | None = Field(None, max_length=80)
    birth_date: date | None = None
    language: str = Field("es", max_length=10)


class LoginIn(BaseModel):
    email: Email
    password: str
    role: Role | None = Field(None, description="If set, login fails unless the account has this role.")


class CompanyOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    category: str | None = None
    logo_url: str | None = None
    website: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    address: str | None = None


class AccountOut(BaseModel):
    id: int
    role: Role
    corporate_level: CorporateLevel | None = None
    company_id: int | None = None
    company: CompanyOut | None = None
    email: str
    username: str | None = None
    display_name: str
    language: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    account: AccountOut


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: Password


# Users / profiles -----------------------------------------------------------------

class PublicProfile(BaseModel):
    """What other users can see. Never includes points or email."""
    id: int
    username: str | None = None
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    city: str | None = None
    interests: list[str] = []
    created_at: datetime


class FriendProfile(PublicProfile):
    is_friend: bool = False


class MeOut(PublicProfile):
    email: str
    birth_date: date | None = None
    language: str
    points: int


class ProfileUpdate(BaseModel):
    username: Username | None = None
    display_name: str | None = Field(None, min_length=1, max_length=80)
    bio: str | None = Field(None, max_length=500)
    avatar_url: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=80)
    birth_date: date | None = None
    interests: list[Annotated[str, Field(max_length=40)]] | None = Field(None, max_length=20)
    language: str | None = Field(None, max_length=10)


# Points ---------------------------------------------------------------------------

class PointTransactionOut(BaseModel):
    id: int
    amount: int
    reason: str
    reference_type: str | None = None
    reference_id: int | None = None
    description: str | None = None
    day: date
    created_at: datetime


class PointsToday(BaseModel):
    chat: int
    puzzle: int
    mission: int
    earned: int
    spent: int


class PointsSummary(BaseModel):
    balance: int
    today: PointsToday
    puzzle_points_remaining_today: int


class ChatLimitOut(BaseModel):
    partner: PublicProfile
    earned_since_reset: int
    remaining: int
    awarded_today: bool


# Friends & chat -------------------------------------------------------------------

class FriendCodeOut(BaseModel):
    code: str = Field(description="Encode this in the QR shown to the other person.")
    expires_in: int


class FriendScanIn(BaseModel):
    code: str


class FriendScanOut(BaseModel):
    status: Literal["pending", "friends", "already_friends"]
    user: PublicProfile
    detail: str


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    body: str
    created_at: datetime
    read_at: datetime | None = None


class SendMessageOut(BaseModel):
    message: MessageOut
    points_awarded: int


class ChatOut(BaseModel):
    friend: PublicProfile
    friends_since: datetime
    last_message: MessageOut | None = None
    unread_count: int


# Missions -------------------------------------------------------------------------

class MissionIn(BaseModel):
    date: Day
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    kind: MissionKind
    target: int = Field(1, ge=1, le=1000)
    points: int = Field(ge=0, le=10000)
    active: bool = True


class MissionUpdate(BaseModel):
    date: Day | None = None
    title: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    kind: MissionKind | None = None
    target: int | None = Field(None, ge=1, le=1000)
    points: int | None = Field(None, ge=0, le=10000)
    active: bool | None = None


class MissionAdminOut(BaseModel):
    id: int
    date: Day
    title: str
    description: str | None = None
    kind: MissionKind
    target: int
    points: int
    active: bool
    created_at: datetime


class MissionOut(BaseModel):
    id: int
    date: Day
    title: str
    description: str | None = None
    kind: MissionKind
    target: int
    points: int
    progress: int
    completed: bool
    claimed: bool


class MissionClaimOut(BaseModel):
    mission_id: int
    points_awarded: int
    balance: int


# Puzzles --------------------------------------------------------------------------

class PuzzleIn(BaseModel):
    date: Day
    kind: PuzzleKind
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    data: dict[str, Any] = Field(default_factory=dict, description="Board/grid/clues sent to players.")
    solution: Any = Field(
        description='Expected answer. Use {"any_of": [...]} to accept several answers.'
    )
    active: bool = True


class PuzzleUpdate(BaseModel):
    date: Day | None = None
    kind: PuzzleKind | None = None
    title: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    data: dict[str, Any] | None = None
    solution: Any = None
    active: bool | None = None


class PuzzleOut(BaseModel):
    id: int
    date: Day
    kind: PuzzleKind
    title: str
    description: str | None = None
    difficulty: str | None = None
    data: dict[str, Any]
    solved: bool = False
    attempts: int = 0


class PuzzleAdminOut(PuzzleOut):
    solution: Any
    active: bool
    created_at: datetime


class PuzzleSolveIn(BaseModel):
    answer: Any


class PuzzleSolveOut(BaseModel):
    correct: bool
    already_solved: bool
    attempts: int
    points_awarded: int
    puzzle_points_today: int
    puzzle_points_remaining_today: int


# Promotions / market ------------------------------------------------------------

class PromotionIn(BaseModel):
    kind: PromotionKind = "individual"
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    terms: str | None = Field(None, max_length=2000)
    category: str | None = Field(None, max_length=60)
    image_url: str | None = Field(None, max_length=500)
    points_cost: int = Field(0, ge=0)
    discount_type: DiscountType
    discount_value: float = Field(gt=0, description="Discount per person (group) or total (individual).")
    max_discount: float | None = Field(None, gt=0, description="Group promos: cap for the whole order.")
    stock: int | None = Field(None, ge=0)
    per_user_limit: int | None = Field(None, ge=1)
    starts_on: date | None = None
    ends_on: date | None = None
    redemption_valid_days: int = Field(30, ge=1, le=365)
    active: bool = True

    @model_validator(mode="after")
    def _check(self) -> "PromotionIn":
        validate_discount(self.kind, self.discount_type, self.discount_value, self.max_discount)
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


def validate_discount(kind: str, discount_type: str, value: float, cap: float | None) -> None:
    if discount_type == "percent" and value > 100:
        raise ValueError("Percent discounts cannot exceed 100")
    if kind == "group":
        if cap is None:
            raise ValueError("Group promotions require max_discount")
        if cap < value:
            raise ValueError("max_discount must be at least discount_value")
        if discount_type == "percent" and cap > 100:
            raise ValueError("Percent discounts cannot exceed 100")


class PromotionUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    terms: str | None = Field(None, max_length=2000)
    category: str | None = Field(None, max_length=60)
    image_url: str | None = Field(None, max_length=500)
    points_cost: int | None = Field(None, ge=0)
    discount_type: DiscountType | None = None
    discount_value: float | None = Field(None, gt=0)
    max_discount: float | None = Field(None, gt=0)
    stock: int | None = Field(None, ge=0)
    per_user_limit: int | None = Field(None, ge=1)
    starts_on: date | None = None
    ends_on: date | None = None
    redemption_valid_days: int | None = Field(None, ge=1, le=365)
    active: bool | None = None


class PromotionOut(BaseModel):
    id: int
    company_id: int
    company_name: str | None = None
    kind: PromotionKind
    title: str
    description: str | None = None
    terms: str | None = None
    category: str | None = None
    image_url: str | None = None
    points_cost: int
    discount_type: DiscountType
    discount_value: float
    max_discount: float | None = None
    stock: int | None = None
    per_user_limit: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    redemption_valid_days: int


class CompanyPromotionOut(PromotionOut):
    active: bool
    views: int
    created_at: datetime
    updated_at: datetime


class MarketCompanyOut(CompanyOut):
    promotions: list[PromotionOut] = []


class RedemptionOut(BaseModel):
    id: int
    code: str = Field(description="Render as a QR code; cashiers can also type it.")
    promotion_id: int
    promotion_title: str | None = None
    promotion_kind: PromotionKind | None = None
    company_id: int
    company_name: str | None = None
    points_spent: int
    status: Literal["active", "reserved", "claimed", "cancelled", "expired"]
    discount_applied: float | None = None
    created_at: datetime
    expires_at: datetime
    claimed_at: datetime | None = None


# Company: checkouts --------------------------------------------------------------

class CheckoutIn(BaseModel):
    reference: str | None = Field(None, max_length=80, description="Store order number, optional.")


class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class CheckoutRedemptionOut(BaseModel):
    code: str
    customer_name: str
    discount_applied: float | None = None
    status: str


class CheckoutOut(BaseModel):
    id: int
    reference: str | None = None
    status: Literal["open", "completed", "cancelled"]
    promotion: PromotionOut | None = None
    discount_type: DiscountType | None = None
    total_discount: float
    max_discount: float | None = None
    participants: int
    redemptions: list[CheckoutRedemptionOut] = []
    created_at: datetime
    closed_at: datetime | None = None


class RedemptionLookupOut(BaseModel):
    code: str
    status: str
    customer_name: str
    promotion: PromotionOut
    created_at: datetime
    expires_at: datetime
    claimed_at: datetime | None = None
    usable: bool
    detail: str


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    category: str | None = Field(None, max_length=60)
    logo_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=300)
    contact_email: Email | None = None
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)


# Tickets --------------------------------------------------------------------------

class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=150)
    category: str | None = Field(None, max_length=60)
    body: str = Field(min_length=1, max_length=5000)


class TicketMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class TicketMessageOut(BaseModel):
    id: int
    author_id: int
    author_name: str | None = None
    from_staff: bool
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    id: int
    author_id: int
    author_name: str | None = None
    author_role: Role
    company_id: int | None = None
    subject: str
    category: str | None = None
    status: TicketStatus
    priority: TicketPriority
    assigned_to: int | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[TicketMessageOut] = []


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: int | None = None


# Corporate ------------------------------------------------------------------------

class CorporateAccountOut(AccountOut):
    """Full account view for corporate staff (includes points)."""
    bio: str | None = None
    avatar_url: str | None = None
    city: str | None = None
    birth_date: date | None = None
    points: int
    chat_limit_epoch: int


class AccountUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=80)
    email: Email | None = None
    status: Literal["active", "banned"] | None = None


class PointsAdjustIn(BaseModel):
    amount: int = Field(description="Positive to add, negative to remove.")
    description: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _non_zero(self) -> "PointsAdjustIn":
        if self.amount == 0:
            raise ValueError("amount cannot be 0")
        return self


class PointsAdjustOut(BaseModel):
    user_id: int
    amount: int
    balance: int


class ResetLimitOut(BaseModel):
    user_id: int
    chat_limit_epoch: int
    detail: str


class StaffAccountIn(BaseModel):
    email: Email
    password: Password
    display_name: str = Field(min_length=1, max_length=80)


class CorporateAccountIn(StaffAccountIn):
    corporate_level: CorporateLevel = "support"


class CorporateLevelUpdate(BaseModel):
    corporate_level: CorporateLevel


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    category: str | None = Field(None, max_length=60)
    logo_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=300)
    contact_email: Email | None = None
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)


class CompanyAdminUpdate(CompanyUpdate):
    status: Literal["active", "inactive"] | None = None


class CompanyAdminOut(CompanyOut):
    status: str
    created_at: datetime


# Statistics -----------------------------------------------------------------------

class DailyCount(BaseModel):
    day: date
    redemptions: int
    claims: int


class PromotionStats(BaseModel):
    promotion_id: int
    title: str
    kind: PromotionKind
    active: bool
    views: int
    redemptions: int
    claimed: int
    pending: int
    cancelled: int
    expired: int
    points_spent: int
    unique_customers: int


class CompanyStats(BaseModel):
    promotions: int
    active_promotions: int
    total_views: int
    redemptions: int
    claimed: int
    unique_customers: int
    points_spent: int
    checkouts_completed: int
    average_group_size: float | None = None
    total_amount_discounted: float = Field(description="Sum of fixed-amount discounts given at checkout.")
    daily: list[DailyCount]
    by_promotion: list[PromotionStats]


class PlatformStats(BaseModel):
    users: int
    users_banned: int
    new_users_today: int
    active_users_today: int
    companies: int
    active_companies: int
    friendships: int
    messages_today: int
    points_in_circulation: int
    points_earned_today: int
    redemptions: int
    redemptions_claimed: int
    open_tickets: int


# Languages ------------------------------------------------------------------------

class LanguageOut(BaseModel):
    code: str
    name: str
