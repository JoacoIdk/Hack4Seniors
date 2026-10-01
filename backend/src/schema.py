"""
Database schema. Column definitions are PostgreSQL DDL; the flatfile backend
only uses the table names. Application code always inserts every column
explicitly, so both backends store identical rows.
"""

import logging

import config
from datastore import Storage
from services.accounts import create_account

logger = logging.getLogger(__name__)

ID = "SERIAL PRIMARY KEY"
NOW = "TIMESTAMPTZ NOT NULL DEFAULT now()"


def ref(table: str, nullable: bool = False, cascade: bool = False) -> str:
    return (
        f"INTEGER {'' if nullable else 'NOT NULL '}REFERENCES {table}(id)"
        f"{' ON DELETE CASCADE' if cascade else ''}"
    )


# (table, columns, constraints) — order matters for foreign keys.
TABLES: list[tuple[str, dict[str, str], list[str]]] = [
    ("companies", {
        "id": ID,
        "name": "TEXT NOT NULL",
        "description": "TEXT",
        "category": "TEXT",
        "logo_url": "TEXT",
        "website": "TEXT",
        "contact_email": "TEXT",
        "phone": "TEXT",
        "address": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'active'",  # active | inactive
        "created_at": NOW,
    }, []),

    # Every account (user, company staff, corporate staff) lives here.
    ("users", {
        "id": ID,
        "role": "TEXT NOT NULL",  # user | company | corporate
        "corporate_level": "TEXT",  # support | admin | superadmin (corporate only)
        "company_id": ref("companies", nullable=True),
        "email": "TEXT NOT NULL UNIQUE",
        "password_hash": "TEXT NOT NULL",
        "username": "TEXT UNIQUE",
        "display_name": "TEXT NOT NULL",
        "bio": "TEXT",
        "avatar_url": "TEXT",
        "city": "TEXT",
        "birth_date": "DATE",
        "interests": "JSONB NOT NULL DEFAULT '[]'",
        "language": "TEXT NOT NULL DEFAULT 'es'",
        "points": "INTEGER NOT NULL DEFAULT 0",
        "chat_limit_epoch": "INTEGER NOT NULL DEFAULT 0",  # bumped by reset_limit
        "status": "TEXT NOT NULL DEFAULT 'active'",  # active | banned | deleted
        "created_at": NOW,
        "last_login_at": "TIMESTAMPTZ",
    }, ["CHECK (points >= 0)"]),

    # Ledger of every point movement; users.points is the running balance.
    ("point_transactions", {
        "id": ID,
        "user_id": ref("users"),
        "amount": "INTEGER NOT NULL",
        "reason": "TEXT NOT NULL",  # chat | puzzle | mission | redemption | refund | adjustment
        "reference_type": "TEXT",
        "reference_id": "INTEGER",
        "description": "TEXT",
        "actor_id": ref("users", nullable=True),  # corporate account for manual adjustments
        "day": "DATE NOT NULL",
        "created_at": NOW,
    }, []),

    # One-directional scans; two matching scans within the window make a friendship.
    ("friend_scans", {
        "id": ID,
        "scanner_id": ref("users"),
        "target_id": ref("users"),
        "created_at": NOW,
    }, []),

    # user_a_id < user_b_id. Each friendship is also the chat between both users.
    ("friendships", {
        "id": ID,
        "user_a_id": ref("users"),
        "user_b_id": ref("users"),
        "created_at": NOW,
        "last_message_at": "TIMESTAMPTZ",
    }, ["UNIQUE (user_a_id, user_b_id)", "CHECK (user_a_id < user_b_id)"]),

    ("messages", {
        "id": ID,
        "friendship_id": ref("friendships", cascade=True),
        "sender_id": ref("users"),
        "recipient_id": ref("users"),
        "body": "TEXT NOT NULL",
        "day": "DATE NOT NULL",
        "created_at": NOW,
        "read_at": "TIMESTAMPTZ",
    }, []),

    ("chat_awards", {
        "id": ID,
        "user_id": ref("users"),
        "partner_id": ref("users"),
        "day": "DATE NOT NULL",
        "epoch": "INTEGER NOT NULL",
        "points": "INTEGER NOT NULL",
        "created_at": NOW,
    }, ["UNIQUE (user_id, partner_id, day)"]),

    ("missions", {
        "id": ID,
        "date": "DATE NOT NULL",
        "title": "TEXT NOT NULL",
        "description": "TEXT",
        "kind": "TEXT NOT NULL",
        "target": "INTEGER NOT NULL DEFAULT 1",
        "points": "INTEGER NOT NULL",
        "active": "BOOLEAN NOT NULL DEFAULT TRUE",
        "created_by": ref("users", nullable=True),
        "created_at": NOW,
    }, []),

    ("mission_claims", {
        "id": ID,
        "mission_id": ref("missions", cascade=True),
        "user_id": ref("users"),
        "points": "INTEGER NOT NULL",
        "created_at": NOW,
    }, ["UNIQUE (mission_id, user_id)"]),

    ("puzzles", {
        "id": ID,
        "date": "DATE NOT NULL",
        "kind": "TEXT NOT NULL",  # chess | crossword | sudoku | wordsearch | trivia | riddle | other
        "title": "TEXT NOT NULL",
        "description": "TEXT",
        "difficulty": "TEXT",
        "data": "JSONB NOT NULL DEFAULT '{}'",  # sent to clients
        "solution": "JSONB NOT NULL",  # never sent to users
        "active": "BOOLEAN NOT NULL DEFAULT TRUE",
        "created_by": ref("users", nullable=True),
        "created_at": NOW,
    }, []),

    ("puzzle_plays", {
        "id": ID,
        "puzzle_id": ref("puzzles", cascade=True),
        "user_id": ref("users"),
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "solved": "BOOLEAN NOT NULL DEFAULT FALSE",
        "solved_at": "TIMESTAMPTZ",
        "solved_day": "DATE",
        "points_awarded": "INTEGER NOT NULL DEFAULT 0",
        "created_at": NOW,
    }, ["UNIQUE (puzzle_id, user_id)"]),

    # Promotions double as market ads.
    ("promotions", {
        "id": ID,
        "company_id": ref("companies"),
        "kind": "TEXT NOT NULL",  # individual | group
        "title": "TEXT NOT NULL",
        "description": "TEXT",
        "terms": "TEXT",
        "category": "TEXT",
        "image_url": "TEXT",
        "points_cost": "INTEGER NOT NULL DEFAULT 0",
        "discount_type": "TEXT NOT NULL",  # percent | amount
        "discount_value": "DOUBLE PRECISION NOT NULL",  # per person for group promos
        "max_discount": "DOUBLE PRECISION",  # group cap, same unit as discount_type
        "stock": "INTEGER",  # NULL = unlimited
        "per_user_limit": "INTEGER",  # NULL = unlimited
        "starts_on": "DATE",
        "ends_on": "DATE",
        "redemption_valid_days": "INTEGER NOT NULL DEFAULT 30",
        "active": "BOOLEAN NOT NULL DEFAULT TRUE",
        "views": "INTEGER NOT NULL DEFAULT 0",
        "created_at": NOW,
        "updated_at": NOW,
    }, ["CHECK (stock IS NULL OR stock >= 0)"]),

    # A cashier's order: one or more redemption QR codes scanned together.
    ("checkouts", {
        "id": ID,
        "company_id": ref("companies"),
        "promotion_id": ref("promotions", nullable=True),
        "reference": "TEXT",  # optional order/ticket number from the store
        "status": "TEXT NOT NULL DEFAULT 'open'",  # open | completed | cancelled
        "discount_type": "TEXT",
        "total_discount": "DOUBLE PRECISION NOT NULL DEFAULT 0",
        "participants": "INTEGER NOT NULL DEFAULT 0",
        "opened_by": ref("users"),
        "created_at": NOW,
        "closed_at": "TIMESTAMPTZ",
    }, []),

    ("redemptions", {
        "id": ID,
        "code": "TEXT NOT NULL UNIQUE",
        "user_id": ref("users"),
        "promotion_id": ref("promotions"),
        "company_id": ref("companies"),
        "points_spent": "INTEGER NOT NULL",
        "status": "TEXT NOT NULL DEFAULT 'active'",  # active | reserved | claimed | cancelled
        "checkout_id": ref("checkouts", nullable=True),
        "discount_applied": "DOUBLE PRECISION",
        "day": "DATE NOT NULL",
        "created_at": NOW,
        "expires_at": "TIMESTAMPTZ NOT NULL",
        "claimed_at": "TIMESTAMPTZ",
        "claimed_by": ref("users", nullable=True),
    }, []),

    ("tickets", {
        "id": ID,
        "author_id": ref("users"),
        "author_role": "TEXT NOT NULL",
        "company_id": ref("companies", nullable=True),
        "subject": "TEXT NOT NULL",
        "category": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'open'",  # open | in_progress | resolved | closed
        "priority": "TEXT NOT NULL DEFAULT 'normal'",  # low | normal | high | urgent
        "assigned_to": ref("users", nullable=True),
        "created_at": NOW,
        "updated_at": NOW,
    }, []),

    ("ticket_messages", {
        "id": ID,
        "ticket_id": ref("tickets", cascade=True),
        "author_id": ref("users"),
        "from_staff": "BOOLEAN NOT NULL DEFAULT FALSE",
        "body": "TEXT NOT NULL",
        "created_at": NOW,
    }, []),
]

