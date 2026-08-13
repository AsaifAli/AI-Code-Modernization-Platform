# app/infrastructure/utils/migration_workflow_strings.py


class MigrationWorkflowStrings:

    # Logs
    WORKFLOW_START = "🧩 Executing migration workflow for {user_id} / {migration_name}"
    GITHUB_MODE = "🔵 GitHub mode: pushing changes to new branch for repo {repo}"
    ZIP_LOG = "📦 Zipping output for user {user_id}: {zip_path}"
    INSIDE_IF = "inside if"

    # Branch / GitHub messages
    CREATE_OR_UPDATE_BRANCH = (
        "🔨 Creating/updating branch '{branch_name}' with ONLY target_path content"
    )
    BRANCH_EXISTS = "🔄 Branch '{branch_name}' already exists. Checking out."
    BRANCH_CREATE = "🆕 Creating new branch '{branch_name}'"
    BRANCH_PUSH_SUCCESS = "✅ Branch '{branch_name}' updated and pushed successfully."

    # Defaults
    DEST_FOLDER = "Dest"
    MIGRATED_CODE = "migrated_code"
    ZIP_SUFFIX = "_processed.zip"
    MIGRATION_PREFIX = "migration/"
    COMMIT_MESSAGE = "Automated migration output"
    MIGRATION_PLAN_NOT_FOUND = "migration_plan.json not found at {plan_file_path}"
    CONVERSION_WORKFLOW_COMPLETED = "Conversion workflow completed"
