from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey,
    Boolean, Enum, text, Text, or_, func, Float
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY as PG_ARRAY, UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import os
from datetime import datetime, timezone
from typing import Optional

# Get database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Create SQLAlchemy engine with SSL mode require
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require"
    }
)

# Create declarative base
Base = declarative_base()

# Enums for lead status and stage
class LeadStatus(enum.Enum):
    money = 'money'
    hot = 'hot'
    warm = 'warm'
    cold = 'cold'

class LeadStage(enum.Enum):
    new = 'new'
    contacted = 'contacted'
    qualified = 'qualified'
    closed_won = 'closed_won'
    closed_lost = 'closed_lost'

class Users(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'public'}

    user_id = Column(PG_UUID, primary_key=True) 
    first_name = Column(Text)
    last_name = Column(Text)
    email = Column(Text, unique=True)
    company = Column(Text)
    position = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))

    # Relationship to leads created by this user
    # Moved lead relationship definition below Lead class
    # leads_created = relationship("Lead", back_populates="creator")

class UserPreferences(Base):
    __tablename__ = 'user_preferences'
    __table_args__ = {'schema': 'public'}

    user_id = Column(PG_UUID, ForeignKey('auth.users.id', ondelete='CASCADE'), primary_key=True)
    selected_signals = Column(PG_ARRAY(Text), nullable=False)
    brand_voice = Column(Text, nullable=False)
    core_problem = Column(Text)
    solution_summary = Column(Text)
    differentiators = Column(PG_ARRAY(Text))
    icp_industry = Column(Text)
    icp_company_size = Column(Text)
    icp_region = Column(Text)
    icp_role = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))

    def to_dict(self):
        return {
            "user_id": str(self.user_id),
            "selected_signals": self.selected_signals,
            "brand_voice": self.brand_voice,
            "core_problem": self.core_problem,
            "solution_summary": self.solution_summary,
            "differentiators": self.differentiators,
            "icp_industry": self.icp_industry,
            "icp_company_size": self.icp_company_size,
            "icp_region": self.icp_region,
            "icp_role": self.icp_role,
            "created_at": str(self.created_at),
            "updated_at": str(self.updated_at)
        }

# Define Signal before Lead
class Signal(Base):
    __tablename__ = 'signals'
    __table_args__ = {'schema': 'public'}

    id = Column(PG_UUID, primary_key=True, server_default=text('gen_random_uuid()'))
    lead_id = Column(PG_UUID, ForeignKey('public.leads.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(PG_UUID, nullable=False) # Removed ForeignKey('auth.users.id')
    signal_type = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    details = Column(JSONB, nullable=False)
    source = Column(Text, nullable=False)
    source_url = Column(Text)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    is_processed = Column(Boolean, default=False)
    is_relevant = Column(Boolean, default=True)
    priority = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))

    # Relationship with lead (defined after Lead class)
    # lead = relationship("Lead", back_populates="signals")

