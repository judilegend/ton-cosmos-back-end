from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, Dict

class ReportCreate(BaseModel):
    order_id: int
    generation_duration: float = Field(..., description="Durée de génération en secondes")
    
    astral_data_json: Dict[str, Any] = Field(default_factory=dict)
    ai_content_json: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)