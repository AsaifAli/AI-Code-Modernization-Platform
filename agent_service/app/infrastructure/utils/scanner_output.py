import json
from app.infrastructure.utils.Constants.migration import MigrationConstants as MC

def extract_migration_data(scanner_response: dict):
    project_graph = scanner_response.get("project_graph", {})
    tech_data = scanner_response.get("tech_data", {})

    files = project_graph.get("files", [])
    file_index = project_graph.get("file_index", {})
    symbols = project_graph.get("symbols", [])

    # Build symbol map for line range lookups
    symbol_map = {s.get("symbol_id"): s for s in symbols}

    # Derive per-file function count and LOC from file_index and symbol line ranges
    file_function_counts = {}
    file_loc = {}
    for fp, sym_refs in file_index.items():
        file_function_counts[fp] = len(sym_refs)
        max_line = 0
        for sym_ref in sym_refs:
            sym = symbol_map.get(sym_ref.get("symbol_id"), {})
            end = sym.get("line_range", {}).get("end", 0)
            if end > max_line:
                max_line = end
        file_loc[fp] = max_line

    detected_languages = [
        lang.get("name", "") for lang in tech_data.get("languages", [])
    ]

    data = {
        MC.TOTAL_FILES: len(files),
        MC.TOTAL_LOC: tech_data.get("total_loc", 0),
        MC.TOTAL_FUNCTIONS: len(symbols),

        MC.DETECTED_PRIMARY_LANGUAGE: tech_data.get("language", ""),
        MC.DETECTED_LANGUAGES: detected_languages,
        MC.DETECTED_DEPENDENCIES: tech_data.get("dependencies", []),
        MC.DETECTED_EXTENSIONS: tech_data.get("extensions", []),

        MC.TECH_STACK: {
            MC.SOURCE_LANGUAGE: tech_data.get("language", ""),
            MC.TARGET_LANGUAGE: tech_data.get("target_language", ""),
            MC.ORM_TECH: ", ".join(tech_data.get("libraries", [])),
            MC.DATABASE: tech_data.get("databaseName", ""),
            MC.BUILD_TOOL: tech_data.get("build_tool", "")
        },

        MC.ARCHITECTURE: {
            MC.DETECT_ARCH: tech_data.get("architecture", ""),
            MC.DEST_ARCH: tech_data.get("framework", ""),
        },

        MC.ENTITY_DETECTED: tech_data.get("entityDetected", []),

        MC.FILES: [
            {
                MC.FILE_NAME: f.get("file_path", "").replace("\\", "/").split("/")[-1],
                MC.FILE_PATH: f.get("file_path", ""),
                MC.FILE_TYPE: f.get("language", ""),
                MC.FILE_SIZE: 0,
                MC.LINES_OF_CODE: file_loc.get(f.get("file_path", ""), 0),
                MC.FUNCTION_COUNT: file_function_counts.get(f.get("file_path", ""), 0)
            }
            for f in files
        ],

        MC.CONFIG_FILES: tech_data.get("configurationFiles", []),
        MC.NON_CONVERTIBLE_FILES: scanner_response.get("non_convertible_files", [])
    }

    return data

def build_summary_section(data: dict) -> dict:
    return {
        MC.TITLE: MC.SUMMARY_TITLE,

        MC.METRICS: {
            MC.TOTAL_FILES: data[MC.TOTAL_FILES],
            "totalLinesOfCode": data[MC.TOTAL_LOC],
            "totalFunctions": data[MC.TOTAL_FUNCTIONS]
        },

        MC.TECH_STACK_UI: {
            MC.SOURCE_LANGUAGE: data[MC.TECH_STACK][MC.SOURCE_LANGUAGE],
            MC.TARGET_LANGUAGE: data[MC.TECH_STACK][MC.TARGET_LANGUAGE],
            MC.ORM_TECH: data[MC.TECH_STACK][MC.ORM_TECH],
            MC.DATABASE: data[MC.TECH_STACK][MC.DATABASE],
            MC.BUILD_TOOL: data[MC.TECH_STACK][MC.BUILD_TOOL]
        },

        MC.ARCHITECTURE_UI: {
            "source": data[MC.ARCHITECTURE][MC.DETECT_ARCH],
            "destination": data[MC.ARCHITECTURE][MC.DEST_ARCH]
        },

        MC.DETECTED_PRIMARY_LANGUAGE: data[MC.DETECTED_PRIMARY_LANGUAGE],
        MC.DETECTED_LANGUAGES: data[MC.DETECTED_LANGUAGES],
        MC.DETECTED_DEPENDENCIES: data[MC.DETECTED_DEPENDENCIES],
        MC.DETECTED_EXTENSIONS: data[MC.DETECTED_EXTENSIONS],

        MC.ENTITIES: data[MC.ENTITY_DETECTED],
        MC.FILES: data[MC.FILES],

        MC.CONFIG_FILES: data[MC.CONFIG_FILES],
        MC.NON_CONVERTIBLE_FILES: data[MC.NON_CONVERTIBLE_FILES]
    }
    
    
def build_recommendation_section(data: dict) -> dict:
    return {
        MC.AUTO_SELECTED: True,

        MC.TARGET_TECH_STACK: {
            "language": data[MC.TECH_STACK][MC.TARGET_LANGUAGE],
            "framework": data[MC.ARCHITECTURE][MC.DEST_ARCH],
            MC.BUILD_TOOL: data[MC.TECH_STACK][MC.BUILD_TOOL],
            "orm": data[MC.TECH_STACK][MC.ORM_TECH],
            MC.DATABASE: data[MC.TECH_STACK][MC.DATABASE]
        },

        MC.NEXT_STEPS: MC.NEXT_STEPS_LIST,
        MC.NOTES: MC.NOTES_LIST
    }
    
def generate_full_migration_response(migration_data: dict) -> dict:
    return {
        MC.TYPE: MC.TYPE_VALUE,
        MC.SUMMARY_ROOT: build_summary_section(migration_data),
        MC.RECOMMENDATIONS_ROOT: build_recommendation_section(migration_data)
    }
