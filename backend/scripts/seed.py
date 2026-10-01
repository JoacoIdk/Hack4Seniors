"""
Load demo data through the HTTP API (safe to run repeatedly):

- today's chess and crossword puzzles and missions
- the neighbourhood shops and their promotions
- a demo user (rosa@demo.cl / rosa1234) with some starting points

Requires ADMIN_EMAIL / ADMIN_PASSWORD (read from backend/.env) and a running API.

    python scripts/seed.py [http://localhost:8000]
"""

import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

_ = load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_URL = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
TODAY = datetime.now(ZoneInfo(os.getenv("APP_TIMEZONE", "America/Santiago"))).date().isoformat()

DEMO_USER = {
    "email": "rosa@demo.cl",
    "password": "rosa1234",
    "username": "rosa.martinez",
    "display_name": "Rosa Martínez",
    "city": "Santiago",
}
DEMO_STARTING_POINTS = 100
COMPANY_PASSWORD = "empresa1234"

# Chess: mate in 3 with two rooks ("mate de la escalera"). White plays.
CHESS_PUZZLE = {
    "kind": "chess",
    "title": "Desafío Ajedrez",
    "description": "Encuentra el jaque mate en 3 jugadas",
    "difficulty": "easy",
    "data": {
        "fen": "8/8/5k2/1R6/8/8/8/R6K w - - 0 1",
        "prompt": "Juegan las blancas. Da jaque mate en 3 jugadas.",
        # Alternates the user's move (white) and black's scripted reply.
        "line": [
            {"from": "a1", "to": "a6"},
            {"from": "f6", "to": "e7"},
            {"from": "b5", "to": "b7"},
            {"from": "e7", "to": "d8"},
            {"from": "a6", "to": "a8"},
        ],
        "notation": "1. Ta6+ Re7  2. Tb7+ Rd8  3. Ta8#",
        "explanation": (
            'Es el "mate de la escalera": las dos torres empujan al rey hacia el borde, fila por fila.\n\n'
            "1. Torre a6, jaque: la torre de b5 vigila la fila 5, así que el rey solo puede subir.\n"
            "2. Torre b7, jaque: ahora la torre de a6 vigila la fila 6 y el rey debe ir a la última fila.\n"
            "3. Torre a8, jaque mate: la fila 8 está en jaque y la torre de b7 cierra la fila 7. "
            "¡El rey no tiene escapatoria!"
        ),
    },
    "solution": ["Ra6", "Rb7", "Ra8"],
}

# Crossword (7x7). "#" = letter cell, "." = blank.
#   . A . . P . I
#   A B U E L O S
#   . R . . A . L
#   . A . . Y . A
#   A Z U C A R .
#   . O . . S . .
#   A S A R . . .
CROSSWORD_WORDS = [
    ("4-across", 4, "across", 1, 0, "ABUELOS", "Los padres de tus padres"),
    ("5-across", 5, "across", 4, 0, "AZUCAR", "Endulza el café o el té"),
    ("6-across", 6, "across", 6, 0, "ASAR", "Cocinar a la parrilla"),
    ("1-down", 1, "down", 0, 1, "ABRAZOS", "Muestras de cariño que se dan con los brazos"),
    ("2-down", 2, "down", 0, 4, "PLAYAS", "Lugares con arena junto al mar"),
    ("3-down", 3, "down", 0, 6, "ISLA", "Porción de tierra rodeada de agua"),
]
CROSSWORD_PUZZLE = {
    "kind": "crossword",
    "title": "Mini Crucigrama",
    "description": "6 palabras para ejercitar la memoria",
    "difficulty": "easy",
    "data": {
        "cells": [".#..#.#", "#######", ".#..#.#", ".#..#.#", "######.", ".#..#..", "####..."],
        "words": [
            {"id": i, "number": n, "direction": d, "row": r, "col": c, "length": len(a), "clue": clue}
            for i, n, d, r, c, a, clue in CROSSWORD_WORDS
        ],
    },
    "solution": {i: a for i, _, _, _, _, a, _ in CROSSWORD_WORDS},
}

