"""Create a consistent SQLite backup without deleting or overwriting source data."""
from datetime import datetime
from pathlib import Path
import sqlite3
from config import BASE_DIR


def main():
    src = BASE_DIR / 'instance' / 'campusfind.db'
    if not src.exists():
        raise SystemExit('No database exists yet. Run python run.py first.')
    backup_dir = BASE_DIR / 'backups'
    backup_dir.mkdir(exist_ok=True)
    destination = backup_dir / ('campusfind-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.db')
    with sqlite3.connect(src) as original, sqlite3.connect(destination) as replica:
        original.backup(replica)
    print(f'Backup created at: {destination}')


if __name__ == '__main__':
    main()
