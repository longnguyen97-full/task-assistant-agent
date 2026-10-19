"""
Backward-compatibility wrapper for project and change note operations.
All underlying database operations are implemented in app.database.
"""
from app.database import (
    db_get_all_projects,
    db_create_project,
    db_add_change_note,
    db_get_change_notes
)

__all__ = [
    "db_get_all_projects",
    "db_create_project",
    "db_add_change_note",
    "db_get_change_notes"
]
