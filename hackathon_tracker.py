#!/usr/bin/env python3
"""
Hackathon Team Formation and Idea Tracker
=========================================

A dependency-free command line app (Python 3.8+ and SQLite) that helps
hackathon organizers and participants:

  * register participants and their skills
  * pitch, vote on and track project ideas
  * create teams and assign members
  * get skill-based teammate suggestions
  * export data and view summary stats

Usage examples:
    python hackathon_tracker.py add-participant "Asha" asha@mail.com "python,ml,design"
    python hackathon_tracker.py add-idea "Smart Recycler" "AI bin sorter" --owner 1
    python hackathon_tracker.py vote 1 --participant 2
    python hackathon_tracker.py create-team "Green Coders" --idea 1 --max-size 4
    python hackathon_tracker.py join-team 1 --participant 2
    python hackathon_tracker.py suggest 1
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.environ.get("HACKATHON_DB", "hackathon.db")

IDEA_STATUSES = ["proposed", "approved", "in-progress", "completed", "rejected"]
DEFAULT_MAX_TEAM_SIZE = 5


SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    skills      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    owner_id     INTEGER,
    status       TEXT NOT NULL DEFAULT 'proposed',
    needed_skills TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES participants(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS votes (
    idea_id        INTEGER NOT NULL,
    participant_id INTEGER NOT NULL,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (idea_id, participant_id),
    FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teams (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    idea_id    INTEGER,
    max_size   INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS team_members (
    team_id        INTEGER NOT NULL,
    participant_id INTEGER NOT NULL UNIQUE,
    joined_at      TEXT NOT NULL,
    PRIMARY KEY (team_id, participant_id),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
);
"""


def now():
    """Return the current timestamp as a readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    """Open a database connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist yet."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def normalize_skills(raw):
    """Turn 'Python, ML ,design' into a clean, sorted, comma-separated string."""
    if not raw:
        return ""
    items = {s.strip().lower() for s in raw.split(",") if s.strip()}
    return ",".join(sorted(items))


def skill_set(raw):
    """Return a set of skills from a comma-separated string."""
    return {s for s in (raw or "").split(",") if s}


def print_table(headers, rows):
    """Print rows as a simple aligned text table."""
    if not rows:
        print("  (nothing to show)")
        return
    widths = [len(h) for h in headers]
    str_rows = [[str(c) for c in row] for row in rows]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in str_rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


