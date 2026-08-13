from app.infrastructure.utils.file_utils import get_migration_directory, read_file_content
from agno.db.sqlite import SqliteDb
from agno.memory import MemoryManager
from agno.tools.memory import MemoryTools
from app.infrastructure.agents_backend.model_provider import model
from agno.agent import Agent
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from agno.db.schemas import UserMemory


splitter = RecursiveCharacterTextSplitter(
    # chunk_size=CHUNK_SIZE,
    # chunk_overlap=CHUNK_OVERLAP,
    separators=["\n", " ", ".", ",", ";", ":"],
) 

def flatten_json(data, prefix=""):
    """Recursively flatten JSON into key-path → value text pairs."""
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            items.extend(flatten_json(v, new_prefix))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_prefix = f"{prefix}[{i}]"
            items.extend(flatten_json(v, new_prefix))
    else:
        # Create readable descriptive text
        text = f"{prefix}: {data}"
        items.append(text)
    return items

class SyntaticASTMemoryAgent:
    
    def __init__(self,):
        
        folder_path = get_migration_directory("", "") / "memory_data/syntatic_ast.db"
   
        # Setup your database
        self.db = SqliteDb(db_file = folder_path)
        
        # Setup your Memory Manager, to adjust how memories are created
        self.memory_manager = MemoryManager(
           db=self.db,
           # Select the model used for memory creation and updates. If unset, the default model of the Agent is used.
           model=model,
        )
          
        self.memory_agent = Agent(
            name="Memory Agent",
            model=model,
            # knowledge=get_instance().kb,
            markdown=False,
            use_json_mode=True,
            tools = [
                MemoryTools(
                  db=self.db,
                )
            ],
            instructions=(
                "Read the memory and provide the output"
             ),
            memory_manager=self.memory_manager,
            enable_user_memories=True,
            debug_mode=True,
            description=(
                "For adding data into Memory and using that for generating documentations.",
              )
            )


    def add_data_from_file(self, file_path: str): 
        # reading text from file
        text = read_file_content(Path(file_path))

        # IMPORTANT (syntactic_ast):
        # - The scanner output may contain a very large `syntactic_ast` with embedded code snippets.
        # - Storing the full AST in the memory DB causes size growth and later prompt/context issues.
        # - The AST/code is indexed losslessly in the KB (chunked). Memory should keep only lighter metadata.
        if isinstance(text, dict) and "syntactic_ast" in text:
            safe_text = dict(text)
            safe_text["syntactic_ast"] = "<omitted: stored as KB chunks>"
            text = safe_text
        
        # Creating flat JSON
        text_blocks = flatten_json(text)
                   
        # Splitting text block into smaller documents 
        documents = splitter.create_documents(text_blocks) 
                         
                             
        for i, doc in enumerate(documents):
           # Adding in memory of agent
           self.memory_agent.memory_manager.add_user_memory(UserMemory(memory=doc.page_content))
     

_instance = None  # will hold the single instance

def get_syntatic_ast_memory_agent_instance():
    global _instance
    if _instance is None:
        _instance = SyntaticASTMemoryAgent()
    return _instance






class ComplexScoreMemoryAgent:
    
    def __init__(self,):
        
        folder_path = get_migration_directory("", "") / "memory_data/complex_score.db"
   
        # Setup your database
        self.db = SqliteDb(db_file = folder_path)
        
        # Setup your Memory Manager, to adjust how memories are created
        self.memory_manager = MemoryManager(
           db=self.db,
           # Select the model used for memory creation and updates. If unset, the default model of the Agent is used.
           model=model,
        )
          
        self.memory_agent = Agent(
            name="Memory Agent",
            model=model,
            # knowledge=get_instance().kb,
            markdown=False,
            use_json_mode=True,
            tools = [
                MemoryTools(
                  db=self.db,
                )
            ],
            instructions=(
                "You MUST respond with ONLY valid JSON. No explanations. No commentary. No markdown. "
                "Start with { and end with }. Nothing else. Read the memory and provide JSON output only."
             ),
            memory_manager=self.memory_manager,
            enable_user_memories=True,
            debug_mode=True,
            description=(
                "For adding data into Memory and using that for generating project structure json.",
              )
            )


    def add_data_from_file(self, file_path: str): 
         
        # reading text from file 
        text= read_file_content(Path(file_path))
        
        # Creating flat JSON
        text_blocks = flatten_json(text)
                   
        # Splitting text block into smaller documents 
        documents = splitter.create_documents(text_blocks) 
                         
                             
        for i, doc in enumerate(documents):
           # Adding in memory of agent
           self.memory_agent.memory_manager.add_user_memory(UserMemory(memory=doc.page_content))
     

_instance = None  # will hold the single instance

def get_complex_score_memory_agent_instance():
    global _instance
    if _instance is None:
        _instance = ComplexScoreMemoryAgent()
    return _instance


class PlanningMemoryAgent:
    
    def __init__(self,):
        
        folder_path = get_migration_directory("", "") / "memory_data/planning_memory.db"
   
        # Setup your database
        self.db = SqliteDb(db_file = folder_path)
        
        # Setup your Memory Manager, to adjust how memories are created
        self.memory_manager = MemoryManager(
           db=self.db,
           # Select the model used for memory creation and updates. If unset, the default model of the Agent is used.
           model=model,
        )
          
        self.memory_agent = Agent(
            name="Memory Agent",
            model=model,
            # knowledge=get_instance().kb,
            markdown=True,
            use_json_mode=True,
            tools = [
                MemoryTools(
                  db=self.db,
                )
            ],
            instructions=(
                "Read the memory and provide the output"
             ),
            memory_manager=self.memory_manager,
            enable_user_memories=True,
            debug_mode=True,
            description=(
                "For adding data into Memory and using that for generating project structure json.",
              )
            )


    def add_data_from_file(self, file_path: str): 
         
        # reading text from file 
        text= read_file_content(Path(file_path))
        
        # Creating flat JSON
        text_blocks = flatten_json(text)
                   
        # Splitting text block into smaller documents 
        documents = splitter.create_documents(text_blocks) 
                         
                             
        for i, doc in enumerate(documents):
           # Adding in memory of agent
           self.memory_agent.memory_manager.add_user_memory(UserMemory(memory=doc.page_content))
     

_instance = None  # will hold the single instance

def get_memory_agent_instance():
    global _instance
    if _instance is None:
        _instance = PlanningMemoryAgent()
    return _instance

