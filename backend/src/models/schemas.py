from pydantic import BaseModel
from typing import List, Optional

class UserInput(BaseModel):
    user_id: str
    image_url: str
    clothing_options: List[str]

class GeneratedImage(BaseModel):
    user_id: str
    image_url: str
    clothing_combination: str
    generated_at: Optional[str] = None