MISSIONS = [
    {"kind": "checkin", "title": "Visita la app", "description": "Entra a la app hoy", "target": 1, "points": 5},
    {"kind": "solve_puzzles", "title": "Juega 2 juegos diarios", "description": "Resuelve dos juegos de hoy",
     "target": 2, "points": 10},
    {"kind": "add_friends", "title": "Haz un nuevo amigo", "description": "Escanea el QR de alguien en persona",
     "target": 1, "points": 15},
]

# (shop, category, promotion, discount %, points)
PROMOTIONS = [
    ("Panadería La Espiga", "Panadería", "Empanada de pino", 10, 50),
    ("Salón de Té Las Camelias", "Cafetería", "Té con galletas", 10, 60),
    ("Café Aroma", "Cafetería", "Café con medialuna", 15, 80),
    ("Heladería Polo Sur", "Heladería", "Helado doble", 25, 120),
    ("Restaurante El Rincón", "Restaurante", "Almuerzo del día", 20, 150),
    ("Pastelería Dulce Hogar", "Pastelería", "Trozo de torta", 20, 200),
]


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status


def call(method: str, path: str, body=None, token: str | None = None):
    request = urllib.request.Request(
        API_URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read() or "null")
    except urllib.error.HTTPError as error:
        raise ApiError(error.code, error.read().decode()) from None


def login(email: str, password: str, role: str) -> dict:
    return call("POST", "/auth/login", {"email": email, "password": password, "role": role})


def slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def seed_daily(admin: str) -> None:
    existing = {p["kind"] for p in call("GET", f"/corporate/puzzles?from={TODAY}&to={TODAY}", token=admin)}
    for puzzle in (CHESS_PUZZLE, CROSSWORD_PUZZLE):
        if puzzle["kind"] not in existing:
            _ = call("POST", "/corporate/puzzles", {**puzzle, "date": TODAY}, token=admin)
            print(f"  + puzzle {puzzle['title']}")

    existing = {m["kind"] for m in call("GET", f"/corporate/missions?from={TODAY}&to={TODAY}", token=admin)}
    for mission in MISSIONS:
        if mission["kind"] not in existing:
            _ = call("POST", "/corporate/missions", {**mission, "date": TODAY}, token=admin)
            print(f"  + mission {mission['title']}")


def seed_market(admin: str) -> None:
    existing = {c["name"] for c in call("GET", "/corporate/companies?limit=100", token=admin)}
    for shop, category, title, discount, cost in PROMOTIONS:
        if shop in existing:
            continue
        company = call("POST", "/corporate/companies", {"name": shop, "category": category}, token=admin)
        email = f"{slug(shop)}@demo.cl"
        _ = call("POST", f"/corporate/companies/{company['id']}/accounts", {
            "email": email, "password": COMPANY_PASSWORD, "display_name": shop,
        }, token=admin)
        staff = login(email, COMPANY_PASSWORD, "company")["access_token"]
        _ = call("POST", "/company/promotions", {
            "title": title, "category": category, "discount_type": "percent",
            "discount_value": discount, "points_cost": cost,
        }, token=staff)
        print(f"  + {shop}: {title}")


def seed_demo_user(admin: str) -> None:
    try:
        _ = login(DEMO_USER["email"], DEMO_USER["password"], "user")
        return
    except ApiError as error:
        if error.status != 401:
            raise
    user = call("POST", "/auth/register", DEMO_USER)["account"]
    _ = call("POST", f"/corporate/users/{user['id']}/points", {
        "amount": DEMO_STARTING_POINTS, "description": "Puntos de bienvenida",
    }, token=admin)
    print(f"  + demo user {DEMO_USER['email']} / {DEMO_USER['password']}")


def main() -> None:
    email, password = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if not (email and password):
        sys.exit("Set ADMIN_EMAIL and ADMIN_PASSWORD in backend/.env to seed demo data.")
    print(f"Seeding {API_URL} for {TODAY}")
    admin = login(email, password, "corporate")["access_token"]
    seed_daily(admin)
    seed_market(admin)
    seed_demo_user(admin)


if __name__ == "__main__":
    main()
