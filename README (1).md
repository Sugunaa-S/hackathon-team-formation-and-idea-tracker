# Hackathon Team Formation and Idea Tracker

A lightweight command-line tool for running the people side of a hackathon: register participants, pitch and vote on ideas, and form teams with balanced skills.

Built with pure Python 3.8+ and SQLite. No dependencies to install.

## Features

- **Participants**: register people with their skills; filter by skill or by who is still unassigned
- **Ideas**: pitch ideas with the skills they need, vote on them, rank by votes, and track status (`proposed`, `approved`, `in-progress`, `completed`, `rejected`)
- **Teams**: create teams with a size limit; each participant can join only one team
- **Smart suggestions**: get ranked teammate recommendations based on the skills a team is still missing

## Getting started

```bash
git clone https://github.com/<your-username>/hackathon-team-formation-idea-tracker.git
cd hackathon-team-formation-idea-tracker
python hackathon_tracker.py --help
```

Data is stored in `hackathon.db` in the current folder. Set the `HACKATHON_DB` environment variable to use a different file.

## Usage

```bash
# Add participants (skills are comma-separated)
python hackathon_tracker.py add-participant "Asha" asha@mail.com "python,ml"
python hackathon_tracker.py add-participant "Ravi" ravi@mail.com "design,react"

# Pitch an idea and vote on it
python hackathon_tracker.py add-idea "Smart Recycler" "AI bin sorter" --owner 1 --needs "python,design"
python hackathon_tracker.py vote 1 --participant 2
python hackathon_tracker.py set-status 1 approved
python hackathon_tracker.py list-ideas

# Form a team
python hackathon_tracker.py create-team "Green Coders" --idea 1 --max-size 4
python hackathon_tracker.py join-team 1 --participant 1
python hackathon_tracker.py list-teams

# Find who the team should recruit next
python hackathon_tracker.py suggest 1
```

## Commands

| Command | Description |
|---|---|
| `add-participant` | Register a participant with skills |
| `list-participants` | List participants (`--skill`, `--unassigned`) |
| `add-idea` | Pitch an idea (`--owner`, `--needs`) |
| `list-ideas` | List ideas ranked by votes (`--status`) |
| `set-status` | Change an idea's status |
| `vote` | Vote for an idea (one vote per person) |
| `create-team` | Create a team (`--idea`, `--max-size`) |
| `join-team` | Add a participant to a team |
| `list-teams` | Show teams and their members |
| `suggest` | Recommend unassigned people who fill missing skills |

## How suggestions work

For a given team, the tool compares the skills required by its idea with the skills its members already have. Unassigned participants are scored by how many missing skills they cover (weighted most heavily) and how many new skills they add.

## Roadmap

- Stats and CSV/JSON export
- Web interface
- Automatic team formation for all unassigned participants

## License

MIT
