from crewai.tools.base_tool import BaseTool
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from typing import Optional, Type, List, Dict
from pydantic import BaseModel, Field
import logging
import os
import json

class SearchAndContentsInput(BaseModel):
    """Input schema for SearchAndContentsTool."""
    search_query: str = Field(description="Mandatory search query to execute using SerperDevTool.")
    scrape_url: Optional[str] = Field(description="Optional URL to scrape using ScrapeWebsiteTool if direct search is insufficient or specific content is needed.", default=None)
    max_search_results: int = Field(description="Maximum number of search results to return.", default=3)

class SearchAndContentsTool(BaseTool):
    name: str = "Search and Contents Tool"
    description: str = (
        "Performs a web search using SerperDevTool and optionally scrapes content from a URL using ScrapeWebsiteTool. "
        "Useful for finding information online and extracting content from specific web pages. "
        "Returns search results and scraped content if a URL is provided."
    )
    args_schema: Type[BaseModel] = SearchAndContentsInput
    serper_api_key: str = Field(default_factory=lambda: os.getenv('SERPER_API_KEY'))
    
    def _run(self, search_query: str, scrape_url: Optional[str] = None, max_search_results: int = 3) -> Dict:
        """The main execution method for the tool."""
        results = {}
        
        # Initialize tools internally
        try:
            search_tool = SerperDevTool(api_key=self.serper_api_key)
            scrape_tool = ScrapeWebsiteTool()
        except Exception as e:
            logging.error(f"Failed to initialize internal tools: {e}")
            return {"error": f"Failed to initialize tools: {e}"}
        
        # Perform Search
        try:
            logging.info(f"Performing search with query: '{search_query}'")
            search_results = search_tool.run(query=search_query)
            # Depending on SerperDevTool version, results might be JSON string or Dict
            # Let's try to ensure it's a dictionary/list
            if isinstance(search_results, str):
                try:
                    search_results = json.loads(search_results)
                except json.JSONDecodeError:
                    logging.warning(f"SerperDevTool returned a string that is not valid JSON: {search_results[:100]}...")
                    # Keep it as string if parsing fails, maybe agent can handle
                    pass 
            
            # Limit results if necessary (assuming search_results is a list or can be sliced)
            if isinstance(search_results, list) and len(search_results) > max_search_results:
                 logging.info(f"Limiting search results from {len(search_results)} to {max_search_results}")
                 results["search_results"] = search_results[:max_search_results]
            else:
                 results["search_results"] = search_results
                 
        except Exception as e:
            logging.error(f"Error during search: {e}", exc_info=True)
            results["search_error"] = f"Search failed: {e}"

        # Perform Scraping (if URL provided)
        if scrape_url:
            try:
                logging.info(f"Performing scrape on URL: {scrape_url}")
                # Ensure scrape_tool takes url directly in run, or adjust call
                # Check ScrapeWebsiteTool documentation/implementation if needed
                scraped_content = scrape_tool.run(website_url=scrape_url) 
                results["scraped_content"] = scraped_content
                logging.info(f"Scraping successful for {scrape_url}")
            except Exception as e:
                logging.error(f"Error during scraping '{scrape_url}': {e}", exc_info=True)
                results["scrape_error"] = f"Scraping failed for {scrape_url}: {e}"
        
        if not results or (results.get("search_error") and results.get("scrape_error")):
             return {"error": "Both search and scraping failed or no operations performed."}
             
        return results 