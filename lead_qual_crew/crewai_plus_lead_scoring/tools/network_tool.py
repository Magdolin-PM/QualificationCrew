from crewai.tools.base_tool import BaseTool
from typing import List, Dict, Optional, Type
import logging
import re
from urllib.parse import urlparse
from pydantic import BaseModel, Field # Use standard Pydantic V2+ BaseModel

class DomainMatchToolInput(BaseModel):
    """Input schema for DomainMatchTool."""
    contacts_data: List[Dict] = Field(description="List of dictionaries, where each dictionary represents a contact from the user's network (e.g., from CSV export). Expected keys include 'email'.")
    lead_website: Optional[str] = Field(description="The website URL of the lead company.", default=None)
    lead_email: Optional[str] = Field(description="An email address associated with the lead or lead company.", default=None)

class DomainMatchTool(BaseTool):
    name: str = "Domain Match Tool"
    description: str = (
        "Compares the domain of a lead (derived from their website or email) "
        "against the email domains of contacts provided in a list. "
        "Returns a list of contacts whose email domain matches the lead's domain."
    )
    args_schema: Type[BaseModel] = DomainMatchToolInput
    contacts_data: List[Dict] = [] # To hold contacts passed during crew execution

    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        """Extracts the domain name (e.g., 'example.com') from a URL."""
        if not url:
            return None
        try:
            # Ensure scheme is present for urlparse
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            parsed_uri = urlparse(url)
            domain = parsed_uri.netloc
            # Remove 'www.' prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain.lower() if domain else None
        except Exception as e:
            logging.warning(f"Could not parse domain from URL '{url}': {e}")
            return None

    def _extract_domain_from_email(self, email: str) -> Optional[str]:
        """Extracts the domain name from an email address."""
        if not email or '@' not in email:
            return None
        try:
            domain = email.split('@')[1]
            return domain.lower() if domain else None
        except IndexError:
            logging.warning(f"Could not parse domain from email '{email}'")
            return None

    def _run(
        self,
        contacts_data: List[Dict],
        lead_website: Optional[str] = None,
        lead_email: Optional[str] = None
    ) -> str:
        """The main execution method for the tool."""
        lead_domain: Optional[str] = None

        if lead_website:
            lead_domain = self._extract_domain_from_url(lead_website)
            logging.info(f"Extracted lead domain '{lead_domain}' from website '{lead_website}'")

        if not lead_domain and lead_email:
            lead_domain = self._extract_domain_from_email(lead_email)
            logging.info(f"Extracted lead domain '{lead_domain}' from email '{lead_email}'")

        if not lead_domain:
            logging.warning("No lead domain could be determined from website or email.")
            return "Failed to determine lead domain from provided website or email."

        matching_contacts = []
        logging.info(f"Searching {len(contacts_data)} contacts for domain match with '{lead_domain}'")
        
        contact_count = 0
        match_count = 0
        for contact in contacts_data:
            contact_count += 1
            contact_email = contact.get('email')
            if not contact_email or not isinstance(contact_email, str):
                # logging.debug(f"Skipping contact {contact.get('name', 'N/A')} due to missing/invalid email.")
                continue

            contact_domain = self._extract_domain_from_email(contact_email)
            if contact_domain and contact_domain == lead_domain:
                match_count += 1
                match_info = {
                    "name": contact.get("name", "N/A"),
                    "email": contact_email,
                    "matched_domain": contact_domain
                }
                # Add other relevant contact details if needed
                # if contact.get('current_company'): match_info['company'] = contact.get('current_company')
                matching_contacts.append(match_info)
                # logging.debug(f"Found match: {match_info}")


        logging.info(f"Domain match search complete. Processed {contact_count} contacts. Found {match_count} matches for domain '{lead_domain}'.")

        if not matching_contacts:
            return f"No contacts found with a matching email domain for '{lead_domain}'."
        else:
            # Return a string representation, as agents process text better
            result_str = f"Found {len(matching_contacts)} contact(s) with matching domain '{lead_domain}':\n"
            for match in matching_contacts:
                result_str += f"- Name: {match['name']}, Email: {match['email']}\n"
            return result_str 