class Lead(Base):
    __tablename__ = 'leads'
    __table_args__ = {'schema': 'public'}

    id = Column(PG_UUID, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id = Column(PG_UUID, ForeignKey('public.users.user_id', ondelete='CASCADE'), nullable=False)
    first_name = Column(Text)
    last_name = Column(Text)
    email = Column(Text)
    company = Column(Text)
    position = Column(Text)
    company_size = Column(Text)
    industry = Column(Text)
    region = Column(Text)
    lead_source = Column(Text)
    score = Column(Integer, default=0)
    last_contacted = Column(DateTime(timezone=True))
    phone = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'))
    linkedin = Column(Text)
    website = Column(Text)
    notes = Column(Text)
    languages = Column(PG_ARRAY(Text))
    updated_at = Column(DateTime(timezone=True), server_default=text('now()'))
    last_suggestion_id = Column(PG_UUID)
    new_since = Column(DateTime(timezone=True), server_default=text('now()'))
    connection_degree = Column(Integer)
    lead_status = Column(Enum(LeadStatus, name='lead_status', schema='public'))
    lead_stage = Column(Enum(LeadStage, name='lead_stage', schema='public'), default=LeadStage.new)
    enrichment_data = Column(JSONB)
    is_enriched = Column(Boolean, default=False)
    scoring_details = Column(JSONB, nullable=True)
    ai_confidence = Column(Float)
    
    # Relationship with signals (defined here, after Signal class)
    signals = relationship("Signal", back_populates="lead")
    # Relationship with creator profile
    creator = relationship("Users", back_populates="leads_created")

    def to_dict(self):
        return {
            "id": str(self.id),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "email": self.email,
            "position": self.position,
            "company_size": self.company_size,
            "industry": self.industry,
            "region": self.region,
            "lead_source": self.lead_source,
            "score": self.score,
            "last_contacted": str(self.last_contacted),
            "phone": self.phone,
            "created_at": str(self.created_at),
            "linkedin": self.linkedin,
            "website": self.website,
            "notes": self.notes,
            "languages": self.languages,
            "updated_at": str(self.updated_at),
            "last_suggestion_id": str(self.last_suggestion_id),
            "new_since": str(self.new_since),
            "connection_degree": self.connection_degree,
            "lead_status": self.lead_status.value if self.lead_status else None,
            "lead_stage": self.lead_stage.value if self.lead_stage else None,
            "enrichment_data": self.enrichment_data,
            "is_enriched": self.is_enriched,
            "scoring_details": self.scoring_details,
            "user_id": str(self.user_id),
        }

# Define back-populating relationships after all classes are defined
Users.leads_created = relationship("Lead", back_populates="creator")
Signal.lead = relationship("Lead", back_populates="signals")

# Create session factory
SessionLocal = sessionmaker(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_unprocessed_leads(limit: int = 5):
    """Get leads that need to be processed (score = 0)"""
    db = SessionLocal()
    try:
        return (
            db.query(Lead)
            .filter(Lead.score == 0)
            .limit(limit)
            .all()
        )
    finally:
        db.close()

def update_lead(lead_id: PG_UUID, **update_data):
    """Update lead data (simplified)."""
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            # Update fields dynamically
            for key, value in update_data.items():
                if hasattr(lead, key):
                    setattr(lead, key, value)
                else:
                    print(f"Warning: Lead model has no attribute '{key}'. Skipping update.")
                    
            db.commit()
            db.refresh(lead)
            return lead
        return None # Return None if lead not found
    finally:
        db.close()

def get_lead_by_id(lead_id: PG_UUID):
    """Get lead by ID"""
    db = SessionLocal()
    try:
        return db.query(Lead).filter(Lead.id == lead_id).first()
    finally:
        db.close()

def create_signal(lead_id: PG_UUID, user_id: PG_UUID, signal_type: str, description: str, details: dict, source: str, source_url: Optional[str] = None, detected_at: Optional[datetime] = None):
    """Create a new signal for a lead, allowing detected_at to be passed."""
    db = SessionLocal()
    try:
        # Ensure detected_at is set, default to now if not provided
        if detected_at is None:
            detected_at = datetime.now(timezone.utc)
        elif isinstance(detected_at, str):
            # Attempt to parse if passed as string
            try:
                detected_at_str = detected_at.replace('Z', '+00:00')
                detected_at = datetime.fromisoformat(detected_at_str)
                if detected_at.tzinfo is None:
                     detected_at = detected_at.replace(tzinfo=timezone.utc)
            except ValueError:
                print(f"Warning: Invalid detected_at string '{detected_at}', using current time.")
                detected_at = datetime.now(timezone.utc)
        elif detected_at.tzinfo is None:
            # Ensure timezone aware if passed as naive datetime
            detected_at = detected_at.replace(tzinfo=timezone.utc)
            
        signal = Signal(
            lead_id=lead_id,
            user_id=user_id,
            signal_type=signal_type,
            description=description,
            details=details,
            source=source,
            source_url=source_url,
            detected_at=detected_at # Set the passed or default timestamp
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        return signal
    finally:
        db.close()

def get_user_preferences(user_id: PG_UUID):
    """Get user preferences"""
    db = SessionLocal()
    try:
        return db.query(UserPreferences).filter_by(user_id=user_id).first()
    finally:
        db.close()

def update_user_preferences(user_id: PG_UUID, **pref_data):
    """Update user preferences"""
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter_by(user_id=user_id).first()
        if prefs:
            for key, value in pref_data.items():
                setattr(prefs, key, value)
            prefs.updated_at = text('now()')
        else:
            prefs = UserPreferences(user_id=user_id, **pref_data)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
        return prefs
    finally:
        db.close()

def get_unprocessed_lead_ids(user_id: PG_UUID, limit: int = 5):
    """Fetches the IDs of leads for a user that have not yet been scored (score is NULL or 0)."""
    db = SessionLocal()
    try:
        from sqlalchemy import or_
        
        # Filter leads that either:
        # 1. Have NULL score (never processed)
        # 2. Have score = 0 (default value)
        # 3. AND belong to the given user (using the correct user_id column)
        lead_ids = db.query(Lead.id)\
            .filter(
                or_(
                    Lead.score == None,
                    Lead.score == 0
                )
            )\
            .filter(Lead.user_id == user_id)\
            .limit(limit)\
            .all()
            
        # Extract UUIDs from tuples
        return [lead_id[0] for lead_id in lead_ids]
    finally:
        db.close()

# --- NEW FUNCTION for Summary ---
def get_lead_status_summary(user_id: PG_UUID) -> dict:
    """Calculates the count of leads for a user, grouped by their status."""
    db = SessionLocal()
    try:
        # Query counts grouped by priority enum value
        # Filters by the user who created the lead
        summary = db.query(
                Lead.lead_status,
                func.count(Lead.id).label('count')
            )\
            .filter(Lead.user_id == user_id)\
            .group_by(Lead.lead_status)\
            .all()

        # Convert the result (list of tuples) into a dictionary
        # Handles cases where a priority might have 0 leads (won't appear in query result)
        summary_dict = {
            status.name: 0 for status in LeadStatus # Initialize all statuses to 0
        }
        for status_enum, count in summary:
            if status_enum: # Ensure status is not NULL
                 summary_dict[status_enum.name] = count
            # Optionally handle NULL status leads if needed:
            # else:
            #    summary_dict['unknown'] = count 

        return summary_dict
    finally:
        db.close()
# --- END NEW FUNCTION --- 