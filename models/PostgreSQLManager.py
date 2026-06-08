import os
import sys
from dotenv import load_dotenv

# Ensure we can import from ssh_library
from ssh_library.reports import SecReportsManager

class PostgreSQLManager(SecReportsManager):
    """PostgreSQL backend — now a lightweight wrapper subclassing ssh_library's SecReportsManager.
    
    This ensures that the scraper pipeline, telegram enrichers, and alert keywords
    all run on a unified codebase powered by ssh_library, completely removing redundant SQL 
    definitions from the scraper app itself while maintaining 100% drop-in backward compatibility.
    """

    def __init__(self):
        load_dotenv(override=False)
        
        # Read scraper-specific DB configurations (with fallbacks compatible with ssh_library)
        db_name = os.getenv("POSTGRES_REPORT_DB", "ssh_reports_hub")
        user = os.getenv("POSTGRES_USER", "ssh_reports_hub")
        keyword_db = os.getenv("POSTGRES_KEYWORD_DB", db_name)
        
        # Initialize the shared library's SecReportsManager
        super().__init__(
            db_name=db_name,
            user=user,
            keyword_db_name=keyword_db
        )
        
        # Compatibility mapping for legacy local references
        self.main_table_name = self.table_name