def fail(message):
    """Print an error and exit with a non-zero code."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def require_row(conn, table, row_id, label):
    """Fetch a row by id or exit with a friendly error."""
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        fail(f"{label} with id {row_id} not found.")
    return row


def cmd_add_participant(args):
    skills = normalize_skills(args.skills)
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO participants (name, email, skills, created_at) "
                "VALUES (?, ?, ?, ?)",
                (args.name.strip(), args.email.strip().lower(), skills, now()),
            )
        print(f"Added participant #{cur.lastrowid}: {args.name} ({skills or 'no skills'})")
    except sqlite3.IntegrityError:
        fail(f"A participant with email '{args.email}' already exists.")


def cmd_list_participants(args):
    query = (
        "SELECT p.id, p.name, p.email, p.skills, "
        "COALESCE(t.name, '-') AS team "
        "FROM participants p "
        "LEFT JOIN team_members tm ON tm.participant_id = p.id "
        "LEFT JOIN teams t ON t.id = tm.team_id "
    )
    params = []
    if args.skill:
        query += "WHERE (',' || p.skills || ',') LIKE ? "
        params.append(f"%,{args.skill.strip().lower()},%")
    if args.unassigned:
        query += ("AND " if args.skill else "WHERE ") + "t.id IS NULL "
    query += "ORDER BY p.id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    print_table(
        ["ID", "Name", "Email", "Skills", "Team"],
        [(r["id"], r["name"], r["email"], r["skills"], r["team"]) for r in rows],
    )


def cmd_add_idea(args):
    with get_conn() as conn:
        if args.owner is not None:
            require_row(conn, "participants", args.owner, "Participant")
        cur = conn.execute(
            "INSERT INTO ideas (title, description, owner_id, needed_skills, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                args.title.strip(),
                (args.description or "").strip(),
                args.owner,
                normalize_skills(args.needs),
                now(),
            ),
        )
    print(f"Added idea #{cur.lastrowid}: {args.title}")


def cmd_list_ideas(args):
    query = (
        "SELECT i.id, i.title, i.status, i.needed_skills, "
        "COALESCE(p.name, '-') AS owner, "
        "(SELECT COUNT(*) FROM votes v WHERE v.idea_id = i.id) AS votes "
        "FROM ideas i LEFT JOIN participants p ON p.id = i.owner_id "
    )
    params = []
    if args.status:
        query += "WHERE i.status = ? "
        params.append(args.status)
    query += "ORDER BY votes DESC, i.id ASC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    print_table(
        ["ID", "Title", "Status", "Owner", "Votes", "Needs"],
        [
            (r["id"], r["title"], r["status"], r["owner"], r["votes"], r["needed_skills"])
            for r in rows
        ],
    )


def cmd_set_status(args):
    with get_conn() as conn:
        require_row(conn, "ideas", args.idea, "Idea")
        conn.execute("UPDATE ideas SET status = ? WHERE id = ?", (args.status, args.idea))
    print(f"Idea #{args.idea} status set to '{args.status}'.")


def cmd_vote(args):
    with get_conn() as conn:
        require_row(conn, "ideas", args.idea, "Idea")
        require_row(conn, "participants", args.participant, "Participant")
        try:
            conn.execute(
                "INSERT INTO votes (idea_id, participant_id, created_at) VALUES (?, ?, ?)",
                (args.idea, args.participant, now()),
            )
        except sqlite3.IntegrityError:
            fail("This participant has already voted for that idea.")
    print(f"Participant #{args.participant} voted for idea #{args.idea}.")


def team_member_count(conn, team_id):
    return conn.execute(
        "SELECT COUNT(*) AS c FROM team_members WHERE team_id = ?", (team_id,)
    ).fetchone()["c"]


def cmd_create_team(args):
    with get_conn() as conn:
        if args.idea is not None:
            require_row(conn, "ideas", args.idea, "Idea")
        try:
            cur = conn.execute(
                "INSERT INTO teams (name, idea_id, max_size, created_at) "
                "VALUES (?, ?, ?, ?)",
                (args.name.strip(), args.idea, args.max_size, now()),
            )
        except sqlite3.IntegrityError:
            fail(f"A team named '{args.name}' already exists.")
    print(f"Created team #{cur.lastrowid}: {args.name} (max {args.max_size} members)")


def cmd_join_team(args):
    with get_conn() as conn:
        team = require_row(conn, "teams", args.team, "Team")
        require_row(conn, "participants", args.participant, "Participant")
        if team_member_count(conn, args.team) >= team["max_size"]:
            fail(f"Team '{team['name']}' is already full.")
        try:
            conn.execute(
                "INSERT INTO team_members (team_id, participant_id, joined_at) "
                "VALUES (?, ?, ?)",
                (args.team, args.participant, now()),
            )
        except sqlite3.IntegrityError:
            fail("That participant is already on a team.")
    print(f"Participant #{args.participant} joined team '{team['name']}'.")


def cmd_list_teams(args):
    with get_conn() as conn:
        teams = conn.execute(
            "SELECT t.id, t.name, t.max_size, COALESCE(i.title, '-') AS idea "
            "FROM teams t LEFT JOIN ideas i ON i.id = t.idea_id ORDER BY t.id"
        ).fetchall()
        rows = []
        for t in teams:
            members = conn.execute(
                "SELECT p.name FROM team_members tm "
                "JOIN participants p ON p.id = tm.participant_id "
                "WHERE tm.team_id = ? ORDER BY p.name",
                (t["id"],),
            ).fetchall()
            rows.append(
                (
                    t["id"],
                    t["name"],
                    t["idea"],
                    f"{len(members)}/{t['max_size']}",
                    ", ".join(m["name"] for m in members) or "-",
                )
            )
    print_table(["ID", "Team", "Idea", "Size", "Members"], rows)


def team_skills(conn, team_id):
    """Union of all skills currently on a team."""
    rows = conn.execute(
        "SELECT p.skills FROM team_members tm "
        "JOIN participants p ON p.id = tm.participant_id WHERE tm.team_id = ?",
        (team_id,),
    ).fetchall()
    combined = set()
    for r in rows:
        combined |= skill_set(r["skills"])
    return combined


def cmd_suggest(args):
    """Suggest unassigned participants who fill a team's missing skills."""
    with get_conn() as conn:
        team = require_row(conn, "teams", args.team, "Team")
        needed = set()
        if team["idea_id"]:
            idea = require_row(conn, "ideas", team["idea_id"], "Idea")
            needed = skill_set(idea["needed_skills"])
        have = team_skills(conn, args.team)
        missing = needed - have
        candidates = conn.execute(
            "SELECT p.id, p.name, p.skills FROM participants p "
            "WHERE p.id NOT IN (SELECT participant_id FROM team_members)"
        ).fetchall()

    print(f"Team '{team['name']}'")
    print(f"  Skills needed  : {', '.join(sorted(needed)) or '-'}")
    print(f"  Skills present : {', '.join(sorted(have)) or '-'}")
    print(f"  Skills missing : {', '.join(sorted(missing)) or 'none'}")
    print()

    scored = []
    for c in candidates:
        skills = skill_set(c["skills"])
        fills = skills & missing
        # Prefer people who fill gaps; break ties with people who add new skills.
        score = len(fills) * 10 + len(skills - have)
        if score > 0:
            scored.append((score, c, fills))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))

    rows = [
        (c["id"], c["name"], s, ", ".join(sorted(f)) or "-", c["skills"])
        for s, c, f in scored[: args.limit]
    ]
    print("Suggested teammates:")
    print_table(["ID", "Name", "Score", "Fills gaps", "Skills"], rows)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="hackathon_tracker",
        description="Hackathon Team Formation and Idea Tracker",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-participant", help="Register a participant")
    p.add_argument("name")
    p.add_argument("email")
    p.add_argument("skills", nargs="?", default="", help="comma-separated skills")
    p.set_defaults(func=cmd_add_participant)

    p = sub.add_parser("list-participants", help="List participants")
    p.add_argument("--skill", help="filter by a skill")
    p.add_argument("--unassigned", action="store_true", help="only people without a team")
    p.set_defaults(func=cmd_list_participants)


    p = sub.add_parser("add-idea", help="Pitch a new idea")
    p.add_argument("title")
    p.add_argument("description", nargs="?", default="")
    p.add_argument("--owner", type=int, help="participant id of the pitcher")
    p.add_argument("--needs", default="", help="comma-separated skills needed")
    p.set_defaults(func=cmd_add_idea)

    p = sub.add_parser("list-ideas", help="List ideas ranked by votes")
    p.add_argument("--status", choices=IDEA_STATUSES)
    p.set_defaults(func=cmd_list_ideas)


    p = sub.add_parser("set-status", help="Change an idea's status")
    p.add_argument("idea", type=int)
    p.add_argument("status", choices=IDEA_STATUSES)
    p.set_defaults(func=cmd_set_status)

    p = sub.add_parser("vote", help="Vote for an idea")
    p.add_argument("idea", type=int)
    p.add_argument("--participant", type=int, required=True)
    p.set_defaults(func=cmd_vote)


    p = sub.add_parser("create-team", help="Create a team")
    p.add_argument("name")
    p.add_argument("--idea", type=int, help="idea the team is working on")
    p.add_argument("--max-size", type=int, default=DEFAULT_MAX_TEAM_SIZE)
    p.set_defaults(func=cmd_create_team)

    p = sub.add_parser("join-team", help="Add a participant to a team")
    p.add_argument("team", type=int)
    p.add_argument("--participant", type=int, required=True)
    p.set_defaults(func=cmd_join_team)


    p = sub.add_parser("list-teams", help="List teams and members")
    p.set_defaults(func=cmd_list_teams)

    p = sub.add_parser("suggest", help="Suggest teammates for a team")
    p.add_argument("team", type=int)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_suggest)


    return parser


def main():
    init_db()
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
