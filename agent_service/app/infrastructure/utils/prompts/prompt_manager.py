from app.infrastructure.utils.prompts.prompt import Prompt
from app.infrastructure.utils.prompts.single_framework_migration_prompt import SingleFrameworkMigrationPrompt

class PromptManager:
    
       
    def __init__(self,):
        
        # select prompt type
        # Add logic below in future for managing differen types of Prompt
        self.prompt = SingleFrameworkMigrationPrompt()
        

_instance = None  # will hold the single instance

def get_prompt_manager_instance():
    global _instance
    if _instance is None:
        _instance = PromptManager()
    return _instance 