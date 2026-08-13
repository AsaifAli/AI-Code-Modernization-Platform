import os
from typing import List
from app.infrastructure.utils.Constants.app_constants import PathConstants

class MigrationListService:
    """
    Lists all migrations for a given user.
    """

    def __init__(self):
        self.temp_dir = PathConstants.TEMP_DIR

    def get_user_migrations(self, user_id: str) -> List[str]:
        """
        Returns a list of migration names (directories)
        for the given user.
        """
        user_dir = os.path.join(self.temp_dir, str(user_id))
        print(f"user_dir = ", user_dir)
        if not os.path.exists(user_dir):
            return []  # No migrations yet for this user
        print(f"user_dir 2 = ", user_dir)
        migrations = []
        for entry in os.listdir(user_dir):
            path = os.path.join(user_dir, entry)
            if os.path.isdir(path):
                migrations.append(entry)

        return sorted(migrations)
 