INDEXES: list[tuple[str, list[str]]] = [
    ("point_transactions", ["user_id", "day"]),
    ("friend_scans", ["scanner_id", "target_id"]),
    ("messages", ["friendship_id", "id"]),
    ("messages", ["sender_id", "day"]),
    ("chat_awards", ["user_id", "partner_id", "epoch"]),
    ("missions", ["date"]),
    ("puzzles", ["date"]),
    ("puzzle_plays", ["user_id", "solved_day"]),
    ("promotions", ["company_id"]),
    ("redemptions", ["user_id", "promotion_id"]),
    ("redemptions", ["company_id", "status"]),
    ("redemptions", ["checkout_id"]),
    ("tickets", ["status"]),
]


async def create_schema(storage: Storage) -> None:
    for table, columns, constraints in TABLES:
        await storage.create_table(table, columns, constraints)
    for table, columns in INDEXES:
        await storage.create_index(table, columns)


async def bootstrap_admin(storage: Storage) -> None:
    """Create the first superadmin from ADMIN_EMAIL / ADMIN_PASSWORD if missing."""
    if not (config.ADMIN_EMAIL and config.ADMIN_PASSWORD):
        if not await storage.exists("users", {"role": "corporate"}):
            logger.warning("No corporate account exists; set ADMIN_EMAIL and ADMIN_PASSWORD to create one.")
        return
    email = config.ADMIN_EMAIL.strip().lower()
    if await storage.exists("users", {"email": email}):
        return
    _ = await create_account(
        storage,
        role="corporate",
        corporate_level="superadmin",
        email=email,
        password=config.ADMIN_PASSWORD,
        display_name="Administrator",
    )
    logger.info("Created superadmin account %s", email)
