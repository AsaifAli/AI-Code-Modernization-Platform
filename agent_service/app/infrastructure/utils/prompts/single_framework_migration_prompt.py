import pathlib
from app.infrastructure.utils.Constants.app_constants import Constants
import json
from app.infrastructure.utils.prompts.prompt import Prompt
from typing import List


class SingleFrameworkMigrationPrompt(Prompt):

    # Used in doc agent by tool create_save_technical_documentation for creating technical documentation             
    def getTechnicalDocumentationPrompt(respDetectedTechGraph: str) -> str:
        # Dependency Graph Data: {respDependencyGraph}
                    # Detected Tech Graph Data: {respDetectedTechGraph}
                    #  AST Data: {respAst}
                    #    {json.dumps(respAst)}
        path = pathlib.PurePath(Constants.source_path)
                   
        return f"""Generate COMPREHENSIVE and DETAILED technical documentation in markdown format based on the provided AST data and Detected Tech Graph.
                
                CRITICAL INSTRUCTION: You MUST document EVERY SINGLE FILE found in the AST data below. Do NOT skip any files.
                
                Scan through ALL files in the AST data and document each one, regardless of folder name or file type. This includes but is not limited to:                
                
                Original AST Data:
                [AST Data is added in memory, Iterate through the memory to create the documentation]
                
                Detected Tech Graph:
                {json.dumps(respDetectedTechGraph, indent=2)[:30000]}
                
                
                DOCUMENTATION STRUCTURE:
                
                # TECHNICAL DOCUMENTATION - [{path.name}]
                
                ## Project Overview
                - Brief description of what the project does
                - Purpose and goals
                - Overall architecture summary
                
                ## Key Modules & Components
                - List all major modules/components with brief descriptions
                - Explain the role of each module in the system
                
                ---
                
                ## FILE-LEVEL DOCUMENTATION
                
                REMINDER: Document EVERY SINGLE FILE in the AST data - scroll through ALL files in the data and document each one.
                
                For EACH file in the project, provide the following detailed breakdown:
                
                ### File Name: [filename]
                
                **Overview:**
                - Clear description of what this file does
                - Its role in the overall application
                - How it fits into the architecture
                
                **Functions / Components / Classes:**
                
                For EACH function, method, class, or component, document:
                
                1. **[Function/Class Name]**: [Type: Function/Class/Component/Middleware/Route]
                   - **Description**: What it does and why it exists
                   - **Key Parameters**: 
                     * parameter_name: Type - Description
                     * parameter_name: Type - Description
                   - **Return Type**: Specify return type and what is returned
                   - **Interactions**: 
                     * What other functions/modules it calls
                     * What calls this function
                     * Database operations performed
                     * API endpoints used
                     * External services accessed
                
                **Global Variables / Constants:**
                
                **Data Flow:**
                
                **Dependencies:**

                
                **Environment Configuration:**
                - Environment variables used
                - Configuration files referenced
                - API keys or secrets required
                
                **Interactions:**
                
                **Architecture and Design Patterns:**
                
                **Logging / Error Handling:**
                
                **Special Considerations:**
                
                ---
                
                ## Architecture Overview
                
                **Overall Architecture:**
                - Describe the high-level architecture (e.g., MVC, Microservices, Layered)
                - Explain how components interact
                - Data flow across the system
                - Authentication/Authorization flow
                - Request/Response cycle
                
                **Design Patterns Used:**
                - List and explain design patterns implemented throughout the project
                
                **Database Architecture:**
                - Database schema overview
                - Relationships between entities
                - Indexing strategy
                
                ---
                
                ## Tech Stack & Dependencies
                
                **Core Technologies:**
                - Language and version
                - Framework and version
                - Database and version
                
                **Dependencies:**
                - Production dependencies with versions and purposes
                - Development dependencies with versions and purposes
                
                **External Services:**
                - APIs integrated
                - Third-party services used
                - Cloud services utilized
                
                ---
                
                ## Setup / Usage Instructions
                
                **Prerequisites:**
                - Required software and versions
                - System requirements
                
                **Installation:**
                1. Step-by-step installation instructions
                2. Environment setup
                3. Configuration steps
                4. Database setup
                
                **Running the Application:**
                - Development mode commands
                - Production mode commands
                - Testing commands
                - Build commands
                
                **Environment Variables:**
                - Complete list of required environment variables
                - Example values
                - Where to obtain values
                
                ---
                
                ## API Documentation (if applicable)
                
                For each API endpoint:
                - **Endpoint**: Method and URL
                - **Description**: What it does
                - **Authentication**: Required or not
                - **Parameters**: Query params, path params, body params
                - **Request Example**: Sample request
                - **Response Example**: Sample response
                - **Status Codes**: Possible status codes and meanings
                - **Error Handling**: Error responses
                
                ---
                
                IMPORTANT REQUIREMENTS:
                1. Be EXTREMELY DETAILED - document EVERY function, class, and method
                2. Do NOT skip any code elements
                3. Include ALL parameters with types
                4. Specify ALL return types
                5. Explain ALL interactions and dependencies
                6. Document ALL error handling
                7. Mention ALL security considerations
                8. Use clear, professional technical language
                9. Organize content logically and consistently
                10. Ensure documentation is comprehensive enough for a new developer to understand the entire codebase
                11. CRITICAL: Document EVERY SINGLE FILE in the AST data - verify you've covered all files before finishing
                12. Don't give unnecessary spaces between lines or words
                
                FINAL VERIFICATION: Before you finish, count all files in the AST data and ensure you documented each one. Do not skip any files!
                
                Generate the complete documentation now."""
                    
    # Used in doc agent by tool 'create_save_functional_documentation' for creating functional documentation             
    def getFunctionalDocumentationPrompt(respDetectedTechGraph: str) -> str:
                # Dependency Graph Data: {respDependencyGraph}
                    #  Detected Tech Graph Data: {respDetectedTechGraph}
        
        path = pathlib.PurePath(Constants.source_path)
        
        return f"""Generate COMPREHENSIVE and DETAILED functional documentation in markdown format based on the provided AST data and Detected Tech Graph.

                     CRITICAL INSTRUCTIONS:
                     1. Focus on WHAT the application does from a user/business perspective, NOT how it's technically implemented
                     2. Document EVERY functional capability found in the code - including main features, utility functions, helper scripts, and standalone tools
                     3. Even simple utility files or standalone scripts should be documented as features if they provide ANY functionality to users or the system
                     
                    Original AST Data:
                    [AST Data is added in memory, Iterate through the memory to create the documentation]
                
                    Detected Tech Graph:
                    {json.dumps(respDetectedTechGraph, indent=2)[:30000]}

                     DOCUMENTATION STRUCTURE:
                     
                     # FUNCTIONAL DOCUMENTATION - [{path.name}]
                     
                     ## Project Overview
                     - What the application does (business purpose)
                     - Who the application is for (target users)
                     - Key business problems it solves
                     - High-level capabilities and features
                     
                     ## Key Features Overview
                     - List all major features/capabilities of the application
                     - Brief description of what each feature provides to users
                     - How features relate to each other
                     
                     ---
                     
                     ## FEATURE-BY-FEATURE BREAKDOWN
                     
                     CRITICAL: Document EVERY functional capability found in the code. This includes:
                     - Core business features and main application workflows
                     - Utility functions and tools of any type
                     - Helper scripts and automation capabilities
                     - Standalone capabilities (simple scripts, one-off tools, utility modules, etc.)
                     - API endpoints, services, and integrations
                     
                     
                     For EACH feature/capability in the application, provide:
                     
                     ### Feature Name: [Feature Name]
                     
                     **Overview:**
                     - What this feature does from a user perspective
                     - Business value it provides
                     - Who uses this feature
                     
                     **Functionality Explanation:**
                     
                     Document each aspect of this feature:
                     
                     1. **[Functionality Name]**: 
                        - What it does in simple terms
                        - How users interact with it
                        - What inputs are required from users
                        - What outputs/results users receive
                     
                     2. **[Next Functionality Name]**:
                        - [Same detailed breakdown]
                     
                     **User Workflow:**
                     - Step-by-step process users follow
                     - Decision points and branches
                     - Prerequisites for using this feature
                     
                     **Business Rules:**
                     - Constraints and validations
                     - Required vs optional inputs
                     - Access permissions and restrictions
                     
                     **Integration Points:**
                     - How this feature connects with other features
                     - External systems or services used
                     - Data shared between features
                     
                     ---
                     
                     ## User Roles & Permissions
                     
                     **Available Roles:**
                     - List all user roles in the system
                     - Describe what each role represents
                     
                     **Permissions by Role:**
                     For each role, document:
                     - What features/actions they can access
                     - What data they can view/modify
                     - Restrictions and limitations
                     
                     **Authentication & Access:**
                     - How users log in and authenticate
                     - Password requirements and policies
                     - Session management and timeout
                     
                     ---
                     
                     ## Use Cases / User Scenarios
                     
                     For key workflows, provide complete use cases:
                     
                     **Use Case: [Use Case Name]**
                     - **Actor**: Who performs this action
                     - **Goal**: What they want to achieve
                     - **Preconditions**: What must be true before starting
                     - **Main Flow**: Step-by-step normal scenario
                     - **Alternative Flows**: Different paths through the feature
                     - **Postconditions**: System state after completion
                     - **Business Rules**: Rules that govern this workflow
                     
                     ---
                     
                     ## System Behavior & Business Logic
                     
                     **Data Management:**
                     - What types of data the system manages
                     - How data is organized and categorized
                     - Data lifecycle (creation, update, deletion)
                     - Data relationships and dependencies
                     
                     **Validation Rules:**
                     - Input validation requirements
                     - Data format requirements
                     - Business rule validations
                     - Cross-field validations
                     
                     **Workflow Automation:**
                     - Automatic processes and triggers
                     - Scheduled tasks and jobs
                     - Notifications and alerts
                     - Background processing
                     
                     **Error Handling:**
                     - How errors are presented to users
                     - User recovery options
                     - Validation failure messages
                     - System error scenarios
                     
                     ---
                     
                     ## Data Flow & Processes
                     
                     **Key Business Processes:**
                     For each major process:
                     1. **Process Name**
                        - What triggers this process
                        - Step-by-step flow
                        - Decision points
                        - Expected outcomes
                        - Error scenarios and handling
                     
                     **Data Input/Output:**
                     - What data users provide
                     - What data the system generates
                     - Data transformations applied
                     - Output formats and destinations
                     
                     ---
                     
                     ## Reports & Analytics
                     
                     **Available Reports:**
                     - List all reports users can generate
                     - What data each report shows
                     - Filters and parameters available
                     - Export formats supported
                     
                     **Analytics & Insights:**
                     - Metrics and KPIs tracked
                     - Dashboards and visualizations
                     - Trending and historical data
                     - Performance indicators
                     
                     ---
                     
                     ## Notifications & Communications
                     
                     **Notification Types:**
                     - What events trigger notifications
                     - Notification delivery methods (email, in-app, SMS, etc.)
                     - User preferences and settings
                     - Notification content and format
                     
                     **Communication Features:**
                     - User-to-user communication
                     - System-to-user messages
                     - Announcements and broadcasts
                     
                     ---
                     
                     ## Configuration & Settings
                     
                     **System Configuration:**
                     - Configurable settings and options
                     - Default values and behaviors
                     - Admin configuration capabilities
                     - Environment-specific settings
                     
                     **User Preferences:**
                     - Settings users can customize
                     - Display and appearance options
                     - Notification preferences
                     - Privacy and security settings
                     
                     ---
                     
                     ## Integration & External Systems
                     
                     **External Integrations:**
                     - Third-party services connected
                     - Data exchanged with external systems
                     - API endpoints exposed for external use
                     - Webhooks and event notifications
                     
                     **Import/Export:**
                     - Supported data import formats
                     - Export capabilities and formats
                     - Bulk operations available
                     - Data migration features
                     
                     ---
                     
                     ## Security & Compliance
                     
                     **Security Features:**
                     - Authentication mechanisms
                     - Authorization and access control
                     - Data encryption and protection
                     - Audit logging and tracking
                     
                     **Compliance:**
                     - Regulatory requirements met
                     - Data privacy protections
                     - User consent and preferences
                     - Data retention policies
                     
                     ---
                     
                     ## Performance & Scalability
                     
                     ---
                     
                     ## Limitations & Constraints
                     
                     ---
                     
                     IMPORTANT REQUIREMENTS:
                     1. Write in clear, non-technical language that business users can understand
                     2. Focus on WHAT the system does, not HOW it's implemented technically
                     3. Describe functionality from the user's perspective
                     4. Include business rules and validations
                     5. Explain user workflows and processes
                     6. Document all user-facing features comprehensively
                     7. Provide complete use cases for key scenarios
                     8. Be extremely detailed in functionality explanations
                     9. Cover all aspects: inputs, outputs, validations, workflows, permissions
                     10. Make it comprehensive enough for product managers, business analysts, and end users to understand the complete system
                     11. CRITICAL: Document EVERY capability - do not skip utility functions, helper scripts, or simple standalone tools
                     12. Don't give unnecessary spaces between lines or words
                     
                     
                     Do NOT skip any functional capability, regardless of how simple it may seem!
                     
                     Generate the complete functional documentation now."""
    
    # Used in scanner agent by tool 'generate_enhanced_response_json' for creating scanner response 
    def getEnhancedScannerResponsePrompt(source_path: str, folder_structure_text: str, tech_data: dict, semantic_summary: List, dependency_graph: dict, entity_list: List, ) -> str:
 
        return f"""You are an experienced software architect. Analyze the provided project data and output a valid JSON object.

                   PROJECT PATH: {source_path}
                   
                   FOLDER STRUCTURE (sample):
                   {folder_structure_text}
                   
                   DETECTED TECHNOLOGY:
                   - Language: {tech_data.get('language', 'Unknown')}
                   - Framework: {tech_data.get('framework', 'None')}
                   - Build Tool: {tech_data.get('build_tool', 'Unknown')}
                   - Architecture: {tech_data.get('architecture', 'Unknown')}
                   - Libraries: {', '.join(tech_data.get('libraries', [])[:20])}
                   
                   SEMANTIC IR SUMMARY (first 20 classes):
                   {json.dumps(semantic_summary, indent=2)}
                   
                   DEPENDENCY GRAPH:
                   {json.dumps(dependency_graph, indent=2)[:5000]}  # Limit size
                   
                   DETECTED ENTITIES:
                   {', '.join(entity_list[:90])}

                    YOUR TASK:
                    Analyze this project and provide intelligent recommendations. DO NOT use placeholder values.
                    
                    1. **Source Language**: Identify the PRIMARY language used (return as single-item list, uppercase)
                    2. **Current Architecture**: Classify the architecture pattern (Monolith, Microservices, Layered, MVC, Single Page Application, Serverless, etc.)
                    3. **Build Tool**: Identify the build/dependency tool (npm, pip, maven, gradle, cargo, composer, make, etc.)
                    4. **Upgraded Architectures**: Based on the CURRENT architecture and project complexity, recommend 1-3 SPECIFIC modern architectures that would be suitable upgrades. Consider:
                       - If it's a Monolith → suggest Microservices or Layered
                       - If it's MVC → suggest Clean Architecture or Hexagonal
                       - If it's a web app → suggest SPA or JAMstack
                       - Be specific and realistic based on project size and domain
                    5. **Target Languages**: Based on the SOURCE language and detected framework, recommend 1-3 SPECIFIC languages for migration. Consider:
                       - For PHP projects → Python (Django/Flask), Node.js (Express), Java (Spring Boot)
                       - For legacy Java → Kotlin, Go, Rust (for performance-critical parts)
                       - For JavaScript → TypeScript, Go (for backend services)
                       - Match recommendations to the project's domain and scale
                    6. **ORM Technologies**: If database usage is detected, recommend specific ORMs for the target languages (e.g., Eloquent, SQLAlchemy, Hibernate, Prisma, TypeORM)
                    7. **Configuration Files**: List ALL actual configuration files found (package.json, composer.json, .env, config.yml, etc.)
                    8. 8. **Non-Convertible Files**: Based on the folder structure, identify files that should NOT be converted:
                       - Binary files (images: .jpg, .png, .gif, .svg, .ico)
                       - Documents (.pdf, .doc, .xlsx)
                       - Media files (.mp4, .mp3)
                       - Dependency directories (vendor/, node_modules/, .git/)
                       - Lock files (composer.lock, package-lock.json)
                       - Compiled files (.pyc, .class)
                       - DO NOT include regular source code files (.php, .js, .py, etc.)
                       Return relative paths from project root
                    9. **Entities**: Extract business entities/models from the semantic IR
                    10. **Database**: Detect the database system used (MySQL, PostgreSQL, MongoDB, SQLite, Oracle, or NoDatabase)
                    11. 11. **Framework Version**: If a framework is detected, try to find its version from:
                        - composer.json (for PHP: look for framework in require section)
                        - package.json (for Node.js: look for version in dependencies)
                        - pom.xml or build.gradle (for Java)
                        - requirements.txt or pyproject.toml (for Python)
                        Return the actual version string (e.g., "8.x", "3.2.1") or null if not found. DO NOT return "N/A" or placeholder values.
                    12. **File Dependencies**: For EACH file in syntactic_ast, map its dependencies (libraries and internal classes)
                    
                    CRITICAL OUTPUT RULES:
                    1. Output ONLY valid JSON - no markdown, no explanations, no code blocks
                    2. All recommendations must be SPECIFIC and JUSTIFIED by the actual project data
                    3. Do NOT include generic "all options" lists - be selective and intelligent
                    4. 'src_lang' must be a list with ONE uppercase language name (e.g., ["PHP"], ["PYTHON"])
                    5. 'upgraded_architectures' should contain 1-3 realistic recommendations based on current state
                    6. 'target_languages' should contain 1-3 languages that make sense for THIS specific project
                    7. 'orm_technologies' should only include ORMs relevant to recommended target languages
                    8. 'database_name' should be specific (MySQL, PostgreSQL, etc.) or "NoDatabase"
                    
                    Return JSON with this EXACT structure:
                    {{
                      "src_lang": ["LANGUAGE"],
                      "architecture": "Current Architecture Pattern",
                      "build_tool": "detected tool or 'No build tool'",
                      "upgraded_architectures": ["specific_arch_1", "specific_arch_2"],
                      "target_languages": ["specific_lang_1", "specific_lang_2"],
                      "orm_technologies": ["ORM1", "ORM2"],
                      "configuration_files": ["actual_file1.ext", "actual_file2.ext"],
                      "entities": ["Entity1", "Entity2"],
                      "non_convertible_files": ["relative/path/to/image.png", "vendor/package/file.php", "node_modules/lib/index.js"],
                      "database_name": "DetectedDatabase or NoDatabase",
                      "framework_version": "version if detected",
                      "file_dependencies": {{
                        "file1.php": ["library1", "library2", "InternalClass"],
                        "file2.php": ["library3", "Model"]
                      }}
                    }}
                    
                    EXAMPLE GOOD RESPONSES (for context only, don't copy):
                    
                    For a PHP Laravel MVC app with MySQL:
                    {{
                      "src_lang": ["PHP"],
                      "architecture": "MVC",
                      "build_tool": "composer",
                      "upgraded_architectures": ["Clean Architecture", "Microservices", "Hexagonal Architecture"],
                      "target_languages": ["Python (Django)", "Node.js (NestJS)", "Java (Spring Boot)"],
                      "orm_technologies": ["Eloquent", "SQLAlchemy", "TypeORM", "Hibernate"],
                      "database_name": "MySQL"
                    }}
                    
                    For a React SPA with Node.js backend:
                    {{
                      "src_lang": ["JAVASCRIPT"],
                      "architecture": "Single Page Application",
                      "build_tool": "npm",
                      "upgraded_architectures": ["JAMstack", "Micro-frontend", "Server-Side Rendering (Next.js)"],
                      "target_languages": ["TypeScript", "Go (backend)", "Rust (performance-critical services)"],
                      "orm_technologies": ["Prisma", "TypeORM", "Drizzle"],
                      "database_name": "PostgreSQL"
                    }}
                    
                    Now analyze the provided project data and generate a precise, data-driven response.
                    """
                    
                    
    def getPumlPrompt(semantic_ir: List, tech_data: dict, dep_graph: dict,) -> str:
       
       return f"""You are a PlantUML diagram generator. Create a valid PlantUML component diagram.

                  Semantic IR Summary:
                  - Classes/Modules: {len(semantic_ir)}
                  - Tech Stack: {json.dumps(tech_data, indent=2)[:90]}
                  
                  Dependencies (sample):
                  {json.dumps(dep_graph.get('edges', [])[:1500], indent=2)}
                  
                  Key Entities:
                  {', '.join([entry.get('class', '') for entry in semantic_ir[:60000] if entry.get('class')])}
                  
                  Create a PlantUML component diagram with:
                  1. Main application components
                  2. Key modules/packages
                  3. Database/external services (if detected)
                  4. Relationships between components
                  
                  CRITICAL RULES:
                  - Return ONLY PlantUML code
                  - Start with @startuml
                  - End with @enduml
                  - Use component, package, and database elements
                  - Use --> for relationships
                  - NO markdown formatting
                  - NO backticks
                  - NO explanatory text
                  
                  Example format:
                  @startuml
                  !theme plain
                  skinparam componentStyle rectangle
                  
                  package "Application Layer" {{
                      component [API Server]
                      component [Business Logic]
                  }}
                  
                  package "Data Layer" {{
                      database [Database]
                  }}
                  
                  [API Server] --> [Business Logic]
                  [Business Logic] --> [Database]
                  
                  @enduml
                  
                  Generate the diagram now:"""
                       